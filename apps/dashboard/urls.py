from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("overview/outlook.json", views.outlook_json, name="outlook_json"),
    path("overview/heatmap.json", views.heatmap_json, name="heatmap_json"),
]
