import { useMemo, useState } from "react";

const MIN = 2;
const MAX = 8;

// Pick companies to analyze: toggle from the curated catalog and/or add any
// other Yahoo symbol. Enforces the same 2–8 bound as the backend so the user
// gets immediate feedback instead of a 400.
export function TickerPicker({ catalog, onAnalyze, running }) {
  const [selected, setSelected] = useState(() => new Set());
  const [custom, setCustom] = useState("");

  const catalogSymbols = useMemo(() => new Set(catalog.map((c) => c.ticker)), [catalog]);
  const extras = [...selected].filter((s) => !catalogSymbols.has(s));

  const count = selected.size;
  const tooFew = count < MIN;
  const tooMany = count > MAX;
  const canAnalyze = !running && !tooFew && !tooMany;

  function toggle(sym) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(sym) ? next.delete(sym) : next.add(sym);
      return next;
    });
  }

  function addCustom(e) {
    e.preventDefault();
    const sym = custom.trim().toUpperCase();
    if (!sym) return;
    setSelected((prev) => new Set(prev).add(sym));
    setCustom("");
  }

  return (
    <section className="picker" aria-labelledby="picker-h">
      <div className="picker-head">
        <h2 id="picker-h">Select companies</h2>
        <p className="picker-sub">
          Choose {MIN}–{MAX} stocks; the models will rank the drivers and explain why each fell.
        </p>
      </div>

      <div className="chip-grid" role="group" aria-label="Catalog tickers">
        {catalog.map((c) => {
          const on = selected.has(c.ticker);
          return (
            <button
              key={c.ticker}
              type="button"
              className={`chip${on ? " on" : ""}`}
              aria-pressed={on}
              title={`${c.name} · ${c.sector}`}
              onClick={() => toggle(c.ticker)}
            >
              <span className="chip-sym">{c.ticker}</span>
              <span className="chip-name">{c.name}</span>
            </button>
          );
        })}
      </div>

      {extras.length > 0 && (
        <div className="chip-grid" role="group" aria-label="Custom tickers">
          {extras.map((sym) => (
            <button
              key={sym}
              type="button"
              className="chip on custom"
              aria-pressed="true"
              onClick={() => toggle(sym)}
              title="Remove"
            >
              <span className="chip-sym">{sym}</span>
              <span className="chip-name">custom ✕</span>
            </button>
          ))}
        </div>
      )}

      <div className="picker-actions">
        <form className="custom-add" onSubmit={addCustom}>
          <label htmlFor="custom-ticker" className="sr-only">
            Add a custom ticker symbol
          </label>
          <input
            id="custom-ticker"
            type="text"
            placeholder="Add symbol (e.g. ORCL)"
            value={custom}
            maxLength={8}
            autoComplete="off"
            onChange={(e) => setCustom(e.target.value)}
          />
          <button type="submit" className="btn-secondary" disabled={!custom.trim()}>
            Add
          </button>
        </form>

        <div className="picker-run">
          <span className={`count${tooMany ? " over" : ""}`} aria-live="polite">
            {count} selected
          </span>
          <button
            type="button"
            className="run-all"
            disabled={!canAnalyze}
            onClick={() => onAnalyze([...selected])}
          >
            {running ? "Analyzing…" : "Analyze selection"}
          </button>
        </div>
      </div>

      {tooMany && (
        <p className="picker-hint" role="alert">
          Please select at most {MAX} companies.
        </p>
      )}
    </section>
  );
}
