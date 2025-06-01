from telegram.ext import Updater, CommandHandler
from telegram import Bot
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import pytz
import time
import threading
import os

# توکن و آیدی کانال
TOKEN = "7996297648:AAHBtbd6lGGQjUIOjDNRsqETIOCNUfPcU00"
CHANNEL_ID = "-1002605751569"

# مسیر فایل‌ها
BACKGROUND_IMAGE = "clock.png"
FONT_PATH = "Pinar-Black.ttf"
FONT_SIZE = 100

bot = Bot(token=TOKEN)

def get_tehran_time():
    tz = pytz.timezone('Asia/Tehran')
    return datetime.now(tz).strftime("%H:%M")

def create_image_with_time():
    img = Image.open(BACKGROUND_IMAGE).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    time_text = get_tehran_time()
    text_width, text_height = draw.textsize(time_text, font=font)
    img_width, img_height = img.size
    x = (img_width - text_width) / 2
    y = (img_height - text_height) / 2

    draw.text((x, y), time_text, font=font, fill="white")
    output_path = "output.jpg"
    img.save(output_path)
    return output_path

def send_clock_image():
    try:
        img_path = create_image_with_time()
        with open(img_path, "rb") as photo:
            bot.send_photo(chat_id=CHANNEL_ID, photo=photo)
    except Exception as e:
        print("خطا در ارسال تصویر:", e)

def job_loop():
    while True:
        send_clock_image()
        time.sleep(300)  # هر 5 دقیقه

# دستور /start
def start(update, context):
    update.message.reply_text("سلام! شروع شد :)")
    send_clock_image()
    # فقط یک بار حلقه شروع بشه
    if not job_thread.is_alive():
        job_thread.start()

# تنظیمات ربات
updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher
dispatcher.add_handler(CommandHandler("start", start))

# شروع حلقه ارسال دوره‌ای
job_thread = threading.Thread(target=job_loop)
job_thread.daemon = True  # خروج برنامه رو بلاک نکنه

# اجرا
updater.start_polling()
updater.idle()
