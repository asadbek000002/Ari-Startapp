import random
from django.core.cache import cache
from rest_framework import serializers
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


class DeliverProfileSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(source="user.avatar", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = DeliverProfile
        fields = ["avatar", "full_name", "created_at"]
