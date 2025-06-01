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

# ==== ساخت تصویر ====
def create_image_with_text():
    image = Image.open("000.png").convert("RGBA")
    draw = ImageDraw.Draw(image)

    now = datetime.now(pytz.timezone("Asia/Tehran"))
    gregorian = now.strftime("%Y/%m/%d")
    hijri = Gregorian(now.year, now.month, now.day).to_hijri().isoformat().replace("-", "/")
    jalali = now.strftime("%Y/%m/%d")  # اختیاری: می‌تونی jdatetime استفاده کنی

    hadith = get_random_hadith()

    font_black = ImageFont.truetype(FONT_BLACK, 70)
    font_bold = ImageFont.truetype(FONT_BOLD, 70)

    draw.text((100, 50), "امروز", font=font_black, fill="white", stroke_width=5, stroke_fill="black")
    draw.text((100, 150), f"تاریخ شمسی: {jalali}", font=font_bold, fill="white")
    draw.text((100, 230), f"تاریخ قمری: {hijri}", font=font_bold, fill="white")
    draw.text((100, 310), f"تاریخ میلادی: {gregorian}", font=font_bold, fill="white")

    hadith_title_font = ImageFont.truetype(FONT_BLACK, 70)
    hadith_text_font = ImageFont.truetype(FONT_BOLD, 70)

    w, h = draw.textbbox((0, 0), "حدیث", font=hadith_title_font)[2:]
    draw.rectangle([100, 390, 100 + 300, 390 + 25], fill="white")
    draw.text((100 + (300 - w) // 2, 392), "حدیث", font=hadith_title_font, fill="#014612", stroke_width=5, stroke_fill="white")

    hadith_lines = hadith.split("\n")
    y = 460
    text_area_w = 1300
    line_spacing = 90
    total_height = line_spacing * len(hadith_lines)
    draw.rectangle([90, y, 90 + text_area_w, y + total_height + 30], fill="#800080")

    for i, line in enumerate(hadith_lines):
        draw.text((100, y + i * line_spacing), line, font=hadith_text_font, fill="white", stroke_width=5, stroke_fill="white")

    output_path = "output.png"
    image.save(output_path)
    return output_path

# ==== ارسال تصویر ====
async def send_image(chat_id=CHANNEL_ID):
    try:
        path = create_image_with_text()
        with open(path, "rb") as photo:
            await bot.send_photo(chat_id=chat_id, photo=photo)
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
