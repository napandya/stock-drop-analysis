import { fmt, humanize } from "../format.js";

// Generic metrics table. Numeric columns are right-aligned and tagged so screen
// readers and sighted users get a consistent reading order.
export function MetricsTable({ rows, caption }) {
  if (!rows || !rows.length) return null;
  const cols = Object.keys(rows[0]);
  return (
    <div className="table-wrap" role="region" aria-label={caption} tabIndex={0}>
      <table>
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {cols.map((c) => {
              const isNum = typeof rows[0][c] === "number";
              return (
                <th key={c} scope="col" className={isNum ? "num" : undefined}>
                  {humanize(c)}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {cols.map((c) => {
                const isNum = typeof r[c] === "number";
                return (
                  <td key={c} className={isNum ? "num" : undefined}>
                    {String(fmt(r[c]))}
                  </td>
                );
              })}
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
