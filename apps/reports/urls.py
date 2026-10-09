from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.reports_home, name="reports_home"),
    path("shipment-forecast/", views.shipment_forecast, name="shipment_forecast"),
    path("factory-performance/", views.factory_performance, name="factory_performance"),
]
