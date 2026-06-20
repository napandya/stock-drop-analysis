// Compact dataset summary shown in the top bar.
export function DatasetPills({ dataset }) {
  if (!dataset) return null;
  const ds = dataset;
  return (
    <div className="pills" aria-label="Dataset summary">
      {ds.synthetic ? (
        <span className="pill warn">
          <b>Synthetic</b> · preview only
        </span>
      ) : (
        <span className="pill live">
          <b>Live data</b>
        </span>
      )}
      <span className="pill">
        <b>{ds.rows.toLocaleString()}</b> stock-days
      </span>
      <span className="pill">
        <b>{ds.drop_events}</b> drops ({(ds.drop_rate * 100).toFixed(1)}%)
      </span>
      <span className="pill">
        {ds.date_start} → {ds.date_end}
      </span>
    </div>
  );
}
