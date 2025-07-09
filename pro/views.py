from django.shortcuts import render, get_object_or_404
from rest_framework.decorators import permission_classes, api_view
from rest_framework.generics import ListAPIView, RetrieveAPIView
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
    SendProCodeSerializer, VerifyProCodeSerializer, CheckSerializer, OrderHistoryProSerializer, \
    OrderHistoryProDetailSerializer, OrderProDetailSerializer
from .models import DeliverProfile
from goo.models import Order, Check
from django.utils import timezone
from datetime import datetime, timedelta, time
from django.utils.timezone import now, make_aware
from django.db.models import Sum
from pyzbar.pyzbar import decode
from PIL import Image

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


from bs4 import BeautifulSoup
import requests
from decimal import Decimal


class UploadCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        qr_url = request.data.get("qr_url")  # Endi URL to‘g‘ridan-to‘g‘ri kelyapti
        order = request.data.get("order")
        image = request.FILES.get("image")  # Agar sizda rasm ham kelsa saqlab qolamiz

        if not qr_url or not order:
            return Response(
                {"detail": "QR URL va order ID kerak."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # HTML sahifani olish
            response = requests.get(qr_url, timeout=1.5)
            if response.status_code != 200:
                return Response(
                    {"detail": "QR URL orqali sahifa topilmadi."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            soup = BeautifulSoup(response.text, "html.parser")
            total_label = soup.find("td", string=lambda s: s and "Jami to`lov:" in s)
            if total_label and total_label.find_next_sibling("td"):
                price_tag = total_label.find_next_sibling("td")
            else:
                return Response(
                    {"detail": "Yakuniy to‘lov (chegirmadan keyin) topilmadi."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not price_tag:
                return Response(
                    {"detail": "Narx topilmadi."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            raw_price = price_tag.text.strip().replace(",", "")
            try:
                price = Decimal(raw_price)
            except Exception:
                return Response(
                    {"detail": f"Narxni Decimal ga aylantirib bo‘lmadi: '{raw_price}'"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Orderni yangilash
            try:
                order = Order.objects.get(id=order)
            except Order.DoesNotExist:
                return Response(
                    {"detail": "Order topilmadi."},
                    status=status.HTTP_404_NOT_FOUND
                )

            order.item_price = price
            order.total_price = price + order.delivery_price
            order.save()

            # Check yaratish
            check = Check.objects.create(
                order=order,
                image=image,
                qr_url=qr_url
            )
            channel_layer = get_channel_layer()
            group_name = f"user_{order.user_id}_goo"

            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "send_notification",
                    "message": {
                        "type": "order_price",
                        "order_id": order.id,
                        "delivery_price": str(order.delivery_price),
                        "item_price": str(order.item_price),
                        "total_price": str(order.total_price)
                    }
                }
            )

            serializer = CheckSerializer(check, context={"request": request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"detail": f"Ichki xatolik: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UploadManualCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        image_file = request.FILES.get("image")
        order_id = request.data.get("order")
        price = request.data.get("price")

        if not image_file or not order_id or not price:
            return Response({"detail": "Image, order ID va narx kerak."}, status=400)

        try:
            order = Order.objects.get(id=order_id)

            try:
                # Narxdan vergul va probellarni tozalab float ga aylantiramiz
                cleaned_price = str(price).replace(",", "").strip()
                order.item_price = Decimal(cleaned_price)
                order.total_price = Decimal(cleaned_price) + order.delivery_price
                order.save()
            except ValueError:
                return Response({"detail": f"Narx noto‘g‘ri formatda: '{price}'"}, status=400)

            # QRsiz check yoziladi
            check = Check.objects.create(
                order=order,
                image=image_file,
                qr_url=None  # QR kodi yo‘q
            )

            channel_layer = get_channel_layer()
            group_name = f"user_{order.user_id}_goo"

            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "send_notification",
                    "message": {
                        "type": "order_price",
                        "order_id": order.id,
                        "delivery_price": str(order.delivery_price),
                        "item_price": str(order.item_price),
                        "total_price": str(order.total_price)
                    }
                }
            )

            serializer = CheckSerializer(check, context={"request": request})
            return Response(serializer.data, status=201)

        except Order.DoesNotExist:
            return Response({"detail": "Order topilmadi."}, status=404)
        except Exception as e:
            return Response({"detail": f"Xatolik: {str(e)}"}, status=500)


class ProOrderHistoryView(ListAPIView):
    serializer_class = OrderHistoryProSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            deliver_profile = DeliverProfile.objects.get(user=self.request.user)
        except DeliverProfile.DoesNotExist:
            return Order.objects.none()  # Hech nima qaytmaydi
        return Order.objects.filter(deliver=deliver_profile, status='completed').order_by('-created_at')


class OrderHistoryProDetailView(RetrieveAPIView):
    queryset = Order.objects.select_related('shop').all()
    serializer_class = OrderHistoryProDetailSerializer
    permission_classes = [IsAuthenticated]


def get_last_sunday_noon():
    today = now().date()
    # Yakshanba haftaning 6-kuni bo‘ladi (0 = Dushanba, 6 = Yakshanba)
    days_since_sunday = (today.weekday() + 1) % 7  # Yakshanba uchun 0
    last_sunday = today - timedelta(days=days_since_sunday)
    last_sunday_noon = make_aware(datetime.combine(last_sunday, time(hour=12)))
    return last_sunday_noon


class WeeklyEarningsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            profile = DeliverProfile.objects.get(user=request.user)
        except DeliverProfile.DoesNotExist:
            return Response({"detail": "DeliverProfile not found."}, status=404)

        from_time = get_last_sunday_noon()

        orders = Order.objects.filter(
            deliver=profile,
            status="completed",
            delivered_at__gte=from_time
        )

        totals = orders.aggregate(
            total_price_sum=Sum("total_price"),
            delivery_price_sum=Sum("delivery_price")
        )

        return Response({
            "since": from_time.isoformat(),
            "total_price": totals["total_price_sum"] or 0,
            "delivery_price": totals["delivery_price_sum"] or 0
        })


class OrderProDetailView(RetrieveAPIView):
    serializer_class = OrderProDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return (
            Order.objects
            .select_related('shop')
            .filter(deliver__user=self.request.user,
                    status__in=["pending", "searching", "assigned"])
        )
