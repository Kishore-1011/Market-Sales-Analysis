import pandas as pd
import pytest
from matplotlib.figure import Figure

from market_sales import charts
from market_sales.charts import CHARTS, CITY_COLORS, save_all
from market_sales.cleaning import clean_sales
from market_sales.config import RAW_DATA


@pytest.fixture(scope="module")
def real():
    return clean_sales(pd.read_csv(RAW_DATA))


@pytest.mark.parametrize("name", sorted(CHARTS))
def test_each_chart_draws_with_a_title_and_readable_labels(real, name):
    fig = CHARTS[name](real)
    assert isinstance(fig, Figure)
    axes = fig.axes
    assert axes
    assert fig._suptitle is not None or any(axis.get_title() for axis in axes)
    for axis in axes:
        for label in (axis.get_xlabel(), axis.get_ylabel()):
            assert "_" not in label  # no raw column names shown to readers


@pytest.mark.parametrize("name", sorted(CHARTS))
def test_charts_leave_the_data_alone(real, name):
    before = real.copy()
    CHARTS[name](real)
    pd.testing.assert_frame_equal(real, before)


def test_bars_that_compare_amounts_start_at_zero(real):
    for name in ["city_sales", "weekday_pattern", "hourly_pattern", "monthly_by_city"]:
        assert CHARTS[name](real).axes[0].get_ylim()[0] == 0, name


def test_the_city_chart_shows_the_real_totals(real):
    axis = charts.city_sales(real).axes[0]
    heights = sorted(patch.get_height() for patch in axis.patches)
    assert heights[-1] == pytest.approx(real.groupby("city", observed=True)["subtotal"].sum().max())
    assert sum(heights) == pytest.approx(real["subtotal"].sum())


def test_every_city_keeps_its_colour_across_charts(real):
    def bar_colours(fig):
        return {tuple(round(c, 3) for c in patch.get_facecolor()[:3]) for axis in fig.axes for patch in axis.patches}

    from matplotlib.colors import to_rgb
    expected = {tuple(round(c, 3) for c in to_rgb(colour)) for colour in CITY_COLORS.values()}
    assert expected <= bar_colours(charts.monthly_by_city(real))
    assert expected <= bar_colours(charts.product_by_city(real))


def test_cities_are_listed_in_the_same_order_everywhere(real):
    order = charts._city_order(real)
    mix = charts.payment_and_customer_mix(real)
    assert [t.get_text() for t in mix.axes[0].get_yticklabels()] == order
    monthly_labels = [t.get_text() for t in charts.monthly_by_city(real).axes[0].get_legend().get_texts()]
    assert monthly_labels == order


def test_text_colour_is_readable_on_each_background():
    assert charts._text_on("#0072B2") == "white"
    assert charts._text_on("#E69F00") == "black"
    assert charts._text_on("#56B4E9") == "black"


def test_the_interval_chart_shows_one_range_per_city(real):
    axis = charts.city_order_intervals(real).axes[0]
    assert len(axis.containers) == 3
    assert axis.get_ylim()[0] == 0


def test_the_weekday_chart_has_one_dot_per_day(real):
    axis = charts.weekday_spread(real).axes[0]
    dots = sum(len(collection.get_offsets()) for collection in axis.collections)
    assert dots == 89 + 7  # every day, plus one average marker per weekday


def test_the_chance_chart_reports_the_same_p_value_as_the_test(real):
    from market_sales.stats import run_all

    expected = run_all(real, permutations=500).set_index("id").loc["weekday_gap", "p_value"]
    label = charts.weekday_gap_by_chance(real).axes[0].get_legend().get_texts()[0].get_text()
    shown = int(label.split("this or more ")[1].split("%")[0])
    assert abs(shown - expected * 100) < 3


def test_the_detection_chart_draws_from_power_tables():
    city = pd.DataFrame({"lift": [0, 0.1, 0.3], "detected": [0.05, 0.3, 0.95]})
    weekday = pd.DataFrame({"lift": [0, 0.5, 1.0], "kruskal_detected": [0.04, 0.5, 0.97],
                            "gap_detected": [0.05, 0.6, 0.99]})
    axis = charts.detection_power(city, weekday).axes[0]
    assert len(axis.lines) >= 2
    assert axis.get_ylim()[0] == 0


def test_save_all_writes_every_chart(real, tmp_path, monkeypatch):
    # The power simulations are slow and have their own tests, so a quick stand-in is used here.
    quick = pd.DataFrame({"lift": [0, 1.0], "detected": [0.05, 1.0], "kruskal_detected": [0.05, 1.0],
                          "gap_detected": [0.05, 1.0]})
    monkeypatch.setattr(charts, "power_city_order_size", lambda df: quick)
    monkeypatch.setattr(charts, "power_weekday", lambda df: quick)
    names = save_all(real, tmp_path)
    assert names == sorted([*CHARTS, "detection_power"])
    for name in names:
        assert (tmp_path / f"{name}.png").stat().st_size > 5_000
