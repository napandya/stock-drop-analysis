// Loading, error and empty states. Loading/error use aria-live so assistive
// technology announces them when results change.
export function Loading({ message }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

export function ErrorBanner({ error }) {
  let detail = error.message;
  if (error.kind === "DataSourceError") {
    detail +=
      " — the market/macro source is unreachable. Check your connection, or set USE_SYNTHETIC=true to preview offline.";
  }
  return (
    <div className="error" role="alert">
      <h2>{error.kind || "Something went wrong"}</h2>
      <p>{detail}</p>
    </div>
  );
}

export function EmptyState() {
  return (
    <div className="empty">
      <h2>Pick an analysis to begin</h2>
      <p>
        Choose a section on the left, or run the full pipeline. Results appear here as metric
        tables and figures.
      </p>
    </div>
  );
}
