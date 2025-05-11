from django.shortcuts import render, get_object_or_404
from rest_framework.views import APIView
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from pro.serializers import ProRegistrationSerializer, DeliverHomeSerializer, DeliverProfileSerializer, \
    OrderActiveProSerializer
from .models import DeliverProfile
from goo.models import Order

User = get_user_model()


class ProRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = ProRegistrationSerializer
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


class DeliverOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Zakazchining eng oxirgi "assigned" statusidagi buyurtmasi
        order = Order.objects.filter(user=request.user, status="assigned").order_by('-created_at').first()

        if order:
            serializer = OrderActiveProSerializer(order)
            return Response(serializer.data)
        else:
            return Response({"detail": "No active order found."}, status=404)
