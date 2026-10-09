from django.urls import path

from . import views

app_name = "alerts"

urlpatterns = [
    path("", views.alert_list, name="alert_list"),
    path("feed/", views.alert_feed_partial, name="alert_feed_partial"),
    path("<int:pk>/ack/", views.alert_ack, name="alert_ack"),
    path("<int:pk>/assign/", views.alert_assign, name="alert_assign"),
    path("<int:pk>/snooze/", views.alert_snooze, name="alert_snooze"),
]
