import pandas as pd
import pytest

from market_sales.cleaning import (
    CLEAN_COLUMNS,
    DROPPED,
    DataQualityError,
    assert_sound,
    check_raw,
    clean_sales,
    find_problems,
)
from market_sales.config import CLEAN_DATA, WEEKDAYS
from tests.conftest import make_raw


# --- The real file ---

def test_real_file_cleans_without_problems(raw):
    assert find_problems(clean_sales(raw)) == []


def test_no_rows_are_lost_or_added(raw):
    clean = clean_sales(raw)
    assert len(clean) == len(raw) == 1000
    assert set(clean["invoice_id"]) == set(raw["Invoice ID"])


def test_totals_survive_cleaning(raw):
    clean = clean_sales(raw)
    assert clean["total"].sum() == pytest.approx(raw["Total"].sum())
    assert clean["quantity"].sum() == raw["Quantity"].sum()


def test_columns_and_order(raw):
    assert list(clean_sales(raw).columns) == CLEAN_COLUMNS


def test_misleading_columns_are_gone_and_renamed(raw):
    clean = clean_sales(raw)
    for column in [*DROPPED, "cogs", "Tax 5%"]:
        assert column not in clean.columns
    assert {"subtotal", "tax"} <= set(clean.columns)


def test_sorted_oldest_first(raw):
    assert clean_sales(raw)["sold_at"].is_monotonic_increasing


def test_timestamps_are_real_dates(raw):
    clean = clean_sales(raw)
    assert pd.api.types.is_datetime64_any_dtype(clean["sold_at"])
    assert clean["sold_at"].min() == pd.Timestamp("2019-01-01 10:39")
    assert clean["sold_at"].max().date() == pd.Timestamp("2019-03-30").date()


def test_time_breakdowns_agree_with_the_timestamp(raw):
    clean = clean_sales(raw)
    assert (clean["hour"] == clean["sold_at"].dt.hour).all()
    assert (clean["month"] == clean["sold_at"].dt.month).all()
    assert (clean["weekday"].astype(str) == clean["sold_at"].dt.day_name()).all()
    assert (clean["is_weekend"] == clean["weekday"].isin(["Saturday", "Sunday"])).all()


def test_weekdays_sort_in_calendar_order(raw):
    weekday = clean_sales(raw)["weekday"]
    assert list(weekday.cat.categories) == WEEKDAYS
    assert weekday.cat.ordered


def test_months_sort_in_calendar_order(raw):
    assert list(clean_sales(raw)["month_name"].cat.categories) == ["January", "February", "March"]


def test_saved_clean_file_is_up_to_date(raw, tmp_path):
    """Fails if someone changes the cleaning rules but forgets to re-run python -m market_sales.clean."""
    fresh = tmp_path / "fresh.csv"
    clean_sales(raw).to_csv(fresh, index=False, date_format="%Y-%m-%d %H:%M", lineterminator="\n")
    assert fresh.read_bytes() == CLEAN_DATA.read_bytes()


# --- Each rule, one at a time ---

def clean_with(**changes):
    """A valid cleaned row with some values broken, so each rule can be tested on its own."""
    clean = clean_sales(make_raw())
    for column, value in changes.items():
        clean[column] = value
    return clean


def test_a_valid_row_is_accepted():
    assert find_problems(clean_sales(make_raw())) == []


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"unit_price": 11.0}, "Subtotal is not unit price times quantity"),
        ({"subtotal": 25.0}, "Subtotal is not unit price times quantity"),
        ({"tax": 2.0}, "Tax is not 5%"),
        ({"total": 25.0}, "Total is not subtotal plus tax"),
        ({"rating": 11.0}, "Rating must be between"),
        ({"rating": 0.5}, "Rating must be between"),
        ({"quantity": 0}, "Quantity must be"),
        ({"quantity": 1.5}, "Quantity must be"),
        ({"unit_price": 0.0}, "Unit price must be above zero"),
        ({"payment": None}, "Missing values in: payment"),
    ],
)
def test_each_broken_rule_is_reported(changes, expected):
    problems = find_problems(clean_with(**changes))
    assert any(expected in problem for problem in problems), problems

def test_duplicate_invoice_ids_are_reported():
    raw = pd.concat([make_raw(), make_raw()], ignore_index=True)
    assert any("more than once" in p for p in find_problems(clean_sales(raw)))


def test_a_city_with_two_branches_is_reported():
    raw = pd.concat([make_raw(), make_raw(**{"Invoice ID": "222", "Branch": "B"})], ignore_index=True)
    assert any("more than one" in p for p in find_problems(clean_sales(raw)))


def test_assert_sound_lists_every_problem_at_once():
    with pytest.raises(DataQualityError) as error:
        assert_sound(clean_with(rating=11.0, total=25.0))
    assert "Rating" in str(error.value) and "Total" in str(error.value)


# --- Damaged files ---

def test_missing_column_is_named():
    with pytest.raises(DataQualityError, match="Rating"):
        clean_sales(make_raw().drop(columns="Rating"))


@pytest.mark.parametrize("date", ["13/45/2019", "not a date", ""])
def test_unreadable_date_names_the_spreadsheet_row(date):
    raw = pd.concat([make_raw(), make_raw(**{"Invoice ID": "222", "Date": date})], ignore_index=True)
    with pytest.raises(DataQualityError, match=r"row\(s\): 3"):
        clean_sales(raw)


def test_unreadable_time_is_reported():
    with pytest.raises(DataQualityError, match="Unreadable"):
        clean_sales(make_raw(Time="25:99"))


def test_a_column_is_not_dropped_if_it_stops_being_a_copy():
    with pytest.raises(DataQualityError, match="gross income"):
        check_raw(make_raw(**{"gross income": 99.0}))


def test_a_changed_tax_is_caught_before_anything_is_dropped():
    with pytest.raises(DataQualityError, match="no longer income divided by total"):
        check_raw(make_raw(**{"Tax 5%": 2.0, "gross income": 2.0, "Total": 22.0}))


def test_a_varying_margin_column_is_not_dropped():
    raw = pd.concat([make_raw(), make_raw(**{"gross margin percentage": 5.0})], ignore_index=True)
    with pytest.raises(DataQualityError, match="margin"):
        check_raw(raw)
