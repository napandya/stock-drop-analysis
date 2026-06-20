import { useEffect, useState, useCallback } from "react";
import {
  getHealth,
  getSections,
  getTickers,
  analyzeSection,
  analyzeAll,
  analyzeSelection,
} from "./api.js";
import { Sidebar } from "./components/Sidebar.jsx";
import { DatasetPills } from "./components/DatasetPills.jsx";
import { SectionCard } from "./components/SectionCard.jsx";
import { TickerPicker } from "./components/TickerPicker.jsx";
import { Explanations } from "./components/Explanations.jsx";
import { Loading, ErrorBanner, EmptyState } from "./components/States.jsx";

export default function App() {
  const [sections, setSections] = useState([]);
  const [indexByKey, setIndexByKey] = useState({});
  const [catalog, setCatalog] = useState([]);
  const [health, setHealth] = useState({ state: "", text: "checking backend…" });

  const [activeKey, setActiveKey] = useState(null);
  const [dataset, setDataset] = useState(null);
  const [results, setResults] = useState(null); // { mode: "one"|"all", payload }
  const [status, setStatus] = useState({ phase: "idle", message: "", error: null });

  // ---- bootstrap: health + section list ----------------------------------
  useEffect(() => {
    getHealth()
      .then((h) =>
        setHealth({ state: "ok", text: h.synthetic ? "backend ok · synthetic" : "backend ok · live" })
      )
      .catch(() => setHealth({ state: "down", text: "backend offline" }));

    getSections()
      .then(({ sections }) => {
        setSections(sections);
        setIndexByKey(Object.fromEntries(sections.map((s, i) => [s.key, i + 1])));
      })
      .catch((error) => setStatus({ phase: "error", message: "", error }));

    getTickers()
      .then(({ catalog }) => setCatalog(catalog))
      .catch(() => setCatalog([]));
  }, []);

  // ---- actions -----------------------------------------------------------
  const runSection = useCallback(async (key) => {
    setActiveKey(key);
    setStatus({ phase: "loading", message: `Running ${key}…`, error: null });
    try {
      const data = await analyzeSection(key);
      setDataset(data.dataset);
      setResults({ mode: "one", key, payload: data });
      setStatus({ phase: "done", message: "", error: null });
    } catch (error) {
      setStatus({ phase: "error", message: "", error });
    }
  }, []);

  const runAll = useCallback(async () => {
    setActiveKey(null);
    setStatus({ phase: "loading", message: "Running the full pipeline…", error: null });
    try {
      const data = await analyzeAll();
      setDataset(data.dataset);
      setResults({ mode: "all", payload: data });
      setStatus({ phase: "done", message: "", error: null });
    } catch (error) {
      setStatus({ phase: "error", message: "", error });
    }
  }, []);

  const runSelection = useCallback(async (tickers) => {
    setActiveKey(null);
    setStatus({
      phase: "loading",
      message: `Analyzing ${tickers.length} companies…`,
      error: null,
    });
    try {
      const data = await analyzeSelection(tickers);
      setDataset(data.dataset);
      setResults({ mode: "all", payload: data });
      setStatus({ phase: "done", message: "", error: null });
    } catch (error) {
      setStatus({ phase: "error", message: "", error });
    }
  }, []);

  // ---- results region ----------------------------------------------------
  function renderResults() {
    if (status.phase === "loading") return <Loading message={status.message} />;
    if (status.phase === "error") return <ErrorBanner error={status.error} />;
    if (!results) return <EmptyState />;

    if (results.mode === "one") {
      return (
        <SectionCard
          index={indexByKey[results.key]}
          sectionKey={results.key}
          data={results.payload}
        />
      );
    }
    return (
      <>
        {results.payload.explanations && (
          <Explanations data={results.payload.explanations} />
        )}
        {Object.entries(results.payload.sections).map(([key, sec]) => (
          <SectionCard key={key} index={indexByKey[key]} sectionKey={key} data={sec} />
        ))}
      </>
    );
  }

  return (
    <div className="shell">
      <a className="skip-link" href="#results">
        Skip to results
      </a>

      <Sidebar
        sections={sections}
        activeKey={activeKey}
        onSelect={runSection}
        onRunAll={runAll}
        running={status.phase === "loading"}
        health={health}
      />

      <main className="main">
        <header className="topbar">
          <div>
            <h1>Drivers Behind Significant Price Drops</h1>
            <p className="lede">
              Run each model section to identify and rank the factors most associated with sharp
              single-day stock declines.
            </p>
          </div>
          <DatasetPills dataset={dataset} />
        </header>

        {catalog.length > 0 && (
          <TickerPicker
            catalog={catalog}
            onAnalyze={runSelection}
            running={status.phase === "loading"}
          />
        )}

        <section id="results" aria-live="polite" aria-busy={status.phase === "loading"}>
          {renderResults()}
        </section>
      </main>
    </div>
  );
}
