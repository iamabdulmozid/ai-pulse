from django.conf import settings
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=16, unique=True)  # Men / Women / Kids

    def __str__(self):
        return self.name


class Season(models.Model):
    code = models.CharField(max_length=8, unique=True)  # AW26, HO26, SS27, SU27
    kind = models.CharField(max_length=2)  # AW/HO/SS/SU
    year = models.SmallIntegerField()

    def __str__(self):
        return self.code


class Factory(models.Model):
    code = models.CharField(max_length=8, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    area = models.CharField(max_length=80)
    district = models.CharField(max_length=40)
    address = models.CharField(max_length=200, blank=True)
    supplier_since = models.DateField(null=True, blank=True)
    gauges = models.CharField(max_length=40)  # "5GG, 7GG, 12GG"
    linking_machines = models.PositiveIntegerField(default=0)
    washing = models.CharField(max_length=12, default="In-house")  # In-house / Subcontract
    knitting_shifts = models.PositiveSmallIntegerField(default=2)
    knitting_hours_day = models.PositiveSmallIntegerField(default=20)
    linking_hours_day = models.PositiveSmallIntegerField(default=10)
    workforce = models.PositiveIntegerField(null=True, blank=True)
    certifications = models.CharField(max_length=200, blank=True)
    bsci_rating = models.CharField(max_length=2, blank=True)
    last_social_audit = models.DateField(null=True, blank=True)
    contact_name = models.CharField(max_length=80, blank=True)
    contact_title = models.CharField(max_length=80, blank=True)
    merchandiser = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_factories"
    )
    status = models.CharField(max_length=10, default="Active")  # Active / Inactive

    class Meta:
        verbose_name_plural = "factories"

    def __str__(self):
        return f"{self.code} — {self.name}"


class FactoryMachine(models.Model):
    factory = models.ForeignKey(Factory, on_delete=models.CASCADE, related_name="machines")
    gauge = models.PositiveSmallIntegerField()  # 3/5/7/12/14
    count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("factory", "gauge")]

    def __str__(self):
        return f"{self.factory.code} {self.gauge}GG×{self.count}"


class HolidayCalendar(models.Model):
    date = models.DateField(unique=True, db_index=True)
    name = models.CharField(max_length=80)

    class Meta:
        verbose_name = "holiday"
        verbose_name_plural = "holiday calendar"

    def __str__(self):
        return f"{self.date} {self.name}"


class EngineParameter(models.Model):
    key = models.CharField(max_length=60, unique=True)
    value = models.DecimalField(max_digits=12, decimal_places=4)
    description = models.CharField(max_length=200, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.key}={self.value}"


class TATemplate(models.Model):
    name = models.CharField(max_length=60, unique=True)

    def __str__(self):
        return self.name


class TAMilestoneDef(models.Model):
    template = models.ForeignKey(TATemplate, on_delete=models.CASCADE, related_name="milestones")
    seq = models.PositiveSmallIntegerField()
    milestone = models.CharField(max_length=40)
    days_before_exfactory = models.PositiveSmallIntegerField()
    responsible = models.CharField(max_length=60)

    class Meta:
        unique_together = [("template", "seq")]
        ordering = ["seq"]

    def __str__(self):
        return f"{self.seq}. {self.milestone} (-{self.days_before_exfactory}d)"
