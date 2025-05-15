from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
import json
import redis
from goo.models import Order, DeliverProfile
from django.utils.timezone import localtime
from django.utils.timezone import now

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
        print("Kelgan xom text_data:", repr(text_data))
        data = json.loads(text_data)
        action = data.get("action")
        order_id = data.get("order_id")

        if action == "accept":
            await self.accept_order(order_id)
        elif action == "reject":
            await self.reject_order(order_id)
        elif action == "location_update":
            await self.update_location(data)

    async def update_location(self, data):
        lat = data.get("latitude")
        lon = data.get("longitude")
        if lat is None or lon is None:
            return

        try:
            profile = await sync_to_async(DeliverProfile.objects.get)(user_id=self.user_id)
            if not profile.work_active:
                return  # Faqat active bo'lgan kuryerlar

        except DeliverProfile.DoesNotExist:
            return

        redis_key = f"location:{self.user_id}"
        timestamp = localtime(now()).isoformat()
        r.set(redis_key, json.dumps({
            "lat": lat,
            "lon": lon,
            "work_active": profile.work_active,
            "is_busy": profile.is_busy,
            "timestamp": timestamp
        }), ex=10800)  # 3 soat expiration (optional)

        # Shu yerda siz WebSocket orqali joylashuvni boshqa guruhlarga yuborsangiz ham bo'ladi
        # await self.channel_layer.group_send(
        #     self.room_group_name,
        #     {
        #         "type": "location_broadcast",
        #         "user_id": str(self.user_id),
        #         "lat": lat,
        #         "lon": lon
        #     }
        # )

        # Faqat ushbu foydalanuvchining o'ziga WebSocket orqali joylashuvni yuborish
        await self.send(text_data=json.dumps({
            "type": "location_broadcast",
            "user_id": str(self.user_id),
            "lat": lat,
            "lon": lon
        }))

    async def location_broadcast(self, event):
        await self.send(text_data=json.dumps({
            "type": "location_update",
            "user_id": event["user_id"],
            "latitude": event["lat"],
            "longitude": event["lon"]
        }))

    async def accept_order(self, order_id):
        order = await sync_to_async(Order.objects.get)(id=order_id)

        if order.status != "pending":
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
