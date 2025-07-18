from django.contrib import admin
from .models import Shop, ShopRole, Sale, Advertising, ShopFeedback
from django import forms

from .tasks import schedule_shop_tasks


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
    list_display = ("title_uz", "title_ru", "role", "is_active", "is_verified")  # Faqat tarjima qilingan maydonlar
    search_fields = ("phone_number", "title_uz", "title_ru")
    list_filter = ("role", "is_verified")
    exclude = ('title', 'locations', 'about')

    def save_model(self, request, obj, form, change):
        # Do‘konni saqlaymiz
        super().save_model(request, obj, form, change)

        # SIGNALS ISHLAMAYDI. TASK FAQAT BIR MARTA ISHLAYDI.
        schedule_shop_tasks.delay(obj.id)


@admin.register(ShopRole)
class ShopRoleAdmin(admin.ModelAdmin):
    list_display = ("name",)
    exclude = ('name',)



@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("shop", "amount", "date")


@admin.register(Advertising)
class AdvertisingAdmin(admin.ModelAdmin):
    list_display = ("title",)
    exclude = ('title', 'text')


admin.site.register(ShopFeedback)