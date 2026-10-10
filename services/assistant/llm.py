"""OpenAI tool-calling path for the assistant (docs/ai/assistant.md).

The model chooses tools and phrases the answer; every NUMBER still comes from the tools (which call the
same services.* functions the screens use). No free-form SQL. On any error the caller falls back to the
deterministic router, so the demo never depends on the network.
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from services.assistant import tools as toolmod

MAX_ROUNDS = 6
MAX_HISTORY_TURNS = 10
TOTAL_BUDGET_S = 40  # whole answer; past this the caller falls back to the deterministic router

SYSTEM = (
    "You are the AI Pulse assistant for Karbar Sourcing Bangladesh, a sweater sourcing office that places "
    "knitwear orders with Bangladeshi factories. Users are merchandisers, QA and management.\n\n"
    "HOW TO ANSWER\n"
    "1. Business data (orders, POs, factories, on-time, value at risk, AQL pass rates, reporting, "
    "shipments): call tools. Every number about the business MUST come from a tool result — never invent, "
    "estimate or round differently. Mention the snapshot 'as of' time given below.\n"
    "2. Concepts and industry terms (e.g. AQL, ex-factory, FOB, OTD, gauge, linking, pre-final "
    "inspection, air freight vs sea): explain them from your own garment/sourcing knowledge. When "
    "relevant, also pull the matching data — e.g. 'What is the AQL pass of a factory?' → explain AQL "
    "pass rate briefly AND, in the same answer, call list_factory_scorecards and summarise the factories' "
    "AQL pass % (weakest first). Don't just offer to fetch data you can fetch now.\n"
    "3. Ambiguous questions: if a question could mean several things or is missing something you need "
    "(which factory, which PO, which month) and a sensible default does not exist, ask ONE short "
    "clarifying question, offering concrete options (e.g. factory codes from the tools). If there is a "
    "sensible default (e.g. show all factories), answer with it and offer to narrow down.\n"
    "4. Use the conversation history: a short reply like 'GRL' or 'the second one' answers your previous "
    "question.\n"
    "5. Only say you don't have something when it is genuinely outside the data AND outside general "
    "sourcing knowledge (e.g. revenue/margin, weather). Then say what you can help with instead.\n\n"
    "DATA NOTES: Purchase orders are 8-digit numbers like 71010305. Factories are identified by 3-letter "
    "codes (GRL, IRB, SLM…). AQL pass % is the share of the factory's inspections passed in the last 90 "
    "days; OTD % is 12-month on-time delivery. Today is 15 Oct 2026.\n\n"
    "STYLE: Concise plain English — a few sentences or a short list. Bold key numbers with **…**. "
    "Write dates like '7 Nov 2026', never raw ISO timestamps. "
    "Do not use markdown tables or headings; the UI renders a table from the tool data for you."
)

# OpenAI function schemas for the tool catalogue.
TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "get_portfolio_kpis", "description": "Open POs, pcs, FOB value, October on-time %, value at risk, air exposure, reporting state.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_october_ontime", "description": "October predicted on-time percentage.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_value_at_risk", "description": "Total value at risk (USD) and the breakdown by factory with shares.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "list_factories_missing_report", "description": "Factories that have not reported the latest expected day.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_po_prediction", "description": "Prediction for one PO: band, projected ex-factory, slip, probability, drivers.",
        "parameters": {"type": "object", "properties": {"po_no": {"type": "string"}}, "required": ["po_no"]}}},
    {"type": "function", "function": {
        "name": "get_po_whatif", "description": "Simulate a PO with different linking machines and/or Friday overtime days.",
        "parameters": {"type": "object", "properties": {
            "po_no": {"type": "string"},
            "link_machines": {"type": "integer"},
            "overtime_days": {"type": "array", "items": {"type": "string", "description": "ISO date e.g. 2026-10-16"}}},
            "required": ["po_no"]}}},
    {"type": "function", "function": {
        "name": "get_po_recommendation", "description": "Recommended actions to recover a late PO, with predicted date and cost.",
        "parameters": {"type": "object", "properties": {"po_no": {"type": "string"}}, "required": ["po_no"]}}},
    {"type": "function", "function": {
        "name": "get_factory_scorecard",
        "description": "Full scorecard for one factory: AQL pass % (90 days), OTD % (12 months), knit load, "
                       "machines by gauge, linking machines, open POs/pcs, exposure, value at risk, "
                       "certifications, BSCI rating, last report date.",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string", "description": "Factory code (e.g. GRL) or part of its name"}},
            "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "list_factory_scorecards",
        "description": "Every factory's AQL pass % (90 days), OTD % (12 months), knit load %, open POs, value "
                       "at risk and whether it reported today. Use to compare factories or when no factory "
                       "is named.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "list_at_risk_pos", "description": "List at-risk POs, optionally filtered by factory code, department, band, or ex-factory month (YYYY-MM).",
        "parameters": {"type": "object", "properties": {
            "factory": {"type": "string"}, "dept": {"type": "string"},
            "band": {"type": "array", "items": {"type": "string"}},
            "exf_month": {"type": "array", "items": {"type": "string"}},
            "limit": {"type": "integer"}}}}},
    {"type": "function", "function": {
        "name": "get_shipment_outlook", "description": "8-week shipment outlook by band with on-time % and value at risk.",
        "parameters": {"type": "object", "properties": {}}}},
]

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
    """Prior user/assistant text turns from the client, trimmed to the last MAX_HISTORY_TURNS."""
    out = []
    for h in (history or [])[-MAX_HISTORY_TURNS * 2:]:
        if isinstance(h, dict) and h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str):
            out.append({"role": h["role"], "content": h["content"][:4000]})
    return out


def _model_params() -> dict:
    """gpt-5 / o-series are reasoning models: no custom temperature, take reasoning_effort instead."""
    model = settings.OPENAI_MODEL
    if model.startswith(("gpt-5", "o3", "o4")):
        return {"model": model, "reasoning_effort": settings.OPENAI_REASONING_EFFORT}
    return {"model": model, "temperature": 0.2}


def answer_llm(run, question: str, user=None, history=None) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=1)
    deadline = time.monotonic() + TOTAL_BUDGET_S
    role = None
    if user is not None:
        groups = set(user.groups.values_list("name", flat=True))
        role = next((g for g in ("Admin", "Management", "Merchandiser", "QA") if g in groups), None)

    as_of = timezone.localtime(run.as_of).strftime("%d %b %Y, %H:%M")
    sys = SYSTEM + f"\nThe data snapshot is as of {as_of} Dhaka time — quote it exactly like that."
    sys += f"\nThe user's role is {role}; all roles may read the whole book." if role else ""
    messages = [{"role": "system", "content": sys}, *_history_messages(history),
                {"role": "user", "content": question}]
    steps: list[str] = []
    last_table = None
    params = _model_params()

    for _ in range(MAX_ROUNDS):
        remaining = deadline - time.monotonic()
        if remaining < 2:
            raise TimeoutError("assistant LLM time budget exhausted")
        resp = client.chat.completions.create(
            messages=messages, tools=TOOL_SCHEMAS, tool_choice="auto",
            timeout=min(settings.OPENAI_REQUEST_TIMEOUT_S, remaining), **params,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            text = (msg.content or "").strip()
            return {"steps": steps, "text": text, "table": last_table, "chart": None,
                    "sources": [{"name": "Prediction snapshot", "as_of": run.as_of.isoformat()}],
                    "followups": []}
        messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            steps.append(f"Calling {name}")
            try:
                result = _jsonify(_call_tool(name, args, run))
            except Exception as e:  # noqa: BLE001
                result = {"error": str(e)}
            maybe = _table_from(result)
            if maybe:
                last_table = maybe
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})

    # Ran out of tool rounds without a final answer.
    return {"steps": steps, "text": "I couldn't finish that one — could you narrow it down (e.g. a factory "
            "code or a PO number)?", "table": last_table, "chart": None,
            "sources": [{"name": "Prediction snapshot", "as_of": run.as_of.isoformat()}], "followups": []}


def _table_from(result):
    """Best-effort table for the UI from a tool result's data."""
    data = result.get("data") if isinstance(result, dict) else None
    if isinstance(data, dict) and isinstance(data.get("by_factory"), list) and data["by_factory"]:
        rows = data["by_factory"]
        cols = list(rows[0].keys())
        return {"columns": cols, "rows": [[r.get(c) for c in cols] for r in rows]}
    if isinstance(data, list) and data and isinstance(data[0], dict):
        cols = list(data[0].keys())[:6]
        return {"columns": cols, "rows": [[r.get(c) for c in cols] for r in data[:25]]}
    return None
