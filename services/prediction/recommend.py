"""Recommendation rules (docs/ai/prediction-engine.md §7).

Read-side service: builds a single PO context from the ORM, then uses the pure what-if engine to find the
cheapest fix and names a donor PO for machine reallocation. Options carry a predicted date and a cost.
"""
from __future__ import annotations

from datetime import date

# Candidate Friday overtime days after DEMO_TODAY (the demo uses 16 & 23 Oct).
OVERTIME_FRIDAYS = [date(2026, 10, 16), date(2026, 10, 23), date(2026, 10, 30)]
MAX_MACHINES_ADD = 12


def recommend(po_no: str, run, today: date | None = None) -> list[dict]:
    from django.conf import settings

    from services.prediction.run import _load_params, build_po_context
    from services.prediction.whatif import simulate

    today = today or settings.DEMO_TODAY
    params = _load_params()
    ctx = build_po_context(po_no, today)
    if ctx is None:
        return []
    base = simulate(ctx, params, today)
    if base["slip_days"] <= 0:
        return []  # already on time

    options: list[dict] = []
    current = ctx.link_machines_current or 0

    # 1. Combined cheapest fix: fewest machines, then fewest Fridays, that lands on time.
    best = None
    for add in range(0, MAX_MACHINES_ADD + 1):
        for nf in range(0, len(OVERTIME_FRIDAYS) + 1):
            mc = current + add if current else None
            ot = frozenset(OVERTIME_FRIDAYS[:nf])
            sim = simulate(ctx, params, today, link_machines=mc, overtime_days=ot)
            if sim["on_time"]:
                best = (add, nf, sim)
                break
        if best:
            break

    donor = _find_donor(ctx, run, po_no)
    if best and (best[0] or best[1]):
        add, nf, sim = best
        bits = []
        if add:
            d = f" from {donor}" if donor else ""
            bits.append(f"move {add} linking machines ({current}→{current + add}){d}")
        if nf:
            fr = ", ".join(d.strftime("%d %b") for d in OVERTIME_FRIDAYS[:nf])
            bits.append(f"{nf} Friday overtime day{'s' if nf > 1 else ''} ({fr})")
        options.append({
            "title": "Recover to on time",
            "body": "To hit ex-factory, " + " and ".join(bits) + ".",
            "impact_days": base["slip_days"], "projected_exfactory": sim["projected_exfactory"],
            "cost_usd": 0.0, "cost_note": f"Avoids {sim['air_freight_avoided_usd']:,.0f} USD air freight",
            "action": {"link_machines": (current + add) if (add and current) else current,
                       "overtime_days": [d.isoformat() for d in OVERTIME_FRIDAYS[:nf]]},
        })

    # 2. Air-freight baseline (do nothing but fly it).
    air = round(ctx.order_qty * ctx.weight_kg_pc * (params.air_usd_per_kg - params.sea_usd_per_kg), 2)
    options.append({
        "title": "Air freight the shortfall",
        "body": "Keep the current plan and fly to hold the delivery date.",
        "impact_days": 0, "projected_exfactory": None, "cost_usd": air,
        "cost_note": "Extra freight vs sea", "action": None,
    })
    return options


def _find_donor(ctx, run, po_no: str) -> str | None:
    """A PO at the same factory and gauge with the most slack (earliest finish) to lend machines."""
    from apps.predictions.models import PredictionSnapshot

    po = PredictionSnapshot.objects.select_related("purchase_order__factory", "purchase_order__style").get(
        run=run, purchase_order__po_no=po_no
    ).purchase_order
    cand = (
        PredictionSnapshot.objects.filter(
            run=run, purchase_order__factory=po.factory, purchase_order__style__gauge=po.style.gauge,
            slip_days__lt=0,
        )
        .exclude(purchase_order__po_no=po_no)
        .order_by("slip_days")
        .select_related("purchase_order")
        .first()
    )
    return cand.purchase_order.po_no if cand else None
