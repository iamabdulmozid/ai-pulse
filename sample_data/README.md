# AI Pulse: demo data set

Dummy data for the AI Pulse CEO demo. It covers one brand (Karbar), sweaters only, 22 Bangladesh factories, and 12 months of shipped history plus the open order book.

All company and person names are fictional. Any resemblance to a real company is coincidental.

- **As of:** Thursday **15 Oct 2026**. Factories report the previous working day, so the latest expected report is 14 Oct. Friday is the weekend.
- **Regenerate:** run `python scripts/generate_sample_data.py`. The output is seeded, so every run gives the same files.
- **Check:** run `python scripts/validate_sample_data.py`. It checks integrity and rebuilds the answer key from the six files alone.

## Files

| File | Rows | What it is |
|---|---|---|
| `01_Order_Book.xlsx` | 1,287 POs · 3,104 colour lines | **PO Header**: style, gauge, yarn, weight, standard minutes, factory, qty, FOB, planned ex-factory. **PO Lines**: colour × size breakdown. Includes the shipped POs. A PO is open when it has no row in the Shipment Log. |
| `02_TA_Calendar.xlsx` | 14,157 | 11 Time & Action milestones per PO: planned, revised, actual date, status, delay reason |
| `03_Factory_Daily_Production_Report.xlsx` | 6,809 | 1 Sep – 14 Oct 2026, one row per PO per working day. Day and cumulative figures for knitting, linking, trimming & mending, washing, ironing and packing, plus knitting/linking machines |
| `04_Inspection_Log.xlsx` | 1,196 | Inline, pre-final, final and re-inspections, using AQL II / 2.5 / 4.0 |
| `05_Factory_Master.xlsx` | 22 | Location, gauges, machines by gauge, linking machines, certifications, Karbar owner |
| `06_Shipment_Log.xlsx` | 875 | Planned vs actual ex-factory, mode (sea / air / sea-air), ETD/ETA, invoice, air-freight cost and who paid it |
| `00_Answer_Key.xlsx` | — | **Not an upload.** Expected KPIs, the prediction for each open PO, a factory summary, the 8-week outlook, the hero PO what-if, and every engine parameter. Use it as golden test data |
| `demo_uploads/DPR_PBB_2026-10-14.xlsx` | 3 | A clean late report for the live upload demo. "Reported today" moves from 18 to 19 of 22; no other headline number changes |
| `demo_uploads/DPR_HMR_2026-10-14_with_errors.xlsx` | 8 | Contains three deliberate errors for the validation demo: an unknown PO (`71999999`), a negative Linking Day, and a Knitting Cum that goes down |

Every workbook has a **Columns** sheet with the type, whether the column is required, a description and an example for each column.

Two caveats:

- **Machine counts are low.** Factory Master machine counts are sized from Karbar's own load, so they are smaller than a real factory's total.
- **No holidays in the calendar.** The data uses a Friday-only weekend. Load Bangladesh public holidays into the app's holiday calendar separately.

## The story the numbers tell

| KPI | Value |
|---|---|
| Open POs / pcs / FOB | **412** / **1,900,020** / **USD 18,601,449** |
| October on-time (predicted) | **86.25%**: 160 POs; 56 of 60 shipped on time, 82 of 95 open predicted on time, 5 already late |
| Value at risk (FOB of At risk + Critical + Late) | **USD 2,400,006**, across 48 POs |
| Top 3 factories by value at risk | **Greyloom (GRL) 774k, Ironbridge (IRB) 478k, Saltmarsh (SLM) 428k = 70.0%** |
| Air-freight exposure | USD 539,720 |
| Bands | On track 354 · Watch 10 · At risk 28 · Critical 13 · Late 7 |
| Factories reported today | **18 of 22**. Missing: SLM (last 12 Oct), OKH (11 Oct), HMR and PBB (13 Oct) |
| Rest of October | 95 POs, 455,364 pcs, USD 4.88M |

### Hero PO: `71010305`

- **Order:** Lambswool V-neck Cardigan, Women's, 7GG, 9,600 pcs at USD 16.50 (USD 158,400).
- **Factory:** Greyloom Knitwear, Konabari, Gazipur.
- **Dates:** planned ex-factory 29 Oct.
- **What went wrong:**
  - Yarn arrived on 22 Sep, 8 days late.
  - Knitting started on 24 Sep and is nearly done (8,946 pcs).
  - Linking only started on 7 Oct, because the factory's linking machines were busy. It now runs 13 machines at **411 pcs/day; 680/day is needed**.
- **Prediction:** ready on 5 Nov, so it **ships 7 Nov, 9 days late**. Band **Critical** (score 76). On-time probability 2%.
- **Options** (from the answer key's Hero What-if sheet):

| Option | Projected ex-factory | Result |
|---|---|---|
| Current plan | 7 Nov | 9 days late |
| +6 linking machines (13 → 19) | 1 Nov | 3 days late |
| 2 Friday overtime days (16 and 23 Oct) | 4 Nov | 6 days late |
| **+6 linking machines and 2 Friday overtime days** | **29 Oct** | **On time. Avoids USD 38,016 of air freight** (9,600 pcs × 0.72 kg × (6.00 − 0.50) USD/kg) |

- **Where the machines come from:** donor PO **`71009573`**, a Men's 7GG crew-neck, 14,400 pcs, also at Greyloom, ex-factory 10 Nov. Giving up 6 of its 22 linking machines moves it from 9 days early to 5 days early, so it is still on time.

## Reference prediction engine

The generator and the answer key use the rules below. The app must reproduce them exactly; the answer key is the test.

1. **Working days:** every day except Friday. `Available WD` = working days from today up to, but not including, the planned ex-factory date.
2. **Stage rate:** a weighted average of the last 7 working days of output, ending at the factory's latest report. The weights are 1..n, with the latest day heaviest. Only days since the stage's first output count.
3. **Projected finish per stage**, in working days from today, taking stages in order (knitting → linking → mending → washing, if the style is washed → ironing → packing):
   - Finished stage (nothing remaining): 0.
   - **Supply-limited stage:** the stage has not started, or its work-in-front (upstream cum − own cum) is at most 1.5 days of its own rate, and its upstream stage still has work left. It finishes at upstream finish + lag. Lags are linking 1.0 and every later stage 0.5.
   - Otherwise: max(remaining ÷ rate, upstream finish + lag).
   - The **bottleneck** is the last stage whose finish comes from its own rate.
4. **Completion day N** = ceil(packing finish). Projected ex-factory = the working day after the N-th working day (counting today as day 1). When the PO is fully packed, it is today.
5. **Required rate** = bottleneck remaining ÷ (available WD − the lags of the stages after it).
6. **Not yet knitting:** projected knitting start = max(planned knitting start, yarn in-house date + 2 days, and today if the planned start has passed). The yarn date is the actual date, else the revised date, else the planned date. If knitting has started but is not yet reported, use the actual start. Projected ex-factory = planned + the start delay.
7. **Slip days** = projected − planned ex-factory, in calendar days. On time when slip ≤ 0.
8. **Risk score (0–100):**

| Component | Max | Rule |
|---|---|---|
| Schedule | 50 | 0 when fully packed. Slip > 0: 35 + min(15, 1.5 × slip). Slack ≤ 2 WD: 25. Slack 3–5 WD: 12. Otherwise 0 |
| T&A | 20 | Yarn in-house late ≥ 8 days: 12; 4–7 days: 8; 1–3 days: 4. Plus 8 if PP sample approval is ≥ 3 days late |
| Factory OTD | 15 | min(15, (1 − OTD over the last 12 months) × 50) |
| Quality | 10 | 10 if the PO's latest inspection failed; else 5 if the factory's 90-day AQL pass rate is < 85% |
| Freshness | 5 | In-production POs only. Working days the factory has missed reporting: 1 → 3, 2 or more → 5 |

9. **Bands:**
   - By score: < 25 On track; 25–49 Watch; 50–74 At risk; ≥ 75 Critical.
   - Any slip > 0 → at least At risk.
   - Slip ≥ 7 → Critical.
   - Planned ex-factory in the past and not shipped → Late.
10. **On-time probability** = the share of the factory's last-12-month shipments whose slip was ≤ the predicted slack in calendar days, clamped to 2–98%.
11. **Value at risk** = FOB value of At risk + Critical + Late POs. **Air-freight exposure** = pcs × kg/pc × (6.00 − 0.50) for POs predicted late or already late.
12. **October on-time %** = (POs planned for October and shipped on time + open October POs predicted on time) ÷ all POs planned for October.
