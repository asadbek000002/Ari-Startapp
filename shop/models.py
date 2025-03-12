from django.db import models
from django.contrib.gis.db import models as gis_models
import os
import uuid
from geopy.geocoders import Nominatim


def image_name(instance, filename):
    ext = filename.split('.')[-1]  # Fayl kengaytmasini olish (jpg, png, ...)
    filename = f"{uuid.uuid4()}.{ext}"  # UUID bilan nomlash

    return os.path.join("users", filename)


class ShopRole(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


# Create your models here.
class Shop(models.Model):
    roles = models.ForeignKey(ShopRole, on_delete=models.SET_NULL, related_name="users", null=True, blank=True)
    image = models.ImageField(upload_to=image_name, blank=True, null=True)
    title = models.CharField(max_length=55, null=True, blank=True)
    phone_number = models.CharField(max_length=13, null=True, blank=True)
    locations = models.CharField(max_length=150, null=True, blank=True)
    # POINT(longitude latitude)
    coordinates = gis_models.PointField(geography=True)  # Majburiy, chunki joy tanlanishi kerak
    about = models.TextField(max_length=2000, null=True, blank=True)
    rating = models.FloatField(default=0, null=True, blank=True)
    work_start = models.TimeField(null=True, blank=True)
    work_end = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)  # Do‘kon faol yoki yo‘qligi
    is_verified = models.BooleanField(default=False)  # Tasdiqlangan yoki yo‘q

    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Shop'
        verbose_name_plural = 'Shops'

    def save(self, *args, **kwargs):
        if self.coordinates and not self.locations:
            geolocator = Nominatim(user_agent="geoapiExercises")
            location = geolocator.reverse((self.coordinates.y, self.coordinates.x), exactly_one=True)
            if location:
                self.locations = location.address
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


# Dokon savdosi haqida atchot
class Sale(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="sales")
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Summasi
    date = models.DateTimeField(auto_now_add=True)  # Qachon bo‘lgani

    def __str__(self):
        return self.shop.name


# Home page reklama modeli
class Advertising(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="advertising")
    image = models.ImageField(upload_to="advertising/", null=True, blank=True)
    title = models.CharField(max_length=50, null=True, blank=True)
    text = models.TextField(max_length=100, null=True, blank=True)
    link = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
