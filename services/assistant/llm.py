"""OpenAI tool-calling path for the assistant (docs/ai/assistant.md).

The model chooses tools and phrases the answer; every NUMBER still comes from the tools (which call the
same services.* functions the screens use). No free-form SQL. On any error the caller falls back to the
deterministic router, so the demo never depends on the network.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings

from services.assistant import tools as toolmod

MAX_ROUNDS = 5

SYSTEM = (
    "You are the AI Pulse assistant for Karbar Sourcing Bangladesh, a sweater sourcing office. "
    "Answer the user's question about the order book, factories, predictions and risk. "
    "RULES: Every number MUST come from a tool result — never invent or estimate numbers. "
    "Call tools to get data, then answer concisely in plain English. "
    "Always state the 'as of' time from the tool results. "
    "If the tools cannot answer, say 'I don't have that.' Do not guess. "
    "Purchase orders are 8-digit numbers like 71010305. 'Hero' metrics: today is 15 Oct 2026. "
    "Keep answers to a few sentences; use the numbers precisely."
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
        "name": "get_factory_scorecard", "description": "Scorecard for one factory by code (e.g. GRL).",
        "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}},
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


def answer_llm(run, question: str, user=None) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    role = None
    if user is not None:
        groups = set(user.groups.values_list("name", flat=True))
        role = next((g for g in ("Admin", "Management", "Merchandiser", "QA") if g in groups), None)

    sys = SYSTEM + (f" The user's role is {role}; all roles may read the whole book." if role else "")
    messages = [{"role": "system", "content": sys}, {"role": "user", "content": question}]
    steps: list[str] = []
    last_table = None

    for _ in range(MAX_ROUNDS):
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL, messages=messages, tools=TOOL_SCHEMAS,
            tool_choice="auto", temperature=0.2,
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

    # Ran out of rounds — return whatever the last assistant text was.
    return {"steps": steps, "text": "I don't have that.", "table": last_table, "chart": None,
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
