from django.contrib import admin

from .models import Alert, AlertRule


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ("kind", "enabled", "default_severity")


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("kind", "severity", "state", "created_at", "purchase_order", "factory", "owner")
    list_filter = ("kind", "severity", "state")
    search_fields = ("text", "dedupe_key")
