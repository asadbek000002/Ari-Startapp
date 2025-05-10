import random
import uuid
from django.db import models
from django.contrib.gis.db import models as gis_models  # GeoDjango uchun
from django.conf import settings


# Kuryer ning malumotlari modeli
class DeliverProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deliver_profile")
    deliver_id = models.CharField(max_length=8, unique=True, editable=False)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
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
