const ATTR_LABEL = {
  "market/sector-driven": "Market / sector-driven",
  "stock-specific": "Stock-specific",
  mixed: "Mixed",
};

// Earnings catalyst tag: whether the fall landed on/around an earnings report,
// and the EPS surprise (a miss is the classic single-name crash cause).
function EarningsTag({ earnings }) {
  if (!earnings || !earnings.near_earnings) return null;
  const s = earnings.eps_surprise;
  let label = "On earnings";
  if (s != null) label = s < 0 ? `Earnings miss ${s}%` : `Earnings beat +${s}%, fell anyway`;
  return <span className={`attr-badge earnings${s != null && s < 0 ? " miss" : ""}`}>{label}</span>;
}

// A badge classifying the fall as systematic vs idiosyncratic, plus any macro
// context (rate move that day, proximity to an FOMC meeting).
function Attribution({ attribution, macro, earnings }) {
  const a = attribution || {};
  const cls =
    a.type === "stock-specific" ? "idio" : a.type === "market/sector-driven" ? "sys" : "mix";
  const share =
    a.type === "stock-specific"
      ? a.idio_share
      : a.type === "market/sector-driven"
      ? a.systematic_share
      : null;

  const bp = macro && macro.rate_chg_bp;
  const rateNote =
    bp != null && Math.abs(bp) >= 5 ? `10y ${bp > 0 ? "+" : ""}${bp}bp` : null;

  return (
    <div className="why-tags">
      {ATTR_LABEL[a.type] && (
        <span className={`attr-badge ${cls}`}>
          {ATTR_LABEL[a.type]}
          {share != null && <b> {Math.round(share * 100)}%</b>}
        </span>
      )}
      <EarningsTag earnings={earnings} />
      {rateNote && <span className="macro-note">{rateNote}</span>}
      {macro && macro.near_fomc && <span className="macro-note">near FOMC</span>}
    </div>
  );
}

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

      <p className="section-intro">
        For each company we take its worst drop day(s) and rank the drivers by
        <strong> model importance × how abnormal each was that day</strong> (only in the
        direction associated with drops). The badges classify the fall; the bar shows each
        driver's contribution and <strong>σ</strong> is how many standard deviations it sat
        from normal.
      </p>

      <ul className="why-legend" aria-label="Legend">
        <li><span className="attr-badge sys">Market / sector-driven</span> the broad market or sector did most of it (beta)</li>
        <li><span className="attr-badge idio">Stock-specific</span> something specific to the company drove it</li>
        <li><span className="attr-badge earnings miss">Earnings miss</span> fell on/around an earnings report, with the EPS surprise</li>
        <li><span className="macro-note">10y ±bp / near FOMC</span> a rates/macro catalyst that day</li>
      </ul>

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
                <Attribution attribution={e.attribution} macro={e.macro} earnings={e.earnings} />
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
