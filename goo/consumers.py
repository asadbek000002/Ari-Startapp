import redis
import math
import time
import json
from django.utils.timezone import localtime, now
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from goo.tasks import calculate_order_route_info
from user.models import Location
from goo.models import Order
from pro.models import DeliverProfile

# r = redis.StrictRedis(host='localhost', port=6377, db=0)
r = redis.StrictRedis(host='redis', port=6379, db=0)


class OrderOfferConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        path = self.scope.get('path', '')

        if not user.is_authenticated:
            await self.close()
            return

        self.user = user
        self.user_id = user.id

        if 'pro' in path:
            self.role = 'pro'
            self.deliver_profile = await sync_to_async(DeliverProfile.objects.get)(user=user)
        elif 'shop' in path:
            self.role = 'shop'
        elif 'goo' in path:
            self.role = 'goo'
        else:
            self.role = 'default'

        self.room_group_name = f"user_{self.user_id}_{self.role}"
        print(f"User {self.user_id} with role {self.role} connected to group {self.room_group_name}")
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get("action")
        order_id = data.get("order_id")

        if action == "accept":
            await self.accept_order(order_id)
        elif action == "reject":
            await self.reject_order(order_id)
        elif action == "location_update":
            await self.update_location(data)

    def haversine(self, lat1, lon1, lat2, lon2):
        R = 6371000  # meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    async def update_location(self, data):
        lat = data.get("latitude")
        lon = data.get("longitude")
        if lat is None or lon is None:
            return

        profile = await sync_to_async(DeliverProfile.objects.select_related("user").get)(user_id=self.user_id)
        if not profile.work_active:
            return
        timestamp = localtime(now()).isoformat()
        timestampcount = int(time.time())
        redis_key = f"location:{self.user_id}"
        old_data_raw = r.get(redis_key)
        old_data = json.loads(old_data_raw) if old_data_raw else None

        # Redis'ga yangi joylashuvni yozamiz
        r.set(redis_key, json.dumps({
            "lat": lat,
            "lon": lon,
            "work_active": profile.work_active,
            "is_busy": profile.is_busy,
            "timestamp": timestamp
        }), ex=10800)

        # 1. Orderni topamiz
        try:
            order = await sync_to_async(
                lambda: Order.objects.select_related("shop", "user")
                .filter(deliver=profile, status="assigned", assigned_at__isnull=False)
                .first()
            )()

            active_location = await sync_to_async(Location.objects.filter(user=order.user, active=True).first)()


        except Order.DoesNotExist:
            return

        goo_group = f"user_{order.user.id}_goo"

        # 2. Avvalgi joylashuvdan uzoqlikni tekshiramiz (agar bor bo‘lsa)
        distance_m = 1000
        if old_data:
            distance_m = self.haversine(lat, lon, old_data["lat"], old_data["lon"])

        # 3. Har 5s da lat/lon yuboramiz
        last_5s_key = f"loc_sent:{self.user_id}:5s"
        last_5s = r.get(last_5s_key)
        if not last_5s or (timestampcount - int(last_5s)) >= 5:
            await self.channel_layer.group_send(
                goo_group,
                {
                    "type": "location_broadcast",
                    "user_id": str(self.user_id),
                    "latitude": lat,
                    "longitude": lon,
                    "timestamp": timestamp
                }
            )
            r.set(last_5s_key, timestampcount)

        # 4. Har 15s da agar >20m bo‘lsa, duration yuboramiz
        last_15s_key = f"duration_sent:{self.user_id}"
        last_15s = r.get(last_15s_key)
        if (not last_15s or (timestampcount - int(last_15s)) >= 15) and distance_m >= 20:
            deliver_coords = (lon, lat)
            shop_coords = (order.shop.coordinates.x, order.shop.coordinates.y)
            customer_coords = (active_location.coordinates.x, active_location.coordinates.y)
            deliver_role = profile.role

            _, duration_min = await sync_to_async(calculate_order_route_info)(
                deliver_coords, shop_coords, customer_coords, deliver_role, order.direction
            )

            if duration_min:
                await self.channel_layer.group_send(
                    goo_group,
                    {
                        "type": "duration_broadcast",
                        "order_id": str(order.id),
                        "duration_min": duration_min,
                        "timestamp": timestamp
                    }
                )
                r.set(last_15s_key, timestampcount)

    async def location_broadcast(self, event):
        await self.send(text_data=json.dumps({
            "type": "location_update",
            "user_id": event["user_id"],
            "latitude": event["latitude"],
            "longitude": event["longitude"],
            "timestamp": event["timestamp"]
        }))

    async def duration_broadcast(self, event):
        await self.send(text_data=json.dumps({
            "type": "duration_update",
            "order_id": event["order_id"],
            "duration_min": event["duration_min"],
            "timestamp": event["timestamp"]
        }))

    async def accept_order(self, order_id):
        order = await sync_to_async(Order.objects.get)(id=order_id)

        if order.status != "searching":
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Buyurtma allaqachon olingan."
            }))
            return

        already_taken = r.get(f"order_{order.id}_taken")
        if not already_taken:
            r.set(f"order_{order.id}_taken", str(self.user_id))
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "order_taken",
                    "order_id": order.id
                }
            )

    async def reject_order(self, order_id):
        order = await sync_to_async(Order.objects.get)(id=order_id)

        if order.status != "pending":
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Buyurtma allaqachon olingan."
            }))
            return

        # Redisga rad etilgan kuryer haqida ma'lumot qo'shish
        r.set(f"order_{order.id}_rejected_by_{self.user_id}", "rejected")

        # Endi bu yerda guruhga yubormaymiz, faqat o'z kanaliga yuboramiz
        await self.send(text_data=json.dumps({
            "type": "reject_order",  # Xabar turini belgilash
            "order_id": order.id,  # Yuborilayotgan order_id
        }))

    async def order_taken(self, event):
        await self.send(text_data=json.dumps({
            "type": "order_taken",
            "order_id": event["order_id"]
        }))

    async def send_notification(self, event):
        await self.send(text_data=json.dumps(event["message"]))

    async def order_direction_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "order_direction_update",
            "order_id": event["order_id"],
            "direction": event["direction"]
        }))
