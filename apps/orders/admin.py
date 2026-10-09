from django.contrib import admin

from .models import Comment, POLine, PurchaseOrder, Style, TAMilestone


@admin.register(Style)
class StyleAdmin(admin.ModelAdmin):
    list_display = ("style_no", "style_name", "department", "gauge", "wash_required")
    search_fields = ("style_no", "style_name")


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("po_no", "style", "factory", "order_qty", "fob_value_usd", "planned_exfactory", "is_open")
    list_filter = ("is_open", "season", "factory")
    search_fields = ("po_no",)


admin.site.register(POLine)
admin.site.register(TAMilestone)
admin.site.register(Comment)
