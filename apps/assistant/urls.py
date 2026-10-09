from django.urls import path

from . import views

app_name = "assistant"

urlpatterns = [
    path("", views.assistant_page, name="assistant_page"),
    path("panel/", views.assistant_panel, name="assistant_panel"),
    path("stream/", views.assistant_stream, name="assistant_stream"),
    path("threads/", views.threads_list, name="threads_list"),
    path("export.xlsx", views.assistant_export, name="assistant_export"),
]
