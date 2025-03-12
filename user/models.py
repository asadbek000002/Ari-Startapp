import os
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.contrib.gis.db import models as gis_models
from django.conf import settings


class UserRole(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


def image_name(instance, filename):
    ext = filename.split('.')[-1]  # Fayl kengaytmasini olish (jpg, png, ...)
    filename = f"{uuid.uuid4()}.{ext}"  # UUID bilan nomlash

    return os.path.join("users", filename)


class UserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("Telefon raqami kiritilishi shart!")

        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(phone_number, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    roles = models.ManyToManyField(UserRole, related_name="users")
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avatar = models.ImageField(upload_to=image_name, blank=True, null=True)
    phone_number = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=255, null=True, blank=True)
    rating = models.FloatField(default=0, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.phone_number

    def has_role(self, role_name):
        """Berilgan rol foydalanuvchida bor yoki yo‘qligini tekshirish"""
        return self.roles.filter(name=role_name).exists()

    def save(self, *args, **kwargs):
        """Eski faylni o‘chirish"""
        try:
            old_instance = User.objects.get(pk=self.pk)  # Eski obyektni olish
            if old_instance.avatar and old_instance.avatar != self.avatar:
                old_instance.avatar.delete(save=False)  # Eski faylni o‘chirish
        except User.DoesNotExist:
            pass  # Agar foydalanuvchi yangi bo‘lsa, hech narsa qilinmaydi

        super().save(*args, **kwargs)  # Obyektni saqlash


class VerificationCode(models.Model):
    phone_number = models.CharField(max_length=20, unique=True)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)


class Location(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='locations')
    custom_name = models.CharField(max_length=255, blank=True, null=True)  # Foydalanuvchi o‘zi yozishi mumkin
    address = models.CharField(max_length=255, blank=True, null=True)
    coordinates = gis_models.PointField(geography=True)  # Majburiy, chunki joy tanlanishi kerak
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.phone_number} -  {self.address}"
