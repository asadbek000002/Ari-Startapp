import random
from django.core.cache import cache
from django.utils import timezone
from rest_framework import serializers
from django.contrib.gis.measure import D
from geopy.geocoders import Nominatim

from goo.models import Order, Contact, Feedback
from goo.utils import update_user_rating
from pro.models import DeliverProfile
from shop.models import Shop
from user.models import UserRole, VerificationCode, Location
from django.contrib.auth import get_user_model

User = get_user_model()


class GooRegistrationSerializer(serializers.Serializer):
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
        goo_role, _ = UserRole.objects.get_or_create(name="goo")

        # Foydalanuvchini yaratish yoki topish
        worker, _ = User.objects.get_or_create(phone_number=phone_number)

        worker.roles.add(goo_role)

        # Cache va bazadan kodni o‘chiramiz
        cache.delete(f"registration_wait_{phone_number}")
        VerificationCode.objects.filter(phone_number=phone_number).delete()

        return worker


# userlar o'z joylashuvini qoshadi va yaratadi
class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'custom_name', 'address', 'coordinates', 'created_at', "active"]
        read_only_fields = ['created_at', ]

    def create(self, validated_data):
        user = self.context['request'].user
        coordinates = validated_data.get('coordinates')

        # 5 metr radius ichida joy borligini tekshirish
        existing_location = Location.objects.filter(
            user=user,
            coordinates__distance_lte=(coordinates, D(m=5))  # 5 metr radius
        ).first()

        if existing_location:
            # Mavjud joyni yangilash
            existing_location.custom_name = validated_data.get('custom_name', existing_location.custom_name)
            existing_location.coordinates = coordinates
            existing_location.address = validated_data.get('address', existing_location.address)
            existing_location.save()
            return existing_location

        # Yangi joy yaratish
        validated_data['user'] = user
        return super().create(validated_data)


class LocationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'custom_name', 'address', 'coordinates', 'active']
        read_only_fields = ['id']

    def update(self, instance, validated_data):
        # Agar foydalanuvchi maydonlarni yangilasa, shular yangilanadi
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class LocationActiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['custom_name', 'address']


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['phone_number', 'full_name', 'avatar']  # Faqat update bo‘ladigan maydonlar
        extra_kwargs = {
            'phone_number': {'required': False},
            'full_name': {'required': False},
            'avatar': {'required': False}
        }


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['phone_number', 'full_name', 'avatar']


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ['phone_number', 'telegram_link']


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["id", "user", "shop", "deliver", "items", "allow_other_shops", "status", "created_at"]
        read_only_fields = ["id", "user", "shop", "status", "created_at", "deliver"]

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user

        if not user.has_role("goo"):  # Faqat 'goo' roli bo‘lsa zakaz bera oladi
            raise serializers.ValidationError("Siz zakaz bera olmaysiz, chunki sizda kerakli rol mavjud emas.")

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        shop_id = self.context.get("shop_id")  # `shop_id` ni kontekstdan olish

        validated_data["user"] = request.user  # Foydalanuvchini qo‘shish

        # `shop_id` orqali do‘konni olish
        try:
            shop = Shop.objects.get(id=shop_id, is_verified=True)
        except Shop.DoesNotExist:
            raise serializers.ValidationError({"shop": "Bunday do‘kon topilmadi yoki tasdiqlanmagan."})

        validated_data["shop"] = shop  # Do‘konni avtomatik o‘rnatish

        return super().create(validated_data)


class OrderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            "house_number",
            "apartment_number",
            "floor",
            "intercom_code",
            "additional_note",
        ]


class RetryUpdateOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            "items",
            "allow_other_shops",
            "house_number",
            "apartment_number",
            "floor",
            "intercom_code",
            "additional_note",
        ]


class CancelGooOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)


class DeliverUserInfoSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source='user.id')
    full_name = serializers.CharField(source='user.full_name')
    phone_number = serializers.CharField(source='user.phone_number')
    rating = serializers.FloatField(source='user.rating')
    avatar = serializers.SerializerMethodField()
    role = serializers.CharField()  # deliver_profile.role

    class Meta:
        model = DeliverProfile
        fields = ['id', 'full_name', 'phone_number', 'rating', 'avatar', 'role']

    def get_avatar(self, obj):
        request = self.context.get('request')
        avatar = obj.user.avatar
        if avatar and hasattr(avatar, 'url'):
            return request.build_absolute_uri(avatar.url)
        return None


class OrderActiveGooSerializer(serializers.ModelSerializer):
    deliver_user = DeliverUserInfoSerializer(source='deliver', read_only=True)
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
            'deliver_user',
            'customer_location',
            'shop_location',
            'courier_location',

        ]

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


class PendingSearchingAssignedOrderSerializer(serializers.ModelSerializer):
    shop_title = serializers.CharField(source='shop.title')
    shop_id = serializers.CharField(source='shop.id')

    class Meta:
        model = Order
        fields = ['id', 'order_code', 'shop_title', 'shop_id', 'items', 'created_at', 'status']


# Order Detail
class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ['title', 'image']  # image maydoni shu yerda


class OrderLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['address', 'coordinates']


class OrderUserSerializer(serializers.ModelSerializer):
    active_location = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['phone_number', 'active_location']

    def get_active_location(self, obj):
        location = obj.locations.filter(active=True).first()
        if location:
            return OrderLocationSerializer(location).data
        return None


class OrderDetailSerializer(serializers.ModelSerializer):
    shop = ShopSerializer(read_only=True)
    user = OrderUserSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            "items",
            "allow_other_shops",
            "house_number",
            "apartment_number",
            "floor",
            "intercom_code",
            "additional_note",
            "shop",
            "user"
        ]


class CompleteOrderSerializer(serializers.Serializer):
    rating = serializers.IntegerField(required=False, min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, data):
        order = self.context.get('order')
        user = self.context.get('request').user

        if order.status in ['completed', 'canceled']:
            raise serializers.ValidationError("Buyurtma allaqachon yakunlangan yoki bekor qilingan.")

        if order.direction != 'arrived_to_customer':
            raise serializers.ValidationError("Buyurtma hali manzilga yetib kelmagan.")

        return data

    def save(self, **kwargs):
        order = self.context.get('order')
        user = self.context.get('request').user
        rating = self.validated_data.get('rating')
        comment = self.validated_data.get('comment', '')

        # Orderni yakunlash
        order.status = 'completed'
        order.delivered_at = timezone.now()
        order.save(update_fields=['status', 'delivered_at'])

        # Agar baho bo‘lsa — saqlaymiz
        if rating and order.deliver and order.deliver.user:
            feedback, created = Feedback.objects.get_or_create(
                from_user=user,
                to_user=order.deliver.user,
                order=order,
                defaults={
                    'rating': rating,
                    'comment': comment
                }
            )
            if created:
                update_user_rating(order.deliver.user)

        return order
