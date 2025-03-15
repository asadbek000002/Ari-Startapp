from django.shortcuts import render, get_object_or_404
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from goo.serializers import GooRegistrationSerializer, LocationSerializer, OrderSerializer, LocationUpdateSerializer
from shop.models import Shop
from user.models import Location

User = get_user_model()


class GooRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = GooRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        worker = serializer.save()

        refresh = RefreshToken.for_user(worker)

        return Response({
            # "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)


class LocationCreateView(generics.CreateAPIView):
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_locations(request):
    user = request.user
    locations = Location.objects.filter(user=user)
    locations = locations.order_by('-active', '-created_at')
    serializer = LocationSerializer(locations, many=True)

    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_location(request, location_id):
    user = request.user
    location = get_object_or_404(Location, id=location_id, user=user)

    serializer = LocationUpdateSerializer(location, data=request.data, partial=True)  # Qisman yangilash
    serializer.is_valid(raise_exception=True)
    serializer.save()

    return Response({
        "message": "Location yangilandi va active qilindi",
        "updated_location": serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detail_location(request, location_id):
    user = request.user
    location = get_object_or_404(Location, id=location_id, user=user)

    serializer = LocationUpdateSerializer(location)
    return Response(serializer.data)


# goo da zakazchik zakaz berish uchun mahsulatlarga

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_order(request, shop_id):
    """Do‘kon ID bo‘yicha zakaz yaratish"""
    serializer = OrderSerializer(data=request.data,
                                 context={"request": request, "shop_id": shop_id})  # shop_id'ni qo‘shdik

    if serializer.is_valid():
        order = serializer.save()
        return Response(OrderSerializer(order, context={"request": request}).data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
