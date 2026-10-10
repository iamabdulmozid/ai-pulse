"""T-18/T-19 acceptance: assistant tools over services, 30 golden questions incl. 3 demo, provenance."""
import pytest
from django.core.management import call_command

from services import metrics
from services.assistant import router, tools


@pytest.fixture(scope="module")
def seeded(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("seed_demo")
        yield


pytestmark = pytest.mark.django_db

DEMO_Q1 = "Which factories will miss October ex-factory and by how much?"
DEMO_Q2 = "Why is PO 71010305 late and what is the fastest way to make it on time?"
DEMO_Q3 = "What is our October on-time %, and where is the USD 2.4M at risk concentrated?"

# 30 golden questions: (question, substrings that must appear in the answer text or a table cell)
GOLDEN = [
    (DEMO_Q1, ["GRL"]),
    (DEMO_Q2, ["Critical", "07 Nov"]),
    (DEMO_Q3, ["86.25%", "70%"]),
    ("What is our October on-time percentage?", ["86.25%"]),
    ("Where is the value at risk concentrated?", ["GRL"]),
    ("How much value is at risk?", ["2.4M"]),
    ("Which factories have not reported today?", ["SLM"]),
    ("Which factories are quiet?", ["OKH"]),
    ("Why is PO 71010305 late?", ["9 days", "Critical"]),
    ("What is the fastest way to make 71010305 on time?", ["on time"]),
    ("Show me the risk on 71010305", ["Critical"]),
    ("How many open POs are there?", ["412"]),
    ("What is the open order book value?", ["18.6M"]),
    ("Which factories will miss October and by how much?", ["GRL"]),
    ("October misses by factory", ["GRL"]),
    ("on-time % for October", ["86.25%"]),
    ("value at risk by factory", ["IRB"]),
    ("top factories by exposure", ["SLM"]),
    ("factories not reporting", ["HMR"]),
    ("why is 71010305 behind", ["Linking"]),
    ("what if we add machines to 71010305", ["Critical"]),
    ("October on time and risk concentration", ["86.25%", "70%"]),
    ("how many pieces are open", ["1,900,020"]),
    ("which POs are at risk", ["At risk"]),
    ("show October late factories", ["GRL"]),
    ("who carries the most risk", ["GRL"]),
    ("is PO 71010305 on track", ["Critical"]),
    ("what is at risk this month", ["86.25%"]),
    ("list the quiet factories", ["PBB"]),
    ("october predicted on time", ["86.25%"]),
]


def _text_and_cells(result):
    blob = result["text"]
    if result.get("table"):
        for row in result["table"]["rows"]:
            blob += " " + " ".join(str(c) for c in row)
    return blob


def test_assistant_tools_use_services(seeded):
    run = metrics.latest_run()
    k = tools.get_portfolio_kpis(run)
    assert k["data"]["open_pos"] == 412
    assert k["as_of"] and k["source"]
    var = tools.get_value_at_risk(run)
    assert round(var["data"]["total_usd"], 2) == 2400006.24
    assert var["data"]["by_factory"][0]["code"] == "GRL"


def test_assistant_provenance(seeded):
    run = metrics.latest_run()
    for name, fn in tools.CATALOGUE.items():
        if name in ("get_po_whatif",):
            continue
        if name in ("get_po_prediction", "get_po_recommendation", "get_po_details", "get_factory_scorecard"):
            res = fn(run, "71010305" if "po" in name else "GRL")
        elif name == "calculate_late_penalty":
            res = fn(run, "71010305", 4)
        else:
            res = fn(run)
        assert "as_of" in res and "source" in res, name


def test_assistant_demo_questions(seeded):
    run = metrics.latest_run()
    r1 = router.answer(run, DEMO_Q1)
    assert r1["table"] and r1["chart"]
    assert "GRL" in _text_and_cells(r1)
    r2 = router.answer(run, DEMO_Q2)
    assert "Critical" in r2["text"] and "07 Nov" in r2["text"]
    assert "on time" in r2["text"].lower()
    r3 = router.answer(run, DEMO_Q3)
    assert "86.25%" in r3["text"] and "70%" in r3["text"]
    assert all(f in _text_and_cells(r3) for f in ("GRL", "IRB", "SLM"))


def test_assistant_golden_questions(seeded):
    run = metrics.latest_run()
    failures = []
    for q, expects in GOLDEN:
        blob = _text_and_cells(router.answer(run, q)).lower()
        for e in expects:
            if e.lower() not in blob:
                failures.append((q, e, blob[:120]))
    assert not failures, f"{len(failures)} golden failures: {failures[:5]}"
    assert len(GOLDEN) == 30


def test_assistant_refuses_unknown(seeded):
    run = metrics.latest_run()
    r = router.answer(run, "what is the weather in Dhaka tomorrow?")
    assert "don't have that" in r["text"].lower()


def test_assistant_stream_and_page(seeded, client, django_user_model):
    u = django_user_model.objects.get(username="ceo")
    client.force_login(u)
    assert client.get("/assistant/", HTTP_HOST="localhost").status_code == 200
    resp = client.post("/assistant/stream/", {"message": DEMO_Q3}, HTTP_HOST="localhost")
    body = b"".join(resp.streaming_content).decode()
    assert "86.25%" in body and "event: done" in body


def test_assistant_export(seeded, client, django_user_model):
    import json

    u = django_user_model.objects.get(username="ceo")
    client.force_login(u)
    resp = client.post("/assistant/export.xlsx", data=json.dumps({"columns": ["A", "B"], "rows": [[1, 2]]}),
                       content_type="application/json", HTTP_HOST="localhost")
    assert resp.status_code == 200
    assert "spreadsheet" in resp["Content-Type"]


def test_assistant_explains_aql_and_asks_which_factory(seeded):
    """'What is AQL pass of a factory?' must explain AQL, show every factory's rate and ask which one."""
    run = metrics.latest_run()
    r = router.answer(run, "What is AQL pass of a factory?")
    assert "acceptable quality level" in r["text"].lower()
    assert "which factory" in r["text"].lower()
    assert r["table"] and len(r["table"]["rows"]) == len(tools.list_factory_scorecards(run)["data"])
    assert "don't have that" not in r["text"].lower()


def test_assistant_factory_followup(seeded):
    """A short reply naming a factory (answering 'which factory?') returns that factory's AQL."""
    run = metrics.latest_run()
    grl = tools.get_factory_scorecard(run, "GRL")["data"]
    r = router.answer(run, "GRL")
    assert "GRL" in r["text"] and f"{grl['aql_pass_pct']:.1f}%" in r["text"]
    assert tools.get_factory_scorecard(run, "greyloom")["data"]["code"] == "GRL"


def test_assistant_stream_accepts_history(seeded, client, django_user_model):
    import json

    client.force_login(django_user_model.objects.get(username="ceo"))
    history = json.dumps([{"role": "user", "content": "What is AQL pass of a factory?"},
                          {"role": "assistant", "content": "Which factory would you like to look at?"}])
    resp = client.post("/assistant/stream/", {"message": "IRB", "history": history}, HTTP_HOST="localhost")
    body = b"".join(resp.streaming_content).decode()
    assert "IRB" in body and "AQL" in body and "event: done" in body


def test_assistant_last_month_shipped(seeded):
    """'Last month' (Sep 2026 on the demo clock) answers from the shipment log, not predictions."""
    from django.conf import settings

    run = metrics.latest_run()
    assert metrics.last_month(settings.DEMO_TODAY) == "2026-09"
    d = tools.get_shipped_summary(run)["data"]
    assert d["month"] == "2026-09" and d["shipments"] > 0
    assert d["late_count"] == d["shipments"] - d["on_time"]
    r = router.answer(run, "What is last month status?")
    assert "September 2026" in r["text"] and f"{d['pcs']:,}" in r["text"]
    late = router.answer(run, "Which September shipments were late?")
    assert len(late["table"]["rows"]) == d["late_count"]
    # The current month without "shipped" stays on predictions (demo Q3 wording).
    assert "86.25%" in router.answer(run, "what is at risk this month")["text"]


def test_assistant_shipped_po_details_and_penalty(seeded):
    """A shipped PO has no prediction, but its order value is reachable and penalties are exact."""
    from django.db.models import F

    from apps.production.models import Shipment

    run = metrics.latest_run()
    s = (Shipment.objects.filter(actual_exfactory__month=9, actual_exfactory__gt=F("planned_exfactory"))
         .select_related("purchase_order").order_by("planned_exfactory").first())
    po, days = s.purchase_order, (s.actual_exfactory - s.planned_exfactory).days
    d = tools.get_po_details(run, po.po_no)["data"]
    assert d["status"] == "Shipped" and d["order_value_usd"] == float(po.fob_value_usd) and d["days_late"] == days

    p = tools.calculate_late_penalty(run, po.po_no, 4)["data"]
    expected = round(float(po.fob_value_usd) * 0.04 * days, 2)
    assert p["days_late"] == days and abs(p["penalty_usd"] - expected) < 0.01
    capped = tools.calculate_late_penalty(run, po.po_no, 4, cap_pct=10)["data"]
    assert capped["capped"] and abs(capped["penalty_usd"] - round(float(po.fob_value_usd) * 0.10, 2)) < 0.01
    weekly = tools.calculate_late_penalty(run, po.po_no, 1, per="week")["data"]
    assert weekly["units"] == -(-days // 7)

    # Prediction-only tools explain instead of inventing numbers for a shipped PO.
    assert "already shipped" in tools.get_po_whatif(po.po_no)["note"]
    assert "already shipped" in tools.get_po_prediction(run, po.po_no)["note"]

    # Fallback router: PO lookup and penalty both work for the shipped PO.
    assert f"{float(po.fob_value_usd):,.2f}" in router.answer(run, f"PO {po.po_no}")["text"]
    r = router.answer(run, f"calculate the fine for {po.po_no} at 4% per day")
    assert f"{expected:,.2f}" in r["text"]
    assert "September 2026" in router.answer(run, "What about Sep shipment??")["text"]
