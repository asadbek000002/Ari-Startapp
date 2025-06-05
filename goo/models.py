import random

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
    DIRECTION_CHOICES = [
        ('en_route_to_store', 'Do‘konga yo‘lda'),
        ('arrived_at_store', 'Do‘konga yetib keldi'),
        ('picked_up', 'Yukni oldi'),
        ('en_route_to_customer', 'Mijozga yo‘lda'),
        ('arrived_to_customer', 'manziliga yetib keldi'),
        ('handed_over', 'Mahsulot topshirildi'),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("searching", "Courier searching"),
        ("assigned", "Assigned"),
        ("completed", "Completed"),
        ("canceled", "Canceled"),
    ]

    CANCELED_BY_CHOICES = [
        ("goo", "Customer"),  # Go-Order-Owner = Goo
        ("pro", "Courier"),  # Professional = Pro
        ("system", "System"),
    ]
    order_code = models.CharField(max_length=30, unique=True, blank=True, null=True)
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
    item_price = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    canceled_by_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name="canceled_orders")

    direction = models.CharField(max_length=30, choices=DIRECTION_CHOICES, default='en_route_to_store')
    canceled_by = models.CharField(max_length=10, choices=CANCELED_BY_CHOICES, null=True, blank=True)
    cancel_reason = models.TextField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    delivery_distance_km = models.FloatField(null=True, blank=True)
    delivery_duration_min = models.FloatField(null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    weather_condition = models.CharField(max_length=255, null=True, blank=True)
    delivery_price = models.PositiveIntegerField(null=True, blank=True)

    picked_up_at = models.DateTimeField(null=True, blank=True)

    def generate_order_code(self):
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        random_digits = random.randint(100, 999)
        return f"AR-{timestamp}-{random_digits}"

    def save(self, *args, **kwargs):
        if not self.order_code:
            for _ in range(5):  # 5 marta urinish
                code = self.generate_order_code()
                if not Order.objects.filter(order_code=code).exists():
                    self.order_code = code
                    break
            else:
                raise ValueError("Takrorlanmas order_code yaratib bo‘lmadi.")
        super().save(*args, **kwargs)

    def get_items_list(self):
        """Mahsulotlarni ro‘yxatga ajratib qaytaradi"""
        return self.items.split("  ")  # Ikki probel bo‘yicha ajratish

    def __str__(self):
        return f"Order {self.id} - {self.shop.title} - {self.user.phone_number}"


class Feedback(models.Model):
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='given_feedbacks'
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_feedbacks'
    )
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='feedbacks')
    rating = models.PositiveSmallIntegerField()  # 1 dan 5 gacha, validatsiya serializerda
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['from_user', 'to_user', 'order']  # Bir odam bir order uchun bir marta feedback bersin


class Contact(models.Model):
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    telegram_link = models.URLField(null=True, blank=True)

    def __str__(self):
        return self.phone_number if self.phone_number else "Noma'lum"
