# Karbar Pulse — 3-minute CEO demo script

**Audience:** Mr. Karim (CEO) · **Date:** 15 Oct 2026 · **Data:** seeded dummy data, English only
**Demo clock (`DEMO_TODAY`):** Thursday 15 Oct 2026, 09:40 Dhaka (reports up to 14 Oct)

> Every figure below is the answer-key canon (`00_Answer_Key.xlsx`), not the design prototype's
> illustrative labels. The hero PO is **71010305** (Greyloom, GRL); the top-risk factory shown is
> **Greyloom (GRL)**. The design handoff is followed for the click-path and talk-track shape only
> (PRD ASSUMPTION A-01). If the assistant is slow, jump to **Fallback** below.

Set-up before you speak: logged in as Management, **dark theme**, Overview open, hero PO 71010305
bookmarked, `DPR_PBB_2026-10-14.xlsx` staged on the desktop. See the **Pre-demo checklist**.

---

## Click-path

### 0:00 — Open the Executive Overview (dark theme)
- **Action:** Land on the Overview; let the AI briefing render, then click **"Why?"** on the briefing.
- **Screen / URL:** `/` (dashboard `overview`), briefing from `/overview/briefing/`.
- **On screen (exact):** briefing names **86.25%** October on-time · **USD 2,400,006** value at risk ·
  **top 3 factories = 70%** · **18 of 22 factories reported** (4 missing: SLM, OKH, HMR, PBB). "Why?"
  expands the arithmetic + sources with **as of 09:40**.
- **Say:** "Every morning this is the state of the business in three sentences, with the evidence one
  click away."

### 0:35 — Scan the KPI row and the outlook
- **Action:** Hover the **Value-at-risk** card note; then show the 8-week outlook and the factory × week
  heatmap.
- **Screen / URL:** `/overview/kpis/`, `/overview/outlook.json`, `/overview/heatmap.json`.
- **On screen (exact):** six KPI cards — Open POs **412** · Open pcs **1,900,020** · Open FOB
  **USD 18,601,449** · October on-time **86.25%** · Value at risk **USD 2,400,006** · Air-freight
  exposure **USD 539,720**. Heatmap: Greyloom (GRL) red across the near weeks; **4 striped rows**
  (SLM / OKH / HMR / PBB = no update).
- **Say:** "Risk is concentrated — three factories carry 70%. A striped row means a factory went quiet,
  and quiet is itself a risk."

### 1:00 — Open the hero PO
- **Action:** ⌘K → "Show me PO 71010305" (or click it from the top-10 at-risk list). Read the drivers,
  then switch to the **T&A** tab.
- **Screen / URL:** `/pos/71010305/`; T&A tab `/pos/71010305/ta/`.
- **On screen (exact):** 7GG Lambswool V-neck Cardigan, Women's, **9,600 pcs**, FOB **USD 158,400**,
  ex-factory **29 Oct**, **predicted 7 Nov**, **slip 9 days**, band **Critical**, risk score **76**,
  on-time probability **2%**. Drivers: yarn in-house late (T&A), linking the bottleneck at **411.1
  pcs/day vs 680 required**, factory OTD. T&A tab flags the late **Yarn in-house** milestone.
- **Say:** "The system doesn't just say late. It says why, in days, per cause."

### 1:40 — Apply the recommendation in the what-if
- **Action:** Click **"Apply plan in what-if"**: linking machines **13 → 19** (+6), Friday overtime
  **0 → 2** (Fridays **16 & 23 Oct**). Then drag the machine slider back to 13 to show it move live.
- **Screen / URL:** `/pos/71010305/whatif/` (POST, read-only partial).
- **On screen (exact):** predicted date snaps to **29 Oct**, slip **0 (on time)**, air freight
  **USD 0**, **USD 38,016 avoided**; the donor PO **71009573** stays early. Drag back to 13 → returns to
  **7 Nov / slip 9**.
- **Say:** "Six linking machines and two Fridays. Thirty-eight thousand dollars of air freight avoided,
  decided before lunch."

### 2:15 — Press ⌘K and ask the assistant
- **Action:** Press **⌘K**, type the question below, press Enter. Watch the steps, then the bar chart +
  table, then sources.
- **Screen / URL:** ⌘K palette → `/assistant/stream/` (SSE).
- **Question (verbatim):** *"Which factories will miss October ex-factory and by how much?"*
- **On screen (exact):** reasoning steps stream (book of **412** open POs narrowed to the October
  at-risk set), then a factory bar chart + table of slip days, then **sources with "as of 09:40"**.
- **Say:** "Anyone in the office can ask in plain English and see exactly how the answer was built."

### 2:45 — Open the factory scorecard
- **Action:** From the answer (or ⌘K), open the **Greyloom (GRL)** scorecard.
- **Screen / URL:** `/factories/GRL/`.
- **On screen (exact):** Greyloom is the top risk contributor — **exposure USD 774,059** (the largest of
  the top-3 that together make 70%: GRL 774,059 / IRB 477,578 / SLM 428,400). Knitting load, OTD, AQL,
  order book, inspections, certificates and the AI summary are all on one card.
- **Say:** "This is the factory conversation for Monday, already prepared."

### 3:00 — Close on Daily Updates + theme toggle
- **Action:** Open Daily Updates; show the 4 missing factories; drag-drop **`DPR_PBB_2026-10-14.xlsx`**;
  watch validation pass. Then toggle to **light theme**.
- **Screen / URL:** `/uploads/` (POST `upload_create` → status poll).
- **On screen (exact):** file validates clean; **reported moves 18 → 19 of 22** (PBB now in); the
  headline KPIs **do not change** (86.25% / USD 2,400,006 hold). Light theme renders identically.
- **Say:** "It runs on the Excel files the factories already send. No new system for them — and it's a
  daily working tool, in dark or light."

---

## The three demo questions (verbatim + expected answers)

| # | Question (verbatim) | Expected answer (exact) |
|---|---|---|
| 1 | *"Which factories will miss October ex-factory and by how much?"* | A ranked factory list with slip days, built from the 412 open POs → October at-risk set; Greyloom (GRL) leads. Chart + table + sources **as of 09:40**. |
| 2 | *"Why is PO 71010305 late and what's the fastest way to make it on time?"* | Predicted **7 Nov**, **slip 9**, **Critical**, prob **2%**; cause = linking bottleneck (411.1 vs 680/day) + late yarn in-house; fastest fix = **+6 linking machines (13→19) and 2 Friday overtimes (16 & 23 Oct) → 29 Oct, on time, air USD 0, USD 38,016 avoided** (donor 71009573 stays early). |
| 3 | *"What's our October on-time %, and where is the USD 2.4M at risk concentrated?"* | **86.25%** October on-time; **USD 2,400,006** at risk, concentrated in the top 3 factories = **70%** (GRL 774,059 / IRB 477,578 / SLM 428,400). |

All three must return **exact** answers (success metric M2: 3/3 demo, 30/30 golden —
`test_assistant_golden_questions`).

---

## FALLBACK — if OpenAI is slow or unavailable

The app runs offline; only the assistant's *free-text* generation depends on OpenAI. If a step stalls:

1. **Use the pre-stored answers.** The 3 demo questions have pre-computed answers stored per
   `ai/assistant.md`; the assistant serves these verbatim when OpenAI is slow/unavailable
   (proven by `test_assistant_fallback`). The numbers are identical to the table above, because they come
   from `services/`, not the model.
2. **If the assistant stalls mid-stream:** cancel, re-ask once; if still slow, say *"the numbers come from
   the same engine the dashboard uses — here is the stored answer"* and show the pre-stored result.
3. **General fallbacks (all pre-staged):**
   - **Seeded DB** — everything is read from the local seeded database; no live network needed.
   - **Dark theme pre-set** — do not toggle until the 3:00 step.
   - **Hero PO bookmarked** — jump straight to `/pos/71010305/` if ⌘K is slow.
   - **Upload file staged** — `DPR_PBB_2026-10-14.xlsx` on the desktop, ready to drag.
   - **Vendored JS** — Alpine / HTMX / ECharts are vendored; charts render with no CDN.
4. **Last resort:** if the assistant is fully down, skip the ⌘K step (2:15) and spend the time on the
   factory scorecard; the dashboard and PO what-if already carry the whole story.

---

## Pre-demo checklist (run on the demo machine; see `tech/deployment.md` demo-day freeze)

- [ ] On the frozen build from **14 Oct** (code freeze); no later commits deployed.
- [ ] Full pytest suite green — `test_engine_matches_answer_key`, `test_kpis_match_answer_key`,
      `test_hero_whatif`, `test_overview_kpis`, `test_po_list_filters`, `test_upload_rejects_bad_batch`,
      `test_assistant_golden_questions`, `test_role_write_scope`.
- [ ] Fresh `seed_demo`; single prediction run **as of 15 Oct 2026** (seed trigger).
- [ ] Headline numbers verified on `/`: 412 · 1,900,020 · USD 18,601,449 · 86.25% · USD 2,400,006 ·
      air USD 539,720 · top-3 70%.
- [ ] Hero PO 71010305 shows 7 Nov / slip 9 / Critical / 76 / 2%; what-if plan → 29 Oct / on time /
      air USD 0 / USD 38,016 avoided.
- [ ] Heatmap shows 18 of 22 reported (SLM / OKH / HMR / PBB striped).
- [ ] Logged in as Management; **dark theme** active; hero PO bookmarked.
- [ ] `DPR_PBB_2026-10-14.xlsx` staged; a trial drag-drop shows reported 18 → 19, headline unchanged
      (then re-seed so the demo starts at 18).
- [ ] Assistant warm: 3 demo questions answered correctly once; **pre-stored fallback answers confirmed**
      (`test_assistant_fallback`).
- [ ] Vendored JS loads with network disabled (offline check).
- [ ] Projector/screen at a resolution where both themes and the charts read clearly.
