import { fmt, humanize } from "../format.js";

// Generic metrics table. Numeric columns are right-aligned and tagged so screen
// readers and sighted users get a consistent reading order.
export function MetricsTable({ rows, caption }) {
  if (!rows || !rows.length) return null;
  // Union of keys across all rows so ragged rows (e.g. sentiment models that
  // only report accuracy) keep stable columns and show "—" for inapplicable
  // cells instead of "undefined".
  const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))];
  const isNumCol = (c) => rows.some((r) => typeof r[c] === "number");
  return (
    <div className="table-wrap" role="region" aria-label={caption} tabIndex={0}>
      <table>
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c} scope="col" className={isNumCol(c) ? "num" : undefined}>
                {humanize(c)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {cols.map((c) => (
                <td key={c} className={isNumCol(c) ? "num" : undefined}>
                  {String(fmt(r[c]))}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Ranked drivers with an importance bar. The bar is decorative; the numeric
// value is always present as text, so the table is fully usable without color.
export function RankingTable({ ranking }) {
  if (!ranking || !ranking.length) return null;
  const max = Math.max(...ranking.map((r) => r.importance)) || 1;
  return (
    <div className="table-wrap" role="region" aria-label="Driver ranking" tabIndex={0}>
      <table className="ranking">
        <thead>
          <tr>
            <th scope="col" className="num">#</th>
            <th scope="col">driver</th>
            <th scope="col" className="num">importance</th>
          </tr>
        </thead>
        <tbody>
          {ranking.map((r, i) => (
            <tr key={r.feature}>
              <td className="num rank-idx">{i + 1}</td>
              <td>{humanize(r.feature)}</td>
              <td className="num bar-cell">
                <span
                  className="bar"
                  style={{ width: `${(r.importance / max) * 100}%` }}
                  aria-hidden="true"
                />
                <span className="bar-val">{r.importance.toFixed(4)}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
