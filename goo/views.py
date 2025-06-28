from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.status import HTTP_200_OK
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import RetrieveAPIView, UpdateAPIView, CreateAPIView, ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from goo.models import Contact, Order
# GooRegistrationSerializer
from goo.serializers import LocationSerializer, OrderSerializer, LocationUpdateSerializer, \
    LocationActiveSerializer, UserUpdateSerializer, UserSerializer, ContactSerializer, OrderUpdateSerializer, \
    OrderActiveGooSerializer, CancelGooOrderSerializer, PendingSearchingAssignedOrderSerializer, \
    RetryUpdateOrderSerializer, \
    OrderDetailSerializer, CompleteOrderSerializer, SendVerificationCodeSerializer, VerifyCodeSerializer, \
    OrderHistorySerializer, OrderHistoryDetailSerializer
from user.models import Location

from goo.tasks import send_order_to_couriers

User = get_user_model()


class SendVerificationCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SendVerificationCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({"detail": "Kod yuborildi."}, status=200)


class VerifyCodeAndLoginView(CreateAPIView):
    serializer_class = VerifyCodeSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            # "refresh": str(refresh)
        }, status=status.HTTP_200_OK)


class LocationCreateView(CreateAPIView):
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


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_location(request, location_id):
    user = request.user
    location = get_object_or_404(Location, id=location_id, user=user)
    location.delete()
    return Response({"status": "success delete"}, status=HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def active_location(request):
    user = request.user
    location = Location.objects.filter(active=True, user=user).order_by(
        "-created_at").first()

    serializer = LocationActiveSerializer(location)
    return Response(serializer.data)


class UserProfileView(RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return User.objects.only('id', 'phone_number', 'full_name', 'avatar', 'rating').get(pk=self.request.user.pk)


class UpdateUserView(UpdateAPIView):
    serializer_class = UserUpdateSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return User.objects.only('id', 'phone_number', 'full_name', 'avatar').get(pk=self.request.user.pk)


class LatestContactView(RetrieveAPIView):
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]  # Agar autentifikatsiya kerak bo'lsa, IsAuthenticated qo'ying

    def get_object(self):
        return Contact.objects.latest('id')  # Eng oxirgi qo‘shilgan ma’lumotni olish


# ORDER YARATADIGAN OYNA
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_order(request, shop_id):
    """Do‘kon ID bo‘yicha zakaz yaratish va pro foydalanuvchilarga yuborish"""
    serializer = OrderSerializer(data=request.data, context={"request": request, "shop_id": shop_id})

    if serializer.is_valid():
        order = serializer.save()

        # Celery taskni chaqirish
        # send_order_to_couriers.delay(order.id, shop_id)

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ORDER MALUMOTLARINI YANIY DOMOFON UY RAQAMLARINI TOLDRADIGAN OYNA
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def address_order(request, order_id):
    """Orderni yangilash (faqat manzil bo‘yicha) va courierlarga yuborish"""
    try:
        order = Order.objects.get(id=order_id, user=request.user, status="pending")
    except Order.DoesNotExist:
        return Response({"detail": "Buyurtma topilmadi yoki uni o‘zgartirish mumkin emas."},
                        status=status.HTTP_404_NOT_FOUND)

    serializer = OrderUpdateSerializer(order, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        # Celery taskni shu yerda chaqiramiz
        send_order_to_couriers.delay(order.id, order.shop.id)
        return Response(OrderSerializer(order).data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ORDER MALUMOTLARINI VA DOMOFON UY RAQAMLARINI TOLDRADIGAN OYNA
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_and_retry_order(request, order_id):
    """Orderni yangilash (faqat manzil bo‘yicha) va courierlarga yuborish"""
    try:
        order = Order.objects.get(id=order_id, user=request.user, status="pending")
    except Order.DoesNotExist:
        return Response({"detail": "Buyurtma topilmadi yoki uni o‘zgartirish mumkin emas."},
                        status=status.HTTP_404_NOT_FOUND)

    serializer = RetryUpdateOrderSerializer(order, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        # Celery taskni shu yerda chaqiramiz
        send_order_to_couriers.delay(order.id, order.shop.id)
        return Response(OrderSerializer(order).data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# KURYER TOPILMAGANDA QAYTA KURYER QIDIRISH OYNASI
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def retry_order_delivery(request, order_id):
    """Buyurtmani qayta courierlarga yuborish"""
    try:
        order = Order.objects.get(id=order_id, user=request.user, status="pending")
    except Order.DoesNotExist:
        return Response({"detail": "Buyurtma topilmadi yoki uni qayta yuborib bo‘lmaydi."},
                        status=status.HTTP_404_NOT_FOUND)

    send_order_to_couriers.delay(order.id, order.shop.id)
    return Response({"detail": "Buyurtma kuryerlarga qayta yuborildi."})


# ORDERNI OTKAZ QILISHI UCHUN CHIQARILGAN OYNA
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_order_by_customer(request, order_id):
    """
    Zakazchini (goo) buyurtmani bekor qilishi.
    """
    # Faqat foydalanuvchi o‘zi bergan zakazni bekor qila oladi
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return Response({'detail': 'Buyurtma topilmadi yoki sizga tegishli emas.'}, status=404)

    # Mahsulot olib ketilgan bo‘lsa — bekor qilib bo‘lmaydi
    if order.direction == 'picked_up':
        return Response({'detail': 'Buyurtma allaqachon olib ketilgan. Endi bekor qilib bo‘lmaydi.'}, status=400)

    if order.status in ['completed', 'canceled']:
        return Response({'detail': 'Bu buyurtma allaqachon yakunlangan yoki bekor qilingan.'}, status=400)

    serializer = CancelGooOrderSerializer(data=request.data)
    if serializer.is_valid():
        reason = serializer.validated_data.get('reason', 'Sababsiz bekor qilindi')
    else:
        reason = 'Sababsiz bekor qilindi'

    order.status = 'canceled'
    order.canceled_by = 'goo'
    order.cancel_reason = reason
    order.canceled_by_user = request.user
    order.canceled_at = timezone.now()
    order.save()
    if order.deliver is not None:
        order.deliver.is_busy = False
        order.deliver.save(update_fields=['is_busy'])

        channel_layer = get_channel_layer()
        group_name = f"user_{order.deliver.user_id}_pro"
        if group_name:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "send_notification",
                    "message": {
                        "type": "order_canceled",
                        "order_id": order.id,
                        "canceled_by": order.canceled_by,
                        "reason": reason,
                    }
                }
            )

    return Response({
        'status': 'success',
        'reason': reason
    }, status=200)


class CustomerOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        order = (
            Order.objects
            .select_related('deliver__user', 'shop')
            .prefetch_related('deliver__deliver_locations', 'user__locations')
            .filter(user=request.user, id=id, status="assigned", assigned_at__isnull=False)
            .order_by('-assigned_at')
            .only(
                'id', 'delivery_price',
                'item_price', 'total_price',
                'assigned_at',
                'direction',
                'delivery_duration_min',
                'deliver__role',
                'deliver__user__id',
                'deliver__user__avatar',
                'deliver__user__full_name',
                'deliver__user__phone_number',
                'deliver__user__rating',
                'shop__title',
                'shop__coordinates',
            )
            .first()
        )

        if not order:
            return Response({"detail": "No active order found."}, status=404)

        serializer = OrderActiveGooSerializer(order, context={'request': request})
        return Response(serializer.data)


class PendingSearchingOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = (
            Order.objects
            .filter(user=request.user, status__in=["pending", "searching"])
            .select_related("shop")
            .only("id", "shop__title", "shop__id", "items", "created_at")
            .order_by("-created_at")
        )

        serializer = PendingSearchingAssignedOrderSerializer(orders, many=True)
        return Response(serializer.data)


class AssignedOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = (
            Order.objects
            .filter(user=request.user, status="assigned")
            .select_related("shop")
            .only("id", "shop__title", "shop__id", "items", "created_at")
            .order_by("-created_at")
        )

        serializer = PendingSearchingAssignedOrderSerializer(orders, many=True)
        return Response(serializer.data)


class OrderDetailView(RetrieveAPIView):
    serializer_class = OrderDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects
            .select_related('user', 'shop')
            .only(
                'id',
                'items',
                'allow_other_shops',
                'house_number',
                'apartment_number',
                'floor',
                'intercom_code',
                'additional_note',
                'shop__id', 'shop__title', 'shop__image',
                'user__id', 'user__phone_number'
            )
            .filter(user=self.request.user,
                    status__in=["pending", "searching", "assigned"])
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_order_by_customer(request, order_id):
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return Response({'detail': 'Buyurtma topilmadi yoki sizga tegishli emas.'}, status=404)

    serializer = CompleteOrderSerializer(data=request.data, context={'request': request, 'order': order})
    if serializer.is_valid():
        serializer.save()
        channel_layer = get_channel_layer()
        group_name = f"user_{order.deliver.user_id}_pro"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "send_notification",  # bu method nomi
                "message": {
                    "event": "order_completed",
                    "order_id": order.id,
                }
            }
        )
        return Response({'status': 'completed'}, status=200)
    return Response(serializer.errors, status=400)


class UserOrderHistoryView(ListAPIView):
    serializer_class = OrderHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user, status='completed', direction='handed_over').order_by('-created_at')



class OrderHistoryDetailView(RetrieveAPIView):
    queryset = Order.objects.select_related('shop', 'location').all()
    serializer_class = OrderHistoryDetailSerializer
    permission_classes = [IsAuthenticated]
