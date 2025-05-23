import random
from django.core.cache import cache
from rest_framework import serializers
from django.contrib.gis.measure import D
from geopy.geocoders import Nominatim

from goo.models import Order, Contact
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
            "has_intercom",
            "intercom_code",
            "additional_note",
        ]


class CancelOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)


class DeliverUserInfoSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'avatar', 'full_name', 'phone_number', 'rating']

    def get_avatar(self, obj):
        request = self.context.get('request')
        if obj.avatar and hasattr(obj.avatar, 'url'):
            return request.build_absolute_uri(obj.avatar.url)
        return None


class OrderActiveGooSerializer(serializers.ModelSerializer):
    deliver_user = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'delivered_at', "direction", 'deliver_user', 'delivery_duration_min']

    def get_deliver_user(self, obj):
        if obj.deliver and hasattr(obj.deliver, 'user'):
            return DeliverUserInfoSerializer(obj.deliver.user, context=self.context).data
        return None

# class OrderActiveGooSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Order
#         fields = [
#             'id',  # Zakaz ID
#             'user',  # Foydalanuvchi (user)
#             'shop',  # Do'kon (shop)
#             'deliver',  # Yetkazib beruvchi (deliver)
#             'items',  # Mahsulotlar ro'yxati (items)
#             'allow_other_shops',  # Boshqa do'konlardan olib kelish (allow_other_shops)
#             'house_number',  # Uy raqami (house_number)
#             'apartment_number',  # Kvartira raqami (apartment_number)
#             'floor',  # Qavat (floor)
#             'has_intercom',  # Interkom mavjudligi (has_intercom)
#             'intercom_code',  # Interkom kodi (intercom_code)
#             'additional_note',  # Qo'shimcha izoh (additional_note)
#             'status',  # Zakaz holati (status)
#             'canceled_by_user',  # Zakazni bekor qilgan foydalanuvchi (canceled_by_user)
#             'canceled_by',  # Zakazni bekor qilgan shaxs (canceled_by)
#             'cancel_reason',  # Bekor qilish sababi (cancel_reason)
#             'canceled_at',  # Bekor qilingan vaqt (canceled_at)
#             'created_at',  # Zakaz yaratish vaqti (created_at)
#             'delivery_distance_km',  # Yetkazib berish masofasi (delivery_distance_km)
#             'delivery_duration_min',  # Yetkazib berish davomiyligi (delivery_duration_min)
#             'assigned_at',  # Tayinlangan vaqt (assigned_at)
#             'delivered_at',  # Yetkazib berilgan vaqt (delivered_at)
#         ]
