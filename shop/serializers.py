from rest_framework import serializers
from shop.models import Shop, ShopRole


class ShopRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopRole
        fields = ["id", "name"]


class ShopFeaturedSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)  # Role ID o‘rniga nomini chiqaradi

    class Meta:
        model = Shop
        fields = ["id", "image", "title", "is_active", "locations", "role_name"]  # "roles" o‘rniga "role_name"


class ShopListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ["id", "image", "title", "work_start", "work_end", "locations", "is_active", "role"]


class ShopMapListSerializer(serializers.ModelSerializer):
    # role_name = serializers.CharField(source="roles.name", read_only=True)  # Role ID o‘rniga nomini chiqaradi

    class Meta:
        model = Shop
        fields = ["id", "image", "coordinates", "locations", "title", "is_active"]


class ShopDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ["id", "image", "title", "work_start", "work_end", "phone_number", "rating", "about", "coordinates",
                  "is_active", "role"]
