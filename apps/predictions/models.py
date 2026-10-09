from django.db import models


class PredictionRun(models.Model):
    TRIGGER = [("nightly", "nightly"), ("upload", "upload"), ("seed", "seed"), ("manual", "manual")]
    as_of = models.DateTimeField(db_index=True)
    trigger = models.CharField(max_length=12, choices=TRIGGER)
    upload_batch = models.ForeignKey(
        "production.UploadBatch", null=True, blank=True, on_delete=models.SET_NULL
    )
    pos_scored = models.IntegerField(default=0)
    params_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-as_of"]

    def __str__(self):
        return f"run {self.id} @ {self.as_of:%Y-%m-%d} ({self.trigger})"


class PredictionSnapshot(models.Model):
    purchase_order = models.ForeignKey(
        "orders.PurchaseOrder", on_delete=models.CASCADE, related_name="snapshots"
    )
    run = models.ForeignKey(PredictionRun, on_delete=models.CASCADE, related_name="snapshots")
    as_of = models.DateTimeField(db_index=True)
    state = models.CharField(max_length=16)  # In production / Pre-production
    bottleneck_stage = models.CharField(max_length=16, blank=True)
    bottleneck_rate = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True)
    required_rate = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True)
    projected_finish_wd = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    completion_day_n = models.IntegerField(null=True, blank=True)
    available_wd = models.IntegerField(default=0)
    slack_wd = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    projected_exfactory = models.DateField()
    slip_days = models.IntegerField()
    score_schedule = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    score_ta = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    score_otd = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    score_quality = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    score_freshness = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    risk_score = models.PositiveSmallIntegerField(db_index=True)
    band = models.CharField(max_length=10, db_index=True)
    on_time_probability = models.DecimalField(max_digits=4, decimal_places=3)
    value_at_risk_usd = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    air_freight_exposure_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    drivers = models.JSONField(default=list)
    model_version = models.CharField(max_length=12, default="engine-1.0")

    class Meta:
        unique_together = [("purchase_order", "run")]
        indexes = [
            models.Index(fields=["as_of", "band"]),
            models.Index(fields=["run", "band"]),
        ]


class FactoryStat(models.Model):
    run = models.ForeignKey(PredictionRun, on_delete=models.CASCADE, related_name="factory_stats")
    factory = models.ForeignKey("masterdata.Factory", on_delete=models.CASCADE)
    otd_12m = models.DecimalField(max_digits=4, decimal_places=3, default=0)
    aql_pass_90d = models.DecimalField(max_digits=4, decimal_places=3, default=1)
    slip_distribution = models.JSONField(default=list)
    last_report_date = models.DateField(null=True, blank=True)
    reported_today = models.BooleanField(default=False)
    missed_wd = models.PositiveSmallIntegerField(default=0)
    knit_load_pct = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    open_pos = models.IntegerField(default=0)
    open_pcs = models.IntegerField(default=0)
    exposure_usd = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    value_at_risk_usd = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        unique_together = [("run", "factory")]
