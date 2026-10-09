from django.contrib import admin

from .models import AuditLog, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_role")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("at", "user", "action", "target", "ip")
    list_filter = ("action",)
    search_fields = ("target",)
    readonly_fields = ("at", "user", "action", "target", "meta", "ip")
