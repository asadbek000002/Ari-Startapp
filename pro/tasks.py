from celery import shared_task
import requests
from django.utils.timezone import now
from django.conf import settings
from openrouteservice import Client, exceptions as ors_exceptions
from pro.models import WeatherData, DeliveryPricePolicy  # model nomlarini moslashtiring
from decimal import Decimal


@shared_task
def fetch_and_save_weather():
    API_KEY = "69a65d7f961f9aee4b956d0c502bcfdd"
    CITY = "Tashkent"
    url = f"https://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&units=metric"

    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        WeatherData.objects.create(
            city=CITY,
            temperature=data['main']['temp'],
            condition=data['weather'][0]['main'],  # Masalan: Rain, Clear, Clouds
            wind_speed=data['wind']['speed'],
            humidity=data['main']['humidity']
        )


def get_latest_weather_condition():
    """
    So‘nggi ob-havo holatini qaytaradi (WeatherData modelidan).
    """
    latest_weather = WeatherData.objects.order_by('-timestamp').first()
    return latest_weather.condition if latest_weather else None


def calculate_delivery_price(distance_km, transport_type, weather_condition):
    """
    Masofa, transport turi va ob-havo asosida narx hisoblaydi.
    """
    try:
        # Mos keladigan narx siyosatini topamiz
        policy = DeliveryPricePolicy.objects.filter(
            transport_type=transport_type,
            min_distance__lte=Decimal(distance_km),
            max_distance__gte=Decimal(distance_km)
        ).first()

        if not policy:
            return None  # Narx siyosati topilmadi

        # Asosiy narx
        price = policy.base_price + int(Decimal(distance_km) * policy.price_per_km)

        # Ob-havo ta’siri (masalan, yomg'ir bo‘lsa 10% qimmat)
        if weather_condition in ['Rain', 'Snow', 'Thunderstorm']:
            price = int(price * 1.1)  # 10% qoshiladi

        return price
    except Exception as e:
        print(f"Narx hisoblash xatosi: {e}")
        return None
