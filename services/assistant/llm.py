"""Claude tool-calling path for the assistant (docs/ai/assistant.md).

The model chooses tools and phrases the answer; every NUMBER still comes from the tools (which call the
same services.* functions the screens use). No free-form SQL. On any error, refusal or time-out the caller
falls back to the deterministic router, so the demo never depends on the network.
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from services import metrics
from services.assistant import tools as toolmod

MAX_ROUNDS = 6
MAX_HISTORY_TURNS = 10
TOTAL_BUDGET_S = 40  # whole answer; past this the caller falls back to the deterministic router

SYSTEM = (
    "You are the AI Pulse assistant for Karbar Sourcing Bangladesh, a sweater sourcing office that places "
    "knitwear orders with Bangladeshi factories. Users are merchandisers, QA and management.\n\n"
    "HOW TO ANSWER\n"
    "1. Business data (orders, POs, factories, on-time, value at risk, AQL pass rates, reporting, "
    "shipments, inspections, T&A, alerts): call tools. Every number about the business MUST come from a "
    "tool result — never invent, estimate or round differently. Mention the snapshot 'as of' time given "
    "below.\n"
    "2. Concepts and industry terms (e.g. AQL, ex-factory, FOB, OTD, gauge, linking, pre-final "
    "inspection, air freight vs sea): explain them from your own garment/sourcing knowledge. When "
    "relevant, also pull the matching data — e.g. 'What is the AQL pass of a factory?' → explain AQL "
    "pass rate briefly AND, in the same answer, call list_factory_scorecards and summarise the factories' "
    "AQL pass % (weakest first). Don't just offer to fetch data you can fetch now.\n"
    "3. Ambiguous questions: if a question could mean several things or is missing something you need "
    "(which factory, which PO, which month) and a sensible default does not exist, ask ONE short "
    "clarifying question, offering concrete options (e.g. factory codes from the tools). If there is a "
    "sensible default (e.g. show all factories), answer with it and offer to narrow down.\n"
    "4. Time ('today', 'this week', 'this month', 'last month' are given below). Past periods are about "
    "what actually shipped (get_shipped_summary, by month or date range); open orders and predictions are "
    "about what is still to ship (search_pos with an ex-factory window, get_shipment_outlook). For a vague "
    "'how was last month / last month status', summarise the shipped actuals: shipments, pcs, value, "
    "on-time %, worst factories and late shipments. 'What changed / since last week / since the last "
    "update' → get_changes_since_last_run.\n"
    "5. Use the conversation history: a short reply like 'GRL' or 'the second one' answers your previous "
    "question.\n"
    "6. POs: use get_po_details for a PO's quantity, FOB, order value or shipment facts — it works for "
    "shipped POs too. If a PO was named earlier in the conversation, use it instead of asking again. "
    "Prediction / what-if / recommendation tools only cover OPEN POs. Penalties, fines, late charges, "
    "deductions or claims: call calculate_late_penalty with the user's rate (if the rate or whether it is "
    "per day/week/flat is unclear, ask once). Show the formula and the base it was applied to. If the "
    "user gave no cap, compute uncapped and mention that penalty clauses are often capped.\n"
    "7. Only say you don't have something when it is genuinely outside the data AND outside general "
    "sourcing knowledge (e.g. revenue/margin, weather). Then say what you can help with instead.\n\n"
    "DATA NOTES: Purchase orders are 8-digit numbers like 71010305. Factories are identified by 3-letter "
    "codes (GRL, IRB, SLM…). AQL pass % is the share of the factory's inspections passed in the last 90 "
    "days; OTD % is 12-month on-time delivery. Bands, best to worst: On track, Watch, At risk, Critical, "
    "Late. The Bangladesh work week is Saturday to Thursday; Friday is off.\n\n"
    "STYLE: Concise plain English — a few sentences or a short list. Bold key numbers with **…**. "
    "Write dates like '7 Nov 2026', never raw ISO timestamps. "
    "Do not use markdown tables or headings; the UI renders a table from the tool data for you."
)

_PO = {"po_no": {"type": "string", "description": "8-digit PO number, e.g. 71010305"}}
_DATE = {"type": "string", "description": "ISO date YYYY-MM-DD"}


def _tool(name: str, description: str, properties: dict | None = None, required: list | None = None) -> dict:
    schema = {"type": "object", "properties": properties or {}}
    if required:
        schema["required"] = required
    return {"name": name, "description": description, "input_schema": schema}


TOOLS = [
    _tool("get_portfolio_kpis", "Headline numbers: open POs, pcs, FOB value, October on-time %, value at risk, "
          "air-freight exposure, at-risk PO count and today's factory reporting state."),
    _tool("get_october_ontime", "October predicted on-time percentage."),
    _tool("get_value_at_risk", "Total value at risk (USD) and the breakdown by factory with shares."),
    _tool("list_factories_missing_report", "Factories that have not sent the latest expected daily report."),
    _tool("get_changes_since_last_run", "What changed since the previous prediction run: KPI before/now, "
          "POs shipped since, POs that got worse or better (band and slip).", {}),
    _tool("search_pos", "Search OPEN POs with any filters (all bands unless band is given) and get count, pcs, "
          "FOB and the rows. Use for upcoming ex-factories (exf_from/exf_to window), a factory's, department's "
          "or merchandiser's orders, critical/late lists, or style search.", {
              "factory": {"type": "string", "description": "Factory code, e.g. GRL"},
              "dept": {"type": "string", "description": "Department name"},
              "merchandiser": {"type": "string", "description": "Merchandiser name or part of it"},
              "band": {"type": "array", "items": {"type": "string",
                       "enum": ["On track", "Watch", "At risk", "Critical", "Late"]}},
              "exf_from": _DATE, "exf_to": _DATE,
              "exf_month": {"type": "string", "description": "Planned ex-factory month YYYY-MM"},
              "text": {"type": "string", "description": "Search PO number, style number or style name"},
              "sort": {"type": "string", "enum": ["risk", "slip", "exf", "fob"]},
              "limit": {"type": "integer"}}),
    _tool("list_at_risk_pos", "List at-risk POs (At risk / Critical / Late), optionally by factory code, "
          "department, band, or ex-factory month (YYYY-MM).", {
              "factory": {"type": "string"}, "dept": {"type": "string"},
              "band": {"type": "array", "items": {"type": "string"}},
              "exf_month": {"type": "array", "items": {"type": "string"}},
              "limit": {"type": "integer"}}),
    _tool("get_po_prediction", "Prediction for one OPEN PO: band, projected ex-factory, slip, probability, drivers.",
          _PO, ["po_no"]),
    _tool("get_po_details", "Order + delivery record for ANY PO, open or already shipped: status, factory, style, "
          "order qty, FOB per pc, order value (USD), planned ex-factory, shipments (actual ex-factory, days late, "
          "shipped qty, invoice value, air freight), latest inspection, and the prediction if still open. Use for "
          "any question about a PO's value, quantity or shipment, and always for shipped POs.", _PO, ["po_no"]),
    _tool("calculate_late_penalty", "Late-delivery fine/penalty/charge/deduction for a PO, computed exactly. Days "
          "late come from the shipment (actual vs planned ex-factory) or, for an open PO, the projected slip. "
          "ALWAYS use this for penalty maths — never multiply yourself.", {
              **_PO,
              "rate_pct": {"type": "number", "description": "Penalty rate in percent, e.g. 4 for 4%"},
              "per": {"type": "string", "enum": ["day", "week", "once"],
                      "description": "day = rate per day late; week = per started week; once = flat one-off"},
              "base": {"type": "string", "enum": ["order_value", "invoice_value"],
                       "description": "order_value = qty x FOB (default); invoice_value = amount invoiced"},
              "days_late": {"type": "integer", "description": "Override only if the user gives the days"},
              "cap_pct": {"type": "number", "description": "Maximum total penalty as % of base, if any"}},
          ["po_no", "rate_pct"]),
    _tool("get_po_whatif", "Simulate an OPEN PO with different linking machines and/or Friday overtime days.", {
              **_PO, "link_machines": {"type": "integer"},
              "overtime_days": {"type": "array", "items": _DATE}}, ["po_no"]),
    _tool("get_po_recommendation", "Recommended actions to recover a late OPEN PO, with predicted date and cost.",
          _PO, ["po_no"]),
    _tool("get_factory_scorecard", "Full scorecard for one factory: AQL pass % (90 days), OTD % (12 months), knit "
          "load, machines by gauge, linking machines, open POs/pcs, exposure, value at risk, certifications, BSCI "
          "rating, last report date.",
          {"code": {"type": "string", "description": "Factory code (e.g. GRL) or part of its name"}}, ["code"]),
    _tool("list_factory_scorecards", "Every factory's AQL pass % (90 days), OTD % (12 months), knit load %, open "
          "POs, value at risk and whether it reported today. Use to compare or rank factories."),
    _tool("get_shipment_outlook", "FORWARD-LOOKING: 8-week predicted shipment outlook by week and band, with "
          "on-time % and value at risk."),
    _tool("get_shipped_summary", "ACTUALS: what already shipped (left the factory) in a calendar month or a date "
          "window — shipments, POs, pcs, invoice value, on-time % vs planned ex-factory, air freight cost, ship "
          "mode, status, by factory, and the late shipments. Omit everything for last month.", {
              "month": {"type": "string", "description": "YYYY-MM, e.g. 2026-09"},
              "date_from": _DATE, "date_to": _DATE}),
    _tool("list_inspections", "QA inspections (inline, pre-final, final, re-inspection) in a date window, default "
          "the last 7 days: totals, pass %, by type, and rows with defects.", {
              "date_from": _DATE, "date_to": _DATE, "factory": {"type": "string"},
              "result": {"type": "string", "enum": ["Pass", "Fail"]},
              "inspection_type": {"type": "string", "description": "Inline, Pre-final, Final, re-inspection"}}),
    _tool("list_overdue_milestones", "Overdue T&A milestones on open POs (yarn, approvals, knitting/linking start, "
          "final inspection, ex-factory), most overdue first.", {"factory": {"type": "string"}}),
    _tool("list_open_alerts", "Open alerts (critical POs, missed reports, late yarn, failed inspections).",
          {"severity": {"type": "string", "enum": ["critical", "risk", "watch", "noupdate"]}}),
]
TOOL_NAMES = {t["name"] for t in TOOLS}

# Tools that do not take the run object.
_NO_RUN = {"get_po_whatif"}


def _jsonify(obj):
    if isinstance(obj, date | datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_jsonify(v) for v in obj]
    return obj


def _call_tool(name: str, args: dict, run):
    fn = toolmod.CATALOGUE[name]
    if name in _NO_RUN:
        return fn(**args)
    return fn(run, **args)


def _history_messages(history) -> list[dict]:
    """Prior user/assistant text turns from the client, trimmed to the last MAX_HISTORY_TURNS, starting
    with a user turn (the Messages API requires it)."""
    out = []
    for h in (history or [])[-MAX_HISTORY_TURNS * 2:]:
        if isinstance(h, dict) and h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str):
            if h["content"].strip():
                out.append({"role": h["role"], "content": h["content"][:4000]})
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


def _system(run, user) -> list[dict]:
    """Static instructions first (cached together with the tools), then the per-request context."""
    role = None
    if user is not None:
        groups = set(user.groups.values_list("name", flat=True))
        role = next((g for g in ("Admin", "Management", "Merchandiser", "QA") if g in groups), None)
    as_of = timezone.localtime(run.as_of).strftime("%d %b %Y, %H:%M")
    today = settings.DEMO_TODAY
    prev = date.fromisoformat(metrics.last_month(today) + "-01")
    week = metrics.outlook_start(today)
    ctx = (f"The data snapshot is as of {as_of} Dhaka time — quote it exactly like that.\n"
           f"Today is {today:%A %d %b %Y}; this work week started {week:%A %d %b}; this month is {today:%B %Y}; "
           f"last month is {prev:%B %Y}.")
    if role:
        ctx += f"\nThe user's role is {role}; all roles may read the whole book."
    return [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}, {"type": "text", "text": ctx}]


def answer_llm(run, question: str, user=None, history=None) -> dict:
    import anthropic

    # A key that is not scoped to a workspace must name one on every request.
    headers = {"anthropic-workspace-id": settings.ANTHROPIC_WORKSPACE_ID} if settings.ANTHROPIC_WORKSPACE_ID else None
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=1, default_headers=headers)
    deadline = time.monotonic() + TOTAL_BUDGET_S
    system = _system(run, user)
    messages = [*_history_messages(history), {"role": "user", "content": question}]
    steps: list[str] = []
    last_table = None
    usage = {"input": 0, "output": 0}
    sources = [{"name": "Prediction snapshot", "as_of": run.as_of.isoformat()}]

    for _ in range(MAX_ROUNDS):
        remaining = deadline - time.monotonic()
        if remaining < 2:
            raise TimeoutError("assistant LLM time budget exhausted")
        resp = client.beta.messages.create(
            model=settings.ANTHROPIC_MODEL, max_tokens=4000, system=system, tools=TOOLS, messages=messages,
            output_config={"effort": settings.ANTHROPIC_EFFORT},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            timeout=min(settings.LLM_REQUEST_TIMEOUT_S, remaining),
        )
        usage["input"] += resp.usage.input_tokens + (resp.usage.cache_read_input_tokens or 0)
        usage["output"] += resp.usage.output_tokens
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"model refused: {getattr(resp.stop_details, 'category', None)}")
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if resp.stop_reason != "tool_use" or not tool_uses:
            text = "\n\n".join(b.text for b in resp.content if b.type == "text").strip()
            return {"steps": steps, "text": text, "table": last_table, "chart": None, "sources": sources,
                    "followups": [], "usage": usage}
        # Keep the whole assistant turn (thinking + tool_use blocks) so the next request stays valid.
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for tu in tool_uses:
            steps.append(f"Calling {tu.name}")
            args = tu.input if isinstance(tu.input, dict) else {}
            try:
                if tu.name not in TOOL_NAMES:
                    raise KeyError(f"unknown tool {tu.name}")
                result = _jsonify(_call_tool(tu.name, args, run))
                is_error = False
            except Exception as e:  # noqa: BLE001
                result, is_error = {"error": str(e)}, True
            maybe = _table_from(result)
            if maybe:
                last_table = maybe
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": json.dumps(result),
                            **({"is_error": True} if is_error else {})})
        messages.append({"role": "user", "content": results})

    # Ran out of tool rounds without a final answer.
    return {"steps": steps, "text": "I couldn't finish that one — could you narrow it down (e.g. a factory "
            "code or a PO number)?", "table": last_table, "chart": None, "sources": sources, "followups": [],
            "usage": usage}


def _table_from(result):
    """Best-effort table for the UI from a tool result's data."""
    data = result.get("data") if isinstance(result, dict) else None
    if isinstance(data, dict) and "formula" in data:  # calculate_late_penalty
        return {"columns": ["Item", "Value"], "rows": [
            ["PO", data["po_no"]], ["Days late", f"{data['days_late']} ({data['days_late_source']})"],
            ["Base", f"{data['base']}: ${data['base_amount_usd']:,.2f}"],
            ["Rate", f"{data['rate_pct']}% per {data['per']}"], ["Total %", f"{data['total_pct']}%"],
            ["Penalty (USD)", f"${data['penalty_usd']:,.2f}"]]}
    if isinstance(data, dict):
        for key in ("by_factory", "pos", "inspections", "milestones", "alerts", "top_worsened"):
            rows = data.get(key)
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                cols = list(rows[0].keys())[:7]
                return {"columns": cols, "rows": [[r.get(c) for c in cols] for r in rows[:25]]}
    if isinstance(data, list) and data and isinstance(data[0], dict):
        cols = list(data[0].keys())[:6]
        return {"columns": cols, "rows": [[r.get(c) for c in cols] for r in data[:25]]}
    return None
