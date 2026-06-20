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
