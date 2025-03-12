from django.contrib import admin
from django.utils.safestring import mark_safe
from .models import Order


class OrderAdmin(admin.ModelAdmin):
    list_display = ("shop", "id", "user", "status", "created_at")


admin.site.register(Order, OrderAdmin)
