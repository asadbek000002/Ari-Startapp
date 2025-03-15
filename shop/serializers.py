from rest_framework import serializers
from shop.models import Shop


class ShopFeaturedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ["id", "image", "title", "is_active", "locations"]


class ShopListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ["id", "image", "title", "work_start", "work_end", "locations", "is_active"]


class ShopMapListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ["id", "image", "coordinates", "locations", "title", "is_active"]


class ShopDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ["id", "image", "title", "work_start", "work_end", "phone_number", "rating", "about", "coordinates",
                  "is_active"]


