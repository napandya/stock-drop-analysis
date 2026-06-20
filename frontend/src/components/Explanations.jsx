// Per-company explanations of the worst drop event(s). Each reason shows the
// plain-language driver plus a small bar for its model contribution; the
// z-score (how abnormal the day was) is shown as text so nothing relies on the
// bar alone.
export function Explanations({ data }) {
  if (!data || !data.explanations) return null;
  const maxContrib = Math.max(
    0.0001,
    ...data.explanations.flatMap((c) =>
      c.events.flatMap((e) => e.reasons.map((r) => r.contribution))
    )
  );

  return (
    <article className="section-card" aria-labelledby="why-h">
      <p className="eyebrow">Per-company · drivers of the fall</p>
      <h2 id="why-h">{data.title}</h2>

      <div className="why-grid">
        {data.explanations.map((c) => (
          <div className="why-card" key={c.ticker}>
            <div className="why-head">
              <span className="why-ticker">{c.ticker}</span>
              <span className="why-sector">{c.sector}</span>
              <span className="why-count">{c.total_drops} drop days</span>
            </div>

            {c.events.length === 0 && (
              <p className="why-none">No qualifying drop in the selected window.</p>
            )}

            {c.events.map((e, i) => (
              <div className="why-event" key={i}>
                <div className="why-event-head">
                  <span className="why-date">{e.date}</span>
                  <span className="why-return">{e.return_pct}%</span>
                </div>
                <ul className="why-reasons">
                  {e.reasons.map((r) => (
                    <li key={r.feature}>
                      <div className="why-reason-text">
                        <span>{r.explanation}</span>
                        <span className="why-z" title="standard deviations from normal">
                          {r.z_score > 0 ? "+" : ""}
                          {r.z_score}σ
                        </span>
                      </div>
                      <span
                        className="why-bar"
                        style={{ width: `${(r.contribution / maxContrib) * 100}%` }}
                        aria-hidden="true"
                      />
                    </li>
                  ))}
                  {e.reasons.length === 0 && (
                    <li className="why-none">No single driver stood out.</li>
                  )}
                </ul>
              </div>
            ))}
          </div>
        ))}
      </div>
    </article>
  );
}
