from django.urls import path

from . import views

app_name = "factories"

urlpatterns = [
    path("", views.factory_list, name="factory_list"),
    path("table/", views.factory_table_partial, name="factory_table_partial"),
    path("<str:code>/", views.factory_detail, name="factory_detail"),
    path("<str:code>/output.json", views.factory_output_json, name="factory_output_json"),
    path("<str:code>/notes/", views.factory_note_create, name="factory_note_create"),
]
