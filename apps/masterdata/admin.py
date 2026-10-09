from django.contrib import admin

from .models import (
    Department,
    EngineParameter,
    Factory,
    FactoryMachine,
    HolidayCalendar,
    Season,
    TAMilestoneDef,
    TATemplate,
)


class FactoryMachineInline(admin.TabularInline):
    model = FactoryMachine
    extra = 0


@admin.register(Factory)
class FactoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "district", "gauges", "linking_machines", "status", "merchandiser")
    list_filter = ("district", "status", "washing")
    search_fields = ("code", "name")
    inlines = [FactoryMachineInline]


@admin.register(EngineParameter)
class EngineParameterAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "description", "updated_at")
    search_fields = ("key",)


class TAMilestoneDefInline(admin.TabularInline):
    model = TAMilestoneDef
    extra = 0


@admin.register(TATemplate)
class TATemplateAdmin(admin.ModelAdmin):
    list_display = ("name",)
    inlines = [TAMilestoneDefInline]


@admin.register(HolidayCalendar)
class HolidayCalendarAdmin(admin.ModelAdmin):
    list_display = ("date", "name")
    ordering = ("date",)


admin.site.register(Department)
admin.site.register(Season)

admin.site.site_header = "AI Pulse administration"
admin.site.site_title = "AI Pulse"
admin.site.index_title = "Master data & settings"
