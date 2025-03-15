from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

from shop.models import Shop
from shop.serializers import ShopFeaturedSerializer, ShopListSerializer, ShopMapListSerializer, ShopDetailSerializer

from user.models import Location


@api_view(["GET"])
def global_search(request):
    """Foydalanuvchi search qilganda faqat title va locations qaytaruvchi API"""

    query = request.query_params.get("search", "").strip()

    if not query:
        return Response([])  # Agar search bo‘lmasa, bo‘sh list qaytadi va bazaga request ketmaydi.

    shops = Shop.objects.filter(
        Q(title__icontains=query) | Q(locations__icontains=query),  # Title yoki locations bo‘yicha qidirish
        is_verified=True
    ).order_by("-rating")[:8]  # 8 ta shop bilan cheklash

    serializer = ShopFeaturedSerializer(shops, many=True, context={"request": request})

    # Faqat title va locations maydonlarini qaytarish
    filtered_data = [{"title": shop["title"], "locations": shop["locations"]} for shop in serializer.data]

    return Response(filtered_data)


# Shop lists

@api_view(["GET"])
def shop_featured_list(request):
    """Birinchi 8 ta do‘konni qaytaruvchi API"""
    shops = Shop.objects.filter(is_verified=True).order_by("order")[:8]  # Eng optimal limit
    serializer = ShopFeaturedSerializer(shops, many=True, context={"request": request})
    return Response(serializer.data)


@api_view(["GET"])
def shop_list(request):
    """Do‘konlarni qidirish va saralash imkoniyatiga ega API"""

    search_query = request.query_params.get("search", "").strip()  # Qidiruv so‘rovi
    filters = Q(is_verified=True)  # Faqat tasdiqlangan do‘konlarni olish
    if search_query:
        filters &= Q(title__icontains=search_query) | Q(locations__icontains=search_query)

    shops = Shop.objects.filter(filters).order_by("order", "-created_at")

    serializer = ShopListSerializer(shops, many=True, context={"request": request})
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])  # Foydalanuvchi autentifikatsiyadan o'tishi shart
def shop_map_list(request):
    """Foydalanuvchining joylashuvi bo‘yicha radiusni o‘zi belgilab do‘konlarni filterlaydigan API"""

    user = request.user
    user_location = Location.objects.filter(user=user).order_by("-created_at").first()  # Eng so‘nggi joylashuv

    # Radiusni olish (default=10 km, min=1 km, max=50 km)
    try:
        radius = min(50, max(1, float(request.query_params.get("radius", 10))))
    except ValueError:
        radius = 10

    if user_location and user_location.coordinates:
        shops = (
            Shop.objects.filter(
                coordinates__dwithin=(user_location.coordinates, D(km=radius)),  # Radius bo‘yicha filterlash
                is_verified=True
            )
            .annotate(distance=Distance("coordinates", user_location.coordinates))  # Masofa hisoblash
            .order_by("distance")  # Masofa bo‘yicha saralash
            .only("id", "title", "image", "locations", "coordinates", "title", "is_active")  # Ortiqcha ma'lumot yuklamaslik
        )
    else:
        shops = Shop.objects.filter(is_verified=True).order_by("order", "-created_at")[:300]  # Limit qo‘shildi

    serializer = ShopMapListSerializer(shops, many=True, context={"request": request})
    return Response(serializer.data)


# Shop detail

@api_view(["GET"])
def shop_detail(request, pk):
    try:
        shop = Shop.objects.get(pk=pk)
        serializer = ShopDetailSerializer(shop, context={"request": request})
        return Response(serializer.data)
    except Shop.DoesNotExist:
        return Response({"error": "Shop not found"}, status=404)
