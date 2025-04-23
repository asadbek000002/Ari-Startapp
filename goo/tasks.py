from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from goo.models import Order, Shop
from pro.models import DeliverLocation, DeliverProfile
from celery import shared_task
from django.db.models import OuterRef, Subquery, Q, F
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import redis
import time
from django.utils.timezone import localtime

r = redis.StrictRedis(host='localhost', port=6377, db=0)
r = redis.StrictRedis(host='redis', port=6379, db=0)


@shared_task
def send_order_to_couriers(order_id, shop_id):
    order = Order.objects.get(id=order_id)
    shop = Shop.objects.get(id=shop_id)
    current_time = localtime().time()

    latest_location_subquery = DeliverLocation.objects.filter(
        deliver=OuterRef('pk')
    ).order_by('-updated_at').values('id')[:1]

    deliver_profiles = DeliverProfile.objects.filter(
        work_active=True,
        work_start__isnull=False,
        work_end__isnull=False
    ).filter(
        Q(work_start__lte=current_time, work_end__gte=current_time) |
        Q(work_start__gt=F('work_end')) & (
                Q(work_start__lte=current_time) | Q(work_end__gte=current_time)
        )
    ).filter(
        deliver_locations__id__in=Subquery(latest_location_subquery)
    ).annotate(
        distance=Distance('deliver_locations__coordinates', shop.coordinates)
    ).filter(distance__lte=D(km=5)).distinct()

    if not deliver_profiles.exists():
        return f"Order {order.id} was not accepted by any courier."

    channel_layer = get_channel_layer()

    for deliver in deliver_profiles[:10]:
        if r.get(f"order_{order.id}_taken"):
            break

        async_to_sync(channel_layer.group_send)(
            f"user_{deliver.user.id}_pro",
            {
                "type": "send_notification",
                "message": {
                    "order_id": order.id,
                    "shop": shop.title,
                    "coordinates": (shop.coordinates.x, shop.coordinates.y),
                    "details": "Yangi buyurtma mavjud."
                }
            }
        )

        for _ in range(10):  # 10 soniya kutish
            if r.get(f"order_{order.id}_taken"):
                break
            time.sleep(1)

        if r.get(f"order_{order.id}_taken"):
            break

        # Agar vaqt tugasa, kuryerga qabul qilish vaqti tugaganini xabar qilish
        if r.get(f"order_{order.id}_taken") is None:
            async_to_sync(channel_layer.group_send)(
                f"user_{deliver.user.id}_pro",
                {
                    "type": "send_notification",
                    "message": {
                        "order_id": order.id,
                        "details": "Buyurtma qabul qilish vaqti tugadi."
                    }
                }
            )

    taken_by = r.get(f"order_{order.id}_taken")
    if taken_by:
        deliver_id = taken_by.decode('utf-8')
        deliver_profile = DeliverProfile.objects.get(user_id=deliver_id)
        order.deliver = deliver_profile
        order.status = "assigned"
        order.save()

        notify_shop_order_taken(order, deliver_id)
        notify_deliver_order_taken(order, deliver_profile)

        r.delete(f"order_{order.id}_taken")
        return f"Order {order.id} assigned to courier {deliver_profile.id}"

    return f"Order {order.id} was not accepted by any courier."


def notify_shop_order_taken(order, deliver_id):
    shop_user = order.shop.user
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{shop_user.id}_shop",
        {
            "type": "send_notification",
            "message": {
                "type": "yangi_zakaz_mavjud",
                "order_id": order.id,
                "deliver_id": deliver_id,
                "details": order.items
            }
        }
    )


def notify_deliver_order_taken(order, deliver_profile):
    order_user = order.user
    channel_layer = get_channel_layer()
    latest_location = DeliverLocation.objects.filter(
        deliver=deliver_profile
    ).order_by('-updated_at').first()

    if latest_location:
        latest_coords = (latest_location.coordinates.x, latest_location.coordinates.y)
    else:
        latest_coords = None

    async_to_sync(channel_layer.group_send)(
        f"user_{order_user.id}_goo",
        {
            "type": "send_notification",
            "message": {
                "type": "zakaz_qabul_qilindi",
                "order_id": order.id,
                "deliver_id": str(deliver_profile.id),
                "deliver_name": deliver_profile.user.full_name,  # Kuryerning ismi
                "deliver_phone": deliver_profile.user.phone_number,  # Kuryerning telefon raqami
                "latest_coords": latest_coords  # Buyurtma ma'lumotlari
            }
        }
    )
