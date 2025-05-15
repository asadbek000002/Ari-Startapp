import random
import uuid
from django.db import models
from django.contrib.gis.db import models as gis_models  # GeoDjango uchun
from django.conf import settings


# Kuryer ning malumotlari modeli
class DeliverProfile(models.Model):
    ROLE_CHOICES = [
        ('foot', 'Foot'),  # Piyoda
        ('bike', 'Bike'),  # Velosiped
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deliver_profile")
    deliver_id = models.CharField(max_length=8, unique=True, editable=False)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    role = models.CharField(max_length=4, choices=ROLE_CHOICES, default='foot')
    work_start = models.TimeField(null=True, blank=True)
    work_end = models.TimeField(null=True, blank=True)
    work_active = models.BooleanField(default=False)
    is_busy = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Deliver Profile'
        verbose_name_plural = 'Deliver Profiles'

    def save(self, *args, **kwargs):
        if not self.deliver_id:
            self.deliver_id = self.generate_unique_id()
        super().save(*args, **kwargs)

    def generate_unique_id(self):
        while True:
            new_id = str(f"A-{random.randint(10000, 99999)}")
            if not DeliverProfile.objects.filter(deliver_id=new_id).exists():
                return new_id

    def __str__(self):
        return f"{self.user.phone_number} | {self.deliver_id}"


# kuryer ning harakati uchun location
class DeliverLocation(models.Model):
    deliver = models.ForeignKey(DeliverProfile, on_delete=models.CASCADE, related_name='deliver_locations')
    # POINT(longitude latitude)
    coordinates = gis_models.PointField(geography=True, srid=4326)  # Doimiy o‘zgarib turadigan location
    updated_at = models.DateTimeField(auto_now=True)  # Har safar yangilanadi

    def __str__(self):
        return f"Courier {self.deliver.user.phone_number} - {self.coordinates}"


class WeatherData(models.Model):
    city = models.CharField(max_length=100)
    temperature = models.FloatField()
    condition = models.CharField(max_length=50)  # Masalan: 'Rain', 'Clear'
    wind_speed = models.FloatField()
    humidity = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.city} - {self.condition} @ {self.timestamp}"


class DeliveryPricePolicy(models.Model):
    TRANSPORT_CHOICES = [
        ('foot', 'Piyoda'),
        ('bike', 'Velosiped'),
    ]
    transport_type = models.CharField(max_length=10, choices=TRANSPORT_CHOICES)
    min_distance = models.DecimalField(max_digits=5, decimal_places=2)  # km
    max_distance = models.DecimalField(max_digits=5, decimal_places=2)  # km

    base_price = models.PositiveIntegerField(help_text="Minimal narx (so'mda)")
    price_per_km = models.PositiveIntegerField(help_text="1 km uchun narx (so'mda)")

    # Ob-havo koeffitsiyentlari
    rain_multiplier = models.FloatField(default=1.3)
    snow_multiplier = models.FloatField(default=1.3)
    thunderstorm_multiplier = models.FloatField(default=1.3)
    drizzle_multiplier = models.FloatField(default=1.1)
    clouds_multiplier = models.FloatField(default=1.1)
    clear_multiplier = models.FloatField(default=1.0)

    def __str__(self):
        return f"{self.transport_type.upper()} | {self.min_distance}-{self.max_distance} km"
