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
from PIL import Image, ImageDraw, ImageFont # این خط باید اینجا باشد
from textwrap import wrap # این خط باید اینجا باشد

# --- تنظیمات اصلی ---
# ==== اطلاعات ربات ====
# **اطمینان حاصل کنید که این توکن دقیقاً توکن ربات شما از BotFather است.**
TOKEN = "7996297648:AAHBtbd6lGGQjUIOjDNRsqETIOCNUfPcU00" # توکن اصلاح شد
CHANNEL_ID = "-1002605751569"
ADMIN_ID = 486475495
WEBHOOK_URL = "https://testmahbood.onrender.com/"
SEND_HOUR = 8


# --- ربات و فلَسک ---
bot = telegram.Bot(token=TOKEN)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Dispatcher با تعداد workers مناسب
dispatcher = Dispatcher(bot, None, workers=4, use_context=True) # workers روی 4 تنظیم شد

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
HADITH_FILE = "hadiths.txt" # نام فایل حدیث اصلاح شد
def get_next_hadith():
    """حدیث بعدی را از فایل می‌خواند و ایندکس را به‌روزرسانی می‌کند.
    و اگر شامل ترجمه انگلیسی بود، آن را هم برمی‌گرداند.
    """
    data = load_data()
    try:
        with open(HADITH_FILE, encoding="utf-8") as f:
            hadiths_raw = f.read().strip().split("\n\n")
            
        hadiths_parsed = []
        for entry in hadiths_raw:
            parts = entry.strip().split("\n")
            if len(parts) >= 1:
                persian_hadith = parts[0].strip()
                english_hadith = ""
                if len(parts) > 1:
                    english_hadith = " ".join(parts[1:]).strip()
                hadiths_parsed.append({"persian": persian_hadith, "english": english_hadith})

    except FileNotFoundError:
        logging.error(f"Hadith file not found: {HADITH_FILE}")
        return {"persian": "خطا: فایل احادیث پیدا نشد.", "english": "Error: Hadith file not found."}
    
    if not hadiths_parsed:
        logging.warning("Hadith file is empty or malformed.")
        return {"persian": "خطا: فایل احادیث خالی است.", "english": "Error: Hadith file is empty."}

    index = data.get("index", 0)
    if index >= len(hadiths_parsed):
        index = 0 # بازنشانی شمارنده در صورت اتمام احادیث
    
    current_hadith = hadiths_parsed[index]
    data["index"] = index + 1
    save_data(data)
    return current_hadith

# --- تولید تصویر حدیث ---
def generate_image():
    """تصویر حدیث روزانه را تولید و مسیر آن را برمی‌گرداند."""
    today = datetime.now() 
    
    # ***** اصلاح تاریخ شمسی اینجا انجام می‌شود *****
    # برای اطمینان از اینکه فقط تاریخ امروز (و نه فردا) گرفته شود، از datetime.now().date() استفاده می‌کنیم.
    jalali_date_obj = JalaliDatetime(today.year, today.month, today.day) # از اجزای تاریخ میلادی استفاده کنید
    jalali = jalali_date_obj.strftime("%d %B %Y") # فرمت: 13 خرداد 1404

    gregorian = today.strftime("%d %B %Y") # فرمت: 02 June 2025
    
    hijri = "تاریخ قمری نامشخص" # مقدار پیش‌فرض در صورت خطا
    try:
        hijri_response = requests.get(f"http://api.aladhan.com/v1/gToH?date={today.strftime('%d-%m-%Y')}")
        hijri_response.raise_for_status() # بررسی خطاهای HTTP
        hijri_data = hijri_response.json()
        if "data" in hijri_data and "hijri" in hijri_data["data"] and "date" in hijri_data["data"]["hijri"]:
            # فرمت قمری را شبیه به نمونه تنظیم می‌کنیم: 06 ذی‌الحجه 1446
            hijri_date_parts = hijri_data["data"]["hijri"]["date"].split('-')
            hijri_day = hijri_date_parts[0]
            hijri_month_name = hijri_data["data"]["hijri"]["month"]["ar"] # نام ماه عربی
            hijri_year = hijri_date_parts[2]
            hijri = f"{hijri_day} {hijri_month_name} {hijri_year}"
        else:
            logging.warning(f"Unexpected response format from AlAdhan API: {hijri_data}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching Hijri date from API: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred while processing Hijri date: {e}")

    hadith_data = get_next_hadith()
    persian_hadith = hadith_data["persian"]
    english_hadith = hadith_data["english"]

    # باز کردن تصویر پس‌زمینه (000.png) و تغییر اندازه آن
    # فرض می‌کنیم 000.png شما یک تصویر پس‌زمینه عمودی است و رزولوشن 1080x1920 را می‌خواهید.
    img = Image.open("000.png").convert("RGB").resize((1080, 1920))
    draw = ImageDraw.Draw(img) # شیء draw اینجا تعریف می‌شود

    # --- تنظیمات فونت و رنگ برای تاریخ‌ها و "امروز" ---
    font_omrooz = load_font("Pinar-DS3-FD-Black", 80) # "امروز" بزرگتر
    font_date = load_font("Pinar-DS3-FD-Bold", 65) # فونت تاریخ‌ها
    color_white = "white"

    # --- رسم "امروز" و تاریخ‌ها ---
    # "امروز"
    text_omrooz = "امروز"
    bbox_omrooz = draw.textbbox((0,0), text_omrooz, font=font_omrooz)
    width_omrooz = bbox_omrooz[2] - bbox_omrooz[0]
    x_omrooz = (img.width - width_omrooz) / 2 # وسط چین
    y_omrooz = 100 
    draw.text((x_omrooz, y_omrooz), text_omrooz, font=font_omrooz, fill=color_white)

    # تاریخ شمسی
    y_jalali = y_omrooz + 120 # فاصله از امروز
    bbox_jalali = draw.textbbox((0,0), jalali, font=font_date)
    width_jalali = bbox_jalali[2] - bbox_jalali[0]
    x_jalali = (img.width - width_jalali) / 2
    draw.text((x_jalali, y_jalali), jalali, font=font_date, fill=color_white)

    # تاریخ قمری
    y_hijri = y_jalali + 80 # فاصله از شمسی
    bbox_hijri = draw.textbbox((0,0), hijri, font=font_date)
    width_hijri = bbox_hijri[2] - bbox_hijri[0]
    x_hijri = (img.width - width_hijri) / 2
    draw.text((x_hijri, y_hijri), hijri, font=font_date, fill=color_white)

    # تاریخ میلادی
    y_gregorian = y_hijri + 80 # فاصله از قمری
    bbox_gregorian = draw.textbbox((0,0), gregorian, font=font_date)
    width_gregorian = bbox_gregorian[2] - bbox_gregorian[0]
    x_gregorian = (img.width - width_gregorian) / 2
    draw.text((x_gregorian, y_gregorian), gregorian, font=font_date, fill=color_white)

    # --- رسم کادر و متن حدیث فارسی ---
    font_hadith_persian = load_font("Pinar-DS3-FD-Bold", 70) # فونت بزرگتر برای حدیث فارسی
    text_padding_x = 80 # فاصله متن از لبه‌های کادر
    text_padding_y = 30
    
    # موقعیت شروع حدیث فارسی
    y_start_hadith_persian = y_gregorian + 120 # فاصله از میلادی
    
    # ابعاد تقریبی کادر حدیث فارسی
    hadith_box_width = img.width - (2 * text_padding_x) # عرض کادر
    
    # برای شکست خطوط حدیث فارسی
    # تخمین تعداد کاراکترها در هر خط (تقریبی)
    avg_char_width_persian = font_hadith_persian.getlength("س")
    if not avg_char_width_persian: avg_char_width_persian = 40 # مقدار پیش‌فرض
    max_chars_per_line_persian = int(hadith_box_width / avg_char_width_persian) - 5 # بافر
    
    wrapped_lines_persian = wrap(persian_hadith, width=max_chars_per_line_persian)
    
    # ارتفاع کلی متن حدیث فارسی برای محاسبه اندازه کادر
    total_text_height_persian = 0
    for line in wrapped_lines_persian:
        bbox = font_hadith_persian.getbbox(line)
        total_text_height_persian += (bbox[3] - bbox[1]) + 20 # ارتفاع خط + فاصله بین خطوط

    # کادر حدیث فارسی
    hadith_box_top = y_start_hadith_persian
    hadith_box_bottom = hadith_box_top + total_text_height_persian + (2 * text_padding_y)
    
    # رسم کادر بنفش برای حدیث فارسی
    draw.rounded_rectangle(
        (text_padding_x, hadith_box_top, img.width - text_padding_x, hadith_box_bottom),
        radius=30, # گوشه‌های گرد
        fill="#4A148C" # بنفش تیره (مطابق نمونه)
    )

    # رسم متن حدیث فارسی در داخل کادر
    y_current_persian = hadith_box_top + text_padding_y
    for line in wrapped_lines_persian:
        bbox_line = draw.textbbox((0,0), line, font=font_hadith_persian)
        width_line = bbox_line[2] - bbox_line[0]
        x_line = (img.width - width_line) / 2 # وسط چین در کادر
        
        draw.text((x_line, y_current_persian), line, font=font_hadith_persian, fill=color_white)
        y_current_persian += (bbox_line[3] - bbox_line[1]) + 20 # افزایش y برای خط بعدی

    # --- رسم کادر و متن حدیث انگلیسی (اگر وجود داشت) ---
    if english_hadith:
        font_hadith_english = load_font("Pinar-DS3-FD-Bold", 55) # فونت کوچکتر برای انگلیسی
        y_start_hadith_english = hadith_box_bottom + 50 # فاصله از کادر فارسی

        # برای شکست خطوط حدیث انگلیسی
        avg_char_width_english = font_hadith_english.getlength("W")
        if not avg_char_width_english: avg_char_width_english = 30 # مقدار پیش‌فرض
        max_chars_per_line_english = int(hadith_box_width / avg_char_width_english) - 5 # بافر
        
        wrapped_lines_english = wrap(english_hadith, width=max_chars_per_line_english)

        total_text_height_english = 0
        for line in wrapped_lines_english:
            bbox = font_hadith_english.getbbox(line)
            total_text_height_english += (bbox[3] - bbox[1]) + 15 # ارتفاع خط + فاصله بین خطوط
        
        # کادر حدیث انگلیسی
        english_box_top = y_start_hadith_english
        english_box_bottom = english_box_top + total_text_height_english + (2 * text_padding_y)

        # رسم کادر زرد برای حدیث انگلیسی
        draw.rounded_rectangle(
            (text_padding_x, english_box_top, img.width - text_padding_x, english_box_bottom),
            radius=30, # گوشه‌های گرد
            fill="#FFC107" # زرد (مطابق نمونه)
        )
        
        # رسم متن حدیث انگلیسی در داخل کادر
        y_current_english = english_box_top + text_padding_y
        for line in wrapped_lines_english:
            bbox_line = draw.textbbox((0,0), line, font=font_hadith_english)
            width_line = bbox_line[2] - bbox_line[0]
            x_line = (img.width - width_line) / 2 # وسط چین در کادر
            
            draw.text((x_line, y_current_english), line, font=font_hadith_english, fill="black") # متن انگلیسی مشکی
            y_current_english += (bbox_line[3] - bbox_line[1]) + 15

    # --- اضافه کردن لوگو (فرض می‌کنیم لوگو در files/logo.png وجود دارد) ---
    # شما باید فایل لوگوی خود را (اگر دارید) به پوشه files/ اضافه کنید
    # و نام آن را با logo.png جایگزین کنید.
    # اگر لوگو ندارید، این بخش را حذف کنید.
    try:
        logo_path = os.path.join("files", "logo.png") # مسیر لوگو
        logo = Image.open(logo_path).convert("RGBA") # لوگو ممکن است شفافیت داشته باشد
        
        # تغییر اندازه لوگو (اندازه دلخواه)
        logo_width = 300 
        logo_height = int(logo.height * (logo_width / logo.width)) # حفظ نسبت ابعاد
        logo = logo.resize((logo_width, logo_height))

        # موقعیت لوگو (پایین، وسط)
        x_logo = (img.width - logo_width) / 2
        y_logo = img.height - logo_height - 50 # 50 پیکسل از پایین فاصله

        img.paste(logo, (int(x_logo), int(y_logo)), logo) # استفاده از ماسک برای شفافیت
    except FileNotFoundError:
        logging.warning("Logo file not found. Skipping logo placement.")
    except Exception as e:
        logging.error(f"Error placing logo: {e}")

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
        logging.info("Daily hadith sent successfully.")
    except Exception as e:
        logging.error(f"خطا در ارسال روزانه: {e}")

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