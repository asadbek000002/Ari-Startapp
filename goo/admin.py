from django.contrib import admin
from django.utils.safestring import mark_safe
from .models import Order, Contact


class OrderAdmin(admin.ModelAdmin):
    list_display = ("shop", "id", "user", "status", "created_at")

class ContactAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "id")


admin.site.register(Order, OrderAdmin)
admin.site.register(Contact, ContactAdmin)
