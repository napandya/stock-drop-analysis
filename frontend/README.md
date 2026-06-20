# Frontend — Drop-Driver Analysis dashboard

A dependency-free dashboard (plain HTML/CSS/JS) that calls the backend API and
renders the analysis as tables and figures.

- `index.html` — layout and the declining-sparkline signature mark
- `styles.css` — deep-ink theme; signal-red is reserved for declines
- `app.js` — fetches `/api/*`, renders sections, handles loading/error states

## Running

The frontend is served by the backend, so just start the backend and open its URL
(<http://127.0.0.1:8000>). It calls the API at the same origin (`/api`), so there
is nothing to configure.

If you want to serve the frontend separately, point it at the backend by changing
the `API` constant at the top of `app.js` to the backend's full URL (the backend
already enables permissive CORS).

## Notes

- Figures arrive as base64 PNGs from the API and render inline — no asset pipeline.
- Responsive down to mobile; respects `prefers-reduced-motion`.
- The data-mode pill turns red when the backend is running on synthetic data.
