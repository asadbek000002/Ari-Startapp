from django.conf import settings
from django.db import models
from pro.models import DeliverProfile
from shop.models import Shop
from django.utils import timezone


class Product(models.Model):
    """Mahsulot nomlari va foiz variantlarini saqlovchi model"""
    name = models.CharField(max_length=100, unique=True)  # Mahsulot nomi
    variants = models.CharField(max_length=255, blank=True,
                                help_text="Foizlar vergul bilan ajratiladi (masalan: 1%, 1.5%, 2%)")

    def get_variant_list(self):
        """Foizlarni ro‘yxat shaklida qaytarish"""
        return self.percentages.split(", ") if self.percentages else []

    def __str__(self):
        return self.name if self.name else "Noma'lum"


# dokonga zakaz berish
class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("assigned", "Assigned"),
        ("completed", "Completed"),
        ("canceled", "Canceled"),
    ]

    CANCELED_BY_CHOICES = [
        ("goo", "Customer"),  # Go-Order-Owner = Goo
        ("pro", "Courier"),  # Professional = Pro
        ("system", "System"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="orders")
    deliver = models.ForeignKey(DeliverProfile, on_delete=models.SET_NULL, related_name="orders", null=True,
                                blank=True)  # Yetkazib beruvchi
    items = models.TextField()  # Zakaz qilinadigan mahsulotlar
    allow_other_shops = models.BooleanField(default=False)  # Boshqa do‘konlardan olib kelish mumkinmi?
    house_number = models.CharField(max_length=10, null=True, blank=True)
    apartment_number = models.CharField(max_length=10, null=True, blank=True)
    floor = models.IntegerField(null=True, blank=True)
    has_intercom = models.BooleanField(default=False)  # kerak emas
    intercom_code = models.CharField(max_length=20, blank=True, null=True)
    additional_note = models.TextField(max_length=250, blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    canceled_by_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name="canceled_orders")
    canceled_by = models.CharField(max_length=10, choices=CANCELED_BY_CHOICES, null=True, blank=True)
    cancel_reason = models.TextField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    delivery_distance_km = models.FloatField(null=True, blank=True)
    delivery_duration_min = models.FloatField(null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    def cancel(self, canceled_by, user, reason=None):
        if self.status == "canceled":
            raise ValueError("Order is already canceled.")
        self.status = "canceled"
        self.canceled_by = canceled_by  # goo yoki pro
        self.canceled_by_user = user  # actual user instance
        self.cancel_reason = reason
        self.canceled_at = timezone.now()
        self.save()

    def get_items_list(self):
        """Mahsulotlarni ro‘yxatga ajratib qaytaradi"""
        return self.items.split("  ")  # Ikki probel bo‘yicha ajratish

    def __str__(self):
        return f"Order {self.id} - {self.shop.title} - {self.user.phone_number}"


class Contact(models.Model):
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    telegram_link = models.URLField(null=True, blank=True)

    def __str__(self):
        return self.phone_number if self.phone_number else "Noma'lum"
