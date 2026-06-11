import random
import requests
from django.conf import settings
from .models import TelegramVerification, Student


def send_telegram_verification_code(phone, purpose):
    # 1. Telefon raqamni normallashtiramiz (+998XXXXXXXXX formatga)
    cleaned = ''.join(c for c in str(phone) if c.isdigit())
    if len(cleaned) == 9:
        cleaned = '998' + cleaned
    formatted_phone = '+' + cleaned

    # Telefon raqam orqali o'quvchini yoki xodimni topamiz va tashkilotini aniqlaymiz
    organization = None
    chat_id = None

    student = Student.objects.filter(phone__in=[phone, cleaned, formatted_phone]).first()
    if student:
        chat_id = student.telegram_chat_id
        organization = student.organization
    else:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.filter(phone__in=[phone, cleaned, formatted_phone]).first()
        if not user:
            user = User.objects.filter(username__in=[phone, cleaned, formatted_phone]).first()

        if user:
            chat_id = user.telegram_chat_id
            organization = user.organization
        else:
            return {"status": False, "message": f"Tizimda bunday telefon raqamli ({phone}) foydalanuvchi topilmadi!"}

    if not chat_id:
        return {"status": False,
                "message": "Foydalanuvchining Telegram Chat IDsi bazada yo'q! Avval botni start (/start) qilish kerak."}

    # 2. Random 6 xonali kod generatsiya qilamiz
    code = str(random.randint(100000, 999999))

    # 3. Kodni bazaga saqlaymiz
    TelegramVerification.objects.create(
        phone=phone,
        code=code,
        purpose=purpose
    )

    # 4. Tashkilotning Telegram sozlamalaridan Verifikatsiya bot tokenini olamiz
    from organizations.models import TelegramNotificationSetting
    setting = TelegramNotificationSetting.objects.filter(organization=organization).first()
    if not setting or not setting.verification_bot_token:
        return {"status": False, "message": "Ushbu tashkilot uchun Verifikatsion bot tokeni kiritilmagan!"}

    BOT_TOKEN = setting.verification_bot_token

    matn = f"🔐 <b>Tasdiqlash kodi</b>\n\n"
    if purpose == 'register':
        matn += f"Akkount yaratishni tasdiqlash kodi: <b>{code}</b>\n"
    elif purpose == 'forgot':
        matn += f"Parolni tiklash uchun tasdiqlash kodi: <b>{code}</b>\n"

    matn += "\nBu kod 2 daqiqa davomida faol bo'ladi. Hech kimga bermang!"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": matn,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload, timeout=8)
        if response.status_code == 200:
            return {"status": True, "message": "Tasdiqlash kodi Telegram botingizga yuborildi! ✅"}
        return {"status": False, "message": f"Bot kodni yubora olmadi. API xatolik: {response.text}"}
    except Exception as e:
        return {"status": False, "message": f"Telegram API xatolik: {str(e)}"}