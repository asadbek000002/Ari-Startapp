from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils import timezone
import json
import redis
from goo.models import Order, DeliverProfile

r = redis.StrictRedis(host='localhost', port=6379, db=0)


class OrderOfferConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        path = self.scope.get('path', '')

        if user.is_authenticated:
            self.user = user
            self.user_id = user.id

            # DeliverProfileni faqat bir marta olish

            if 'goo' in path:
                expected_role = 'goo'
            elif 'pro' in path:
                expected_role = 'pro'
                self.deliver_profile = await sync_to_async(DeliverProfile.objects.get)(user=self.user)

            elif 'shop' in path:
                expected_role = 'shop'
            else:
                expected_role = 'unknown'

            role_obj = await sync_to_async(
                lambda: user.roles.filter(name=expected_role).first()
            )()
            role_name = role_obj.name if role_obj else 'default'

            self.room_group_name = f"user_{self.user_id}_{role_name}"
            print(f"Group name: {self.room_group_name}")

            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

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
                "message": "Buyurtma allaqachon olingan yoki tugagan."
            }))
            return

        # Redis flag — Celery task toxtashi uchun
        r.set(f"order_{order.id}_taken", str(self.user.id))

        # Boshqa kuryerlarga to‘xtatish signali
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "order_taken",
                "order_id": order.id
            }
        )

    async def reject_order(self, order_id):
        # Reject hech narsa qilmaydi, task navbatdagiga o‘tadi
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
        # Taskdan push yuborishda ishlatiladi
        await self.send(text_data=json.dumps(event["message"]))
