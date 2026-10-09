import uuid

from django.conf import settings
from django.db import models


class UploadBatch(models.Model):
    KIND = [
        ("order_book", "Order Book"),
        ("ta_calendar", "T&A Calendar"),
        ("daily_production", "Factory Daily Production Report"),
        ("inspection", "Inspection Log"),
        ("factory_master", "Factory Master"),
        ("shipment", "Shipment Log"),
    ]
    STATUS = [("queued", "queued"), ("running", "running"), ("done", "done"), ("error", "error")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=24, choices=KIND, blank=True)
    original_filename = models.CharField(max_length=200)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    detected_factory = models.ForeignKey(
        "masterdata.Factory", null=True, blank=True, on_delete=models.SET_NULL
    )
    detected_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default="queued", db_index=True)
    rows_accepted = models.IntegerField(default=0)
    warnings = models.JSONField(default=list)
    errors = models.JSONField(default=list)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.original_filename} ({self.status})"


class DailyProduction(models.Model):
    STAGES = [
        ("knitting", "Knitting"),
        ("linking", "Linking"),
        ("trimming_mending", "Trimming & Mending"),
        ("washing", "Washing"),
        ("ironing", "Ironing"),
        ("packing", "Packing"),
    ]
    purchase_order = models.ForeignKey(
        "orders.PurchaseOrder", on_delete=models.CASCADE, related_name="daily_production"
    )
    factory = models.ForeignKey("masterdata.Factory", on_delete=models.PROTECT)
    report_date = models.DateField(db_index=True)
    stage = models.CharField(max_length=16, choices=STAGES)
    day_pcs = models.IntegerField(default=0)
    cum_pcs = models.IntegerField(default=0)
    machines = models.PositiveIntegerField(null=True, blank=True)
    remarks = models.CharField(max_length=200, blank=True)
    upload_batch = models.ForeignKey(UploadBatch, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together = [("purchase_order", "stage", "report_date")]
        indexes = [
            models.Index(fields=["purchase_order", "stage", "report_date"]),
            models.Index(fields=["factory", "report_date"]),
        ]


class Inspection(models.Model):
    inspection_id = models.CharField(max_length=20, unique=True)
    inspection_date = models.DateField(db_index=True)
    inspection_type = models.CharField(max_length=24)
    purchase_order = models.ForeignKey(
        "orders.PurchaseOrder", on_delete=models.CASCADE, related_name="inspections"
    )
    factory = models.ForeignKey("masterdata.Factory", on_delete=models.PROTECT, db_index=True)
    inspector = models.CharField(max_length=60)
    lot_qty = models.PositiveIntegerField()
    aql_level = models.CharField(max_length=20)
    sample_size = models.PositiveIntegerField()
    major_accept = models.PositiveIntegerField()
    critical_found = models.PositiveIntegerField(default=0)
    major_found = models.PositiveIntegerField(default=0)
    minor_found = models.PositiveIntegerField(default=0)
    result = models.CharField(max_length=4, db_index=True)  # Pass / Fail
    main_defect = models.CharField(max_length=60, blank=True)
    measurement_check = models.CharField(max_length=4, default="Pass")
    spec_weight_g = models.PositiveIntegerField(null=True, blank=True)
    avg_weight_g = models.PositiveIntegerField(null=True, blank=True)
    remarks = models.CharField(max_length=200, blank=True)
    upload_batch = models.ForeignKey(UploadBatch, null=True, blank=True, on_delete=models.SET_NULL)


class Shipment(models.Model):
    shipment_id = models.CharField(max_length=20, unique=True)
    purchase_order = models.ForeignKey(
        "orders.PurchaseOrder", on_delete=models.CASCADE, related_name="shipments"
    )
    factory = models.ForeignKey("masterdata.Factory", on_delete=models.PROTECT, db_index=True)
    planned_exfactory = models.DateField()
    actual_exfactory = models.DateField(db_index=True)
    shipped_qty = models.PositiveIntegerField()
    cartons = models.PositiveIntegerField(default=0)
    gross_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ship_mode = models.CharField(max_length=8)
    port_of_loading = models.CharField(max_length=40)
    destination = models.CharField(max_length=80)
    etd = models.DateField(null=True, blank=True)
    eta = models.DateField(null=True, blank=True)
    vessel_flight = models.CharField(max_length=60, blank=True)
    invoice_no = models.CharField(max_length=24)
    invoice_value_usd = models.DecimalField(max_digits=14, decimal_places=2)
    air_freight_cost_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    freight_borne_by = models.CharField(max_length=10, default="Karbar")
    shipment_status = models.CharField(max_length=12, default="At port")
    remarks = models.CharField(max_length=200, blank=True)
    upload_batch = models.ForeignKey(UploadBatch, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        indexes = [models.Index(fields=["factory", "actual_exfactory"])]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Presence of a shipment closes the PO (docs/data/data-model.md).
        if self.purchase_order.is_open:
            self.purchase_order.is_open = False
            self.purchase_order.save(update_fields=["is_open"])
