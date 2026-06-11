import random
import requests
from django.conf import settings
from .models import TelegramVerification, Student


def send_telegram_verification_code(phone, purpose):
    # 1. Telefon raqam orqali o'quvchini va uning telegram_chat_id sini topamiz
    try:
        # Agarda modelingizda telegram_chat_id bo'lsa (uni boya qo'shgandik)
        student = Student.objects.get(phone=phone)
        chat_id = student.telegram_chat_id  # O'quvchining shaxsiy chat IDsi
    except Student.DoesNotExist:
        return {"status": False, "message": "Bu telefon raqamli o'quvchi topilmadi!"}

    if not chat_id:
        return {"status": False,
                "message": "O'quvchining Telegram Chat IDsi bazada yo'q! Avval botni start qilishi kerak."}

    # 2. Random 6 xonali kod generatsiya qilamiz
    code = str(random.randint(100000, 999999))

    # 3. Kodni bazaga saqlaymiz
    TelegramVerification.objects.create(
        phone=phone,
        code=code,
        purpose=purpose
    )

    # 4. Telegram Bot orqali kodni o'quvchiga yuboramiz
    # Bot tokenini settings dan yoki atrof-muhitdan olasiz
    BOT_TOKEN = "BOT_TOKEN_SHU_YERGA_YOZILADI"

    matn = f"🔐 *Tasdiqlash kodi*\n\n"
    if purpose == 'register':
        matn += f"Akkount yaratishni tasdiqlash kodi: *{code}*\n"
    elif purpose == 'forgot':
        matn += f"Parolni tiklash uchun tasdiqlash kodi: *{code}*\n"

    matn += "Bu kod 2 daqiqa davomida faol bo'ladi. Hech kimga bermang!"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": matn,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return {"status": True, "message": "Kod Telegramga yuborildi!"}
        return {"status": False, "message": "Bot kodni yubora olmadi."}
    except Exception as e:
        return {"status": False, "message": f"Telegram API xatolik: {str(e)}"}