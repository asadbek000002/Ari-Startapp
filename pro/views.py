from django.shortcuts import render, get_object_or_404
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from pro.serializers import ProRegistrationSerializer
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
