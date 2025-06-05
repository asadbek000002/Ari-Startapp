import random
from django.core.cache import cache
from django.utils import timezone
from rest_framework import serializers

from goo.models import Order, Feedback
from goo.utils import update_user_rating
from user.models import UserRole, VerificationCode
from django.contrib.auth import get_user_model
from pro.models import DeliverProfile

User = get_user_model()


class ProRegistrationSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=6, required=False)  # Ikkinchi input

    def validate(self, data):
        phone_number = data.get("phone_number")
        code = data.get("code")
        cache_key = f"registration_wait_{phone_number}"

        # 1️⃣ Agar faqat telefon raqami bo'lsa – Kodni yuborish
        if not code:
            # 6 xonali tasdiqlash kodini yaratamiz
            verification_code = str(random.randint(10000, 99999))

            # Cache va bazaga saqlaymiz
            cache.set(cache_key, verification_code, timeout=60)
            VerificationCode.objects.update_or_create(
                phone_number=phone_number, defaults={"code": verification_code}
            )

            # SMS yuborish (hozircha print)
            # print(f"📲 SMS kod: {verification_code}")

            raise serializers.ValidationError(
                f"Iltimos, 1 daqiqa ichida kodni kiriting!  📲 SMS kod: {verification_code} ")

        # 2️⃣ Agar kod yuborilgan bo‘lsa – Uni tekshirish
        cached_code = cache.get(cache_key)
        if not cached_code:
            raise serializers.ValidationError("Kod muddati tugagan yoki noto‘g‘ri raqam!")

        if code != cached_code:
            raise serializers.ValidationError("Kod noto‘g‘ri!")

        return data

    def create(self, validated_data):
        phone_number = validated_data["phone_number"]

        # Ro‘lni topish yoki yaratish
        pro_role, _ = UserRole.objects.get_or_create(name="pro")

        # Foydalanuvchini yaratish yoki topish
        worker, _ = User.objects.get_or_create(phone_number=phone_number)
        worker.roles.add(pro_role)

        # Cache va bazadan kodni o‘chiramiz
        cache.delete(f"registration_wait_{phone_number}")
        VerificationCode.objects.filter(phone_number=phone_number).delete()

        return worker


class DeliverHomeSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(source="user.avatar", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = DeliverProfile
        fields = ["avatar", "full_name", "deliver_id", "work_active"]


class DeliverProfileSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(source="user.avatar", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    phone_number = serializers.CharField(source="user.phone_number", read_only=True)

    class Meta:
        model = DeliverProfile
        fields = ["avatar", "full_name", "deliver_id", "balance", "phone_number", "work_start", "work_end"]


class DeliverActiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliverProfile
        fields = ["work_active"]


class CustomerUserInfoSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'avatar', 'full_name', 'phone_number', 'rating']

    def get_avatar(self, obj):
        request = self.context.get('request')
        if obj.avatar and hasattr(obj.avatar, 'url'):
            return request.build_absolute_uri(obj.avatar.url)
        return None


class CancelProOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)


class OrderActiveProSerializer(serializers.ModelSerializer):
    customer_info = serializers.SerializerMethodField()
    customer_location = serializers.SerializerMethodField()
    shop_location = serializers.SerializerMethodField()
    courier_location = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id',
            'delivery_price',
            'assigned_at',
            'direction',
            'delivery_duration_min',
            'customer_info',
            'customer_location',
            'shop_location',
            'courier_location',
        ]

    def get_customer_info(self, obj):
        request = self.context.get('request')
        return CustomerUserInfoSerializer(obj.user, context={'request': request}).data

    def get_customer_location(self, obj):
        location = obj.user.locations.filter(active=True).first()
        if location:
            return {
                "latitude": location.coordinates.y,
                "longitude": location.coordinates.x,
                "address": location.address,
            }
        return None

    def get_shop_location(self, obj):
        if obj.shop and obj.shop.coordinates:
            return {
                "latitude": obj.shop.coordinates.y,
                "longitude": obj.shop.coordinates.x,
                "title": obj.shop.title,
            }
        return None

    def get_courier_location(self, obj):
        if obj.deliver:
            courier_loc = obj.deliver.deliver_locations.order_by('-updated_at').first()
            if courier_loc:
                return {
                    "latitude": courier_loc.coordinates.y,
                    "longitude": courier_loc.coordinates.x,
                    "updated_at": courier_loc.updated_at,
                }
        return None


class CourierCompleteOrderSerializer(serializers.Serializer):
    rating = serializers.IntegerField(required=False, min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, data):
        order = self.context.get('order')
        user = self.context.get('request').user

        # Faqat o‘ziga tegishli buyurtmani yakunlashi kerak
        if order.deliver is None or order.deliver.user != user:
            raise serializers.ValidationError("Bu buyurtmaga kuryer sifatida siz tegishli emassiz.")

        if order.status != 'completed':
            raise serializers.ValidationError("Buyurtma hali mijoz tomonidan yakunlanmagan.")

        if order.direction != 'arrived_to_customer':
            raise serializers.ValidationError("Buyurtma hali manzilga yetib kelmagan.")

        return data

    def save(self, **kwargs):
        order = self.context.get('order')
        user = self.context.get('request').user
        rating = self.validated_data.get('rating')
        comment = self.validated_data.get('comment', '')

        # Orderni yakunlashni final bosqichi - mahsulot topshirildi
        order.direction = 'handed_over'
        # order.hand_over_at = timezone.now()  # Agar bunday maydon bo'lsa, agar yo'q bo'lsa qo'shish kerak
        order.save(update_fields=['direction'])

        # Agar baho bo‘lsa — saqlaymiz
        if rating:
            feedback, created = Feedback.objects.get_or_create(
                from_user=user,
                to_user=order.user,
                order=order,
                defaults={
                    'rating': rating,
                    'comment': comment
                }
            )
            if created:
                update_user_rating(order.user)

        return order
