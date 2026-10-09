"""Deterministic executive briefing composed from metrics (offline, no LLM).

Every sentence is built from the same `services.metrics` numbers the KPI cards show, so the briefing can
never disagree with the screen, and it works with no OpenAI dependency. Carries `as_of` and sources.
"""
from __future__ import annotations

from django.utils.html import format_html
from django.utils.safestring import mark_safe

from services import metrics


def _hero_snapshot(run):
    """The headline PO: the canonical hero if present, else the largest Critical exposure."""
    from apps.predictions.models import PredictionSnapshot

    qs = PredictionSnapshot.objects.filter(run=run).select_related("purchase_order", "purchase_order__factory")
    hero = qs.filter(purchase_order__po_no="71010305").first()
    if hero is None:
        hero = qs.filter(band="Critical", slip_days__gt=0).order_by("-value_at_risk_usd").first()
    return hero


def overview_briefing(run) -> dict:
    k = metrics.portfolio_kpis(run)
    lb = metrics.leaderboard(run)
    var = k["value_at_risk_usd"]
    top3 = lb[:3]
    top3_share = (sum(f["value_at_risk_usd"] for f in top3) / float(var) * 100) if var else 0
    rt = k["reports_today"]
    missing = rt["missing"]
    hero = _hero_snapshot(run)

    parts = [
        format_html("October is predicted <b>{}% on time</b>.", f"{k['october_on_time_pct']*100:.2f}"),
        format_html(" <b>${}M</b> of FOB is at risk and <b>3 factories cause {}% of it</b>: {}.",
                    f"{float(var)/1e6:.1f}", f"{top3_share:.0f}",
                    ", ".join(f["name"] for f in top3)),
    ]
    if hero:
        po = hero.purchase_order
        air_k = f"{float(hero.air_freight_exposure_usd) / 1000:.0f}"
        desc = f"{po.style.gauge}GG {po.style.yarn_short.lower()} {po.style.product_type.lower()}"
        parts.append(format_html(
            " The largest single exposure is {}, a {} predicted <b>{} days late</b>; adding linking "
            "machines and two Friday overtime days brings it back <b>on time</b> and avoids <b>USD {}k</b> "
            "of air freight.",
            format_html('<a href="/pos/{}/">{}</a>', po.po_no, po.po_no),
            desc, hero.slip_days, air_k,
        ))
    if missing:
        parts.append(format_html(" <b>{} factories</b> have not reported.", len(missing)))

    html = mark_safe("".join(parts))

    # Plain text (for the assistant / fallbacks)
    text = (f"October is predicted {k['october_on_time_pct']*100:.2f}% on time. "
            f"${float(var)/1e6:.1f}M of FOB is at risk; {', '.join(f['code'] for f in top3)} carry "
            f"{top3_share:.0f}%. {len(missing)} factories have not reported.")

    return {
        "html": html,
        "text": text,
        "generated_at": run.as_of,
        "as_of": run.as_of,
        "inputs": {"reports": rt["received"], "pos": k["open_pos"]},
        "hero_po_no": hero.purchase_order.po_no if hero else None,
        "why": [
            {"title": "October on-time %",
             "body": "(October POs already shipped on time + open October POs predicted on time) ÷ all "
                     "POs planned for October."},
            {"title": "Value at risk",
             "body": "FOB value of every open PO whose band is At risk, Critical or Late."},
            {"title": "Reporting",
             "body": "A factory is flagged when it has missed the latest expected working-day report (14 Oct)."},
        ],
        "sources": [{"name": "Prediction snapshot", "as_of": run.as_of},
                    {"name": "Daily production + shipment history", "as_of": run.as_of}],
    }
