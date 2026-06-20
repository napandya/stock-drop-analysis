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

// Numbers get a fixed 4-dp; integers stay whole; everything else passes through.
export const fmt = (v) =>
  typeof v === "number" ? (Number.isInteger(v) ? v.toLocaleString() : v.toFixed(4)) : v;

// "ret_1d" -> "ret 1d" for human-readable table headers / driver names.
export const humanize = (s) => String(s).replace(/_/g, " ");
