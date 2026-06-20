// Display helpers shared across components.

export const FIG_CAPTIONS = {
  pred_vs_actual: "Predicted vs. actual daily return",
  drop_confusion: "Drop vs. no-drop confusion matrix",
  sentiment_confusion: "News-sentiment confusion matrix",
  feature_importance: "Drivers ranked by importance",
  roc: "ROC curves (Random Forest vs. XGBoost)",
  elbow: "Elbow & silhouette for k",
  clusters: "Drop-event clusters (PCA projection)",
};

// Numbers get a fixed 4-dp; integers stay whole; missing values render as an
// em dash (a metric that doesn't apply to a row) rather than "undefined".
export const fmt = (v) => {
  if (v === null || v === undefined || (typeof v === "number" && Number.isNaN(v))) return "—";
  return typeof v === "number" ? (Number.isInteger(v) ? v.toLocaleString() : v.toFixed(4)) : v;
};

// "ret_1d" -> "ret 1d" for human-readable table headers / driver names.
export const humanize = (s) => String(s).replace(/_/g, " ");

// Plain-English, one-line description of what each analysis section does and
// how to read it. Keyed by section key.
export const SECTION_INTRO = {
  regression:
    "Predicts the size of each day's return from the drivers. It answers “how much of the move can the drivers explain?” — read the fit metrics below (higher R², lower error = better).",
  classification:
    "Two separate tasks. (A) Drop classification: can the drivers flag a day as a “drop” vs. a normal day? (B) News sentiment: is a financial headline positive, negative or neutral? The first rows report the drop task (precision/recall/F1 on the drop class); the last rows report the sentiment models (accuracy only).",
  ensembles:
    "Random Forest and XGBoost learn which drivers best separate drop days from normal days. Their averaged importances rank the drivers — this is the project's headline “what drives drops” answer.",
  clustering:
    "Unsupervised: groups drop events into recurring “types”, and separately flags anomalous days with an Isolation Forest — all without using the drop label.",
};

// Definitions of the metrics shown in each section.
export const SECTION_GLOSSARY = {
  regression: [
    ["R²", "Share of the return's variation the model explains (1.0 = perfect, 0 = no better than the average)."],
    ["MAE", "Mean absolute error — the average size of the prediction miss (smaller is better)."],
    ["RMSE", "Root mean squared error — like MAE but penalises big misses more."],
  ],
  classification: [
    ["accuracy", "Share of all days classified correctly. Misleading when drops are rare — a model can score high by always saying “no drop”."],
    ["precision (drop)", "Of the days it called a drop, how many really were."],
    ["recall (drop)", "Of the actual drops, how many it caught."],
    ["F1 (drop)", "Balance of precision and recall on the drop class — the honest score for a rare event."],
  ],
  ensembles: [
    ["importance", "How much a driver contributes to separating drops from normal days (shares sum to ~1 across drivers)."],
    ["accuracy", "Share of days classified correctly (inflated by class imbalance)."],
    ["F1", "Precision/recall balance on the drop class — the realistic score."],
    ["ROC-AUC", "Probability the model ranks a random drop above a random non-drop (0.5 = coin flip, 1.0 = perfect)."],
  ],
  clustering: [
    ["clusters (k)", "Number of drop-event “types” found, chosen by the silhouette score."],
    ["anomalies flagged", "Days the Isolation Forest marked unusual, without seeing the drop label."],
    ["drops recovered", "Share of real drops that fell inside those flagged anomalies."],
  ],
};

// Plain-English meaning of each driver feature (used in the ranking + reasons).
export const FEATURE_GLOSSARY = {
  market_ret: "the broad market's return that day (S&P 500)",
  sector_ret: "the stock's sector return that day (sector ETF)",
  volume_z: "trading volume vs. its normal level, in standard deviations",
  volatility_20d: "how choppy the stock has been over the last 20 days",
  ret_prev: "the previous day's return",
  momentum_5d: "the stock's 5-day cumulative return (recent trend)",
  vix: "the market's “fear gauge” — expected volatility",
  vix_change: "the day's change in the VIX",
  treasury_10y: "the 10-year US Treasury yield (interest rates)",
  cpi_yoy: "year-over-year inflation (CPI)",
};
