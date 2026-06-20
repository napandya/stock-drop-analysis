"""Member 2 -- Drop classification and news-sentiment NLP.

Part A: Logistic Regression and Naive Bayes for drop vs. no-drop.
Part B: TF-IDF sentiment classifier (NB + Logistic) on FinancialPhraseBank, with
        a VADER lexicon baseline. The sentiment task is decoupled from prices.
"""
from __future__ import annotations

import pandas as pd
import seaborn as sns
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix)
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import GaussianNB, MultinomialNB
from sklearn.preprocessing import StandardScaler

from app.config import Settings, get_settings
from app.core.features import FEATURE_COLUMNS
from app.core.validation import chrono_holdout, cv_summary
from app.exceptions import ModelError
from app.logging_config import get_logger
from app.models._plot import fig_to_base64

logger = get_logger(__name__)

_FALLBACK_SENTIMENT = [
    ("positive", "Company profit beats expectations and raises guidance"),
    ("positive", "Revenue grows strongly as demand surges this quarter"),
    ("negative", "Shares plunge after earnings miss and weak outlook"),
    ("negative", "Firm warns of falling sales amid rising costs and layoffs"),
    ("neutral", "The company will report quarterly results next week"),
    ("neutral", "Board schedules its annual shareholder meeting for May"),
] * 30


def _confusion_fig(cm, labels, title):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5, 4))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False,
                xticklabels=labels, yticklabels=labels, ax=ax)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title(title)
    return fig


def _drop_classification(data: pd.DataFrame, settings: Settings) -> dict:
    X, y = data[FEATURE_COLUMNS], data["is_drop"]
    # Chronological out-of-sample split (no look-ahead); cannot stratify by time.
    tr, te = chrono_holdout(data["date"])
    Xtr, Xte, ytr, yte = X[tr], X[te], y[tr], y[te]
    scaler = StandardScaler().fit(Xtr)
    Xtr_s, Xte_s = scaler.transform(Xtr), scaler.transform(Xte)

    models = {
        "Logistic Regression": LogisticRegression(
            max_iter=1000, class_weight="balanced",
            random_state=settings.random_state),
        "Naive Bayes": GaussianNB(),
    }
    rows, best = [], (-1, None, None)
    for name, model in models.items():
        model.fit(Xtr_s, ytr)
        pred = model.predict(Xte_s)
        acc = accuracy_score(yte, pred)
        # labels=[0, 1] so the report is well-defined even if a class is absent.
        rep = classification_report(yte, pred, labels=[0, 1],
                                    target_names=["no-drop", "drop"],
                                    zero_division=0, output_dict=True)
        rows.append({"model": name, "accuracy": float(acc),
                     "precision_drop": float(rep["drop"]["precision"]),
                     "recall_drop": float(rep["drop"]["recall"]),
                     "f1_drop": float(rep["drop"]["f1-score"])})
        if acc > best[0]:
            best = (acc, name, confusion_matrix(yte, pred, labels=[0, 1]))

    # Walk-forward stability of logistic regression (scaled per fold).
    def _fit_score(xa, ya, xb, yb):
        if ya.nunique() < 2 or yb.nunique() < 2:
            return None
        sc = StandardScaler().fit(xa)
        m = LogisticRegression(max_iter=1000, class_weight="balanced",
                               random_state=settings.random_state)
        m.fit(sc.transform(xa), ya)
        pred = m.predict(sc.transform(xb))
        return {"accuracy": float(accuracy_score(yb, pred)),
                "f1_drop": float(classification_report(
                    yb, pred, labels=[0, 1], output_dict=True,
                    zero_division=0)["1"]["f1-score"])}

    validation = cv_summary(X, y, data["date"], _fit_score)
    validation["scheme"] = "chronological holdout (last 30%, 5-day embargo) + walk-forward CV"
    fig = _confusion_fig(best[2], ["no-drop", "drop"],
                         f"Drop Classification ({best[1]})")
    return {"metrics": rows, "figure": fig_to_base64(fig), "validation": validation}


def _read_sentiment_dataset(path) -> pd.DataFrame:
    """Read FinancialPhraseBank in either shipped layout.

    ``.txt`` agreement files are ``sentence@sentiment`` (split on the *last* @,
    since a sentence may contain one); the ``.csv`` is ``sentiment,"headline"``.
    Both are latin-1 with assorted line endings.
    """
    if str(path).lower().endswith(".txt"):
        rows = []
        for line in path.read_text(encoding="latin-1").splitlines():
            line = line.strip()
            if "@" in line:
                sentence, sentiment = line.rsplit("@", 1)
                rows.append((sentiment.strip().lower(), sentence.strip()))
        return pd.DataFrame(rows, columns=["sentiment", "headline"])
    return pd.read_csv(path, encoding="latin-1", header=None,
                       names=["sentiment", "headline"])


def _load_sentiment(settings: Settings) -> tuple[pd.DataFrame, bool]:
    path = settings.sentiment_csv
    if path.exists():
        df = _read_sentiment_dataset(path).dropna()
        if not df.empty:
            logger.info("Sentiment dataset: %s (%d rows).", path.name, len(df))
            return df, True
    logger.warning("FinancialPhraseBank dataset not found at %s; using tiny sample.", path)
    return pd.DataFrame(_FALLBACK_SENTIMENT, columns=["sentiment", "headline"]), False


def _sentiment_classification(settings: Settings) -> dict:
    df, real = _load_sentiment(settings)
    Xtr, Xte, ytr, yte = train_test_split(
        df["headline"], df["sentiment"], test_size=0.25,
        random_state=settings.random_state, stratify=df["sentiment"])
    vec = TfidfVectorizer(stop_words="english", min_df=2, ngram_range=(1, 2))
    Xtr_v, Xte_v = vec.fit_transform(Xtr), vec.transform(Xte)

    rows, best = [], (-1, None, None, None)
    for name, model in {"Multinomial NB": MultinomialNB(),
                        "Logistic Regression": LogisticRegression(max_iter=1000)}.items():
        model.fit(Xtr_v, ytr)
        pred = model.predict(Xte_v)
        acc = accuracy_score(yte, pred)
        rows.append({"model": name, "accuracy": float(acc)})
        if acc > best[0]:
            labels = sorted(df["sentiment"].unique())
            best = (acc, name, confusion_matrix(yte, pred, labels=labels), labels)

    # VADER lexicon baseline.
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        sia = SentimentIntensityAnalyzer()

        def vlabel(t):
            c = sia.polarity_scores(t)["compound"]
            return "positive" if c >= 0.05 else "negative" if c <= -0.05 else "neutral"

        rows.append({"model": "VADER lexicon",
                     "accuracy": float(accuracy_score(yte, Xte.apply(vlabel)))})
    except Exception as exc:  # noqa: BLE001
        logger.warning("VADER baseline skipped: %s", exc)

    fig = _confusion_fig(best[2], best[3], f"Sentiment ({best[1]})")
    return {"metrics": rows, "figure": fig_to_base64(fig),
            "using_real_dataset": real}


def run(data: pd.DataFrame, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    try:
        drop = _drop_classification(data, settings)
        sent = _sentiment_classification(settings)
    except Exception as exc:  # noqa: BLE001
        raise ModelError(f"Classification/sentiment failed: {exc}") from exc

    logger.info("Member 2 classification + sentiment complete.")
    return {
        "title": "Classification & Sentiment",
        "metrics": drop["metrics"] + sent["metrics"],
        "validation": drop["validation"],   # time-series CV applies to the drop task
        "warnings": ([] if sent["using_real_dataset"]
                     else ["Sentiment used a tiny built-in sample; download the "
                           "FinancialPhraseBank CSV for reportable results."]),
        "figures": {"drop_confusion": drop["figure"],
                    "sentiment_confusion": sent["figure"]},
    }
