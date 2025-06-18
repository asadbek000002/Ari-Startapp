from django.shortcuts import render, get_object_or_404
from rest_framework.decorators import permission_classes, api_view
from rest_framework.views import APIView
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from django.contrib.auth import get_user_model
from pro.serializers import DeliverHomeSerializer, DeliverProfileSerializer, \
    OrderActiveProSerializer, CancelProOrderSerializer, CourierCompleteOrderSerializer, AssignedOrderProSerializer, \
    SendProCodeSerializer, VerifyProCodeSerializer
from .models import DeliverProfile
from goo.models import Order
from django.utils import timezone

User = get_user_model()


class SendProVerificationCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SendProCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({"detail": "Kod yuborildi."}, status=200)


class VerifyProCodeLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyProCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        refresh = RefreshToken.for_user(user)

        return Response({
            "access": str(refresh.access_token),
            # "refresh": str(refresh),
        }, status=status.HTTP_200_OK)


# class ProRegistrationView(generics.CreateAPIView):
#     queryset = User.objects.all()
#     serializer_class = ProRegistrationSerializer
#     permission_classes = [AllowAny]
#
#     def create(self, request, *args, **kwargs):
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         worker = serializer.save()
#
#         refresh = RefreshToken.for_user(worker)
#
#         return Response({
#             # "refresh": str(refresh),
#             "access": str(refresh.access_token),
#         }, status=status.HTTP_201_CREATED)


# DELIVERNI HOME PAGEDAGI MALUMOTLARI
class DeliverHomeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            deliver_profile = DeliverProfile.objects.select_related("user").only(
                "id", "deliver_id", "work_active",
                "user__avatar", "user__full_name"
            ).get(user=request.user)
            serializer = DeliverHomeSerializer(deliver_profile, context={"request": request})
            return Response(serializer.data, status=200)
        except DeliverProfile.DoesNotExist:
            return Response({"error": "Deliver profile not found"}, status=404)


# KUREYRNI PROFIL OYNASI
class DeliverProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            deliver_profile = DeliverProfile.objects.select_related("user").only(
                "id", "deliver_id", "balance", "work_start", "work_end",
                "user__avatar", "user__full_name", "user__phone_number"
            ).get(user=request.user)

            serializer = DeliverProfileSerializer(deliver_profile, context={"request": request})
            return Response(serializer.data, status=200)
        except DeliverProfile.DoesNotExist:
            return Response({"error": "Deliver profile not found"}, status=404)


# KURYER ISHGA CHIQGAN VAXTI HOLATINI ACITVE QILA OLADI
class ToggleDeliverActiveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            profile = DeliverProfile.objects.get(user=request.user)
            profile.work_active = not profile.work_active  # holatni teskari qilamiz
            profile.save(update_fields=["work_active"])
            return Response({"work_active": profile.work_active}, status=200)
        except DeliverProfile.DoesNotExist:
            return Response({"error": "Deliver profile not found"}, status=404)


# KURYER ZAKAZNI QABUL QILGANDAN KEYIN OTADIGAN BIRINCHI OYNA
class DeliverOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        order = (
            Order.objects
            .select_related('deliver__user', 'shop')
            .prefetch_related('deliver__deliver_locations', 'user__locations')
            .filter(deliver__user=request.user, id=id, status="assigned", assigned_at__isnull=False)
            .order_by('-assigned_at')
            .only(
                "id", 'delivery_price',
                "assigned_at",
                'direction',
                'delivery_duration_min',
                "user__id",
                "user__avatar",
                "user__full_name",
                "user__phone_number",
                "user__rating",  # Zakaz bergan user maydonlari
                "deliver__user__id",
                'shop__coordinates',  # Faqat filter uchun kerak
            ).first()
        )
        if not order:
            return Response({"detail": "No active order found."}, status=404)

        serializer = OrderActiveProSerializer(order, context={'request': request})
        return Response(serializer.data)


class DeliverActiveOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        order = (
            Order.objects
            .select_related('deliver__user', 'shop')
            .prefetch_related('deliver__deliver_locations', 'user__locations')
            .filter(deliver__user=request.user, status="assigned", assigned_at__isnull=False)
            .order_by('-assigned_at')
            .only(
                "id", 'delivery_price',
                "assigned_at",
                'direction',
                'delivery_duration_min',
                "user__id",
                "user__avatar",
                "user__full_name",
                "user__phone_number",
                "user__rating",  # Zakaz bergan user maydonlari
                "deliver__user__id",
                'shop__coordinates',  # Faqat filter uchun kerak
            ).first()
        )
        if not order:
            return Response({"detail": "No active order found."}, status=404)

        serializer = OrderActiveProSerializer(order, context={'request': request})
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_order_by_courier(request, order_id):
    """
    Kuryerning (pro) buyurtmani bekor qilishi.
    """
    try:
        order = Order.objects.select_related('deliver__user').get(id=order_id, deliver__user=request.user)
    except Order.DoesNotExist:
        return Response({'detail': 'Buyurtma topilmadi yoki sizga biriktirilmagan.'}, status=404)

    serializer = CancelProOrderSerializer(data=request.data)
    if serializer.is_valid():
        reason = serializer.validated_data.get('reason', 'Sababsiz bekor qilindi')
    else:
        reason = 'Sababsiz bekor qilindi'

    if order.status in ['completed', 'canceled']:
        return Response({'detail': 'Bu buyurtma allaqachon yakunlangan yoki bekor qilingan.'}, status=400)

    order.status = 'canceled'
    order.canceled_by = 'pro'
    order.cancel_reason = reason
    order.canceled_by_user = request.user
    order.canceled_at = timezone.now()
    order.save()

    order.deliver.is_busy = False
    order.deliver.save(update_fields=['is_busy'])

    channel_layer = get_channel_layer()
    group_name = f"user_{order.user_id}_goo"
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


# KURYER BORAYOTGAN MANZINI OZGARTRISH UCHUN MISOL UCHUN DOKONGA YETDIM MAHSULOTNI OLDIM
class CourierOrderDirectionUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        new_direction = request.data.get("direction")
        valid_directions = ['arrived_at_store', 'picked_up', 'en_route_to_customer', 'arrived_to_customer',
                            ]

        if new_direction not in valid_directions:
            return Response({"detail": "Invalid direction"}, status=400)

        try:
            order = Order.objects.select_related('deliver__user').get(
                id=order_id,
                deliver__user=request.user,
                status='assigned'  # faqat assigned bo'lgan order
            )
        except Order.DoesNotExist:
            return Response({"detail": "Order not found"}, status=404)

        # Yo'nalish bo'yicha vaqtlar
        if new_direction == 'picked_up':
            order.picked_up_at = timezone.now()
        elif new_direction == 'arrived_to_customer':
            order.deliver.is_busy = False
            order.deliver.save(update_fields=['is_busy'])

        order.direction = new_direction
        order.save()

        # WebSocket orqali order egasiga (goo userga) habar yuborish
        channel_layer = get_channel_layer()
        group_name = f"user_{order.user_id}_goo"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "order_direction_update",
                "order_id": order.id,
                "direction": new_direction
            }
        )
        return Response({"detail": "Direction updated", "direction": order.direction})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_order_by_courier(request, order_id):
    try:
        order = Order.objects.select_related('deliver', 'user').get(id=order_id)
    except Order.DoesNotExist:
        return Response({'detail': 'Buyurtma topilmadi.'}, status=404)

    serializer = CourierCompleteOrderSerializer(data=request.data, context={'request': request, 'order': order})
    if serializer.is_valid():
        serializer.save()
        return Response({'status': 'handed_over'}, status=200)
    return Response(serializer.errors, status=400)


class AssignedOrdersProView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = (
            Order.objects
            .filter(deliver__user=request.user, status="assigned")
            .select_related("shop")
            .only("id", "shop__title", "shop__id", "items", "created_at")
            .order_by("-created_at")
        )

        serializer = AssignedOrderProSerializer(orders, many=True)
        return Response(serializer.data)
