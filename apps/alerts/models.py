from django.conf import settings
from django.db import models


class AlertRule(models.Model):
    KIND = [
        ("po_critical", "PO critical"),
        ("factory_missed_report", "Factory missed report"),
        ("yarn_late", "Yarn in-house late"),
        ("inspection_failed", "Inspection failed"),
        ("po_at_risk", "PO at risk"),
        ("compliance", "Reporting compliance"),
    ]
    kind = models.CharField(max_length=24, choices=KIND, unique=True)
    enabled = models.BooleanField(default=True)
    threshold = models.JSONField(default=dict)
    default_severity = models.CharField(max_length=10, default="risk")

    def __str__(self):
        return self.kind


class Alert(models.Model):
    kind = models.CharField(max_length=24, db_index=True)
    severity = models.CharField(max_length=10)  # critical/risk/watch/noupdate
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    text = models.CharField(max_length=240)
    purchase_order = models.ForeignKey(
        "orders.PurchaseOrder", null=True, blank=True, on_delete=models.CASCADE
    )
    factory = models.ForeignKey("masterdata.Factory", null=True, blank=True, on_delete=models.CASCADE)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="alerts"
    )
    state = models.CharField(max_length=10, default="open", db_index=True)
    snooze_until = models.DateTimeField(null=True, blank=True)
    run = models.ForeignKey(
        "predictions.PredictionRun", null=True, blank=True, on_delete=models.SET_NULL
    )
    dedupe_key = models.CharField(max_length=80, unique=True)

    class Meta:
        indexes = [models.Index(fields=["state", "severity", "created_at"])]
        ordering = ["-created_at"]
