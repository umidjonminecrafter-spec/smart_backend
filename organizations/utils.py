import os
import random
import requests
from django.core.cache import cache

ESKIZ_EMAIL = os.getenv('ESKIZ_EMAIL')
ESKIZ_PASSWORD = os.getenv('ESKIZ_PASSWORD')


def generate_verification_code():
    """Tasodifiy 6 xonali son yaratadi"""
    return str(random.randint(100000, 999999))


def get_eskiz_token():
    """Eskiz JWT token oladi va keshga saqlaydi"""
    token = cache.get('eskiz_api_token')
    if token:
        return token

    url = "https://notify.eskiz.uz/api/auth/login"
    payload = {'email': ESKIZ_EMAIL, 'password': ESKIZ_PASSWORD}

    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            new_token = response.json().get('data', {}).get('token')
            cache.set('eskiz_api_token', new_token, 23 * 3600)
            return new_token
    except Exception as e:
        print(f"Eskiz token xatosi: {str(e)}")
    return None


def send_sms(phone_number, message):
    """Eskiz orqali SMS yuboradi"""
    token = get_eskiz_token()
    if not token:
        return False, "Token xatosi"

    url = "https://notify.eskiz.uz/api/message/sms/send"
    headers = {'Authorization': f'Bearer {token}'}
    clean_phone = "".join(filter(str.isdigit(), str(phone_number)))

    payload = {
        'mobile_phone': clean_phone,
        'message': message,
        'from': '4546'  # Bepul sinov davrida '4546' qoladi
    }

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        res_data = response.json()
        if response.status_code == 200 and res_data.get('status') == 'waiting':
            return True, "Yuborildi"
        return False, res_data.get('message', "Xatolik")
    except Exception as e:
        return False, str(e)