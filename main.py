import os
import logging
import random # برای get_random_hadith که در کد جدید شما بود
from flask import Flask, request
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler
from khayyam import JalaliDatetime, JalaliDate # JalaliDate هم اضافه شد
from datetime import datetime, timedelta
import requests
import json
from PIL import Image, ImageDraw, ImageFont # این خط باید اینجا باشد
from textwrap import wrap # این خط باید اینجا باشد
from hijri_converter import Gregorian # این خط هم اضافه شد
import pytz # این خط هم اضافه شد

# --- تنظیمات اصلی ---
# ==== اطلاعات ربات ====
TOKEN = "7996297648:AAHBtbd6lGGQjUIOjDNRsqETIOCNUfPcU00" # توکن شما
CHANNEL_ID = "-1002605751569" # آیدی کانال شما
ADMIN_ID = 486475495 # آیدی ادمین شما
WEBHOOK_URL = "https://testmahbood.onrender.com/"
SEND_HOUR = 8


# ==== فونت‌ها (جدید از کد شما) ====
FONT_DIR = "fonts" # پوشه فونت‌ها
FONT_BLACK = os.path.join(FONT_DIR, "Pinar-DS3-FD-Black.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "Pinar-DS3-FD-Bold.ttf")

# ==== نام ماه‌های قمری فارسی (جدید از کد شما) ====
HIJRI_MONTHS_FA = [
    "محرم", "صفر", "ربیع‌الاول", "ربیع‌الثانی", "جمادی‌الاول", "جمادی‌الثانی",
    "رجب", "شعبان", "رمضان", "شوال", "ذی‌القعده", "ذی‌الحجه"
]


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


# --- تابع کمکی برای شکستن خطوط متن (از کد شما) ---
def wrap_text(text, font, max_width, draw):
    lines = []
    words = text.split()
    line = ""
    for word in words:
        test_line = f"{line} {word}".strip()
        # استفاده از textbbox برای اندازه گیری عرض
        # textbbox returns (left, top, right, bottom), so width is right - left
        w = draw.textbbox((0, 0), test_line, font=font)[2] - draw.textbbox((0, 0), test_line, font=font)[0]
        if w <= max_width:
            line = test_line
        else:
            if line: # اگر خط فعلی خالی نباشد، اضافه کن
                lines.append(line)
            line = word # شروع خط جدید با کلمه فعلی
    if line:
        lines.append(line)
    return lines


# --- مدیریت احادیث ---
HADITH_FILE = "hadiths.txt" # نام فایل احادیث صحیح
def get_next_hadith():
    """حدیث بعدی را از فایل می‌خواند و ایندکس را به‌روزرسانی می‌کند.
    و اگر شامل ترجمه انگلیسی بود، آن را هم برمی‌گرداند.
    این تابع برای خواندن جفت حدیث فارسی/انگلیسی و حذف پیشوند اصلاح شده است.
    """
    data = load_data()
    try:
        with open(HADITH_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            
        hadiths_parsed = []
        # فرض می‌کنیم فرمت همیشه جفت‌های حدیث فارسی و سپس انگلیسی است.
        for i in range(0, len(lines), 2):
            persian_text = lines[i]
            english_text = lines[i+1] if (i+1) < len(lines) else ""
            
            # حذف پیشوند 
            if persian_text.startswith("", 1)[1].strip()
            if english_text.startswith("", 1)[1].strip()

            hadiths_parsed.append({"persian": persian_text, "english": english_text})

    except FileNotFoundError:
        logging.error(f"Hadith file not found: {HADITH_FILE}")
        return {"persian": "خطا: فایل احادیث پیدا نشد.", "english": "Error: Hadith file not found."}
    except Exception as e:
        logging.error(f"Error parsing hadith file: {e}")
        return {"persian": "خطا در خواندن فایل احادیث.", "english": "Error reading hadith file."}
    
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


# --- تولید تصویر حدیث (بخش طراحی بازسازی شده) ---
def generate_image():
    """تصویر حدیث روزانه را با طرح جدید تولید و مسیر آن را برمی‌گرداند."""

    # ==== محاسبه تاریخ‌ها (از کد شما) ====
    # مطمئن شوید که Asia/Tehran به درستی منطقه زمانی را مدیریت می‌کند
    now = datetime.now(pytz.timezone("Asia/Tehran"))
    gregorian = now.strftime("%d %B %Y") # 02 June 2025

    # قمری (از کد شما)
    hijri_obj = Gregorian(now.year, now.month, now.day).to_hijri()
    hijri_month_name = HIJRI_MONTHS_FA[hijri_obj.month - 1]
    hijri = f"{hijri_obj.day:02d} {hijri_month_name} {hijri_obj.year}" # 06 ذی‌الحجه 1446

    # شمسی (از کد شما)
    jalali = JalaliDate.today().strftime("%d %B %Y") # 13 خرداد 1404

    # ==== دریافت حدیث (با استفاده از تابع موجود) ====
    hadith_data = get_next_hadith()
    hadith_fa = hadith_data["persian"]
    hadith_tr = hadith_data["english"]

    # ==== ایجاد تصویر و شیء رسم (از کد شما) ====
    image = Image.open("000.png").convert("RGBA").resize((1080, 1920))
    draw = ImageDraw.Draw(image)

    # ==== بارگذاری فونت‌ها (از کد شما) ====
    font_black = ImageFont.truetype(FONT_BLACK, 70)
    font_bold = ImageFont.truetype(FONT_BOLD, 70)
    
    # فونت‌های کوچکتر برای متون داخل کادرها
    font_hadith_box = ImageFont.truetype(FONT_BOLD, 65) # کمی کوچکتر برای جا شدن بهتر
    font_translation_box = ImageFont.truetype(FONT_BOLD, 55) # برای ترجمه انگلیسی

    # ==== رسم تاریخ‌ها و "امروز" (از کد شما) ====
    y_current = 100 # شروع Y

    # "امروز"
    text = "امروز"
    bbox = draw.textbbox((0, 0), text, font=font_black)
    w = bbox[2] - bbox[0]
    x = (image.width - w) // 2
    draw.text((x, y_current), text, font=font_black, fill="white")
    y_current += (bbox[3] - bbox[1]) + 40 # افزایش y با ارتفاع متن و فاصله

    # تاریخ شمسی
    text = jalali
    bbox = draw.textbbox((0, 0), text, font=font_bold)
    w = bbox[2] - bbox[0]
    x = (image.width - w) // 2
    draw.text((x, y_current), text, font=font_bold, fill="white")
    y_current += (bbox[3] - bbox[1]) + 20

    # تاریخ قمری
    text = hijri
    bbox = draw.textbbox((0, 0), text, font=font_bold)
    w = bbox[2] - bbox[0]
    x = (image.width - w) // 2
    draw.text((x, y_current), text, font=font_bold, fill="white")
    y_current += (bbox[3] - bbox[1]) + 20

    # تاریخ میلادی
    text = gregorian
    bbox = draw.textbbox((0, 0), text, font=font_bold)
    w = bbox[2] - bbox[0]
    x = (image.width - w) // 2
    draw.text((x, y_current), text, font=font_bold, fill="white")
    y_current += (bbox[3] - bbox[1]) + 60 # فاصله بیشتر تا حدیث

    # ==== رسم احادیث در کادرها (از کد شما) ====
    max_text_width = image.width - 160 # عرض حداکثری برای متن در کادرها (1080 - 2 * 80)

    # پاک کردن کاراکترهای اضافی از حدیث (از کد شما)
    hadith_fa = hadith_fa.strip(" .●ـ*-–—")
    hadith_tr = hadith_tr.strip(" .●ـ*-–—")

    # شکستن خطوط احادیث با تابع wrap_text
    hadith_lines_fa = wrap_text(hadith_fa, font_hadith_box, max_text_width, draw)
    hadith_lines_tr = wrap_text(hadith_tr, font_translation_box, max_text_width, draw)

    # تنظیمات ابعاد کادر و فاصله (از کد شما)
    line_height_fa = 60 # ارتفاع تقریبی خط برای فارسی
    line_spacing = 30 # فاصله بین کادرها و خطوط
    box_padding_x = 20 # padding داخلی کادر
    box_padding_y = 5 # padding داخلی کادر
    corner_radius = 30 # شعاع گوشه‌های گرد

    # حدیث فارسی با مستطیل بنفش
    y_current += 60 # فاصله اولیه تا کادر حدیث
    for line in hadith_lines_fa:
        text_width, text_height = draw.textbbox((0, 0), line, font=font_hadith_box)[2:] # اندازه‌گیری دقیق عرض و ارتفاع متن
        
        # محاسبه ابعاد کادر بر اساس عرض متن
        box_width = text_width + 2 * box_padding_x
        # اطمینان از اینکه کادر کمتر از یک حداقل عرض نباشد
        if box_width < 400: box_width = 400 
        
        box_height = line_height_fa # ارتفاع ثابت برای هر خط در کادر
        
        # موقعیت x برای کادر (وسط چین)
        x_box = (image.width - box_width) // 2
        
        draw.rounded_rectangle([x_box, y_current, x_box + box_width, y_current + box_height], 
                               radius=corner_radius, 
                               fill="#4A148C") # بنفش تیره (مطابق نمونه)

        # موقعیت x برای متن داخل کادر (وسط چین)
        text_x = (image.width - text_width) // 2
        text_y = y_current + box_padding_y + ((box_height - text_height) // 2) - 5 # کمی تنظیم دستی y
        draw.text((text_x, text_y), line, font=font_hadith_box, fill="white", stroke_width=3, stroke_fill="#10024a") # Stroke

        y_current += box_height + line_spacing

    # ترجمه با مستطیل رنگ خاص (زرد)
    if hadith_tr: # فقط اگر ترجمه وجود داشت
        line_height_tr = 50 # ارتفاع تقریبی خط برای انگلیسی (کوچکتر)
        y_current += 30 # فاصله بیشتر بین کادر فارسی و انگلیسی
        for line in hadith_lines_tr:
            text_width, text_height = draw.textbbox((0, 0), line, font=font_translation_box)[2:]
            
            box_width = text_width + 2 * box_padding_x
            if box_width < 400: box_width = 400 # حداقل عرض
            
            box_height = line_height_tr
            
            x_box = (image.width - box_width) // 2
            
            draw.rounded_rectangle([x_box, y_current, x_box + box_width, y_current + box_height], 
                                   radius=corner_radius, 
                                   fill="#FFC107") # زرد (مطابق نمونه)

            text_x = (image.width - text_width) // 2
            text_y = y_current + box_padding_y + ((box_height - text_height) // 2) - 5
            draw.text((text_x, text_y), line, font=font_translation_box, fill="#10024a", stroke_width=3, stroke_fill="#f5ce00") # متن انگلیسی مشکی با stroke

            y_current += box_height + line_spacing


    # --- اضافه کردن لوگو (از کد قبلی شما) ---
    try:
        logo_path = os.path.join("files", "logo.png") # مسیر لوگو
        logo = Image.open(logo_path).convert("RGBA") # لوگو ممکن است شفافیت داشته باشد
        
        # تغییر اندازه لوگو (اندازه دلخواه)
        logo_width = 300 
        logo_height = int(logo.height * (logo_width / logo.width)) # حفظ نسبت ابعاد
        logo = logo.resize((logo_width, logo_height))

        # موقعیت لوگو (پایین، وسط)
        x_logo = (image.width - logo_width) / 2
        y_logo = image.height - logo_height - 50 # 50 پیکسل از پایین فاصله

        image.paste(logo, (int(x_logo), int(y_logo)), logo) # استفاده از ماسک برای شفافیت
    except FileNotFoundError:
        logging.warning("Logo file not found. Skipping logo placement.")
    except Exception as e:
        logging.error(f"Error placing logo: {e}")

    # ==== ذخیره و برگرداندن مسیر (از کد شما) ====
    output_path = "temp_hadith_preview.png" # نام فایل موقت برای ذخیره
    image.save(output_path) # ذخیره تصویر
    return output_path # برگرداندن مسیر فایل


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
            total = len(f.read().strip().split("\n\n")) # این خط نیاز به اصلاح با get_next_hadith دارد برای دقت
            # اما طبق درخواست شما، فقط بخش طراحی تغییر می کند.
            # برای دقیق‌تر شدن این آمار، باید از منطق get_next_hadith استفاده کنیم
            # اما فعلا به دلیل محدودیت درخواست شما، آن را دست نمی‌زنیم.
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