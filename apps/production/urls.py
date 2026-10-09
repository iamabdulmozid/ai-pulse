from django.urls import path

from . import views

app_name = "production"

urlpatterns = [
    path("", views.uploads_home, name="uploads_home"),
    path("", views.upload_create, name="upload_create"),  # POST
    path("<uuid:batch_id>/status/", views.batch_status_partial, name="batch_status_partial"),
    path("reporting/", views.reporting_status_partial, name="reporting_status_partial"),
    path("templates/", views.templates_list, name="templates_list"),
]
