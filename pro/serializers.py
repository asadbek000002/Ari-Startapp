import random
from django.core.cache import cache
from rest_framework import serializers

from goo.models import Order
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


class OrderActiveProSerializer(serializers.ModelSerializer):
    customer_info = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'delivered_at', 'direction', 'customer_info']

    def get_customer_info(self, obj):
        request = self.context.get('request')
        return CustomerUserInfoSerializer(obj.user, context={'request': request}).data

# class OrderActiveProSerializer(serializers.ModelSerializer):
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
