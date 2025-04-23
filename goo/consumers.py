from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
import json
import redis
from goo.models import Order, DeliverProfile

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
        await self.send(text_data=json.dumps({
            "type": "rejected",
            "order_id": order_id
        }))

    async def order_taken(self, event):
        await self.send(text_data=json.dumps({
            "type": "order_taken",
            "order_id": event["order_id"]
        }))

    async def send_notification(self, event):
        await self.send(text_data=json.dumps(event["message"]))
