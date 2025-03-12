from django.contrib import admin

from .models import DeliverProfile


@admin.register(DeliverProfile)
class DeliverProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "deliver_id", "balance", "work_active")
    search_fields = ("user__phone_number", "deliver_id")
    list_filter = ("work_active",)
