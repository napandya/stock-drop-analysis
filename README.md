# Stock Drop-Driver Analysis

A full-stack application that identifies and **ranks the drivers behind significant
stock price drops** (ITS 836 course project). A FastAPI backend runs the four
analysis sections; a React + Vite dashboard visualises the metrics and figures.

```
stock_drops_app/
├── backend/      FastAPI app, models, tests
└── frontend/     React + Vite dashboard (light, WCAG 2.1 AA)
```

---

## Architecture

| Layer | Tech | Responsibility |
|-------|------|----------------|
| **Backend** | FastAPI + scikit-learn + XGBoost | data pipeline, four model sections, JSON API |
| **Frontend** | React 18 + Vite | accessible (WCAG 2.1 AA) dashboard that calls the API and renders tables + figures |

Once the frontend is built (`npm run build`), the backend serves the bundle, so a
single process gives you the whole app. For UI development, run the Vite dev
server alongside the backend — see [frontend/README.md](frontend/README.md).

### Backend layout (best-practice package)

```
backend/app/
├── config.py            typed settings (pydantic-settings, env-overridable)
├── exceptions.py        domain exception hierarchy
├── logging_config.py    structured logging (no print)
├── main.py              FastAPI app + global exception handlers
├── core/
│   ├── features.py      pure feature engineering + drop labelling
│   ├── synthetic.py     offline synthetic data generator
│   └── data_pipeline.py loaders with retry/backoff + caching + fallback
├── models/              one module per member (regression, classification,
│                        ensembles, clustering) returning metrics + base64 figures
└── services/            orchestration between API and models
backend/tests/           pytest suite (features, pipeline, resiliency, models, API)
```

Engineering practices baked in: typed settings and responses, a custom exception
hierarchy mapped to HTTP status codes, **retry with exponential backoff** on every
external data call (`tenacity`), graceful synthetic fallback, in-process caching,
logging instead of `print`, and a full **pytest** suite that runs offline.

---

## ML methods

The task is framed around two targets per stock-day: a binary label
**`is_drop`** (did the stock fall more than the threshold — default −5% — in one
day?) and the continuous daily return **`ret_1d`**. Both are explained by nine
engineered driver features (`market_ret`, `volume_z`, `volatility_20d`,
`ret_prev`, `momentum_5d`, `vix`, `vix_change`, `treasury_10y`, `cpi_yoy`). The
analysis is split into four sections:

| Section | Type | Techniques | Reported |
|---------|------|------------|----------|
| **1 · Regression** | Supervised (magnitude) | Simple & Multiple **Linear Regression**, **Decision Tree** regressor | R², MAE, RMSE |
| **2 · Classification & Sentiment** | Supervised + NLP | **Logistic Regression** & **Gaussian Naive Bayes** for drop vs. no-drop; **TF-IDF** + **Multinomial NB** / **Logistic Regression** and a **VADER** lexicon baseline for news sentiment | accuracy, precision/recall/F1, confusion matrices |
| **3 · Ensembles & driver ranking** | Supervised | **Random Forest** + **XGBoost** classifiers; feature importances averaged across both | accuracy, F1, **ROC-AUC**, ranked drop drivers |
| **4 · Clustering & anomalies** | Unsupervised | **K-Means** (k chosen by **silhouette**), **PCA** for projection, **Isolation Forest** for anomaly detection | cluster profiles, drops recovered |

Cross-cutting practices: feature scaling (`StandardScaler`) for scale-sensitive
models, class-imbalance handling (balanced weights / `scale_pos_weight`), a fixed
`random_state` for reproducibility, and deliberate **leakage avoidance** —
`ret_1d` is excluded from the feature set because `is_drop` is derived from it.

### Time-aware validation

The stock models predict a same-day outcome, so the supervised sections
(regression, drop-classification, ensembles) are evaluated with a **chronological
out-of-sample split** (last 30% of dates) plus **purged walk-forward CV** — an
expanding window with a 5-day embargo between train and test, since several
features use trailing windows that would otherwise straddle the boundary
(`core/validation.py`). Each section reports the mean ± std of its metrics across
folds. This replaces a random `train_test_split`, which trained on the future and
inflated the scores; the walk-forward F1 on the rare drop class is far more sober
and honest. (The NLP sentiment task keeps a random split — it is not temporal;
clustering/anomaly detection is unsupervised.)

### Drop attribution: systematic vs. idiosyncratic

A fall is only "explained" once you know whether the stock dropped *because the
market/sector dropped* (beta) or because something hit the name specifically. So
each day's return is decomposed via a **trailing-window regression on the market
and its sector ETF** (no look-ahead): `systematic_ret = β_mkt·market + β_sec·sector`,
and `idio_ret = ret − systematic`. Each drop is then classified **market/sector-driven**,
**stock-specific** or **mixed** (`core/factors.py`). Macro context is attached too
(`core/macro_calendar.py`): the same-day **10-year yield move (bp)** as an unbiased
rate-shock proxy, and proximity to a **scheduled FOMC date**. These are
attribution-only signals — never model features (they are same-day, so using them
to predict would be leakage). *Honest limitation:* true CPI/PCE/dot-plot
**surprises** (actual vs. consensus) need a paid macro feed and are not included;
the rate-move magnitude is the proxy used instead.

**Earnings catalysts** (`core/earnings.py`): the most common single-name crash
cause. Yahoo provides announcement dates **and** the EPS surprise (reported vs.
consensus) back ~12 years for established names, so each drop is tagged
`near_earnings` with the matched `eps_surprise` — e.g. META's −26% on
2022-02-03 lands on a −4.1% earnings miss. Best-effort and date-aligned (it
degrades to "untagged" if Yahoo's earnings feed is unavailable), and like the
other attribution layers it is never a model feature.

---

## Quick start

```bash
cd backend
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows (Git Bash)
source venv/Scripts/activate

# Windows (PowerShell)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
venv\Scripts\Activate.ps1

# Windows (Command Prompt)
venv\Scripts\activate.bat

pip install -r requirements.txt

# run the API (and the dashboard, once it's been built)
python -m uvicorn app.main:app --reload --port 8000
```

> **Python version:** use CPython 3.11–3.13 for the smoothest install. The data
> stack runs on 3.14 too, but `setuptools` must be present (it ships in
> `requirements.txt`) because `distutils` was removed from the stdlib in 3.12.

### Frontend (one-time build, then served by the backend)

```bash
cd frontend
npm install
npm run build          # emits frontend/dist/, which the backend serves
```

For hot-reload UI development run `npm run dev` instead (Vite on :5173, proxies
`/api` to the backend). Full details in [frontend/README.md](frontend/README.md).

These activation commands assume your current directory is `backend/`. If you are
already inside `backend/venv/`, use `source Scripts/activate` in Git Bash or move
back up one level before following the quick-start commands.

If PowerShell reports that scripts are disabled on your system, the
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` command above only
relaxes the policy for the current shell session and avoids changing the machine
or user-wide execution policy.

Open <http://127.0.0.1:8000> and click a section, or **Run full analysis**.

### Offline preview (no internet / no data)

```bash
USE_SYNTHETIC=true python -m uvicorn app.main:app --port 8000
```

The dashboard shows a red **“Synthetic · preview only”** pill in this mode. These
numbers are illustrative — switch it off for anything that goes in the paper.

---

## Real data

- **Prices, macro & earnings** download automatically on first request (yfinance
  + FRED). The default study window is ~10 years (2015–2024) for more regimes,
  walk-forward folds and earnings events; override via `DATE_START`/`DATE_END`.
- **News sentiment** (Member 2): the FinancialPhraseBank dataset
  (`ankurzing/sentiment-analysis-for-financial-news`, CC BY-NC-SA — see
  `backend/data/License.txt`) ships in the repo. By default the model trains on
  the **>75% annotator-agreement** subset (`Sentences_75Agree.txt`); set
  `SENTIMENT_AGREEMENT` to `all` (100%, cleanest), `66`, `50`, or `csv` to use a
  different subset (higher agreement = less label noise = higher accuracy). With
  no dataset present it falls back to a tiny built-in sample (flagged with a
  warning).

Configure tickers, dates, and the drop threshold in `backend/app/config.py` or via
environment variables (e.g. `DROP_THRESHOLD=-0.07`).

---

## Tests

```bash
cd backend
python -m pytest          # all tests run on synthetic data, no network needed
```

---

## API reference

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/health` | status, data mode, configured tickers |
| GET | `/api/sections` | the four available analysis sections |
| GET | `/api/tickers` | curated ticker catalog for the picker |
| GET | `/api/analyze/{section}` | metrics + figures for one section (default universe) |
| GET | `/api/analyze` | the full pipeline on the default universe |
| POST | `/api/analyze` | full pipeline on a **chosen** set of tickers, plus per-company explanations — body `{"tickers": ["AAPL", "NVDA", …]}` (2–8 symbols) |

Errors return a typed JSON body, e.g. `{"error": "DataSourceError", "detail": "..."}`,
with the matching HTTP status (400 invalid tickers, 503 upstream down, 422 insufficient data, 500 model error).

### Pick companies & explain their falls

`POST /api/analyze` runs all four sections on a user-selected universe and adds an
`explanations` block: for each stock it finds the worst drop day(s) and ranks the
drivers by **model importance × how abnormal the feature was that day** (in the
drop-associated direction), turning them into plain-language reasons (e.g. "the
broad market sold off sharply", "trading volume was abnormally high"). The
frontend exposes this as a ticker picker (curated list + custom symbols) and a
"Why these stocks fell" panel.
