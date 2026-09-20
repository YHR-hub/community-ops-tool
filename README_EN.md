# miHoYo Community Ops Tool (米游社运营助手) v4.2

<div align="center">

[简体中文](README.md) | [English](README_EN.md)

[![CI](https://github.com/YHR-hub/community-ops-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/YHR-hub/community-ops-tool/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Tests](https://img.shields.io/badge/tests-74%20passing-brightgreen)

**[⬇ Download exe (Windows, no install required)](https://github.com/YHR-hub/community-ops-tool/releases/latest)**

</div>

A full-workflow desktop tool for game community operations, built for the daily work of
operating miHoYo titles (Genshin Impact · Honkai: Star Rail · Zenless Zone Zero · Honkai Impact 3rd).
Covers metric ingestion, version management, retention analysis, anomaly attribution,
a daily-brief operations agent, and report delivery.

## Highlights

| Module | What it does |
|--------|--------------|
| Overview | KPI cards with WoW deltas, dual-axis DAU/engagement trend, risk feed (manually logged + **real-time anomaly detection**), **one-click daily briefing agent** |
| Data | Daily metric ingestion (duplicate-aware overwrite, retention validation), CSV import/export, character usage rate, community platform heat |
| Versions | Status board / Gantt timeline / version detail drawer (tasks · risks · budget · character usage) |
| Analysis | Four-dimension version health check, AI ops advisor (7 scenarios), two-version comparison, **retention analysis (curves + health line + cross-attribution)** |
| Reports | Four-section smart report, periodic reports (weekly/monthly/quarterly, CSV export), report archive |

## The Daily-Brief Agent: Perceive → Decide → Compose

The core piece (v4.2, `agent.py`) answers one question: **where should the boundary of AI
judgment sit in operations work?**

1. **Perceive** — four probes: data freshness, retention drop against baseline, retention ×
   engagement cross-validation, overdue tasks, budget headroom. Thresholds are **shared
   constants from the data layer** (`ANOMALY_RULES` / `valid_retention`) — the agent and the
   data layer never disagree about what "a drop" means.
2. **Decide** — deterministic rule routing. A retention drop triggers a cross-check against
   engagement: if engagement fell too, attribution points to content fatigue; if engagement
   held, to acquisition-channel quality. Every anomaly maps to a concrete action.
3. **Compose** — headline + leveled alerts (danger/warn/info) + recommended actions + a full
   **decision trace**. The LLM only polishes wording (opt-in via API key, auto-fallback to
   rule templates on any failure). **Rules own correctness; the LLM owns phrasing.**

Two design decisions worth calling out:

- **Data judgment stays deterministic.** Letting an LLM judge the numbers is non-reproducible
  and unauditable — operations owns its conclusions. Same data in, same brief out.
- **The trace is a first-class feature.** Operations AI that cannot explain itself will not
  be trusted. Every run records what it perceived, why it cross-checked, what it found,
  and where it attributed — visible in the UI.

## Data Layer & Engineering

- **SQLite**: WAL mode + busy_timeout + 13 indexes + 4 unique constraints. Retention metrics
  use aggregated BI-style daily rates (not user-level cohorts — ops tooling rarely gets
  row-level logs; `0` means "not measured", never "0%").
- **Anomaly detection**: latest data day vs trailing 7-day mean (calendar-day comparisons
  produce false positives; weekly seasonality is absorbed by the mean). Dimension-specific
  thresholds: DAU ±10%, new users ±12%, engagement ±0.5pp. Multi-game DAU anomalies are
  decomposed per game, counting only games with data that day.
- **74 automated tests** (smoke 40 + flow 34), including layout-invariant assertions verified
  by fault injection — remove a styling height and the suite goes red, proving the tests can
  actually catch regressions. CI runs the full suite on every push (Windows runner).
- **Packaging**: single-file PyInstaller exe; in frozen mode the database lands next to the
  executable (`data/`), so user data survives restarts.

## Run It

### Download (Windows)
Grab the latest exe from [Releases](https://github.com/YHR-hub/community-ops-tool/releases/latest) —
no Python needed. First launch creates an empty database; click "Load demo data" on the
overview page for the full experience.

### From source
```bash
pip install customtkinter openai pillow
python main.py
```

### Demo data
```bash
python seed_demo.py           # fill if empty
python seed_demo.py --force   # regenerate (aligned to HSR 3.8)
```

### Tests
```bash
python smoke_test.py          # 40 items
python flow_test.py --force   # 34 items, re-seeds demo data
```

### Build
```bash
pyinstaller --onefile --noconsole --name "MiyoOpsTool" \
  --icon "icon.ico" \
  --hidden-import "openai" --hidden-import "customtkinter" --hidden-import "PIL" \
  --collect-data "customtkinter" --collect-submodules "customtkinter" \
  --exclude-module torch --exclude-module torchaudio --exclude-module torchvision \
  --exclude-module scipy --exclude-module matplotlib --exclude-module pandas \
  main.py
```

> Packaging note: `openai`'s dependency analysis can pull local `torch` (GBs of CUDA
> libraries) into the build graph and stall Analysis for 10+ minutes — the excludes above
> are mandatory. Do not use `--collect-all`; customtkinter only needs data + submodules.

## Project Structure

```
community-ops-tool/
├── main.py                  # Entry + App shell + sidebar + command palette
├── agent.py                 # Daily-brief agent: perceive → decide → compose (with trace)
├── theme.py                 # Design system: luminance ladder / semantic colors / type
├── components.py            # Reusable components: Card / StatCard / Badge / EmptyState
├── icons.py                 # 33 hand-drawn Canvas vector icons
├── charts.py                # Adaptive charts: Line / Bar / Gantt / ProgressBar
├── db.py                    # Data layer: schema / indexes / queries / input validation
├── seed_demo.py             # Demo data generator (HSR 3.8)
├── smoke_test.py            # Render smoke tests (incl. layout invariants)
├── flow_test.py             # Business-flow tests
├── capture.py               # Screenshot acceptance script
├── views/                   # overview / data / versions / analysis / report
└── _legacy/                 # v2.x views (deprecated, kept for reference)
```

## License

[MIT](LICENSE)
