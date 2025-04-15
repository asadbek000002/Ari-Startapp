from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from goo.models import Order, Shop
from pro.models import DeliverLocation, DeliverProfile
from celery import shared_task
from django.db.models import OuterRef, Subquery, Q, F  # F import qilindi
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import redis
import time
from django.utils.timezone import localtime

r = redis.StrictRedis(host='localhost', port=6377, db=0)

@shared_task
def send_order_to_couriers(order_id, shop_id):
    order = Order.objects.get(id=order_id)
    shop = Shop.objects.get(id=shop_id)

    current_time = localtime().time()

    # Subquery: eng so‘nggi joylashuv IDsi
    latest_location_subquery = DeliverLocation.objects.filter(
        deliver=OuterRef('pk')
    ).order_by('-updated_at').values('id')[:1]

    # Faol kuryerlarni aniqlaymiz (kechasi ishlovchilarni ham)
    deliver_profiles = DeliverProfile.objects.filter(
        work_active=True,
        work_start__isnull=False,
        work_end__isnull=False
    ).filter(
        # Faol kuryerlarni aniqlash: Kunduzi va kechasi ishlovchilar
        Q(work_start__lte=current_time, work_end__gte=current_time) |  # kunduzi ishlovchilar
        Q(work_start__gt=F('work_end')) & (Q(work_start__lte=current_time) | Q(work_end__gte=current_time))  # kechasi ishlovchilar
    ).filter(
        deliver_locations__id__in=Subquery(latest_location_subquery)
    ).annotate(
        distance=Distance('deliver_locations__coordinates', shop.coordinates)
    ).filter(distance__lte=D(km=5)).distinct()

    if not deliver_profiles.exists():
        print("Hech qanday faol kuryer topilmadi.")
        return f"Order {order.id} was not accepted by any courier."

    # Kuryerlarni 10 taga cheklaymiz
    for deliver in deliver_profiles[:10]:
        if r.get(f"order_{order.id}_taken"):
            break

        # WebSocket orqali xabar
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{deliver.user.id}_pro",
            {
                "type": "send_notification",
                "message": {
                    "order_id": order.id,
                    "details": "Yangi buyurtma mavjud."
                }
            }
        )

        # 7 soniya kutish
        for _ in range(7):
            if r.get(f"order_{order.id}_taken"):
                break
            time.sleep(1)

        if r.get(f"order_{order.id}_taken"):
            break

    if r.get(f"order_{order.id}_taken"):
        deliver_id = r.get(f"order_{order.id}_taken").decode('utf-8')
        deliver_profile = DeliverProfile.objects.get(user_id=deliver_id)
        order.deliver = deliver_profile
        order.status = "assigned"
        order.save()

        print(f"Buyurtma kuryerga berildi. Kuryer ID: {deliver_profile.id}")
        return f"Order {order.id} successfully assigned to courier {deliver_profile.id}"

    return f"Order {order.id} was not accepted by any courier."
