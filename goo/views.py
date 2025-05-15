from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import RetrieveAPIView, UpdateAPIView, CreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status

from goo.models import Contact, Order
from goo.serializers import GooRegistrationSerializer, LocationSerializer, OrderSerializer, LocationUpdateSerializer, \
    LocationActiveSerializer, UserUpdateSerializer, UserSerializer, ContactSerializer, OrderUpdateSerializer, \
    OrderActiveGooSerializer, CancelOrderSerializer
from user.models import Location

from goo.tasks import send_order_to_couriers

User = get_user_model()


class GooRegistrationView(CreateAPIView):
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
def update_order(request, order_id):
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
def cancel_order(request, order_id):
    # URL'ga qarab ro'lni aniqlash
    if 'goo' in request.path:
        canceled_by = 'goo'  # Zakazchi (Customer)
    elif 'pro' in request.path:
        canceled_by = 'pro'  # Kuryer (Courier)
    else:
        return HttpResponseForbidden("Invalid role in URL")  # Noto'g'ri URL

    # Order'ni olish
    order = get_object_or_404(Order, id=order_id)

    # Serializer yordamida reason (izoh)ni olish
    serializer = CancelOrderSerializer(data=request.data)
    if serializer.is_valid():
        reason = serializer.validated_data.get('reason', 'No reason provided')
    else:
        reason = 'No reason provided'

    # Orderni bekor qilish
    try:
        order.cancel(canceled_by=canceled_by, user=request.user, reason=reason)
    except ValueError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

        # Agar kuryer bekor qilgan bo‘lsa, u yana available bo'lishi kerak
    if order.deliver:
        deliver_profile = order.deliver
        deliver_profile.is_busy = False
        deliver_profile.save(update_fields=["is_busy"])

    return JsonResponse({
        'status': 'success',
        'message': f'Order {order.id} has been canceled by {canceled_by}.',
        'canceled_by_user': request.user.id,
        'reason': reason
    })


# ZAKAZCHIK KURYERNI TOPGANDAN KEYIN OTADIGAN BIRINCHI OYNASI
class CustomerOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        order = (
            Order.objects
            .select_related('deliver__user')
            .only(
                'id', 'delivered_at',
                'direction',
                'delivery_duration_min',
                'deliver__user__id',
                'deliver__user__avatar',
                'deliver__user__full_name',
                'deliver__user__phone_number',
                'deliver__user__rating',
            )
            .filter(user=request.user, status="assigned")
            .order_by('-created_at')
            .first()
        )

        if order:
            serializer = OrderActiveGooSerializer(order, context={'request': request})
            return Response(serializer.data)
        else:
            return Response({"detail": "No active order found."}, status=404)
