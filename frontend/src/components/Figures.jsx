import { FIG_CAPTIONS } from "../format.js";

// Base64 PNG figures from matplotlib. Each image carries a descriptive alt text
// (the caption) so the dashboard remains meaningful to screen-reader users.
export function Figures({ figures }) {
  const entries = Object.entries(figures || {});
  if (!entries.length) return null;
  return (
    <div className="figs">
      {entries.map(([name, b64]) => {
        const caption = FIG_CAPTIONS[name] || name;
        return (
          <figure className="fig" key={name}>
            <img src={`data:image/png;base64,${b64}`} alt={caption} loading="lazy" />
            <figcaption className="cap">{caption}</figcaption>
          </figure>
        );
      })}
    </div>
  );
}
