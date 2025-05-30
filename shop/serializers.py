from rest_framework import serializers
from django.utils.translation import get_language
import random
from django.core.cache import cache
from django.contrib.auth import get_user_model

from shop.models import Shop, ShopRole, Advertising
from user.models import UserRole, VerificationCode

User = get_user_model()


class ShopRegistrationSerializer(serializers.Serializer):
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
        shop_role, _ = UserRole.objects.get_or_create(name="shop")

        # Foydalanuvchini yaratish yoki topish
        shop, _ = User.objects.get_or_create(phone_number=phone_number)

        shop.roles.add(shop_role)

        # Cache va bazadan kodni o‘chiramiz
        cache.delete(f"registration_wait_{phone_number}")
        VerificationCode.objects.filter(phone_number=phone_number).delete()

        return shop


class ShopRoleSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = ShopRole
        fields = ["id", "name"]  # Faqat dinamik nom

    def get_name(self, obj):
        lang = get_language()  # Foydalanuvchining hozirgi tili
        return getattr(obj, f"name_{lang}", obj.name_uz)  # Agar name_{lang} bo‘lmasa, default "uz"


class ShopFeaturedSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    locations = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = ["id", "image", "title", "is_active", "locations", "role"]

    def get_request_language(self):
        """ Foydalanuvchining 'Accept-Language' header'ini olish """
        request = self.context.get("request")
        if request:
            return request.headers.get("Accept-Language", "uz")  # Default: "uz"
        return "uz"

    def get_role(self, obj):
        lang = self.get_request_language()
        return getattr(obj.role, f"name_{lang}", obj.role.name_uz) if obj.role else None

    def get_locations(self, obj):
        lang = self.get_request_language()
        return getattr(obj, f"locations_{lang}", obj.locations_uz)

    def get_title(self, obj):
        lang = self.get_request_language()
        return getattr(obj, f"title_{lang}", obj.title_uz)


class ShopListSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    locations = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = ["id", "image", "title", "work_start", "work_end", "locations", "is_active", "role"]

    def get_title(self, obj):
        lang = get_language()
        return getattr(obj, f"title_{lang}", obj.title_uz)  # Default: title_uz

    def get_locations(self, obj):
        lang = get_language()
        return getattr(obj, f"locations_{lang}", obj.locations_uz)  # Default: locations_uz

    def get_role(self, obj):
        lang = get_language()
        return getattr(obj.role, f"name_{lang}", obj.role.name_uz) if obj.role else None  # Default: role.name_uz


class ShopMapListSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    locations = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = ["id", "image", "coordinates", "locations", "title", "is_active", "role"]

    def get_title(self, obj):
        lang = get_language()
        return getattr(obj, f"title_{lang}", obj.title_uz)  # Default: title_uz

    def get_locations(self, obj):
        lang = get_language()
        return getattr(obj, f"locations_{lang}", obj.locations_uz)  # Default: locations_uz

    def get_role(self, obj):
        lang = get_language()
        return getattr(obj.role, f"name_{lang}", obj.role.name_uz) if obj.role else None  # Default: role.name_uz


class ShopDetailSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    about = serializers.SerializerMethodField()
    locations = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = ["id", "image", "title", "work_start", "work_end", "phone_number", "rating", "about",
                  "coordinates", "is_active", "role", "locations"]

    def get_title(self, obj):
        lang = get_language()
        return getattr(obj, f"title_{lang}", obj.title_uz)  # Default: title_uz

    def get_about(self, obj):
        lang = get_language()
        return getattr(obj, f"about_{lang}", obj.about_uz)  # Default: about_uz

    def get_locations(self, obj):
        lang = get_language()
        return getattr(obj, f"locations_{lang}", obj.locations_uz)  # Default: locations_uz


class AdvertisingSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    text = serializers.SerializerMethodField()

    class Meta:
        model = Advertising
        fields = ['id', 'shop', 'image', 'title', 'text', 'link', 'created_at']

    def get_title(self, obj):
        lang = get_language()
        return getattr(obj, f"title_{lang}", obj.title_uz)

    def get_text(self, obj):
        lang = get_language()
        return getattr(obj, f"text_{lang}", obj.text_uz)
