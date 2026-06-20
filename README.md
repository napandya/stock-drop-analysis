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

- **Prices & macro** download automatically on first request (yfinance + FRED).
- **News sentiment** (Member 2): download the Kaggle FinancialPhraseBank
  (`ankurzing/sentiment-analysis-for-financial-news`) and put `all-data.csv` in
  `backend/data/`. Without it, that one model falls back to a tiny sample.

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
| GET | `/api/analyze/{section}` | metrics + figures for one section |
| GET | `/api/analyze` | the full pipeline (all four sections) |

Errors return a typed JSON body, e.g. `{"error": "DataSourceError", "detail": "..."}`,
with the matching HTTP status (503 upstream down, 422 insufficient data, 500 model error).
