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
from PIL import Image, ImageDraw, ImageFont # این خط باید اینجا باشد و تکرار نشود

# --- تنظیمات اصلی ---
# ==== اطلاعات ربات ====
TOKEN = "7996297648:AAHBtbd6lGGjUIOjDNRsqETIOCNUfPcU00" # توکن شما
CHANNEL_ID = "-1002605751569" # آیدی کانال شما
ADMIN_ID = 486475495 # آیدی ادمین شما
WEBHOOK_URL = "https://testmahbood.onrender.com/" # آدرس وب‌هوک شما
SEND_HOUR = 8


# --- ربات و فلَسک ---
bot = telegram.Bot(token=TOKEN)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

dispatcher = Dispatcher(bot, None, workers=4, use_context=True) # workers روی 4 تنظیم شد

# --- دیتابیس ساده ---
DATA_FILE = "data.json"
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"index": 0}
    with open(DATA_FILE) as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# --- توابع کمکی برای تصویر ---
def load_font(font_name, font_size):
    try:
        return ImageFont.truetype(f"fonts/{font_name}.ttf", font_size)
    except IOError:
        logging.error(f"Could not load font: fonts/{font_name}.ttf")
        # Fallback to a default font or raise an error if font is critical
        return ImageFont.load_default() # Fallback, you might want to handle this better

# --- مدیریت احادیث ---
HADITH_FILE = "hadiths.txt" # نام فایل احادیث صحیح شد
def get_next_hadith():
    data = load_data()
    with open(HADITH_FILE, encoding="utf-8") as f:
        hadiths = f.read().strip().split("\n\n")
    index = data.get("index", 0)
    if index >= len(hadiths):
        index = 0
    data["index"] = index + 1
    save_data(data)
    return hadiths[index].strip()

# --- تولید تصویر حدیث ---
def generate_image():
    today = datetime.now()
    jalali = JalaliDatetime(today).strftime("%A %d %B %Y")
    gregorian = today.strftime("%A %d %B %Y")
    
    try:
        hijri_response = requests.get(f"http://api.aladhan.com/v1/gToH?date={today.strftime('%d-%m-%Y')}").json()
        hijri = hijri_response["data"]["hijri"]["date"]
    except Exception as e:
        logging.error(f"Error fetching Hijri date: {e}")
        hijri = "تاریخ قمری نامشخص"

    hadith = get_next_hadith()

    # تغییر اندازه به (1080, 1920) برای تصویر عمودی گوشی
    img = Image.open("000.png").convert("RGB").resize((1080, 1920))
    draw = ImageDraw.Draw(img) # شیء draw اینجا تعریف می‌شود

    # رسم متن‌ها
    # موقعیت‌ها و اندازه‌های فونت ممکن است نیاز به تنظیم دقیق داشته باشند
    
    draw.text((50, 50), "امروز", font=load_font("Pinar-DS3-FD-Black", 70), fill="white")
    draw.text((50, 150), f"شمسی: {jalali}", font=load_font("Pinar-DS3-FD-Bold", 70), fill="white")
    draw.text((50, 250), f"میلادی: {gregorian}", font=load_font("Pinar-DS3-FD-Bold", 70), fill="white")
    draw.text((50, 350), f"قمری: {hijri}", font=load_font("Pinar-DS3-FD-Bold", 70), fill="white")

    draw.rectangle((50, 460, 350, 490), fill="white") # کادر برای کلمه "حدیث"
    draw.text((60, 460), "حدیث", font=load_font("Pinar-DS3-FD-Black", 70), fill="#014612")

    # کادر برای حدیث
    draw.rectangle((50, 520, 1030, 1000), fill="#800080") # کادر حدیث (بنفش)
    draw.text((70, 540), hadith, font=load_font("Pinar-DS3-FD-Bold", 50), fill="white")

    image_path = "temp_hadith_preview.png" # نام فایل موقت برای ذخیره
    img.save(image_path) # ذخیره تصویر
    return image_path # برگرداندن مسیر فایل

# --- ارسال پست روزانه (هنوز نیازمند زمانبند خارجی) ---
def send_daily():
    try:
        image_path = generate_image()
        bot.send_photo(chat_id=CHANNEL_ID, photo=open(image_path, "rb"), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 دریافت تصویر", switch_inline_query="share_today")]
        ]))
        os.remove(image_path) # حذف فایل موقت بعد از ارسال
    except Exception as e:
        logging.error(f"خطا در ارسال روزانه: {e}")

# --- پنل ادمین ---
def admin(update, context):
    if update.effective_user.id != ADMIN_ID:
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
    query.answer()
    data = load_data()
    with open(HADITH_FILE, encoding="utf-8") as f:
        total = len(f.read().strip().split("\n\n"))
    
    if query.data == "stats":
        query.edit_message_text(f"تا حالا {data['index']} حدیث ارسال شده.\n{total - data['index']} حدیث باقی‌مانده.")
    elif query.data == "preview":
        image_path = generate_image()
        bot.send_photo(chat_id=ADMIN_ID, photo=open(image_path, "rb"), caption="پیش‌نمایش پست فردا")
        os.remove(image_path) # این خط را برای حذف فایل موقت اضافه کنید
    elif query.data == "reset":
        save_data({"index": 0})
        query.edit_message_text("شمارنده ریست شد.")
    else:
        query.edit_message_text("این گزینه هنوز فعال نیست.")

# --- هندلرها ---
def start(update, context): # اضافه کردن هندلر /start
    update.message.reply_text("سلام! به ربات حدیث خوش آمدید. برای دیدن پنل مدیریت، دستور /admin را ارسال کنید.")

dispatcher.add_handler(CommandHandler("start", start)) # اضافه کردن هندلر /start
dispatcher.add_handler(CommandHandler("admin", admin))
dispatcher.add_handler(CallbackQueryHandler(callback_handler))

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    dispatcher.process_update(telegram.Update.de_json(request.get_json(force=True), bot))
    return "ok"

@app.route("/")
def index():
    return "ربات حدیث فعال است"

if __name__ == '__main__':
    bot.set_webhook(url=WEBHOOK_URL + f"/{TOKEN}")
    # حذف app.run(debug=True) زیرا از hypercorn برای اجرا استفاده می‌کنیم