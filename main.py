from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import pytz
import threading
import time
import os
import traceback

# اطلاعات ربات و کانال
TOKEN = "7996297648:AAHBtbd6lGGQjUIOjDNRsqETIOCNUfPcU00"
CHANNEL_ID = "-1002605751569"     # آی‌دی کانال (با دقت بررسی شود)
ADMIN_ID = 486475495      # آی‌دی عددی خودت برای دریافت خطاها
FONT_PATH = "Pinar-Black.ttf"     # یا مثلاً "arial.ttf" برای تست
BACKGROUND_IMAGE = "clock.png"
FONT_SIZE = 100
WEBHOOK_URL = "https://testmahbood.onrender.com"


# راه‌اندازی Flask و ربات
app = Flask(__name__)
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)

# گرفتن ساعت تهران
def get_tehran_time():
    tz = pytz.timezone("Asia/Tehran")
    return datetime.now(tz).strftime("%H:%M")

# ساخت تصویر ساعت
def create_image_with_time():
    try:
        img = Image.open(BACKGROUND_IMAGE).convert("RGB")
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        time_text = get_tehran_time()

        w, h = draw.textsize(time_text, font=font)
        W, H = img.size
        x = (W - w) / 2
        y = (H - h) / 2

        draw.text((x, y), time_text, font=font, fill="white")
        output_path = "output.jpg"
        img.save(output_path)
        return output_path

    except Exception as e:
        error_text = f"❌ خطا در ساخت تصویر:\n{str(e)}"
        bot.send_message(chat_id=ADMIN_ID, text=error_text)
        bot.send_message(chat_id=ADMIN_ID, text=traceback.format_exc())
        raise e

# ارسال تصویر به کانال
def send_clock_image():
    try:
        image_path = create_image_with_time()
        with open(image_path, "rb") as photo:
            bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=f"🕒 ساعت {get_tehran_time()}")
            bot.send_message(chat_id=ADMIN_ID, text="✅ تصویر ساعت با موفقیت ارسال شد.")
    except Exception as e:
        error_text = f"❌ خطا در ارسال تصویر:\n{str(e)}"
        bot.send_message(chat_id=ADMIN_ID, text=error_text)
        bot.send_message(chat_id=ADMIN_ID, text=traceback.format_exc())

# حلقه‌ی ۵ دقیقه‌ای ارسال
def job_loop():
    while True:
        send_clock_image()
        time.sleep(300)

job_thread = threading.Thread(target=job_loop)
job_thread.daemon = True

# دستور start
def start(update, context):
    user_id = update.effective_user.id
    bot.send_message(chat_id=user_id, text="✅ ارسال ساعت آغاز شد.")
    try:
        send_clock_image()
    except Exception as e:
        bot.send_message(chat_id=user_id, text="❌ خطا هنگام ارسال تصویر: " + str(e))
    if not job_thread.is_alive():
        job_thread.start()

dispatcher.add_handler(CommandHandler("start", start))

# روت اصلی و وب‌هوک
@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "POST":
        try:
            update = Update.de_json(request.get_json(force=True), bot)
            dispatcher.process_update(update)
        except Exception as e:
            bot.send_message(chat_id=ADMIN_ID, text="❌ خطا در پردازش پیام ورودی")
            bot.send_message(chat_id=ADMIN_ID, text=traceback.format_exc())
    return "ok"

# مسیر تست دستی در مرورگر
@app.route("/test")
def test_image():
    try:
        send_clock_image()
        return "✅ تصویر ارسال شد"
    except Exception as e:
        return f"❌ خطا: {str(e)}"

# شروع برنامه
if __name__ == "__main__":
    bot.delete_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
