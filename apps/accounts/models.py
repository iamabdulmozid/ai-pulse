from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    display_role = models.CharField(max_length=16, blank=True)  # ceo/management/merch/qa/shipping

    def __str__(self):
        return f"{self.user.get_username()} ({self.display_role})"


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    at = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(max_length=40)
    target = models.CharField(max_length=80, blank=True)
    meta = models.JSONField(default=dict)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-at"]
