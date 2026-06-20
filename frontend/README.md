# Frontend — Drop-Driver Analysis dashboard

A **React + Vite** single-page app that calls the backend API and renders the
analysis as accessible tables and figures. The theme is a light slate + indigo
palette built to **WCAG 2.1 AA** (contrast ≥ 4.5:1, visible focus, reduced-motion
support, semantic landmarks, keyboard-navigable section list).

## Prerequisites

- **Node.js 18+** and npm (<https://nodejs.org>). Check with `node --version`.

## Install

```bash
cd frontend
npm install
```

## Develop (hot reload)

Run the backend and the Vite dev server in two terminals:

```bash
# terminal 1 — backend (from backend/)
python -m uvicorn app.main:app --reload --port 8000

# terminal 2 — frontend (from frontend/)
npm run dev
```

Open <http://127.0.0.1:5173>. Vite proxies `/api/*` to the backend on `:8000`
(configured in `vite.config.js`), so there is nothing else to wire up.

## Build & present (single origin)

```bash
npm run build      # emits frontend/dist/
```

Then start the backend and open <http://127.0.0.1:8000> — FastAPI automatically
serves `frontend/dist/` when it exists, so the whole app runs from one URL with
no Node process. Ideal for a presentation. (Re-run `npm run build` after UI
changes.)

## Structure

```
frontend/
├─ index.html            Vite entry (mounts #root)
├─ vite.config.js        dev server + /api proxy + build config
├─ package.json
└─ src/
   ├─ main.jsx           React bootstrap
   ├─ App.jsx            layout, state, data fetching
   ├─ api.js             API client (/api/health, /sections, /analyze)
   ├─ format.js          number/label formatting + figure captions
   ├─ styles.css         light WCAG-AA theme (CSS variables)
   └─ components/        Sidebar, DatasetPills, SectionCard, Tables, Figures, States
```

## Accessibility notes

- Skip-to-results link, `<nav>`/`<main>` landmarks, real `<button>` nav items.
- Results region is an `aria-live` polite region; loading/errors announce.
- Figures carry descriptive `alt` text; importance bars are decorative only —
  the numeric value is always shown as text, so nothing depends on color.
- All interactive elements show a clear focus ring; motion honors
  `prefers-reduced-motion`.
