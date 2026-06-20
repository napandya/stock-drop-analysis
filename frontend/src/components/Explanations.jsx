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
// context (rate move that day, proximity to an FOMC meeting) and the global event.
function Attribution({ attribution, macro, earnings, event }) {
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
      {event && (
        <span className="attr-badge event-tag" title={event.description}>
          {event.label}
        </span>
      )}
      <EarningsTag earnings={earnings} />
      {rateNote && <span className="macro-note">{rateNote}</span>}
      {macro && macro.near_fomc && <span className="macro-note">near FOMC</span>}
    </div>
  );
}

// One-line plain-English story for a drop, woven from the signals we have:
// systematic vs idiosyncratic, the global event, earnings, and rates.
function narrative(e) {
  const a = e.attribution || {};
  const parts = [];
  if (a.type === "market/sector-driven")
    parts.push(`A market-wide selloff (${Math.round((a.systematic_share || 0) * 100)}% systematic)`);
  else if (a.type === "stock-specific")
    parts.push(`A stock-specific drop (${Math.round((a.idio_share || 0) * 100)}% idiosyncratic)`);
  else if (a.type === "mixed") parts.push("A mix of market and company-specific moves");
  else parts.push("A sharp drop");

  if (e.event) parts.push(`during the ${e.event.label}`);

  const s = e.earnings && e.earnings.near_earnings ? e.earnings.eps_surprise : undefined;
  if (e.earnings && e.earnings.near_earnings) {
    if (s != null && s < 0) parts.push(`on an earnings miss (${s}%)`);
    else if (s != null) parts.push(`around earnings (beat +${s}%)`);
    else parts.push("around its earnings report");
  }

  const bp = e.macro && e.macro.rate_chg_bp;
  if (bp != null && Math.abs(bp) >= 8) parts.push(`amid a ${bp > 0 ? "+" : ""}${bp}bp move in 10y yields`);
  else if (e.macro && e.macro.near_fomc) parts.push("near an FOMC meeting");

  return parts.join(" ") + ".";
}

// Aggregate context strip: which documented events the selection's drops
// clustered around. Fills the space below the cards with real analysis.
function MarketBackdrop({ breakdown }) {
  if (!breakdown || !breakdown.length) return null;
  return (
    <div className="backdrop" role="note">
      <span className="backdrop-label">Market backdrop · drops clustered around</span>
      <span className="backdrop-items">
        {breakdown.map((b) => (
          <span className="backdrop-chip" key={b.label}>
            {b.label} <b>×{b.count}</b>
          </span>
        ))}
      </span>
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
                <p className="why-narrative">{narrative(e)}</p>
                <Attribution
                  attribution={e.attribution}
                  macro={e.macro}
                  earnings={e.earnings}
                  event={e.event}
                />
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

      <MarketBackdrop breakdown={data.event_breakdown} />
    </article>
  );
}
