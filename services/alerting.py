"""Alert evaluation (FR-ALERT-010).

Alerts are derived from a completed PredictionRun plus reporting facts: they read the run's
PredictionSnapshot rows and FactoryStat, raised from admin-editable AlertRule records, and deduped
across runs by a stable ``dedupe_key`` so one condition yields one live alert — not a duplicate every
night. No number is invented here; every figure traces to the snapshot / stat it came from.

``evaluate_alerts(run)`` creates the matching Alert rows (idempotent via ``get_or_create`` on the
dedupe key) and returns the count created. ``ensure_alerts(run)`` is the lazy entry point used by the
feed view: it generates the run's alerts only if none exist yet.
"""
from __future__ import annotations

# Rule defaults (admin-editable once seeded). Used to lazily create an AlertRule the first time a kind
# is evaluated, so the engine works on a fresh database before any master-data editing. An admin who
# disables a rule in /admin/ keeps it disabled — get_or_create never overwrites an existing row.
DEFAULT_RULES = {
    # High-signal, actionable alerts are on by default — this is a CEO-grade feed, not a log.
    "po_critical": {"default_severity": "critical", "threshold": {"slip_days": 7}, "enabled": True},
    "factory_missed_report": {"default_severity": "noupdate", "threshold": {}, "enabled": True},
    "inspection_failed": {"default_severity": "critical", "threshold": {}, "enabled": True},
    # Lower-signal rules are off by default (the detail already lives on the PO / factory screens).
    # An admin can enable them in /admin/.
    "po_at_risk": {"default_severity": "risk", "threshold": {}, "enabled": False},
    "yarn_late": {"default_severity": "risk", "threshold": {}, "enabled": False},
    "compliance": {"default_severity": "watch", "threshold": {"missed_wd": 2}, "enabled": False},
}


def _ensure_rules() -> dict:
    from apps.alerts.models import AlertRule

    rules = {}
    for kind, defaults in DEFAULT_RULES.items():
        rule, _ = AlertRule.objects.get_or_create(kind=kind, defaults=defaults)
        rules[kind] = rule
    return rules


def _raise(created_counter, *, kind, rule, dedupe_key, text, run,
           purchase_order=None, factory=None, owner=None) -> int:
    """Create one Alert if its dedupe_key is new. Returns the (possibly incremented) counter."""
    from apps.alerts.models import Alert

    _, created = Alert.objects.get_or_create(
        dedupe_key=dedupe_key,
        defaults={
            "kind": kind,
            "severity": rule.default_severity,
            "text": text[:240],
            "purchase_order": purchase_order,
            "factory": factory,
            "owner": owner,
            "run": run,
        },
    )
    return created_counter + (1 if created else 0)


def evaluate_alerts(run) -> int:
    """Derive Alert rows from the run's snapshots + FactoryStat. Idempotent. Returns count created."""
    if run is None:
        return 0

    from apps.predictions.models import FactoryStat, PredictionSnapshot
    from apps.production.models import Inspection

    rules = _ensure_rules()
    created = 0

    snaps = list(
        PredictionSnapshot.objects.filter(run=run).select_related(
            "purchase_order", "purchase_order__factory", "purchase_order__merchandiser"
        )
    )

    # Latest inspection per PO (for the inspection_failed rule).
    po_ids = [s.purchase_order_id for s in snaps]
    latest_inspection: dict[int, Inspection] = {}
    for insp in (
        Inspection.objects.filter(purchase_order_id__in=po_ids)
        .order_by("purchase_order_id", "-inspection_date", "-id")
    ):
        latest_inspection.setdefault(insp.purchase_order_id, insp)

    # ---- PO-level rules ---------------------------------------------------
    po_critical = rules["po_critical"]
    po_at_risk = rules["po_at_risk"]
    yarn_late = rules["yarn_late"]
    inspection_failed = rules["inspection_failed"]
    crit_slip = int((po_critical.threshold or {}).get("slip_days", 7))

    for s in snaps:
        po = s.purchase_order
        po_no = po.po_no
        owner = po.merchandiser

        # po_critical: band Critical, or slip at/above the threshold.
        if po_critical.enabled and (s.band == "Critical" or s.slip_days >= crit_slip):
            created = _raise(
                created, kind="po_critical", rule=po_critical,
                dedupe_key=f"po_critical:{po_no}:{run.id}",
                text=f"PO {po_no} predicted {s.slip_days} days late (band {s.band}).",
                run=run, purchase_order=po, owner=owner,
            )
        # po_at_risk: band moved to At risk.
        if po_at_risk.enabled and s.band == "At risk":
            created = _raise(
                created, kind="po_at_risk", rule=po_at_risk,
                dedupe_key=f"po_at_risk:{po_no}:{run.id}",
                text=f"PO {po_no} turned at risk (slip {s.slip_days}d).",
                run=run, purchase_order=po, owner=owner,
            )
        # yarn_late: a "Yarn in-house" driver is present on the snapshot.
        if yarn_late.enabled and any(str(d).startswith("Yarn in-house") for d in (s.drivers or [])):
            created = _raise(
                created, kind="yarn_late", rule=yarn_late,
                dedupe_key=f"yarn_late:{po_no}:{run.id}",
                text=f"PO {po_no}: yarn in-house milestone is late.",
                run=run, purchase_order=po, owner=owner,
            )
        # inspection_failed: the PO's latest ship-blocking inspection (pre-final/final) is a Fail.
        # Inline failures are routine mid-production and are left off the executive feed.
        insp = latest_inspection.get(po.id)
        if (inspection_failed.enabled and insp is not None and insp.result == "Fail"
                and insp.inspection_type in ("Pre-final", "Final", "Final re-inspection")):
            created = _raise(
                created, kind="inspection_failed", rule=inspection_failed,
                dedupe_key=f"inspection_failed:{po_no}:{run.id}",
                text=f"PO {po_no}: {insp.inspection_type or 'inspection'} failed "
                     f"({insp.main_defect or 'defects found'}).",
                run=run, purchase_order=po, owner=owner,
            )

    # ---- Factory-level rules ---------------------------------------------
    missed = rules["factory_missed_report"]
    compliance = rules["compliance"]
    comp_missed = int((compliance.threshold or {}).get("missed_wd", 2))

    stats = FactoryStat.objects.filter(run=run).select_related("factory", "factory__merchandiser")
    for fs in stats:
        fac = fs.factory
        code = fac.code
        owner = fac.merchandiser
        # factory_missed_report: the factory has not reported today.
        if missed.enabled and not fs.reported_today:
            created = _raise(
                created, kind="factory_missed_report", rule=missed,
                dedupe_key=f"factory_missed_report:{code}:{run.id}",
                text=f"{fac.name} ({code}) has not reported today.",
                run=run, factory=fac, owner=owner,
            )
        # compliance: reporting compliance below threshold (missed working days).
        if compliance.enabled and fs.missed_wd >= comp_missed:
            created = _raise(
                created, kind="compliance", rule=compliance,
                dedupe_key=f"compliance:{code}:{run.id}",
                text=f"{fac.name} ({code}) reporting compliance low "
                     f"({fs.missed_wd} missed working days).",
                run=run, factory=fac, owner=owner,
            )

    return created


def ensure_alerts(run) -> int:
    """Generate the run's alerts lazily — only if none exist for it yet. Returns count created."""
    if run is None:
        return 0
    from apps.alerts.models import Alert

    if Alert.objects.filter(run=run).exists():
        return 0
    return evaluate_alerts(run)
