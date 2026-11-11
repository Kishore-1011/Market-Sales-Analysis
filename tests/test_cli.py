"""The command-line entry points: python -m market_sales.clean / .stats."""

import pandas as pd

from market_sales import clean, stats
from market_sales.cleaning import DataQualityError


def test_clean_writes_the_cleaned_file(tmp_path, monkeypatch, capsys):
    target = tmp_path / "data" / "processed" / "sales_clean.csv"
    monkeypatch.setattr(clean, "CLEAN_DATA", target)

    assert clean.main() == 0

    saved = pd.read_csv(target)
    assert len(saved) == 1000
    assert "Cleaned 1,000 sales" in capsys.readouterr().out


def test_clean_reports_a_missing_raw_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(clean, "RAW_DATA", tmp_path / "missing.csv")
    monkeypatch.setattr(clean, "CLEAN_DATA", tmp_path / "data" / "processed" / "out.csv")

    assert clean.main() == 1
    assert "Error" in capsys.readouterr().err
    assert not (tmp_path / "data" / "processed" / "out.csv").exists()


def test_stats_reports_bad_data_instead_of_crashing(monkeypatch, capsys):
    def fail(path):
        raise DataQualityError("rating out of range")

    monkeypatch.setattr(stats, "load_clean", fail)

    assert stats.main() == 1
    assert "rating out of range" in capsys.readouterr().err


def test_save_results_rounds_and_writes_a_csv(tmp_path):
    table = pd.DataFrame({
        "statistic": [1.234567], "effect_size": [0.987654],
        "p_value": [0.123456789], "p_adjusted": [0.987654321],
    })
    path = tmp_path / "nested" / "results.csv"

    stats.save_results(table, path)

    saved = pd.read_csv(path)
    assert saved.loc[0, "statistic"] == 1.2346
    assert saved.loc[0, "p_value"] == 0.123457
