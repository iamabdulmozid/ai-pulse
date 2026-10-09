# Karbar Pulse — Prediction engine

**Status:** v1 · deterministic formulas (no ML in Phase 0). **Canonical reference:** this document plus
`sample_data/00_Answer_Key.xlsx`. The answer key is the test: the engine must reproduce every open-PO
row in `Open PO Predictions` and every `KPIs`/`Hero What-if` value within rounding.

> The reference implementation lives in `sample_data/scripts/generate_sample_data.py`
> (`weighted_rate`, `stage_rates`, `project`, `project_pre`, `predict_all`, `hero_whatif`). The
> production engine re-implements the same maths as a **pure-Python service module**
> (`services/prediction/`) with **no view or ORM logic inside the formulas**: inputs are plain data
> structures (dataclasses / dicts), outputs are plain results. A thin adapter loads ORM rows into those
> structures and writes results into `PredictionSnapshot` / `FactoryStat`.

All arithmetic uses `Decimal` or exact integer working-day counts so two engineers get identical numbers.
Rounding is applied only at output (the fields in `PredictionSnapshot`), never mid-calculation.

---

## 0. Inputs per PO

For each open PO the engine receives:
- Order facts: `order_qty`, `planned_exfactory`, `weight_kg_pc`, `gauge`, `wash_required`,
  `linking_std_pcs_mc_day`, `knitting_minutes_pc`, factory.
- The PO's **reported** `DailyProduction` rows up to the factory's `last_report` date, pivoted to
  `{date: {stage: day_pcs}}` and cumulative `{stage: cum_pcs}`.
- The PO's 11 `TAMilestone` rows (planned / revised / actual).
- Factory stats for the run: `otd_12m`, `aql_pass_90d`, `slip_distribution`, `last_report_date`,
  `missed_wd`, latest inspection result for the PO.
- The active `EngineParameter` set (§8).

`DEMO_TODAY` (`today`) is a setting; for the seed and demo it is **15 Oct 2026**; the latest expected
report is **14 Oct 2026**.

---

## 1. Working-day calendar

```
is_working_day(d, overtime_days):   d is a working day  ⇔  weekday(d) ≠ Friday  OR  d ∈ overtime_days
                                     AND d ∉ holiday_calendar
wd_between(a, b):   count of days d with a ≤ d < b that are working days          # half-open [a, b)
nth_wd(start, n):   the n-th working day counting `start` as day 1 (if start is a WD)
next_wd(d):         the first working day strictly after d
```

- **Weekend:** Friday only (Bangladesh garment convention).
- **Holidays:** dates in `HolidayCalendar` are non-working. The seed data uses a Friday-only weekend;
  real holidays are loaded separately and flow through `is_working_day` with no formula change.
- **Overtime days** (what-if): a set of dates (always Fridays in the demo) temporarily treated as working.

**Available WD** for a PO = `wd_between(today, planned_exfactory)` (today counted, ex-factory not).
Hero: `wd_between(15 Oct, 29 Oct)` = **12** working days (Fridays 16 & 23 Oct excluded).

---

## 2. Stage rates (effective output per working day)

Stages in order: `knitting → linking → trimming_mending → washing* → ironing → packing`
(*washing only when `wash_required = Y`).

**Rate window:** the last `RATE_WINDOW = 7` working days ending at the factory's `last_report`.

**Weighted average** with linear weights `1..n` (latest day heaviest):
```
weighted_rate(values) = Σ(i · value_i) / Σ(i)      for i = 1..n, value_1 = oldest
```

For each stage:
1. Find the stage's **first output day** (first reported date with `day_pcs > 0`).
2. Keep only window days on/after that first output day (so the ramp-up before a stage starts does not
   dilute its rate).
3. `rate[stage] = weighted_rate(day_pcs over those days)` (missing days inside the window count as 0).
4. If the stage never produced, `rate[stage] = 0`.

A what-if **linking machine multiplier** multiplies `rate[linking]` by `new_machines / current_machines`
(capacity scales linearly with linking machines). Overtime days enter through the calendar (more WD), not
through the rate.

---

## 3. Projection (knitting under way)

Walk the stages in order, carrying the previous stage's remaining work and finish. All finishes are in
**working days from today**.

For stage `s` (with upstream stage `prev`):
```
rem[s]      = order_qty − cum[s]
m           = rate[s]                                   # measured effective rate
limited     = prev exists AND ( cum[s] == 0  OR  cum[prev] − cum[s] ≤ FLOW_LIMIT_DAYS · m )
follows     = limited AND rem[prev] > 0                 # starved: paced by upstream
eff         = max(m, eff[prev]) if limited else m
lower       = finish[prev] + STAGE_LAG[s]   if (prev exists AND rem[prev] > 0)  else 0

if rem[s] ≤ 0:            finish[s] = 0,      binding = "done"
elif follows:            finish[s] = lower,  binding = "flow"
else:
    own = rem[s] / eff   (∞ if eff == 0)
    finish[s] = max(own, lower)
    binding   = "own"  if own ≥ lower  else "flow"
```

- `FLOW_LIMIT_DAYS = 1.5`: if a stage has ≤ 1.5 days of work waiting in front of it (upstream cum −
  own cum) **and** upstream still has work, its measured rate reflects starvation, not capacity, so it is
  paced by upstream (`finish[prev] + lag`).
- **Stage lags (working days):** `linking 1.0, mending 0.5, washing 0.5, ironing 0.5, packing 0.5`
  (knitting has no upstream lag).

**Completion:** `finish = finish[packing]` (last stage). 
```
N = 0 if finish ≤ 0 else ceil(finish − 1e-9)           # working days, today = day 1
projected_exfactory = next_wd(nth_wd(today, N))        # the working day AFTER the N-th working day
if N == 0:  projected_exfactory = max(today, planned_exfactory)   # fully packed, awaiting ex-factory
```

**Bottleneck** = the **last** stage whose `binding == "own"` (its own rate sets the schedule).

**Required rate** (bottleneck pieces/WD to still make ex-factory):
```
later  = stages after the bottleneck
denom  = Available WD − Σ STAGE_LAG[later]
required_rate = rem[bottleneck] / denom      (undefined if denom ≤ 0)
```

**Slack WD** = `Available WD − N`. **Slip days** = `(projected_exfactory − planned_exfactory).days`
(calendar). On time ⇔ slip ≤ 0.

### Worked example — hero PO `71010305`
Reported to 14 Oct: knitting ≈ complete (8,946 of 9,600), linking the bottleneck at effective
**411.1 pcs/day**, 13 linking machines. Downstream stages starved (follow linking + lags).
- `rem[linking] ≈ 9,600 − linking_cum`; linking is `binding = "own"` → **bottleneck = Linking**.
- `finish[packing] ≈ 18.54` WD → `N = 19`.
- Available WD = 12 → **slack = 12 − 19 = −7 WD**.
- `required_rate = rem[linking] / (12 − Σ lags after linking)` = **680 pcs/day**.
- `projected_exfactory = next_wd(nth_wd(15 Oct, 19))` = **7 Nov 2026** → **slip = 9 calendar days**.

Matches the answer key row exactly (Bottleneck Rate 411.1, Required 680, N 19, Available 12, Slack −7,
Projected 2026-11-07, Slip 9).

---

## 4. Projection (knitting not started — pre-production)

```
yarn_date  = yarn_in_house.actual  OR  max(yarn_in_house.revised OR yarn_in_house.planned, today)
if knitting_start.actual exists:   proj_knit = knitting_start.actual
else:
    proj_knit = max(knitting_start.planned, yarn_date + YARN_TO_KNIT_DAYS)   # YARN_TO_KNIT_DAYS = 2
    if knitting_start.planned < today:  proj_knit = max(proj_knit, today)
start_delay          = max(0, (proj_knit − knitting_start.planned).days)      # calendar days
projected_exfactory  = planned_exfactory + start_delay
slip                 = start_delay
state                = "Pre-production"   (no bottleneck / slack / required rate)
```

---

## 5. Risk score (0–100)

Sum of five capped components, rounded to the nearest integer, clamped to 100.

| Component | Cap | Rule |
|---|---|---|
| **Schedule** | 50 | `N == 0` (fully packed): **0**. Else if `slip > 0`: `35 + min(15, 1.5 × slip)`. Else (in production) if `slack_wd ≤ 2`: **25**; if `slack_wd ≤ 5`: **12**; else **0**. |
| **T&A** | 20 | Yarn in-house late: `≥8 d → 12`, `4–7 d → 8`, `1–3 d → 4`, else 0. **Plus 8** if PP sample approval is `≥3 d` late. Capped at 20. |
| **Factory OTD** | 15 | `min(15, (1 − OTD_12m) × 50)`. |
| **Quality** | 10 | PO's latest inspection = Fail → **10**; else factory AQL pass rate (90 d) `< 0.85` → **5**; else 0. |
| **Freshness** | 5 | In-production POs only. Working days the factory has missed reporting: `1 → 3`, `≥2 → 5`; else 0. |

Where:
- **Yarn-late days** = `((yarn.actual OR max(yarn.revised OR yarn.planned, today)) − yarn.planned).days`.
- **PP-late days** = `((pp.actual OR today) − pp.planned).days` when `pp.actual` exists or
  `pp.planned < today`, else 0.
- **Missed WD** = `wd_between(next_wd(factory.last_report), next_wd(latest_expected_report))` for
  in-production POs (0 otherwise).

Hero score: schedule 50 + T&A 12 + OTD 12 + quality 0 + freshness 0 = **76 → Critical**. ✔

---

## 6. Bands

```
band = "On track" if score < 25
     = "Watch"    if score < 50
     = "At risk"  if score < 75
     = "Critical" otherwise                 # score ≥ 75
if slip > 0 and band in {On track, Watch}:  band = "At risk"
if slip ≥ 7:                                band = "Critical"
if planned_exfactory < today and not shipped: band = "Late"     # final override
```

"No update" is **not** a band — it is a factory reporting flag (`FactoryStat.reported_today = False`,
`missed_wd ≥ 1`), surfaced as a stripe/pill and an alert. POs at a quiet factory still carry their score-band.

Demo band counts (sum 412): On track 354 · Watch 10 · At risk 28 · Critical 13 · Late 7.

---

## 7. On-time probability, cost, recommendations

**On-time probability** — from the factory's last-12-month shipment slip distribution:
```
predicted_slack_calendar = −slip
prob = count(historical_slip ≤ predicted_slack_calendar) / count(history)
prob = clamp(prob, 0.02, 0.98)        # 2%–98%
```
Hero: 2%. ✔

**Value at risk** = `fob_value_usd` if `band ∈ {At risk, Critical, Late}` else 0 (summed for portfolio).

**Air-freight exposure** (POs predicted late or already late):
```
exposure = order_qty × weight_kg_pc × (AIR_USD_PER_KG − SEA_USD_PER_KG)     # 6.00 − 0.50
```
Hero: `9,600 × 0.72 × 5.50` = **USD 38,016**. ✔ Portfolio total **USD 539,720**.

**Knitting capacity** (factory load, not per-PO schedule):
```
knit_capacity_pcs_day = Σ_gauge ( machines[gauge] × KNIT_MC_MINUTES_PER_DAY ) / knitting_minutes_pc
knit_load_pct = required_knitting_throughput / knit_capacity_pcs_day
```
`KNIT_MC_MINUTES_PER_DAY = 1020` (2 shifts × 10 h × 85% efficiency).

### Recommendation rules
Each recommendation returns a predicted ex-factory date and a cost, computed by re-running §3 with
overridden inputs (so screen cards and the what-if agree):

1. **Reallocate linking machines** — auto-select a **donor PO** at the same factory with the same
   gauge/linking pool, positive slack, and enough spare machines; move machines until the target PO is on
   time while the donor stays on time. Report both POs' new dates. (Hero donor auto-resolves to `71009573`.)
2. **Friday overtime** — add N Fridays as overtime days (calendar), re-project.
3. **Subcontract knitting** — model added knitting capacity (Later-grade; shown as an option with cost).
4. **Split shipment** — ship the ready portion on time, the remainder later (reduces at-risk pcs).
5. **Air freight** — accept the slip, cost = air exposure; always available as the "do nothing" baseline.

For the demo the two live what-if inputs are **linking machines** and **Friday overtime days**; the other
options appear as read-only recommendation cards with their predicted date and cost.

---

## 8. Parameters (admin-editable `EngineParameter` defaults)

| Key | Default | Meaning |
|---|---|---|
| `air_usd_per_kg` | 6.00 | air freight cost |
| `sea_usd_per_kg` | 0.50 | sea freight cost |
| `rate_window_wd` | 7 | working days in the weighted rate window |
| `flow_limit_days` | 1.5 | work-in-front threshold for a supply-limited stage |
| `yarn_to_knit_days` | 2 | days from yarn in-house to knitting start |
| `knit_mc_minutes_per_day` | 1020 | available knitting minutes/machine/day |
| `stage_lag_linking` | 1.0 | lag (WD) |
| `stage_lag_mending` / `_washing` / `_ironing` / `_packing` | 0.5 each | lags (WD) |
| `score_schedule_cap` / `_ta_cap` / `_otd_cap` / `_quality_cap` / `_freshness_cap` | 50 / 20 / 15 / 10 / 5 | component caps |
| `band_on_track_max` / `_watch_max` / `_at_risk_max` | 25 / 50 / 75 | band cut-offs (score <) |
| `slip_forces_critical` | 7 | slip ≥ this → Critical |
| `freshness_missed1` / `_missed2plus` | 3 / 5 | freshness points |
| `prob_floor` / `prob_ceiling` | 0.02 / 0.98 | probability clamp |

Changing a parameter changes future runs only; each run records a `params_hash` so a snapshot's inputs
are auditable.

---

## 9. Runs and storage

- **When:** after every successful upload (triggered by the ingest task) and **nightly** (django-q2
  schedule). Also by `seed_demo` (trigger `seed`) and admin "re-run".
- **What:** compute `FactoryStat` for all 22 factories, then score all open POs, then raise `Alert`s from
  `AlertRule`s. Write one `PredictionRun` + its `PredictionSnapshot`/`FactoryStat` rows.
- **Reads:** all pages and assistant tools read the **latest** snapshot via `services/`; they never
  recompute on request. Every figure shown carries the run's `as_of`.
- **Accuracy (Later):** because snapshots are kept per run, a backtest can compare `projected_exfactory`
  against eventual `Shipment.actual_exfactory` (MAE days, % within 2). Phase 0 seeds a single run.

---

## 10. What-if

The what-if endpoint calls the **same** `project()` with overridden inputs and returns the delta — it is
never a separate formula. Inputs: `linking_machines` (min/max/current) and `overtime_days`. Output:
`{projected_exfactory, slip_days, on_time_probability, air_cost_usd}`, served as an HTMX partial. It reads
the PO's stored reported rows; it does not write a snapshot.

### Hero what-if (answer-key `Hero What-if`, reproduced exactly)

| Option | Linking pcs/day | Required | Avail WD | N | Projected ex-factory | Slip | On time | Air avoided |
|---|---|---|---|---|---|---|---|---|
| Current plan | 411.1 | 680 | 12 | 19 | 7 Nov | 9 | No | 0 |
| +6 linking M/C (13→19) | 600.8 | 680 | 12 | 14 | 1 Nov | 3 | No | 0 |
| 2 Friday overtime (16, 23 Oct) | 411.1 | 566.7 | 14 | 19 | 4 Nov | 6 | No | 0 |
| **+6 M/C and 2 Fridays** | **600.8** | 566.7 | 14 | **14** | **29 Oct** | **0** | **Yes** | **USD 38,016** |
| Donor `71009573` today | 770.8 | 443.1 | 22 | 14 | 1 Nov | −9 | Yes | — |
| Donor after giving 6 M/C (22→16) | 560.6 | 443.1 | 22 | 18 | 5 Nov | −5 | Yes | — |

Machine multiplier `600.8 = 411.1 × 19/13`; `560.6 = 770.8 × 16/22`. Overtime raises Available WD from
12 to 14 (adds Fridays 16 & 23 Oct), which lowers the required rate (680 → 566.7) and, combined with the
extra machines, pulls N to 14 and ex-factory to 29 Oct — on time, avoiding USD 38,016 of air freight,
while the donor stays 5 days early.

---

## 11. Test obligations (see `tests`, `traceability.md`)

- `test_engine_matches_answer_key`: every row of `Open PO Predictions` reproduced (band, score,
  projected ex-factory, slip, bottleneck, rates, probability, VaR, air exposure) within rounding.
- `test_kpis_match_answer_key`: the `KPIs` sheet reproduced (open counts, October on-time %, VaR, top-3
  share, air exposure, band counts, weekly outlook).
- `test_hero_whatif`: all six `Hero What-if` rows reproduced.
- `test_calendar`: `wd_between`, `nth_wd`, `next_wd` against hand-checked dates incl. overtime & holidays.
- `test_pure_service`: the engine module imports no Django ORM/view symbols.
