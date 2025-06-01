import os
import random
import traceback
from flask import Flask, request
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from hijri_converter import Gregorian
from telegram import Bot
import pytz

# اطلاعات ربات و کانال
TOKEN = "7996297648:AAHBtbd6lGGQjUIOjDNRsqETIOCNUfPcU00"
CHANNEL_ID = "-1002605751569"     # آی‌دی کانال (با دقت بررسی شود)
ADMIN_ID = 486475495      # آی‌دی عددی خودت برای دریافت خطاها
WEBHOOK_URL = "https://testmahbood.onrender.com"


bot = Bot(token=TOKEN)
app = Flask(__name__)

# ==== فونت‌ها ====
FONT_BLACK = "Pinar-DS3-FD-Black.ttf"
FONT_BOLD = "Pinar-DS3-FD-Bold.ttf"

# ==== لیست احادیث ====
def get_random_hadith():
    with open("hadiths.txt", "r", encoding="utf-8") as f:
        hadiths = [h.strip() for h in f.readlines() if h.strip()]
    return random.choice(hadiths)

# ==== تولید تصویر ====
def create_image_with_text():
    try:
        image = Image.open("000.png").convert("RGBA")
        draw = ImageDraw.Draw(image)

        # ساعت ایران
        now = datetime.now(pytz.timezone("Asia/Tehran"))
        gregorian = now.strftime("%Y/%m/%d")
        hijri = Gregorian(now.year, now.month, now.day).to_hijri().isoformat().replace("-", "/")
        jalali = now.strftime("%Y/%m/%d")  # می‌تونی با khayyam یا jdatetime دقیق‌تر کنی

        hadith = get_random_hadith()

        # فونت‌ها
        font_black = ImageFont.truetype(FONT_BLACK, 70)
        font_bold = ImageFont.truetype(FONT_BOLD, 70)

        # نوشتن "امروز"
        draw.text((100, 50), "امروز", font=font_black, fill="white", stroke_width=5, stroke_fill="black")

        # تاریخ‌ها
        draw.text((100, 150), f"تاریخ شمسی: {jalali}", font=font_bold, fill="white")
        draw.text((100, 230), f"تاریخ قمری: {hijri}", font=font_bold, fill="white")
        draw.text((100, 310), f"تاریخ میلادی: {gregorian}", font=font_bold, fill="white")

        # === بخش حدیث ===
        hadith_title_font = ImageFont.truetype(FONT_BLACK, 70)
        hadith_text_font = ImageFont.truetype(FONT_BOLD, 70)

        # اندازه کلمه حدیث
        text = "حدیث"
        w, h = draw.textbbox((0, 0), text, font=hadith_title_font)[2:]
        draw.rectangle([100, 390, 100 + 300, 390 + 25], fill="white")
        draw.text((100 + (300 - w)//2, 392), text, font=hadith_title_font, fill="#014612", stroke_width=5, stroke_fill="white")

        # اندازه مستطیل حدیث (زیر متن حدیث)
        hadith_lines = hadith.split("\n")
        max_width = 1200
        y = 460
        text_area_w = 1300

        # اندازه‌گیری متن حدیث
        line_spacing = 90
        total_height = line_spacing * len(hadith_lines)
        draw.rectangle([90, y, 90 + text_area_w, y + total_height + 30], fill="#800080")

        # نوشتن متن حدیث
        for i, line in enumerate(hadith_lines):
            draw.text((100, y + i * line_spacing), line, font=hadith_text_font, fill="white", stroke_width=5, stroke_fill="white")

        # ذخیره
        output_path = "output.png"
        image.save(output_path)
        return output_path

    except Exception as e:
        bot.send_message(chat_id=ADMIN_ID, text=f"❌ خطا در ساخت تصویر:\n{str(e)}\n\n{traceback.format_exc()}")
        raise e

# ==== ارسال تصویر ====
def send_image():
    try:
        image_path = create_image_with_text()
        with open(image_path, "rb") as img:
            bot.send_photo(chat_id=CHANNEL_ID, photo=img)
    except Exception as e:
        bot.send_message(chat_id=ADMIN_ID, text=f"❌ خطا در ارسال تصویر:\n{str(e)}")

# ==== پینگ اپ‌تایم ====
@app.route("/", methods=["GET", "HEAD"])
def home():
    return "Bot is alive!"

# ==== هندل وب‌هوک Start ====
@app.route("/", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        if "message" in data and "text" in data["message"]:
            text = data["message"]["text"]
            chat_id = data["message"]["chat"]["id"]
            if text == "/start":
                bot.send_message(chat_id=chat_id, text="✅ ربات ساعت حدیث فعال است.")
                send_image()
    except Exception as e:
        bot.send_message(chat_id=ADMIN_ID, text=f"❌ خطای کلی:\n{str(e)}\n{traceback.format_exc()}")
    return "ok"

# ==== زمان‌بندی هر ۵ دقیقه ====
import threading
import time

def loop_sender():
    while True:
        send_image()
        time.sleep(300)  # هر ۵ دقیقه

threading.Thread(target=loop_sender, daemon=True).start()

if __name__ == "__main__":
    bot.delete_webhook()  # اختیاریه: برای اطمینان از پاک بودن قبلی
    bot.set_webhook(url=WEBHOOK_URL)  # این خیلی مهمه ✅
    
    PORT = int(os.environ.get("PORT", 8000))  # از رندر یا پیش‌فرض ۸۰۰۰
    app.run(host="0.0.0.0", port=PORT)
