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
        read_only_fields = ['created_at', 'address']

    def create(self, validated_data):
        user = self.context['request'].user
        coordinates = validated_data.get('coordinates')

        # 5 metr radius ichida joy borligini tekshirish
        existing_location = Location.objects.filter(
            user=user,
            coordinates__distance_lte=(coordinates, D(m=5))  # 5 metr radius
        ).first()

        geolocator = Nominatim(user_agent="geoapi")
        lat, lon = coordinates.y, coordinates.x  # Latitude va Longitude olish
        location = geolocator.reverse((lat, lon), language='en')
        address = location.address if location else "Unknown Location"

        if existing_location:
            # Mavjud joyni yangilash
            existing_location.custom_name = validated_data.get('custom_name', existing_location.custom_name)
            existing_location.coordinates = coordinates
            existing_location.address = address
            existing_location.save()
            return existing_location

        # Yangi joy yaratish
        validated_data['address'] = address
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
