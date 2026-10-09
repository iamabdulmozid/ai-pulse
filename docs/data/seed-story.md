# Karbar Pulse — Seed story (`seed_demo`)

**Status:** v1 · **As of:** 15 Oct 2026. This is the specification for the management command that loads
the demo database so the app reproduces the answer key exactly.

`seed_demo` turns an empty database into the full Karbar Pulse demo: 22 factories, 1,287 POs (412 open),
twelve months of production and shipped history, and a single prediction snapshot as of
`DEMO_TODAY = 15 Oct 2026`. It is the Django counterpart of
`sample_data/scripts/generate_sample_data.py`: the generator and `seed_demo` share the same reference
engine and the same `SEED`, so the data they produce is identical and the answer key
(`sample_data/00_Answer_Key.xlsx`) is the test for both.

```
python manage.py seed_demo                 # seed to DEMO_TODAY (15 Oct 2026)
python manage.py seed_demo --export-xlsx    # also (re)write the six upload workbooks
python manage.py seed_demo --today 2026-10-15
python manage.py reset_demo                 # drop demo data and re-seed to the clean state
```

---

## 1. Determinism

Every value is reproducible from a fixed seed; nothing is random at run time.

- **Fixed seed.** `SEED = 20261015`. The command builds a single `random.Random(SEED)` for the top-level
  scenario construction, and **per-entity seeded generators** keyed by stable strings
  (`f"{SEED}-{po_no}"`, `f"ship-{po_no}"`, `f"insp-{po_no}"`, `f"cc-{po_no}"`, `f"rmk-{po_no}-{date}"`).
  Because each PO's simulation is seeded from its own PO number, the order in which POs are processed does
  not change any individual result.
- **Fixed clock.** `DEMO_TODAY` is a Django setting (default `2026-10-15`, a Thursday; latest expected
  report 14 Oct). The command never reads the wall clock; all "today" logic uses `DEMO_TODAY`.
- **Fixed calendar.** Friday-only weekend; the holiday calendar is seeded **empty** (real Bangladesh
  holidays are loaded separately and flow through `is_working_day` with no formula change).
- **Decimal arithmetic.** Rates, weights and money are `Decimal`/integers, matching the engine, so two
  runs — and two engineers — get byte-identical numbers.

Running `seed_demo` twice on an empty database yields the same rows; `reset_demo` then `seed_demo`
restores the exact clean state used for the CEO demo.

---

## 2. What it generates

### Master data

- **22 factories** (`masterdata.Factory` + `FactoryMachine`), listed below, with machine counts derived
  from the simulated October load (so counts are sized to Karbar's own book, smaller than a full floor).
- **Departments** `Men` / `Women` / `Kids`.
- **Seasons** `AW`/`HO`/`SS`/`SU` + 2-digit year, derived from each PO's ex-factory date (`season_for`).
- **Holiday calendar**: empty by default (Friday-only weekend).
- **Engine parameters** (`EngineParameter`): the defaults from `ai/prediction-engine.md §8`
  (air 6.00, sea 0.50 USD/kg; rate window 7 WD; flow limit 1.5; yarn→knit 2 days; knit 1020 min/mc/day;
  stage lags linking 1.0, others 0.5; score caps 50/20/15/10/5; band cut-offs 25/50/75; slip→Critical 7;
  freshness 3/5; probability clamp 0.02/0.98).
- **T&A template** (`TATemplate` + `TAMilestoneDef`): the single standard sweater template, 11 milestones
  with offsets (days before ex-factory): Yarn booking 95, Yarn shade approval 85, Fit sample approval 80,
  Size set approval 60, PP sample approval 50, Yarn in-house 45, PP meeting 42, Knitting start 40,
  Linking start 34, Final inspection 1, Ex-factory 0.
- **Users / groups**: Admin, Management, Merchandiser, QA, with the eight merchandisers and six QA
  inspectors from the generator (e.g. Farhana Rahman, Tanvir Hasan, Nusrat Jahan …) as `User`s, each with
  a `UserProfile.display_role`.

#### The 22 factories

| Code | Name | Area | District | Gauges | OTD target | Last report |
|---|---|---|---|---|---|---|
| GRL | Greyloom Knitwear Ltd. | Konabari | Gazipur | 5, 7, 12 | 0.68 | 14 Oct |
| IRB | Ironbridge Sweaters Ltd. | Fatullah | Narayanganj | 3, 5, 7 | 0.70 | 14 Oct |
| SLM | Saltmarsh Knit Fashions Ltd. | Ashulia | Dhaka | 7, 12, 14 | 0.72 | **12 Oct** |
| KST | Kestrel Knitwear Ltd. | Kashimpur | Gazipur | 7, 12, 14 | 0.93 | 14 Oct |
| BLF | Bluefinch Sweaters Ltd. | Zirabo | Dhaka | 3, 5, 7 | 0.90 | 14 Oct |
| CPL | Copperleaf Knit Ltd. | DEPZ, Savar | Dhaka | 12, 14 | 0.95 | 14 Oct |
| TLG | Tallgrass Knitwear Ltd. | Sreepur | Gazipur | 5, 7, 12 | 0.88 | 14 Oct |
| RVS | Riverstone Sweaters Ltd. | Siddhirganj | Narayanganj | 3, 5, 7, 12 | 0.86 | 14 Oct |
| AMB | Amberline Knit Ltd. | CEPZ | Chattogram | 7, 12, 14 | 0.94 | 14 Oct |
| SVP | Silverpine Knitwear Ltd. | Tongi | Gazipur | 12, 14 | 0.92 | 14 Oct |
| LTF | Lanternfield Sweaters Ltd. | Mawna | Gazipur | 5, 7 | 0.87 | 14 Oct |
| MDW | Morningdew Knit Ltd. | Ashulia | Dhaka | 7, 12 | 0.91 | 14 Oct |
| OKH | Oakhaven Knitwear Ltd. | Kalurghat | Chattogram | 7, 12, 14 | 0.89 | **11 Oct** |
| WTH | Wildthorn Sweaters Ltd. | Kanchpur | Narayanganj | 3, 5, 7 | 0.85 | 14 Oct |
| BRW | Brightwool Knit Industries Ltd. | Kashimpur | Gazipur | 5, 7, 12 | 0.90 | 14 Oct |
| FNS | Fernstitch Knitwear Ltd. | Savar | Dhaka | 12, 14 | 0.96 | 14 Oct |
| HMR | Highmoor Sweaters Ltd. | Bhaluka | Mymensingh | 3, 5, 7 | 0.84 | **13 Oct** |
| CLB | Cloudberry Knit Ltd. | Chandra | Gazipur | 7, 12 | 0.92 | 14 Oct |
| SND | Sundial Knitwear Ltd. | Baipail, Ashulia | Dhaka | 7, 12, 14 | 0.93 | 14 Oct |
| RSG | Rosegate Sweaters Ltd. | Fatullah | Narayanganj | 3, 5 | 0.83 | 14 Oct |
| PBB | Pebblebrook Knit Ltd. | CEPZ | Chattogram | 12, 14 | 0.97 | **13 Oct** |
| WSM | Westmere Knitwear Ltd. | Tongi | Gazipur | 5, 7, 12 | 0.89 | 14 Oct |

GRL, IRB and SLM are the three higher-volume, lower-OTD factories that concentrate risk. The four with a
last report before 14 Oct are the "No update" factories on the demo day.

### Orders and schedule

- **1,287 POs** total (`PurchaseOrder`): **412 open** + ~875 shipped across 12 months
  (15 Oct 2025 – 14 Oct 2026, with a monthly shape that peaks in late summer/autumn).
- **PO lines** (`POLine` + `POLineSize`): colour × size breakdown per PO, department-appropriate size
  curves; `Order Qty = Σ lines`, each `Line Qty = Σ sizes`.
- **11 T&A milestones per PO** (`TAMilestone`): planned from the template, with revised/actual dates and
  status reflecting each PO's scenario (yarn delays, PP-sample slips, etc.).
- **Daily production** (`DailyProduction`): long-form rows, one per PO × stage × working day, from
  **1 Sep 2026** to each factory's last report (14 Oct for most; 12/11/13 Oct for the four quiet ones).
  Shipped POs carry their full production curve back to 1 Sep where it overlaps the window.
- **Inspections** (`Inspection`): inline / pre-final / final / final re-inspection at AQL II / 2.5 / 4.0;
  weaker factories (notably IRB) carry more failed-then-re-inspected lots.
- **Shipments** (`Shipment`): one per shipped PO, sea/air/sea-air, with air-freight cost and bearer; the
  presence of the row closes the PO.
- **Prediction snapshot**: one `PredictionRun` (trigger `seed`) with one `PredictionSnapshot` per open PO
  and one `FactoryStat` per factory, all `as_of = DEMO_TODAY`.

---

## 3. The hero and donor construction

### Hero PO `71010305` — 9 days late, Critical

Greyloom (GRL), style `KAW26-W-1736`, Lambswool V-neck Cardigan, Women's, 7GG, **9,600 pcs** at
USD 16.50 = **FOB 158,400**, planned ex-factory **29 Oct 2026**, weight 0.72 kg/pc.

What makes it 9 days late is built in deterministically:

- **Yarn in-house 8 days late** — yarn arrived 22 Sep against a 14 Sep plan (T&A yarn delay = 8).
- **Knitting** started 24 Sep and is nearly done (8,946 of 9,600).
- **Linking started only 7 Oct** — the factory's linking machines were tied up on other POs. From 7 Oct
  the PO runs **13 linking machines**, and the reported daily linking output (forced to
  330, 390, 415, 420, 410, 420, 415 over 7–14 Oct) gives an effective weighted rate of **411.1 pcs/day**.
- The engine needs **680 pcs/day** on linking to still make 29 Oct, so linking is the **bottleneck**:
  Completion Day N = 19 against **Available WD = 12** (Fridays 16 & 23 Oct excluded) → slack −7 WD,
  projected ex-factory **7 Nov**, **slip 9 calendar days**.
- **Risk score 76** (schedule 50 + T&A 12 for ≥8-day yarn lateness + factory OTD 12 + quality 0 +
  freshness 0) → band **Critical**; on-time probability **2%**; air-freight exposure
  `9,600 × 0.72 × (6.00 − 0.50) = USD 38,016`.

### Donor PO `71009573` — the slack that fixes the hero

Greyloom (GRL), Men's crew-neck pullover, 7GG, **14,400 pcs** at USD 11.20, ex-factory **10 Nov**, same
gauge and linking pool as the hero. It runs 22 linking machines at ~770.8 pcs/day and sits **9 days
early** (slack positive). Giving up **6 of its 22 linking machines** (22 → 16) moves it from 9 days early
to 5 days early — still comfortably on time — which is exactly the spare capacity the hero needs. This is
why the machine-reallocation recommendation (ASSUMPTION A-11) auto-resolves the hero's donor to
`71009573`.

### Hero what-if (must reproduce `00_Answer_Key.xlsx › Hero What-if`)

| Option | Linking pcs/day | Avail WD | N | Projected ex-factory | Slip | On time | Air avoided |
|---|---|---|---|---|---|---|---|
| Current plan | 411.1 | 12 | 19 | 7 Nov | 9 | No | 0 |
| +6 linking M/C (13→19) | 600.8 | 12 | 14 | 1 Nov | 3 | No | 0 |
| 2 Friday overtime (16, 23 Oct) | 411.1 | 14 | 19 | 4 Nov | 6 | No | 0 |
| **+6 M/C and 2 Fridays** | **600.8** | 14 | **14** | **29 Oct** | **0** | **Yes** | **USD 38,016** |
| Donor `71009573` today | 770.8 | 22 | 14 | 1 Nov | −9 | Yes | — |
| Donor after giving 6 M/C (22→16) | 560.6 | 22 | 18 | 5 Nov | −5 | Yes | — |

---

## 4. Exporting the six upload workbooks

With `--export-xlsx`, `seed_demo` also writes the six upload files (and the two demo uploads) to a target
directory, **structurally identical to `sample_data/`** — same sheet names, same column dictionaries
(each file's **Columns** sheet), same formatting. This lets the upload-flow demo ingest the very data the
database was seeded from, so a re-upload is a no-op (idempotent upserts) and a corrected file demonstrates
the error path.

- `01_Order_Book.xlsx` (PO Header + PO Lines), `02_TA_Calendar.xlsx`,
  `03_Factory_Daily_Production_Report.xlsx`, `04_Inspection_Log.xlsx`, `05_Factory_Master.xlsx`,
  `06_Shipment_Log.xlsx`.
- `demo_uploads/DPR_PBB_2026-10-14.xlsx` (clean, 3 rows) and
  `demo_uploads/DPR_HMR_2026-10-14_with_errors.xlsx` (8 rows, 3 deliberate errors) — see
  [`excel-templates.md`](excel-templates.md) for their exact expected outcomes.

The exporter reuses the generator's writers so the files match byte-for-byte what
`generate_sample_data.py` produces; `validate_sample_data.py` passes against them unchanged.

---

## 5. Fabricated ChromaDB knowledge base (ASSUMPTION A-08)

No unstructured documents exist in `sample_data/`, so `seed_demo` **deterministically generates
clearly-fictional English documents** and indexes them into ChromaDB so the assistant's citations
resolve. All names are fictional; the content is internally consistent with the seeded numbers. Generated
from the same `SEED`, so the corpus is identical every run:

- **Karbar sweater quality manual** — AQL II / 2.5 / 4.0 policy, the common defect list, measurement and
  weight tolerances, inline/pre-final/final/re-inspection flow.
- **T&A standards** — the 11-milestone template, the offset table, and what each milestone means
  (yarn booking through ex-factory), including the yarn-in-house → knitting-start rule.
- **22 factory profiles** — one per factory: location, gauges, machine mix, certifications and BSCI
  rating, washing capability, strengths/weaknesses, consistent with Factory Master.
- **Audit notes** — short fictional social/quality audit summaries per factory, aligned with each
  factory's BSCI rating and OTD/AQL behaviour.
- **Seeded PO comments** (`Comment`, also indexed) — a handful of merchandiser/QA notes on notable POs,
  including the hero (linking-capacity constraint, donor reallocation) so the demo questions have
  grounded evidence to cite.

Each document is stored with stable metadata (`{name, as_of}`) so assistant answers carry a source and an
"as of", matching the one-source-of-numbers rule.

---

## 6. `reset_demo`

`reset_demo` drops all demo-owned rows and re-seeds to the clean `DEMO_TODAY` state in one step
(seed → export optional → re-index ChromaDB), restoring the exact state the CEO demo starts from. It is
the recovery path if a live demo upload or a what-if leaves the database dirty. Operational details
(when to run it, environment guards, data safety) live in the deployment doc; `reset_demo` is the
canonical way to return to the seeded baseline.

---

## 7. Acceptance tests — answer-key parity

`seed_demo` must assert its output against the answer key before it reports success. These are the same
obligations as the engine's test suite (`ai/prediction-engine.md §11`); the command fails loudly if any
check misses.

### Headline KPIs (checklist the command asserts)

- [ ] Open POs = **412**; open pcs = **1,900,020**; open FOB = **USD 18,601,449**.
- [ ] Value at risk = **USD 2,400,006** across **48** POs (FOB of At risk + Critical + Late).
- [ ] Air-freight exposure = **USD 539,720**.
- [ ] October predicted on-time = **86.25%**.
- [ ] Top-3 factories by value at risk: **GRL 774,059 · IRB 477,578 · SLM 428,400 = 70.0%**.
- [ ] Factories reported today = **18 of 22**; missing **SLM (12 Oct), OKH (11 Oct), HMR (13 Oct),
      PBB (13 Oct)**.
- [ ] Rest-of-October outlook = **95 POs, 455,364 pcs, USD 4.88M** (Weekly Outlook sheet).

### Band counts (sum = 412)

- [ ] On track **354** · Watch **10** · At risk **28** · Critical **13** · Late **7**.

### Hero and donor

- [ ] Hero `71010305`: bottleneck **Linking**, bottleneck rate **411.1**, required **680**,
      Available WD **12**, N **19**, slack **−7**, projected **7 Nov 2026**, slip **9**, score **76**,
      band **Critical**, on-time probability **2%**, air avoided **USD 38,016**.
- [ ] Donor auto-resolves to `71009573`; the four what-if options and both donor rows reproduce the
      `Hero What-if` sheet exactly.

### Engine parity

- [ ] **`test_engine_matches_answer_key`** — every row of `Open PO Predictions` (band, score, projected
      ex-factory, slip, bottleneck, rates, probability, VaR, air exposure) reproduced within rounding.
- [ ] **`test_kpis_match_answer_key`** — the `KPIs` sheet reproduced (open counts, October on-time %, VaR,
      top-3 share, air exposure, band counts, weekly outlook).
- [ ] **`test_hero_whatif`** — all six `Hero What-if` rows reproduced.
- [ ] **`test_calendar`** — `wd_between`, `nth_wd`, `next_wd` against hand-checked dates (incl. overtime
      and holidays).
- [ ] **`test_pure_service`** — the engine module imports no Django ORM/view symbols.

The golden file for every value above is `sample_data/00_Answer_Key.xlsx` (sheets `KPIs`,
`Open PO Predictions`, `Factory Summary`, `Weekly Outlook`, `Hero What-if`, `Parameters`).
`sample_data/scripts/validate_sample_data.py` re-derives the answer key from the six upload files alone;
`seed_demo`'s acceptance tests assert the seeded database matches the same key.
