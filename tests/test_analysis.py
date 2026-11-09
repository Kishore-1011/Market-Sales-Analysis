import pandas as pd
import pytest

from market_sales.analysis import (
    average_daily_sales,
    calendar_days,
    daily_sales,
    gap,
    headline,
    sales_mix,
    sales_summary,
)
from market_sales.cleaning import clean_sales
from market_sales.config import RAW_DATA
from tests.conftest import make_raw


def sale(invoice, city, branch, unit, quantity, date, time="12:00", payment="Cash", product="Health and beauty",
         customer="Member", rating=8.0):
    """One valid sale whose arithmetic adds up, so the right answers are easy to work out by hand."""
    subtotal = unit * quantity
    return make_raw(**{
        "Invoice ID": invoice, "City": city, "Branch": branch, "Unit price": unit, "Quantity": quantity,
        "cogs": subtotal, "Tax 5%": subtotal * 0.05, "gross income": subtotal * 0.05, "Total": subtotal * 1.05,
        "gross margin percentage": 4.761904762, "Date": date, "Time": time, "Payment": payment,
        "Product line": product, "Customer type": customer, "Rating": rating,
    })


@pytest.fixture
def small():
    """Five sales over four days in two cities, with sales on 1, 2 and 4 January (3 January is empty)."""
    rows = [
        sale("a", "Yangon", "A", 10, 2, "1/1/2019", "10:00", "Cash", "Food and beverages"),     # Tue, 20
        sale("b", "Yangon", "A", 30, 1, "1/1/2019", "11:00", "Ewallet", "Food and beverages"),  # Tue, 30
        sale("c", "Mandalay", "B", 5, 4, "1/2/2019", "10:00", "Cash", "Sports and travel"),     # Wed, 20
        sale("d", "Mandalay", "B", 10, 1, "1/4/2019", "15:00", "Cash", "Sports and travel"),     # Fri, 10
        sale("e", "Yangon", "A", 20, 1, "1/4/2019", "15:30", "Ewallet", "Sports and travel"),    # Fri, 20
    ]
    return clean_sales(pd.concat(rows, ignore_index=True))


@pytest.fixture(scope="module")
def real():
    return clean_sales(pd.read_csv(RAW_DATA))


# --- Worked by hand on five sales ---

def test_sales_by_city(small):
    summary = sales_summary(small, "city")
    assert summary["sales"].to_dict() == {"Yangon": 70.0, "Mandalay": 30.0}
    assert summary["orders"].to_dict() == {"Yangon": 3, "Mandalay": 2}
    assert summary["units"].to_dict() == {"Yangon": 4, "Mandalay": 5}


def test_summary_is_sorted_biggest_first_and_shares_add_up(small):
    summary = sales_summary(small, "city")
    assert list(summary.index) == ["Yangon", "Mandalay"]
    assert summary["share"].sum() == pytest.approx(1.0)
    assert summary.loc["Yangon", "share"] == pytest.approx(0.7)


def test_average_order_and_rating(small):
    assert sales_summary(small, "city").loc["Yangon", "average_order"] == pytest.approx(70 / 3)
    assert sales_summary(small, "city").loc["Yangon", "average_rating"] == 8.0


def test_unsorted_summary_keeps_the_natural_order(small):
    assert list(sales_summary(small, "weekday", sort=False).index) == ["Tuesday", "Wednesday", "Friday"]


def test_a_day_with_no_sales_counts_as_zero(small):
    daily = daily_sales(small)
    assert list(daily.index.strftime("%d")) == ["01", "02", "03", "04"]
    assert daily.tolist() == [50.0, 20.0, 0.0, 30.0]


def test_calendar_days_count_every_day_in_the_period(small):
    days = calendar_days(small, "weekday")
    assert days["Tuesday"] == days["Wednesday"] == days["Thursday"] == days["Friday"] == 1
    assert days["Monday"] == 0


def test_average_daily_sales_divides_by_the_days_in_the_period(small):
    average = average_daily_sales(small, "weekday")
    assert average["Tuesday"] == 50.0
    assert average["Thursday"] == 0.0  # 3 January was a Thursday with no sales
    assert average["Friday"] == 30.0


def test_a_weekday_missing_from_the_period_has_no_average_instead_of_zero(small):
    assert pd.isna(average_daily_sales(small, "weekday")["Monday"])


def test_average_daily_sales_by_month_and_city(small):
    average = average_daily_sales(small, "month_name", split="city")
    assert average.loc["January", "Yangon"] == pytest.approx(70 / 4)
    assert average.loc["January", "Mandalay"] == pytest.approx(30 / 4)


def test_sales_mix_rows_add_to_one(small):
    mix = sales_mix(small, "city", "payment")
    assert mix.sum(axis=1).tolist() == pytest.approx([1.0, 1.0])
    assert mix.loc["Yangon", "Cash"] == pytest.approx(20 / 70)
    assert mix.loc["Mandalay", "Cash"] == pytest.approx(1.0)


def test_gap_is_relative_to_the_smallest():
    assert gap(pd.Series([100.0, 150.0])) == pytest.approx(0.5)


def test_headline(small):
    numbers = headline(small)
    assert numbers["sales"] == 100.0
    assert numbers["orders"] == 5
    assert numbers["units"] == 9
    assert numbers["days"] == 4
    assert numbers["average_daily_sales"] == 25.0
    assert numbers["median_order"] == 20.0


# --- Properties that must hold for the real data ---

@pytest.mark.parametrize("by", ["city", "product_line", "payment", "customer_type", "gender", "weekday", "hour"])
def test_every_grouping_accounts_for_all_the_sales(real, by):
    summary = sales_summary(real, by)
    assert summary["sales"].sum() == pytest.approx(real["subtotal"].sum())
    assert summary["orders"].sum() == len(real)
    assert summary["units"].sum() == real["quantity"].sum()
    assert summary["share"].sum() == pytest.approx(1.0)


def test_daily_sales_add_up_to_the_total(real):
    daily = daily_sales(real)
    assert daily.sum() == pytest.approx(real["subtotal"].sum())
    assert len(daily) == 89


def test_average_daily_sales_times_days_gives_back_the_totals(real):
    for by in ["weekday", "month_name"]:
        rebuilt = average_daily_sales(real, by) * calendar_days(real, by)
        assert rebuilt.sum() == pytest.approx(real["subtotal"].sum())


def test_the_period_has_the_expected_weekday_and_month_lengths(real):
    assert calendar_days(real, "month_name").to_dict() == {"January": 31, "February": 28, "March": 30}
    assert calendar_days(real, "weekday").sum() == 89


def test_sales_exclude_tax(real):
    assert headline(real)["sales"] == pytest.approx(real["total"].sum() / 1.05)


def test_the_ranking_is_the_same_with_or_without_tax(real):
    with_tax = real.groupby("city", observed=True)["total"].sum().sort_values(ascending=False).index.tolist()
    assert with_tax == sales_summary(real, "city").index.tolist()


def test_analysis_does_not_change_the_data(real):
    before = real.copy()
    sales_summary(real, "city")
    average_daily_sales(real, "weekday")
    sales_mix(real, "city", "payment")
    pd.testing.assert_frame_equal(real, before)
