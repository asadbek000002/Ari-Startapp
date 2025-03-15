from rest_framework import serializers
from shop.models import Shop, ShopRole
from django.utils.translation import get_language


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
