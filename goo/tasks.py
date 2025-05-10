from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.utils.timezone import localtime
from datetime import datetime
from django.db.models import OuterRef, Subquery, Q, F
from uuid import UUID
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import redis
import time

from geopy.distance import geodesic

from goo.models import Order, Shop
from pro.models import DeliverLocation, DeliverProfile

# Redis connection
# r = redis.StrictRedis(host='localhost', port=6377, db=0)


r = redis.StrictRedis(host='redis', port=6379, db=0)


@shared_task
def send_order_to_couriers(order_id, shop_id):
    order = Order.objects.get(id=order_id)
    shop = Shop.objects.get(id=shop_id)
    channel_layer = get_channel_layer()

    # 1. Redisdan kuryer joylashuvlarini topamiz (so‘nggi 3 daqiqadagi)
    nearby_deliver_ids = []
    for key in r.scan_iter(match="location:*"):
        try:
            data = json.loads(r.get(key))
            lat = float(data.get("lat", 0))
            lon = float(data.get("lon", 0))
            work_active = data.get("work_active")
            is_busy = data.get("is_busy")

            if work_active and not is_busy:
                courier_coords = (lat, lon)
                shop_coords = (shop.coordinates.y, shop.coordinates.x)

                distance_km = geodesic(shop_coords, courier_coords).km
                if distance_km <= 5:
                    user_id = UUID(key.decode().split(":")[1])
                    nearby_deliver_ids.append(user_id)
                    print(f"redis {user_id} ta kuryer topildi.")
                    if len(nearby_deliver_ids) >= 10:
                        break
        except Exception as e:
            print(f"Error parsing Redis location for {key}: {e}")

    # 2. Redisdan topilgan kuryerlar bilan boshlaymiz
    deliver_profiles = list(DeliverProfile.objects.filter(
        user__id__in=nearby_deliver_ids,
        work_active=True,
        is_busy=False
    ))

    # 3. Agar Redisdan 10 ta kuryer topilmagan bo‘lsa — bazadan to‘ldiramiz
    if len(deliver_profiles) < 10:
        remaining_needed = 10 - len(deliver_profiles)

        latest_location_subquery = DeliverLocation.objects.filter(
            deliver=OuterRef('pk')
        ).order_by('-updated_at').values('id')[:1]

        additional_deliver_profiles = DeliverProfile.objects.filter(
            work_active=True, is_busy=False,
            deliver_locations__id__in=Subquery(latest_location_subquery)
        ).annotate(
            distance=Distance('deliver_locations__coordinates', shop.coordinates)
        ).filter(distance__lte=D(km=5)).distinct()[:remaining_needed]

        # Qo‘shimcha topilganlarni deliver_profiles ga qo‘shamiz
        deliver_profiles += list(additional_deliver_profiles)

        if additional_deliver_profiles.exists():
            print(f"Bazada {additional_deliver_profiles.count()} ta kuryer topildi.")

    # 4. Agar hech qanday kuryer topilmasa
    if not deliver_profiles:
        notify_customer_no_courier_found(channel_layer, order)
        return f"No available couriers found for Order {order.id}"

    # 5. Buyurtmani yuboramiz — 10 ta kuryerga ketma-ket
    for deliver in deliver_profiles[:10]:
        if r.get(f"order_{order.id}_taken"):
            break

        send_notification_to_deliver(channel_layer, deliver.user.id, order, shop)

        for _ in range(20):  # 20 soniya kutish (1s * 20)
            if r.get(f"order_{order.id}_taken"):
                break
            time.sleep(1)

        if not r.get(f"order_{order.id}_taken"):
            send_timeout_notification(channel_layer, deliver.user.id, order.id)

    # 6. Agar kimdir qabul qilgan bo‘lsa — tayinlaymiz
    taken_by = r.get(f"order_{order.id}_taken")
    if taken_by:
        assign_order_to_courier(order, taken_by.decode('utf-8'))
        r.delete(f"order_{order.id}_taken")
        return f"Order {order.id} assigned to courier {order.deliver.id}"

    # 7. Hech kim olmaydigan bo‘lsa — zakazchiga xabar
    notify_customer_no_courier_found(channel_layer, order)
    return f"Order {order.id} was not accepted by any courier."


# === Helper functions ===

def send_notification_to_deliver(channel_layer, deliver_user_id, order, shop):
    async_to_sync(channel_layer.group_send)(
        f"user_{deliver_user_id}_pro",
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


def send_timeout_notification(channel_layer, deliver_user_id, order_id):
    async_to_sync(channel_layer.group_send)(
        f"user_{deliver_user_id}_pro",
        {
            "type": "send_notification",
            "message": {
                "order_id": order_id,
                "details": "Buyurtma qabul qilish vaqti tugadi."
            }
        }
    )


def assign_order_to_courier(order, deliver_user_id):
    deliver_profile = DeliverProfile.objects.get(user_id=deliver_user_id)
    order.deliver = deliver_profile
    order.status = "assigned"
    order.save()

    deliver_profile.is_busy = True
    deliver_profile.save(update_fields=["is_busy"])

    notify_shop_order_taken(order, deliver_user_id)
    notify_deliver_order_taken(order, deliver_profile)


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

    latest_coords = (latest_location.coordinates.x, latest_location.coordinates.y) if latest_location else None

    async_to_sync(channel_layer.group_send)(
        f"user_{order_user.id}_goo",
        {
            "type": "send_notification",
            "message": {
                "type": "zakaz_qabul_qilindi",
                "order_id": order.id,
                "deliver_id": str(deliver_profile.id),
                "deliver_name": deliver_profile.user.full_name,
                "deliver_phone": deliver_profile.user.phone_number,
                "latest_coords": latest_coords
            }
        }
    )


def notify_customer_no_courier_found(channel_layer, order):
    async_to_sync(channel_layer.group_send)(
        f"user_{order.user.id}_goo",
        {
            "type": "send_notification",
            "message": {
                "type": "kuryer_topilmadi",
                "order_id": order.id,
                "details": "kuryer topilmadi. Iltimos, keyinroq qayta urinib ko‘ring."
            }
        }
    )


@shared_task
def save_locations_from_redis():
    saved_count = 0  # Nechta location saqlandi

    for key in r.scan_iter(match="location:*"):
        try:
            user_id_str = key.decode().split(":")[1]
            user_id = UUID(user_id_str)  # UUID string to UUID object

            data = json.loads(r.get(key))
            lat = data.get("lat")
            lon = data.get("lon")
            timestamp = data.get("timestamp")

            if not (lat and lon and timestamp):
                continue

            profile = DeliverProfile.objects.get(user__id=user_id)
            point = Point(float(lon), float(lat))

            location, created = DeliverLocation.objects.get_or_create(
                deliver=profile,
                defaults={"coordinates": point, "updated_at": datetime.fromisoformat(timestamp)}
            )

            if not created:
                location.coordinates = point
                location.updated_at = datetime.fromisoformat(timestamp)
                location.save()

            saved_count += 1

        except Exception as e:
            print(f"Error updating location for {key}: {e}")

    return f"{saved_count} ta location bazaga saqlandi"
