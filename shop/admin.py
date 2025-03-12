from django.contrib import admin
from .models import Shop, ShopRole, Sale, Advertising
from django import forms


class ShopAdminForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = '__all__'
        widgets = {
            'coordinates': forms.TextInput(attrs={'placeholder': 'Koordinata: (lat, lon)'}),
        }


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    form = ShopAdminForm
    list_display = ("title", "roles", "is_active", "is_verified")
    search_fields = ("phone_number", "title")
    list_filter = ("roles", "is_verified")


@admin.register(ShopRole)
class ShopRoleAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("shop", "amount", "date")


@admin.register(Advertising)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("title",)
