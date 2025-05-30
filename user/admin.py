from django.contrib import admin
from django import forms

from user.models import User, UserRole, VerificationCode, Location

admin.site.register(UserRole)
admin.site.register(VerificationCode)
# admin.site.register(Location)


@admin.register(User)
class AllUserAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "full_name", "get_roles")
    search_fields = ("phone_number", "full_name")
    list_filter = ("roles",)

    def get_roles(self, obj):
        return ",  ".join([role.name for role in obj.roles.all()])

    get_roles.short_description = "User Roles"


class LocationAdminForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = '__all__'
        widgets = {
            'coordinates': forms.TextInput(attrs={'placeholder': 'Koordinata: (lat, lon)'}),
        }


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    form = LocationAdminForm
    list_display = ("user", "id")
