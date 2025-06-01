from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import pytz
import threading
import time
import os

# اطلاعات ربات و کانال
TOKEN = "7996297648:AAHBtbd6lGGQjUIOjDNRsqETIOCNUfPcU00"
CHANNEL_ID = "-1002605751569"
FONT_PATH = "Pinar-Black.ttf"
BACKGROUND_IMAGE = "clock.png"
FONT_SIZE = 100
WEBHOOK_URL = "https://testmahbood.onrender.com"


# راه‌اندازی Flask
app = Flask(__name__)
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)

# دریافت ساعت فعلی تهران
def get_tehran_time():
    tz = pytz.timezone("Asia/Tehran")
    return datetime.now(tz).strftime("%H:%M")

# ساخت عکس با ساعت درج‌شده
def create_image_with_time():
    try:
        img = Image.open(BACKGROUND_IMAGE).convert("RGB")
    except Exception as e:
        print("❌ خطا در باز کردن تصویر:", e)
        raise

    try:
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    except Exception as e:
        print("❌ خطا در لود فونت:", e)
        raise

    time_text = get_tehran_time()
    w, h = draw.textsize(time_text, font=font)
    W, H = img.size
    x = (W - w) / 2
    y = (H - h) / 2

    draw.text((x, y), time_text, font=font, fill="white")
    output_path = "output.jpg"
    img.save(output_path)
    return output_path

# ارسال عکس به کانال
def send_clock_image():
    try:
        image_path = create_image_with_time()
        with open(image_path, "rb") as photo:
            bot.send_photo(chat_id=CHANNEL_ID, photo=photo)
        print("✅ عکس با موفقیت ارسال شد.")
    except Exception as e:
        print("❌ خطا در ارسال تصویر:", e)

# حلقه‌ی ارسال هر ۵ دقیقه
def job_loop():
    while True:
        send_clock_image()
        time.sleep(300)

job_thread = threading.Thread(target=job_loop)
job_thread.daemon = True

# دستور /start
def start(update, context):
    update.message.reply_text("سلام! ارسال ساعت شروع شد.")
    send_clock_image()
    if not job_thread.is_alive():
        job_thread.start()

# ثبت هندلر
dispatcher.add_handler(CommandHandler("start", start))

# روت وب‌هوک برای دریافت پیام‌ها
@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
    return "ok"

# ست کردن وب‌هوک و اجرای سرور
if __name__ == "__main__":
    bot.delete_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

