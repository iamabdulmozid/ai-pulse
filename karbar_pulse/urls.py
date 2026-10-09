from django.contrib import admin
from django.urls import include, path

from apps.dashboard import views as dashboard_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", dashboard_views.health, name="healthz"),
    path("", include("apps.dashboard.urls")),
    path("", include("apps.accounts.urls")),
    path("pos/", include("apps.orders.urls")),
    path("factories/", include("apps.factories.urls")),
    path("uploads/", include("apps.production.urls")),
    path("alerts/", include("apps.alerts.urls")),
    path("reports/", include("apps.reports.urls")),
    path("assistant/", include("apps.assistant.urls")),
]
