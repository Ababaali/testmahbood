import os
import logging
import random
from flask import Flask, request
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler
from khayyam import JalaliDatetime, JalaliDate
from datetime import datetime, timedelta
import requests
import json
from PIL import Image, ImageDraw, ImageFont
from textwrap import wrap
from hijri_converter import Gregorian
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import pytz

# --- تنظیمات اصلی ---
# ==== اطلاعات ربات ====
TOKEN = "7996297648:AAHBtbd6lGGQjUIOjDNRsqETIOCNUfPcU00" # توکن خود را اینجا قرار دهید
CHANNEL_ID = "-1001122601232" # آیدی کانال خود را اینجا قرار دهید
ADMIN_ID = 486475495 # آیدی ادمین خود را اینجا قرار دهید
WEBHOOK_URL = "https://testmahbood.onrender.com/" # آدرس Webhook خود را اینجا قرار دهید
SEND_HOUR = 8


# ==== فونت‌ها ====
FONT_DIR = "fonts"
FONT_BLACK = os.path.join(FONT_DIR, "Pinar-DS3-FD-Black.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "Pinar-DS3-FD-Bold.ttf")

# ==== نام ماه‌های قمری فارسی ====
HIJRI_MONTHS_FA = [
    "محرم", "صفر", "ربیع‌الاول", "ربیع‌الثانی", "جمادی‌الاول", "جمادی‌الثانی",
    "رجب", "شعبان", "رمضان", "شوال", "ذی‌القعده", "ذی‌الحجه"
]


# --- ربات و فلَسک ---
bot = telegram.Bot(token=TOKEN)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

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
        json.dump(data, f, indent=4)


# --- تابع کمکی برای شکستن خطوط متن ---
def wrap_text(text, font, max_width, draw):
    lines = []
    words = text.split()
    line = ""
    for word in words:
        test_line = f"{line} {word}".strip()
        try:
            # استفاده از textbbox برای اندازه گیری عرض
            w = draw.textbbox((0, 0), test_line, font=font)[2] - draw.textbbox((0, 0), test_line, font=font)[0]
        except AttributeError:
             w = font.getsize(test_line)[0] 
        
        if w <= max_width:
            line = test_line
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


# --- مدیریت احادیث ---
HADITH_FILE = "hadiths.txt"
def get_next_hadith():
    data = load_data()
    try:
        with open(HADITH_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        hadiths_parsed = []
        for i in range(0, len(lines), 2):
            persian_text = lines[i]
            english_text = lines[i+1] if (i+1) < len(lines) else ""

            # حذف پیشوندهای احتمالی
            for prefix in ["حدیث:", "حدیث ", ":", "-", "•", "*", "ـ"]:
                if persian_text.startswith(prefix):
                    persian_text = persian_text[len(prefix):].strip()
                if english_text.startswith(prefix):
                    english_text = english_text[len(prefix):].strip()

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
        index = 0

    current_hadith = hadiths_parsed[index]
    data["index"] = index + 1
    save_data(data)
    return current_hadith



# --- تولید تصویر حدیث ---
def generate_image():
    """تصویر حدیث روزانه را با طرح جدید تولید و مسیر آن را برمی‌گرداند."""

    # ==== محاسبه تاریخ‌ها ====
    now = datetime.now(pytz.timezone("Asia/Tehran"))
    gregorian = now.strftime("%d %B %Y")
# اطمینان حاصل کنید که اعداد به لاتین هستند. در برخی محیط‌ها ممکن است strftime اعداد فارسی برگرداند.
# می‌توانیم روز، ماه و سال را جداگانه بگیریم و سپس به هم بچسبانیم.
    gregorian_day = now.day
    gregorian_month_name = now.strftime("%B")
    gregorian_year = now.year
    gregorian = f"{gregorian_day} {gregorian_month_name} {gregorian_year}" 

    # قمری
    try:
        hijri_obj = Gregorian(now.year, now.month, now.day).to_hijri()
        hijri_month_name = HIJRI_MONTHS_FA[hijri_obj.month - 1]
        hijri = f"{hijri_obj.day:02d} {hijri_month_name} {hijri_obj.year}"
    except Exception as e:
        logging.error(f"Error calculating Hijri date: {e}")
        hijri = "تاریخ قمری نامشخص"

    # شمسی
    jalali = JalaliDate.today().strftime("%d %B %Y")

    # ==== دریافت حدیث ====
    hadith_data = get_next_hadith()
    hadith_fa = hadith_data["persian"]
    hadith_tr = hadith_data["english"]

    # ==== ایجاد تصویر و شیء رسم ====
    image = Image.open("000.png").convert("RGBA").resize((1080, 1920))
    draw = ImageDraw.Draw(image)

    # ==== بارگذاری فونت‌ها ====
    try:
        font_black = ImageFont.truetype(FONT_BLACK, 70)
        font_bold = ImageFont.truetype(FONT_BOLD, 70)
        font_hadith_box = ImageFont.truetype(FONT_BOLD, 65)
        font_translation_box = ImageFont.truetype(FONT_BOLD, 55)
    except IOError:
        logging.error("One or more font files not found. Using default fonts.")
        font_black = ImageFont.load_default()
        font_bold = ImageFont.load_default()
        font_hadith_box = ImageFont.load_default()
        font_translation_box = ImageFont.load_default()


    # ==== رسم تاریخ‌ها و "امروز" ====
    y_current = 100

    # "امروز"
    text = "امروز"
    bbox = draw.textbbox((0, 0), text, font=font_black)
    w = bbox[2] - bbox[0]
    x = (image.width - w) // 2
    draw.text((x, y_current), text, font=font_black, fill="white")
    y_current += (bbox[3] - bbox[1]) + 40

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
    y_current += (bbox[3] - bbox[1]) + 60

    # ==== رسم احادیث در کادرها ====
    max_text_width = image.width - 160

    hadith_fa = hadith_fa.strip(" .●ـ*-–—")
    hadith_tr = hadith_tr.strip(" .●ـ*-–—")

    hadith_lines_fa = wrap_text(hadith_fa, font_hadith_box, max_text_width, draw)
    hadith_lines_tr = wrap_text(hadith_tr, font_translation_box, max_text_width, draw)

    line_height_fa = 60
    line_spacing = 30
    box_padding_x = 20
    box_padding_y = 5
    corner_radius = 30

    # حدیث فارسی با مستطیل بنفش
    y_current += 60
    for line in hadith_lines_fa:
        text_width, text_height = draw.textbbox((0, 0), line, font=font_hadith_box)[2:]
        
        box_width = text_width + 2 * box_padding_x
        if box_width < 400: box_width = 400 
        
        box_height = line_height_fa
        
        x_box = (image.width - box_width) // 2
        
        draw.rounded_rectangle([x_box, y_current, x_box + box_width, y_current + box_height], 
                               radius=corner_radius, 
                               fill="#000676")

        text_x = (image.width - text_width) // 2
        text_y = y_current + box_padding_y + ((box_height - text_height) // 2) - 5
        draw.text((text_x, text_y), line, font=font_hadith_box, fill="white", stroke_width=3, stroke_fill="#10024a")

        y_current += box_height + line_spacing

    # ترجمه با مستطیل رنگ خاص (زرد)
    if hadith_tr:
        line_height_tr = 50
        y_current += 30
        for line in hadith_lines_tr:
            text_width, text_height = draw.textbbox((0, 0), line, font=font_translation_box)[2:]
            
            box_width = text_width + 2 * box_padding_x
            if box_width < 400: box_width = 400
            
            box_height = line_height_tr
            
            x_box = (image.width - box_width) // 2
            
            draw.rounded_rectangle([x_box, y_current, x_box + box_width, y_current + box_height], 
                                   radius=corner_radius, 
                                   fill="#FFC107")

            text_x = (image.width - text_width) // 2
            text_y = y_current + box_padding_y + ((box_height - text_height) // 2) - 5
            draw.text((text_x, text_y), line, font=font_translation_box, fill="#000676", stroke_width=3, stroke_fill="#f5ce00")

            y_current += box_height + line_spacing


   

    # ==== ذخیره و برگرداندن مسیر ====
    output_path = "temp_hadith_preview.png"
    image.save(output_path)

# برگرداندن مسیر عکس و همچنین متون برای استفاده در کپشن
    return {
        "image_path": output_path,
        "jalali": jalali,
        "hijri": hijri,
        "gregorian": gregorian,
        "hadith_fa": hadith_fa,
        "hadith_tr": hadith_tr
    }

# --- ارسال پست روزانه (هنوز نیازمند زمانبند خارجی) ---
def send_daily():
    try:
        # دریافت دیکشنری حاوی مسیر عکس و متون
        image_data = generate_image()
        image_path = image_data["image_path"]
        jalali = image_data["jalali"]
        hijri = image_data["hijri"]
        gregorian = image_data["gregorian"]
        hadith_fa = image_data["hadith_fa"]
        hadith_tr = image_data["hadith_tr"]

        # ساخت کپشن
        caption_text = f"""امروز
🗓 {jalali}
🌙 {hijri}
✝️ {gregorian}


{hadith_fa}


{hadith_tr}

┈••✾•🍃🍃🍃•✾••┈•

🎓 مهـــم‌ترین اخبـــار دانشجـــویی 
‌دانشگـــاه هاے استـــــان سمنـــــان‌
را دراینجــــا مشــاهده فرمــــــایید.
yun.ir/Taranomejavani_eitaa
yun.ir/Taranomejavani_tel
yun.ir/Taranomejavani_bale"""

        bot.send_photo(chat_id=CHANNEL_ID, photo=open(image_path, "rb"), caption=caption_text,
                       reply_markup=InlineKeyboardMarkup([
                           [InlineKeyboardButton("📤 دریافت تصویر", switch_inline_query="share_today")]
                       ]))
        os.remove(image_path)
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
    query.answer()
    
    data = load_data()
    try: 
        with open(HADITH_FILE, encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            total = len(lines) // 2 
    except FileNotFoundError:
        total = 0
        logging.error(f"فایل احادیث در تابع callback_handler پیدا نشد: {HADITH_FILE}")
    except Exception as e:
        total = 0
        logging.error(f"خطا در خواندن فایل احادیث برای محاسبه کل: {e}")
    
    if query.data == "stats":
        query.edit_message_text(f"تا حالا {data.get('index', 0)} حدیث ارسال شده.\n{total - data.get('index', 0)} حدیث باقی‌مانده.")
    elif query.data == "preview":
        try:
            # اینجا تغییرات لازم است
            image_data = generate_image()
            image_path = image_data["image_path"]
            jalali = image_data["jalali"]
            hijri = image_data["hijri"]
            gregorian = image_data["gregorian"]
            hadith_fa = image_data["hadith_fa"]
            hadith_tr = image_data["hadith_tr"]

            # ساخت کپشن (همانند send_daily)
            caption_text = f"""امروز
🗓 {jalali}
🌙 {hijri}
✝️ {gregorian}


{hadith_fa}


{hadith_tr}

┈••✾•🍃🍃🍃•✾••┈•

🎓 مهـــم‌ترین اخبـــار دانشجـــویی 
‌دانشگـــاه هاے استـــــان سمنـــــان‌
را دراینجــــا مشــاهده فرمــــــایید.
yun.ir/Taranomejavani_eitaa
yun.ir/Taranomejavani_tel
yun.ir/Taranomejavani_bale"""

            bot.send_photo(chat_id=ADMIN_ID, photo=open(image_path, "rb"), caption=caption_text)
            os.remove(image_path)

            # --- اضافه کردن پیام زمان باقیمانده ---
            next_run = get_next_run_time() # فراخوانی تابع جدید
            now_tehran = datetime.now(pytz.timezone("Asia/Tehran")) # زمان فعلی در تهران
            
            time_until_next_run = next_run - now_tehran
            
            # تبدیل به ساعت و دقیقه
            total_seconds = int(time_until_next_run.total_seconds())
            
            # اگر زمان منفی شد، یعنی ساعت 8 صبح رد شده و باید برای فردا باشد
            # این بخش اطمینان می‌دهد که همیشه زمان مثبتی را نشان می‌دهد
            if total_seconds < 0:
                next_run = next_run + timedelta(days=1)
                time_until_next_run = next_run - now_tehran
                total_seconds = int(time_until_next_run.total_seconds())

            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60

            # ساخت پیام نهایی
            remaining_message = f"زمان آپلود در کانال ترنم:\nدر **{hours} ساعت** و **{minutes} دقیقه** دیگر"
            
            bot.send_message(chat_id=ADMIN_ID, text=remaining_message, parse_mode=telegram.ParseMode.MARKDOWN)

        except Exception as e:
            logging.error(f"خطا در تولید یا ارسال پیش‌نمایش در callback: {e}")
            query.edit_message_text("خطا در تولید یا ارسال پیش‌نمایش. لاگ‌ها را بررسی کنید.")
    elif query.data == "reset":
        save_data({"index": 0})
        query.edit_message_text("شمارنده ریست شد.")
    else:
        query.edit_message_text("این گزینه هنوز فعال نیست.")

def get_next_run_time():
    tehran_tz = pytz.timezone("Asia/Tehran")
    now_tehran = datetime.now(tehran_tz)

    # زمان هدف (8 صبح امروز)
    target_time_today = now_tehran.replace(hour=8, minute=0, second=0, microsecond=0)

    # اگر الان بعد از 8 صبح است، هدف فرداست
    if now_tehran >= target_time_today:
        next_run = target_time_today + timedelta(days=1)
    else:
        # اگر قبل از 8 صبح است، هدف 8 صبح امروز است
        next_run = target_time_today

    return next_run        
# --- هندلرها ---
# --- هندلرها ---
def start(update, context):
    update.message.reply_text("سلام! به ربات حدیث خوش آمدید. برای دیدن پنل مدیریت، دستور /admin را ارسال کنید.")

dispatcher.add_handler(CommandHandler("start", start)) # <<-- این خط را اضافه کنید -->>
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

        # --- اینجا کد APScheduler را اضافه کنید ---
        scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Tehran"))
        scheduler.add_job(send_daily, 'cron', hour=8, minute=0, id='daily_hadith_job')
        logging.info("Scheduler job added for daily hadith at 8:00 AM Tehran time.")
        scheduler.start()
        logging.info("Scheduler started.")
        # --- پایان اضافه کردن کد APScheduler ---

        # Render.com به طور خودکار پورت را تنظیم می‌کند
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    except Exception as e:
        logging.error(f"Error during bot setup: {e}")