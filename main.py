import os
import random
import traceback
from flask import Flask, request
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from hijri_converter import Gregorian
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
import pytz
import asyncio

# ==== اطلاعات ربات ====
TOKEN = "7996297648:AAHBtbd6lGGQjUIOjDNRsqETIOCNUfPcU00"
CHANNEL_ID = "-1002605751569"
ADMIN_ID = 486475495
WEBHOOK_URL = "https://testmahbood.onrender.com"

# ==== ساخت اپلیکیشن تلگرام ====
application = Application.builder().token(TOKEN).build()
bot: Bot = application.bot

# ==== Flask ====
app = Flask(__name__)

# ==== فونت‌ها ====
FONT_BLACK = "Pinar-DS3-FD-Black.ttf"
FONT_BOLD = "Pinar-DS3-FD-Bold.ttf"

# ==== خواندن حدیث ====
def get_random_hadith():
    with open("hadiths.txt", "r", encoding="utf-8") as f:
        hadiths = [h.strip() for h in f.readlines() if h.strip()]
    return random.choice(hadiths)
HIJRI_MONTHS_FA = [
    "محرم", "صفر", "ربیع‌الاول", "ربیع‌الثانی", "جمادی‌الاول", "جمادی‌الثانی",
    "رجب", "شعبان", "رمضان", "شوال", "ذی‌القعده", "ذی‌الحجه"
]

# ==== ساخت تصویر ====
def create_image_with_text():
    # باز کردن و تغییر اندازه تصویر زمینه
    image = Image.open("000.png").convert("RGBA").resize((1080, 1920))
    draw = ImageDraw.Draw(image)

    # تاریخ‌ها
    now = datetime.now(pytz.timezone("Asia/Tehran"))
    gregorian = now.strftime("%d %B %Y")
    hijri_obj = Gregorian(now.year, now.month, now.day).to_hijri()
    hijri_month_name = HIJRI_MONTHS_FA[hijri_obj.month - 1]
    hijri = f"{hijri_obj.day:02d} {hijri_month_name} {hijri_obj.year}"

    jalali = now.strftime("%d %B %Y")  # در صورت استفاده از jdatetime دقیق‌تر میشه

    hadith = get_random_hadith()
    hadith_lines = hadith.split("\n")

    # فونت‌ها
    font_black = ImageFont.truetype(FONT_BLACK, 70)
    font_bold = ImageFont.truetype(FONT_BOLD, 70)

    y = 100  # موقعیت Y شروع

    # ==== کلمه «امروز» ====
    text = "امروز"
    w, h = draw.textbbox((0, 0), text, font=font_black)[2:]
    x = (image.width - w) // 2
    draw.text((x, y), text, font=font_black, fill="white")
    y += h + 40

    # ==== تاریخ شمسی ====
    text = f"تاریخ شمسی: {jalali}"
    w, h = draw.textbbox((0, 0), text, font=font_bold)[2:]
    x = (image.width - w) // 2
    draw.text((x, y), text, font=font_bold, fill="white")
    y += h + 20

    # ==== تاریخ قمری ====
    text = f"تاریخ قمری: {hijri}"
    w, h = draw.textbbox((0, 0), text, font=font_bold)[2:]
    x = (image.width - w) // 2
    draw.text((x, y), text, font=font_bold, fill="white")
    y += h + 20

    # ==== تاریخ میلادی ====
    text = f"تاریخ میلادی: {gregorian}"
    w, h = draw.textbbox((0, 0), text, font=font_bold)[2:]
    x = (image.width - w) // 2
    draw.text((x, y), text, font=font_bold, fill="white")
    y += h + 60

        # ==== مستطیل و عنوان حدیث (وسط‌چین) ====
    hadith_title = "حدیث"
    hadith_title_font = ImageFont.truetype(FONT_BLACK, 70)
    w, h = draw.textbbox((0, 0), hadith_title, font=hadith_title_font)[2:]
    hadith_title_x = (image.width - w) // 2
    draw.rectangle(
        [hadith_title_x - 20, y, hadith_title_x + w + 20, y + 80],
        fill="white"
    )
    draw.text(
        (hadith_title_x, y + 5),
        hadith_title,
        font=hadith_title_font,
        fill="#014612",
        stroke_width=5,
        stroke_fill="white",
    )
    y += 100

    # ==== آماده‌سازی متن حدیث و تقسیم به خطوط ====
    max_text_width = image.width - 2 * 80  # 80 پیکسل حاشیه از چپ و راست
    hadith_lines = wrap_text(hadith, font_bold, max_text_width, draw)

    line_spacing = 90
    total_height = line_spacing * len(hadith_lines)

    draw.rectangle(
        [80, y, image.width - 80, y + total_height + 30],
        fill="#800080"
    )
    for i, line in enumerate(hadith_lines):
        w, _ = draw.textbbox((0, 0), line, font=font_bold)[2:]
        x = (image.width - w) // 2
        draw.text(
            (x, y + i * line_spacing),
            line,
            font=font_bold,
            fill="white",
            stroke_width=5,
            stroke_fill="white",
        )


    # ==== ذخیره تصویر ====
    output_path = "output.png"
    image.save(output_path)
    return output_path


# ==== ارسال تصویر ====
async def send_image(chat_id=CHANNEL_ID):
    try:
        path = create_image_with_text()
        with open(path, "rb") as photo:
            await bot.send_document(chat_id=chat_id, document=photo, filename="output.png")  # ⬅️ ارسال بدون فشرده‌سازی
    except Exception as e:
        await bot.send_message(chat_id=ADMIN_ID, text=f"❌ خطا در ارسال تصویر:\n{e}\n{traceback.format_exc()}")

# ==== هندلر start ====
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ ربات ساعت حدیث فعال است.")
    await send_image(chat_id=update.effective_chat.id)

# ==== ثبت وب‌هوک ====
@app.route("/", methods=["POST"])
async def telegram_webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, bot)
        await application.initialize()  # ✅ اضافه شد
        await application.process_update(update)
    except Exception as e:
        await bot.send_message(chat_id=ADMIN_ID, text=f"❌ خطای اصلی وب‌هوک:\n{e}\n{traceback.format_exc()}")
    return "ok"


@app.route("/", methods=["GET", "HEAD"])
def home():
    return "Bot is running!"

# ==== اجرای Flask با ثبت وب‌هوک ====
async def main():
    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL)

    application.add_handler(CommandHandler("start", start_handler))

    # اجرای Flask با hypercorn
    PORT = int(os.environ.get("PORT", 8000))
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    config = Config()
    config.bind = [f"0.0.0.0:{PORT}"]
    await serve(app, config)


if __name__ == "__main__":
    asyncio.run(main())
