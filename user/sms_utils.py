import requests
from django.conf import settings
from django.core.cache import cache

ESKIZ_TOKEN_CACHE_KEY = "eskiz_token"
ESKIZ_TOKEN_URL = "https://notify.eskiz.uz/api/auth/login"
ESKIZ_SMS_URL = "https://notify.eskiz.uz/api/message/sms/send"


def get_eskiz_token():
    token = cache.get(ESKIZ_TOKEN_CACHE_KEY)
    if token:
        return token

    # Login qilib token olamiz
    response = requests.post(ESKIZ_TOKEN_URL, data={
        "email": settings.ESKIZ_EMAIL,
        "password": settings.ESKIZ_PASSWORD
    })

    if response.status_code == 200:
        token = response.json()["data"]["token"]
        # Tokenni 1 soatga saqlaymiz
        cache.set(ESKIZ_TOKEN_CACHE_KEY, token, timeout=60 * 60)
        return token
    else:
        raise Exception("Eskiz token olishda xatolik: " + response.text)


def send_sms(phone_number: str, text: str):
    token = get_eskiz_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "mobile_phone": phone_number,
        "message": text,
        "from": "4546",  # Eskizda sizga ajratilgan sender ID
        # "callback_url": "http://example.com"  # Shart emas, ixtiyoriy
    }

    response = requests.post(ESKIZ_SMS_URL, headers=headers, data=payload)

    if response.status_code != 200:
        raise Exception("SMS yuborishda xatolik: " + response.text)
