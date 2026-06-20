import { MetricsTable, RankingTable } from "./Tables.jsx";
import { Figures } from "./Figures.jsx";

function StatRow({ stats }) {
  return (
    <div className="stat-row">
      {stats.map(([val, lab, accent], i) => (
        <div className={`stat${accent ? " accent" : ""}`} key={i}>
          <div className="val">{val}</div>
          <div className="lab">{lab}</div>
        </div>
      ))}
    </div>
  );
}

// Out-of-sample validation summary: the honest, time-ordered metrics (mean ± std
// across walk-forward folds) rather than a leaky random split.
function Validation({ validation: v }) {
  if (!v || !v.cv || !v.cv.length) return null;
  return (
    <div className="validation" role="note">
      <span className="validation-label">
        Out-of-sample · {v.n_folds}-fold walk-forward · {v.embargo_days}d embargo
      </span>
      <span className="validation-metrics">
        {v.cv.map((c) => (
          <span className="cv-metric" key={c.metric}>
            {c.metric} <b>{c.mean}</b> ± {c.std}
          </span>
        ))}
      </span>
    </div>
  );
}

// Renders one analysis section's results. Mirrors the shape returned by the
// backend (`ranking`, `metrics`, `anomaly_detection`, `cluster_profiles`,
// `figures`, `warnings`) and only shows the keys that are present.
export function SectionCard({ index, sectionKey, data }) {
  const a = data.anomaly_detection;
  return (
    <article className="section-card" aria-labelledby={`sec-${sectionKey}`}>
      <p className="eyebrow">
        Member {index} · {sectionKey}
      </p>
      <h2 id={`sec-${sectionKey}`}>{data.title || sectionKey}</h2>

      {(data.warnings || []).map((w, i) => (
        <p className="warn-line" key={i} role="note">
          <span aria-hidden="true">⚠ </span>
          {w}
        </p>
      ))}

      {data.ranking && <RankingTable ranking={data.ranking} />}
      {data.metrics && <MetricsTable rows={data.metrics} caption={`${data.title} metrics`} />}
      {data.validation && <Validation validation={data.validation} />}

      {a && (
        <StatRow
          stats={[
            [data.best_k ?? "—", "clusters (k)"],
            [a.anomalies_flagged, "anomalies flagged"],
            [`${Math.round(a.recall_of_drops * 100)}%`, "drops recovered", true],
          ]}
        />
      )}

      {data.cluster_profiles && (
        <MetricsTable rows={data.cluster_profiles} caption="Cluster profiles" />
      )}
      {data.figures && <Figures figures={data.figures} />}
    </article>
  );
}
