import os
import logging
from flask import Flask, request
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler
from khayyam import JalaliDatetime
from datetime import datetime, timedelta
import requests
import json
from PIL import Image, ImageDraw, ImageFont # این خط باید اینجا باشد و فقط یک بار باشد

# --- تنظیمات اصلی ---
# ==== اطلاعات ربات ====
# **اطمینان حاصل کنید که این توکن دقیقاً توکن ربات شما از BotFather است.**
# **من توکن شما را در این نسخه بازسازی شده به حالت اولیه‌اش (آخرین توکن صحیح که شما ارسال کردید) برگرداندم.**
TOKEN = "7996297648:AAHBtbd6lGGQjUIOjDNRsqETIOCNUfPcU00"
CHANNEL_ID = "-1002605751569"
ADMIN_ID = 486475495
WEBHOOK_URL = "https://testmahbood.onrender.com/"
SEND_HOUR = 8


# --- ربات و فلَسک ---
bot = telegram.Bot(token=TOKEN)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO) # تنظیم سطح لاگ برای دیدن اطلاعات بیشتر

# Dispatcher با تعداد workers مناسب
dispatcher = Dispatcher(bot, None, workers=4, use_context=True)

# --- دیتابیس ساده (برای ذخیره ایندکس حدیث) ---
DATA_FILE = "data.json"
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"index": 0}
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from {DATA_FILE}. Returning default data.")
        return {"index": 0}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4) # indent برای خوانایی بیشتر JSON

# --- توابع کمکی برای تصویر و فونت ---
def load_font(font_name, font_size):
    """فونت را از پوشه fonts بارگذاری می‌کند."""
    font_path = os.path.join("fonts", f"{font_name}.ttf") # استفاده از os.path.join برای مسیردهی صحیح
    try:
        return ImageFont.truetype(font_path, font_size)
    except IOError:
        logging.error(f"Could not load font: {font_path}. Using default font.")
        return ImageFont.load_default()

# --- مدیریت احادیث ---
HADITH_FILE = "hadiths.txt" # نام فایل احادیث صحیح
def get_next_hadith():
    """حدیث بعدی را از فایل می‌خواند و ایندکس را به‌روزرسانی می‌کند."""
    data = load_data()
    try:
        with open(HADITH_FILE, encoding="utf-8") as f:
            hadiths = f.read().strip().split("\n\n")
    except FileNotFoundError:
        logging.error(f"Hadith file not found: {HADITH_FILE}")
        return "خطا: فایل احادیث پیدا نشد."
    
    if not hadiths:
        logging.warning("Hadith file is empty or malformed.")
        return "خطا: فایلا حادیث خالی است."

    index = data.get("index", 0)
    if index >= len(hadiths):
        index = 0 # بازنشانی شمارنده در صورت اتمام احادیث
    
    current_hadith = hadiths[index].strip()
    data["index"] = index + 1
    save_data(data)
    return current_hadith

# --- تولید تصویر حدیث ---
def generate_image():
    """تصویر حدیث روزانه را تولید و مسیر آن را برمی‌گرداند."""
    today = datetime.now()
    jalali = JalaliDatetime(today).strftime("%A %d %B %Y")
    gregorian = today.strftime("%A %d %B %Y")
    
    hijri = "تاریخ قمری نامشخص" # مقدار پیش‌فرض در صورت خطا
    try:
        hijri_response = requests.get(f"http://api.aladhan.com/v1/gToH?date={today.strftime('%d-%m-%Y')}")
        hijri_response.raise_for_status() # بررسی خطاهای HTTP
        hijri_data = hijri_response.json()
        if "data" in hijri_data and "hijri" in hijri_data["data"] and "date" in hijri_data["data"]["hijri"]:
            hijri = hijri_data["data"]["hijri"]["date"]
        else:
            logging.warning(f"Unexpected response format from AlAdhan API: {hijri_data}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching Hijri date from API: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred while processing Hijri date: {e}")

    hadith = get_next_hadith()

    # اندازه تصویر پس‌زمینه (مثلاً برای گوشی‌های عمودی)
    # اگر 000.png شما نسبت 1:1 دارد و می‌خواهید پس‌زمینه تصویر کشیده نشود،
    # می‌توانید 000.png را به اندازه (1080, 1920) بسازید یا از یک پس‌زمینه خالی استفاده کنید.
    # در غیر این صورت، این resize باعث کشیدگی می‌شود.
    # برای این مثال، فرض می‌کنیم 000.png شما یک تصویر پس‌زمینه عمودی است.
    img = Image.open("000.png").convert("RGB").resize((1080, 1920))
    draw = ImageDraw.Draw(img) 

    # رسم متن‌ها - تنظیمات موقعیت و فونت‌ها
    # این موقعیت‌ها تقریبی هستند و ممکن است نیاز به تنظیم دقیق داشته باشند.
    
    draw.text((50, 50), "امروز", font=load_font("Pinar-DS3-FD-Black", 70), fill="white")
    draw.text((50, 150), f"شمسی: {jalali}", font=load_font("Pinar-DS3-FD-Bold", 70), fill="white")
    draw.text((50, 250), f"میلادی: {gregorian}", font=load_font("Pinar-DS3-FD-Bold", 70), fill="white")
    draw.text((50, 350), f"قمری: {hijri}", font=load_font("Pinar-DS3-FD-Bold", 70), fill="white")

    draw.rectangle((50, 460, 350, 490), fill="white") 
    draw.text((60, 460), "حدیث", font=load_font("Pinar-DS3-FD-Black", 70), fill="#014612")

    # کادر حدیث - ممکن است نیاز به محاسبات برای قرارگیری بهتر متن داشته باشد.
    draw.rectangle((50, 520, 1030, 1800), fill="#800080") # کادر بزرگتر برای حدیث
    
    # برای شکست خطوط حدیث:
    from textwrap import wrap
    max_width_px = 960 # 1030 - 70 = 960 (عرض کادر منهای padding)
    font_for_hadith = load_font("Pinar-DS3-FD-Bold", 50)
    lines = []
    current_line = ""
    words = hadith.split(' ')
    for word in words:
        test_line = current_line + word + ' '
        if draw.textlength(test_line, font=font_for_hadith) < max_width_px:
            current_line = test_line
        else:
            lines.append(current_line.strip())
            current_line = word + ' '
    lines.append(current_line.strip())

    y_text = 540
    for line in lines:
        draw.text((70, y_text), line, font=font_for_hadith, fill="white")
        y_text += font_for_hadith.getsize(line)[1] + 10 # فاصله بین خطوط

    image_path = "temp_hadith_preview.png" 
    img.save(image_path)
    return image_path

# --- ارسال پست روزانه (هنوز نیازمند زمانبند خارجی) ---
def send_daily():
    try:
        image_path = generate_image()
        bot.send_photo(chat_id=CHANNEL_ID, photo=open(image_path, "rb"), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 دریافت تصویر", switch_inline_query="share_today")]
        ]))
        os.remove(image_path) # حذف فایل موقت بعد از ارسال
        logging.info("Daily hadith sent successfully.")
    except Exception as e:
        logging.error(f"Error sending daily hadith: {e}")

# --- پنل ادمین ---
def admin(update, context):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("شما اجازه دسترسی به این پنل را ندارید.")
        return
    buttons = [
        [InlineKeyboardButton("📈 آمار ارسال‌ها", callback_data="stats")],
        [InlineKeyboardButton("🔮 دیدن پست فردا", callback_data="preview")],
        [InlineKeyboardButton("🔄 بازنشانی شمارنده", callback_data="reset")],
        [InlineKeyboardButton("⚙️ تنظیمات (غیرفعال)", callback_data="settings")]
    ]
    update.message.reply_text("پنل مدیریت:", reply_markup=InlineKeyboardMarkup(buttons))

def callback_handler(update, context):
    query = update.callback_query
    query.answer() # مهم: همیشه query.answer() را فراخوانی کنید
    
    data = load_data()
    try:
        with open(HADITH_FILE, encoding="utf-8") as f:
            total = len(f.read().strip().split("\n\n"))
    except FileNotFoundError:
        total = 0
        logging.error(f"Hadith file not found in callback_handler: {HADITH_FILE}")

    if query.data == "stats":
        query.edit_message_text(f"تا حالا {data.get('index', 0)} حدیث ارسال شده.\n{total - data.get('index', 0)} حدیث باقی‌مانده.")
    elif query.data == "preview":
        try:
            image_path = generate_image()
            bot.send_photo(chat_id=ADMIN_ID, photo=open(image_path, "rb"), caption="پیش‌نمایش پست فردا")
            os.remove(image_path) # حذف فایل موقت
        except Exception as e:
            logging.error(f"Error in preview callback: {e}")
            query.edit_message_text("خطا در تولید یا ارسال پیش‌نمایش. لاگ‌ها را بررسی کنید.")
    elif query.data == "reset":
        save_data({"index": 0})
        query.edit_message_text("شمارنده ریست شد.")
    else:
        query.edit_message_text("این گزینه هنوز فعال نیست.")

# --- هندلرها ---
def start(update, context):
    update.message.reply_text("سلام! به ربات حدیث خوش آمدید. برای دیدن پنل مدیریت، دستور /admin را ارسال کنید.")

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("admin", admin))
dispatcher.add_handler(CallbackQueryHandler(callback_handler))

# --- تنظیم وب‌هوک Flask ---
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    if request.method == "POST":
        update = telegram.Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
    return "ok"

@app.route("/")
def index():
    return "ربات حدیث فعال است"

if __name__ == '__main__':
    logging.info("Setting webhook...")
    try:
        bot.set_webhook(url=WEBHOOK_URL + f"/{TOKEN}")
        logging.info(f"Webhook set to: {WEBHOOK_URL}/{TOKEN}")
    except telegram.error.TelegramError as e:
        logging.error(f"Error setting webhook: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred while setting webhook: {e}")