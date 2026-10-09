from django.conf import settings
from django.db import models
from django.db.models import Q


class Style(models.Model):
    style_no = models.CharField(max_length=24, unique=True, db_index=True)
    style_name = models.CharField(max_length=120)
    product_type = models.CharField(max_length=60)
    department = models.ForeignKey("masterdata.Department", on_delete=models.PROTECT)
    gauge = models.PositiveSmallIntegerField()
    yarn_composition = models.CharField(max_length=80)
    yarn_short = models.CharField(max_length=40)
    wash_required = models.BooleanField(default=False)
    weight_kg_pc = models.DecimalField(max_digits=5, decimal_places=3)
    knitting_minutes_pc = models.DecimalField(max_digits=6, decimal_places=2)
    linking_std_pcs_mc_day = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.style_no} {self.style_name}"


class PurchaseOrder(models.Model):
    po_no = models.CharField(max_length=12, unique=True, db_index=True)
    po_date = models.DateField()
    season = models.ForeignKey("masterdata.Season", on_delete=models.PROTECT)
    style = models.ForeignKey(Style, on_delete=models.PROTECT, related_name="purchase_orders")
    factory = models.ForeignKey("masterdata.Factory", on_delete=models.PROTECT, related_name="purchase_orders")
    merchandiser = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_pos"
    )
    order_qty = models.PositiveIntegerField()
    fob_usd_pc = models.DecimalField(max_digits=8, decimal_places=2)
    fob_value_usd = models.DecimalField(max_digits=14, decimal_places=2)
    planned_exfactory = models.DateField(db_index=True)
    planned_ship_mode = models.CharField(max_length=8, default="Sea")
    port_of_loading = models.CharField(max_length=40, default="Chattogram")
    destination = models.CharField(max_length=80)
    delivery_terms = models.CharField(max_length=40, default="FOB Chattogram")
    is_open = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["factory", "planned_exfactory"]),
            models.Index(fields=["is_open", "planned_exfactory"]),
        ]

    def __str__(self):
        return self.po_no


class POLine(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    colour = models.CharField(max_length=40)
    colour_code = models.CharField(max_length=16)
    line_qty = models.PositiveIntegerField()

    class Meta:
        unique_together = [("purchase_order", "colour_code")]

    def __str__(self):
        return f"{self.purchase_order_id} {self.colour}"


class POLineSize(models.Model):
    po_line = models.ForeignKey(POLine, on_delete=models.CASCADE, related_name="sizes")
    size = models.CharField(max_length=8)
    qty = models.PositiveIntegerField()

    class Meta:
        unique_together = [("po_line", "size")]


class TAMilestone(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="ta_milestones")
    factory = models.ForeignKey("masterdata.Factory", on_delete=models.PROTECT)
    seq = models.PositiveSmallIntegerField()
    milestone = models.CharField(max_length=40)
    responsible = models.CharField(max_length=60)
    planned_date = models.DateField()
    revised_date = models.DateField(null=True, blank=True)
    actual_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, default="Pending")
    remarks = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = [("purchase_order", "seq")]
        indexes = [models.Index(fields=["purchase_order", "seq"])]
        ordering = ["seq"]

    def __str__(self):
        return f"{self.purchase_order_id} {self.milestone}"


class Comment(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder, null=True, blank=True, on_delete=models.CASCADE, related_name="comments", db_index=True
    )
    factory = models.ForeignKey(
        "masterdata.Factory", null=True, blank=True, on_delete=models.CASCADE, related_name="notes", db_index=True
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    text = models.TextField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="comment_exactly_one_target",
                condition=(
                    (Q(purchase_order__isnull=False) & Q(factory__isnull=True))
                    | (Q(purchase_order__isnull=True) & Q(factory__isnull=False))
                ),
            )
        ]
        ordering = ["-created_at"]
