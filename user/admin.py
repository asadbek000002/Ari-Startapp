from django.contrib import admin

from user.models import User, UserRole, VerificationCode, Location

admin.site.register(UserRole)
admin.site.register(VerificationCode)
admin.site.register(Location)


@admin.register(User)
class AllUserAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "full_name", "get_roles")
    search_fields = ("phone_number", "full_name")
    list_filter = ("roles",)

    def get_roles(self, obj):
        return ",  ".join([role.name for role in obj.roles.all()])

    get_roles.short_description = "User Roles"