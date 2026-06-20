"""Sentiment dataset wiring: fallback vs. the real FinancialPhraseBank CSV.

These are deterministic regardless of what's committed under backend/data,
because they point ``data_dir`` at a tmp directory.
"""
from __future__ import annotations

from app.config import Settings
from app.core.data_pipeline import get_modeling_dataset
from app.models import classification


def _run(settings):
    data = get_modeling_dataset(settings, use_cache=False)
    return classification.run(data, settings)


def test_sentiment_falls_back_and_warns_without_csv(tmp_path):
    """No sentiment CSV in data_dir -> tiny built-in sample, with a warning."""
    s = Settings(use_synthetic=True, min_rows_required=50, data_dir=tmp_path)
    assert not s.sentiment_csv.exists()
    out = _run(s)
    assert out["warnings"]                       # fallback sample is flagged


def test_sentiment_uses_real_csv_when_present(tmp_path):
    """A FinancialPhraseBank-style file (latin-1, CR line endings, no header) is
    discovered by filename and used -> no warning, sentiment models reported."""
    rows = []
    for _ in range(40):
        rows += [
            'positive,"Company profit beats expectations and revenue grows strongly ."',
            'negative,"Shares plunge after an earnings miss and a weak outlook ."',
            'neutral,"The company will report quarterly results next week ."',
        ]
    # CR-terminated, latin-1 -- the exact shape of the shipped dataset.
    (tmp_path / "FinancialPhraseBank.csv").write_bytes(
        ("\r".join(rows) + "\r").encode("latin-1"))

    s = Settings(use_synthetic=True, min_rows_required=50, data_dir=tmp_path)
    assert s.sentiment_csv.name == "FinancialPhraseBank.csv" and s.sentiment_csv.exists()

    out = _run(s)
    assert out["warnings"] == []                 # real dataset -> no fallback warning
    models = {m["model"] for m in out["metrics"]}
    assert {"Multinomial NB", "VADER lexicon"} <= models


def test_sentiment_csv_name_is_env_overridable(tmp_path):
    """An explicit name still wins and is resolved first."""
    (tmp_path / "custom.csv").write_bytes(
        ('neutral,"x ."\r' * 3).encode("latin-1"))
    s = Settings(data_dir=tmp_path, sentiment_agreement="csv",
                 sentiment_csv_name="custom.csv")
    assert s.sentiment_csv.name == "custom.csv"


def test_read_at_separated_agreement_file(tmp_path):
    """The `sentence@sentiment` agreement layout parses into the same schema."""
    p = tmp_path / "Sentences_AllAgree.txt"
    p.write_bytes("Good profit news .@positive\r\nWeak outlook .@negative\r\n".encode("latin-1"))
    df = classification._read_sentiment_dataset(p)
    assert list(df.columns) == ["sentiment", "headline"]
    assert set(df["sentiment"]) == {"positive", "negative"}
    assert df.iloc[0]["headline"] == "Good profit news ."   # split on the last @


def test_agreement_file_preferred_over_csv(tmp_path):
    """With an agreement level set, its file is chosen and used end-to-end."""
    lines = []
    for _ in range(40):
        lines += ["Company profit beats expectations .@positive",
                  "Shares plunge after a weak outlook .@negative",
                  "The company reports results next week .@neutral"]
    (tmp_path / "Sentences_75Agree.txt").write_bytes(
        ("\r\n".join(lines) + "\r\n").encode("latin-1"))
    # A CSV is also present, but the agreement file should win.
    (tmp_path / "FinancialPhraseBank.csv").write_bytes('neutral,"x ."\r'.encode("latin-1"))

    s = Settings(use_synthetic=True, min_rows_required=50, data_dir=tmp_path,
                 sentiment_agreement="75")
    assert s.sentiment_csv.name == "Sentences_75Agree.txt"
    out = _run(s)
    assert out["warnings"] == []
    assert {"Multinomial NB", "VADER lexicon"} <= {m["model"] for m in out["metrics"]}
