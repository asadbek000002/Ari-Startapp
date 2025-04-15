from pro.models import DeliverLocation
from django.contrib.gis.measure import D
from channels.db import database_sync_to_async

@database_sync_to_async
def get_nearest_couriers(order):
    shop_location = order.shop.location

    # Faqat faol kuryerlarni hisoblash
    couriers = DeliverLocation.objects.filter(
        is_active=True,  # Kuryerning faol ekanligini tekshirish (agar bu modelda bunday maydon bo'lsa)
        coordinates__distance_lte=(shop_location, D(km=10))  # 10 km radius
    ).order_by('coordinates__distance')  # Masofaga qarab saralash

    return couriers[:5]  # Eng yaqin 5 ta kuryer
