from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.utils.timezone import localtime
from datetime import datetime
from django.utils import timezone
from django.db.models import OuterRef, Subquery, Q, F
from uuid import UUID
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from openrouteservice import Client
from openrouteservice.exceptions import ApiError
from django.conf import settings
import json
import redis
import time

from geopy.distance import geodesic

from goo.models import Order, Shop
from pro.models import DeliverLocation, DeliverProfile
from pro.tasks import get_latest_weather_condition, calculate_delivery_price
from user.models import Location

# Redis connection
# r = redis.StrictRedis(host='localhost', port=6377, db=0)
r = redis.StrictRedis(host='redis', port=6379, db=0)


@shared_task
def send_order_to_couriers(order_id, shop_id):
    order = Order.objects.get(id=order_id)
    shop = Shop.objects.get(id=shop_id)
    channel_layer = get_channel_layer()
    if order.status != "assigned":
        order.status = "searching"
        order.save(update_fields=["status"])
        send_order_status_to_customer(channel_layer, order)

    # 1. Redisdan kuryer joylashuvlarini topamiz (so‘nggi 3 daqiqadagi)
    nearby_deliver_ids = []
    deliver_locations = {}  # ✅ user_id: (lon, lat)
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
                    deliver_locations[user_id] = (lon, lat)  # ✅ joylashuvni saqlab qo'yamiz
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

        # Redisdan topilgan user_id lar
        redis_user_ids = [d.user.id for d in deliver_profiles]
        print(f"Redisdan topilgan kuryerlar ID: {redis_user_ids}")

        latest_location_subquery = DeliverLocation.objects.filter(
            deliver=OuterRef('pk')
        ).order_by('-updated_at').values('id')[:1]

        additional_deliver_profiles = DeliverProfile.objects.filter(
            work_active=True, is_busy=False
        ).exclude(
            user__id__in=redis_user_ids  # 👈 Redisdan topilganlarni chiqarib tashlash
        ).filter(
            deliver_locations__id__in=Subquery(latest_location_subquery)
        ).annotate(
            distance=Distance('deliver_locations__coordinates', shop.coordinates)
        ).filter(distance__lte=D(km=5)).distinct()[:remaining_needed]

        deliver_profiles += list(additional_deliver_profiles)

        if additional_deliver_profiles.exists():
            print(f"Bazada {additional_deliver_profiles.count()} ta kuryer topildi.")

    # 4. Agar hech qanday kuryer topilmasa
    if not deliver_profiles:
        order.status = "pending"  # yoki "no_courier_found"
        order.save(update_fields=["status"])
        send_order_status_to_customer(channel_layer, order, failed=True)
        # notify_customer_no_courier_found(channel_layer, order)
        return f"No available couriers found for Order {order.id}"

    # 5. Buyurtmani yuboramiz — 10 ta kuryerga ketma-ket
    for deliver in deliver_profiles[:10]:
        print(f"[🔄] {deliver.user.id=} - {deliver.user.id} kuryerga order yuboriladi...")
        if r.get(f"order_{order.id}_taken"):
            print(f"[⛔️] Order {order.id} allaqachon olingan. Loop break.")
            break

        user_id = deliver.user.id  ##

        # ✅ Avval Redisdan o‘qilgan joylashuv lug‘idan olamiz
        coords = deliver_locations.get(user_id)  ##
        if coords:  ##
            courier_coords = coords  # (lon, lat) ##
        else:  ##
            # Redisda topilmagan bo‘lsa — bazadan fallback
            last_location = DeliverLocation.objects.filter(  ##
                deliver=deliver  ##
            ).order_by('-updated_at').first()  ##
            if not last_location:  ##
                continue  ##
            courier_coords = (last_location.coordinates.x, last_location.coordinates.y)  ##
            print(f"[📍] Bazadan oxirgi joylashuv olindi: {courier_coords}")
        deliver_role = deliver.role

        # 🆕 2. Do‘kon va mijoz koordinatalari
        shop_coords = (shop.coordinates.x, shop.coordinates.y)
        customer_location = Location.objects.filter(user=order.user, active=True).first()
        if not customer_location:
            print(f"[❌] Buyurtmachining joylashuvi topilmadi.")
            continue
        customer_coords = (customer_location.coordinates.x, customer_location.coordinates.y)

        # 🆕 3. Masofa, vaqtni hisoblash
        distance_km, duration_min = calculate_order_route_info(
            deliver_coords=courier_coords,
            shop_coords=shop_coords,
            customer_coords=customer_coords,
            deliver_role=deliver_role
        )

        # 🆕 4. Ob-havoni olib, narxni hisoblash
        weather_condition = get_latest_weather_condition()
        price = calculate_delivery_price(distance_km, deliver_role, weather_condition)
        print(f"[📦] {user_id=} kuryerga order yuborilmoqda...")
        # 🆕 5. Narx bilan birga yuborish
        send_notification_to_deliver(
            channel_layer,
            deliver.user.id,
            order,
            shop,
            price=price,
            distance=round(distance_km, 2),
            duration=round(duration_min, 1)
        )
        print(f"[⏳] Kuryer {user_id=} dan javob kutilyapti...")
        rejected = False
        for _ in range(20):  # 20 soniya kutish (1s * 20)
            if r.get(f"order_{order.id}_taken"):
                break
            if r.get(f"order_{order.id}_rejected_by_{deliver.user.id}"):
                rejected = True
                r.delete(f"order_{order.id}_rejected_by_{deliver.user.id}")
                break
            time.sleep(1)

        if not r.get(f"order_{order.id}_taken") and not rejected:
            send_timeout_notification(channel_layer, deliver.user.id, order.id)

    # 6. Agar kimdir qabul qilgan bo‘lsa — tayinlaymiz
    taken_by = r.get(f"order_{order.id}_taken")
    if taken_by:
        assign_order_to_courier(order, taken_by.decode('utf-8'), deliver_locations)
        r.delete(f"order_{order.id}_taken")
        return f"Order {order.id} assigned to courier {order.deliver.id}"

    # 7. Hech kim olmaydigan bo‘lsa — zakazchiga xabar va statusni qaytarish
    order.status = "pending"  # yoki 'no_courier_found' agar yangi status bo‘lsa
    order.save(update_fields=["status"])
    send_order_status_to_customer(channel_layer, order, failed=True)
    # notify_customer_no_courier_found(channel_layer, order)
    return f"Order {order.id} was not accepted by any courier."


# === Helper functions ===

def send_notification_to_deliver(channel_layer, deliver_user_id, order, shop, price=None, distance=None, duration=None):
    async_to_sync(channel_layer.group_send)(
        f"user_{deliver_user_id}_pro",
        {
            "type": "send_notification",
            "message": {
                "details": "Yangi buyurtma mavjud.",
                "order_id": order.id,
                "shop": shop.title,
                "price": price,
                "distance_km": distance,
                "duration_min": duration,
                "order_items": order.items,
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


def assign_order_to_courier(order, deliver_user_id, deliver_locations=None):
    deliver_profile = DeliverProfile.objects.get(user_id=deliver_user_id)
    order.deliver = deliver_profile
    order.status = "assigned"
    order.save()

    deliver_role = deliver_profile.role

    deliver_profile.is_busy = True
    deliver_profile.save(update_fields=["is_busy"])

    # 3. Kuryerning joylashuvi (Redis'dan olingan)
    if deliver_locations:
        coords = deliver_locations.get(UUID(deliver_user_id))
    else:
        coords = None

    if coords:
        courier_coords = coords
    else:
        # fallback: bazadan oxirgi joylashuv
        last_location = DeliverLocation.objects.filter(
            deliver=deliver_profile
        ).order_by('-updated_at').first()
        if not last_location:
            return
        courier_coords = (last_location.coordinates.x, last_location.coordinates.y)

    # 4. Do‘kon koordinatalarini olish
    shop_coords = (order.shop.coordinates.x, order.shop.coordinates.y)  # lon, lat

    # 5. Zakazchi manzili (customer location)
    customer_location = Location.objects.filter(user=order.user, active=True).first()
    if not customer_location:
        return
    customer_coords = (customer_location.coordinates.x, customer_location.coordinates.y)

    # 6. Marshrutni hisoblash (kuryer -> do‘kon -> zakazchi)
    distance_km, duration_min = calculate_order_route_info(
        deliver_coords=courier_coords,
        shop_coords=shop_coords,
        customer_coords=customer_coords,
        deliver_role=deliver_role
    )

    if distance_km and duration_min:
        # 8. Ob-havo holatini olish
        weather_condition = get_latest_weather_condition()

        # 9. Narxni hisoblash
        price = calculate_delivery_price(distance_km, deliver_role, weather_condition)

        # 7. Buyurtma ma'lumotlarini yangilash
        order.delivery_distance_km = round(distance_km, 2)
        order.delivery_duration_min = round(duration_min, 1)
        order.weather_condition = weather_condition
        order.delivery_price = price
        order.assigned_at = timezone.now()
        order.save()
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{deliver_user_id}_pro",
            {
                "type": "send_notification",
                "message": {
                    "type": "order.assigned",
                    "order_id": str(order.id),
                }
            }
        )
        # if price:
        #     print("Masofa (km):", distance_km)
        #     print("Vaqt (min):", duration_min)
        #     print("Ob-havo:", weather_condition)
        #     print("Hisoblangan narx (so'm):", price)
        # else:
        #     print("Hisoblashda xatolik yuz berdi.")

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


# ZAKAZCHIGA KURYER IZLASH JARAYONI VA TOPILMMAGANINI HOME PAGEDA BILDRIB TURISH
def send_order_status_to_customer(channel_layer, order, failed=False):
    if order.user and hasattr(order.user, "id"):
        channel_layer = get_channel_layer()
        group_name = f"user_{order.user.id}_goo"

        order_data = {
            "type": "searching" if not failed else "kuryer_topilmadi",
            "id": str(order.id),
            "shop_title": order.shop.title,
            "shop_id": str(order.shop.id),
            "items": order.items,
            "created_at": order.created_at.isoformat(),
            "status": order.status,
        }

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "send_notification",
                "message": order_data
            }
        )


def calculate_order_route_info(deliver_coords, shop_coords, customer_coords, deliver_role, direction=None):
    """
    Kuryer → Do‘kon → Mijoz yoki Kuryer → Mijoz marshrutini hisoblaydi.

    :param deliver_coords: (lon, lat) tuple
    :param shop_coords: (lon, lat) tuple
    :param customer_coords: (lon, lat) tuple
    :param deliver_role: 'bike' yoki 'foot'
    :param direction: order.direction (ixtiyoriy, None bo‘lsa do‘kon ham hisoblanadi)
    :return: (distance_km, duration_min) yoki (None, None)
    """
    try:
        client = Client(key=settings.ORS_API_KEY)

        # Do‘konni tashlab ketiladigan bosqichlar (ya'ni uni hisobga olmaymiz):
        skip_shop_directions = {
            "arrived_at_store",
            "picked_up",
            "en_route_to_customer",
            "arrived_to_customer",
            "handed_over"
        }

        # direction yo‘q bo‘lsa yoki hali do‘konga bormagan bo‘lsa – 3ta nuqta
        if direction in skip_shop_directions:
            coords = [deliver_coords, customer_coords]
        else:
            coords = [deliver_coords, shop_coords, customer_coords]

        # transport vositasiga qarab profil tanlash
        profile = 'cycling-regular' if deliver_role == 'bike' else 'foot-walking'

        # ORS dan route so‘rash
        route = client.directions(
            coordinates=coords,
            profile=profile,
            format='json'
        )

        summary = route['routes'][0]['summary']
        distance_km = round(summary['distance'] / 1000, 2)
        duration_min = round(summary['duration'] / 60, 1)

        return distance_km, duration_min

    except ApiError as e:
        print(f"ORS API xatosi: {e}")
    except Exception as e:
        print(f"ORS umumiy xato: {e}")

    return None, None
