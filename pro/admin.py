from django.contrib import admin

from .models import DeliverProfile, DeliverLocation
from django import forms

@admin.register(DeliverProfile)
class DeliverProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "deliver_id", "balance", "work_active")
    search_fields = ("user__phone_number", "deliver_id")
    list_filter = ("work_active",)

class DeliverAdminForm(forms.ModelForm):
    class Meta:
        model = DeliverLocation
        fields = '__all__'
        widgets = {
            'coordinates': forms.TextInput(attrs={'placeholder': 'Koordinata: (lat, lon)'}),
        }


@admin.register(DeliverLocation)
class DeliverLocationAdmin(admin.ModelAdmin):
    form = DeliverAdminForm
    list_display = ("deliver", "id")
