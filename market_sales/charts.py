"""The charts, one function each, drawn from the cleaned data.

Every function returns a matplotlib Figure and leaves the data untouched. A city always has
the same colour, and bars that compare amounts always start at zero, so a small difference
never looks bigger than it is.

Run with: python -m market_sales.charts
"""

import sys
from pathlib import Path

import matplotlib.dates as mdates
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from market_sales.analysis import (
    average_daily_sales,
    daily_sales,
    sales_mix,
    sales_summary,
)
from market_sales.cleaning import DataQualityError, load_clean
from market_sales.config import RAW_DATA, ROOT

FIGURES_DIR = ROOT / "reports" / "figures"

CITY_COLORS = {"Yangon": "#0072B2", "Mandalay": "#E69F00", "Naypyitaw": "#009E73"}
SEGMENT_COLORS = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9"]
NEUTRAL = "#8a93a3"
LIGHT = "#d6dae1"
SALES_LABEL = "Sales before tax"
MIN_WHITE_TEXT_CONTRAST = 0.4


def _thousands(axis):
    axis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))


def _clean_axes(axis):
    axis.spines[["top", "right"]].set_visible(False)


def _period(df):
    start, end = df["sold_at"].min(), df["sold_at"].max()
    return f"{start:%b} to {end:%b %Y}"


def _text_on(color):
    """Black or white text, whichever is readable on this background colour."""
    red, green, blue = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    brightness = 0.299 * red + 0.587 * green + 0.114 * blue
    return "white" if brightness < MIN_WHITE_TEXT_CONTRAST + 0.1 else "black"


def _figure(width, height):
    return Figure(figsize=(width, height), layout="constrained")


def _city_order(df):
    """Cities from most to least sales, so every chart lists them the same way."""
    return list(sales_summary(df, "city").index.astype(str))


def city_sales(df):
    """Total sales for each city."""
    summary = sales_summary(df, "city")
    fig = _figure(7, 4.3)
    axis = fig.subplots()
    bars = axis.bar(summary.index.astype(str), summary["sales"], color=[CITY_COLORS[c] for c in summary.index])
    axis.bar_label(bars, labels=[f"{s:,.0f}\n{share:.1%}" for s, share in zip(summary["sales"], summary["share"])],
                   padding=3)
    axis.set_ylim(0, summary["sales"].max() * 1.18)
    axis.set_ylabel(SALES_LABEL)
    axis.set_title(f"Sales by city, {_period(df)}")
    _thousands(axis.yaxis)
    _clean_axes(axis)
    return fig


def product_by_city(df):
    """What each city sells, with the products in the same order in every panel."""
    order = sales_summary(df, "product_line").index
    cities = _city_order(df)
    fig = _figure(12, 4.6)
    axes = fig.subplots(1, len(cities), sharex=True, sharey=True)
    for axis, city in zip(axes, cities):
        sales = df[df["city"] == city].groupby("product_line", observed=True)["subtotal"].sum().reindex(order)
        bars = axis.barh(order.astype(str), sales, color=CITY_COLORS[city])
        axis.bar_label(bars, labels=[f"{value:,.0f}" for value in sales], padding=3, fontsize=9)
        axis.set_title(f"{city}: {sales.sum():,.0f} in total")
        axis.set_xlim(0, df.groupby(["city", "product_line"], observed=True)["subtotal"].sum().max() * 1.25)
        _thousands(axis.xaxis)
        _clean_axes(axis)
    axes[0].invert_yaxis()
    fig.supxlabel(SALES_LABEL)
    fig.suptitle("Sales by product line in each city")
    return fig


def daily_trend(df):
    """Sales each day, with a 7-day average to smooth out the ups and downs."""
    daily = daily_sales(df)
    smooth = daily.rolling(7, center=True, min_periods=4).mean()
    fig = _figure(10, 4.3)
    axis = fig.subplots()
    axis.plot(daily.index, daily.values, color=LIGHT, linewidth=1.2, marker="o", markersize=3, label="Each day")
    axis.plot(smooth.index, smooth.values, color=CITY_COLORS["Yangon"], linewidth=2.6, label="7-day average")
    axis.set_ylim(0, daily.max() * 1.08)
    axis.set_ylabel(f"{SALES_LABEL} per day")
    axis.set_title(f"Daily sales across all three cities, {_period(df)}")
    locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
    axis.xaxis.set_major_locator(locator)
    axis.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    axis.legend(frameon=False, loc="upper right")
    _thousands(axis.yaxis)
    _clean_axes(axis)
    return fig


def weekday_pattern(df):
    """Average sales on each day of the week."""
    average = average_daily_sales(df, "weekday")
    overall = daily_sales(df).mean()
    fig = _figure(8, 4.3)
    axis = fig.subplots()
    bars = axis.bar(average.index.astype(str), average.values, color=NEUTRAL)
    axis.bar_label(bars, labels=[f"{value:,.0f}" for value in average.values], padding=3,
                   bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})  # keeps labels readable over the line
    axis.axhline(overall, color=CITY_COLORS["Yangon"], linewidth=1.5, linestyle="--", label=f"Average day: {overall:,.0f}")
    axis.legend(frameon=False, loc="upper left")
    axis.set_ylim(0, average.max() * 1.25)
    axis.set_ylabel(f"Average {SALES_LABEL.lower()} per day")
    axis.set_title("Which days of the week sell most?")
    _thousands(axis.yaxis)
    _clean_axes(axis)
    return fig


def hourly_pattern(df):
    """Total sales in each hour of the day."""
    hourly = sales_summary(df, "hour", sort=False)["sales"]
    fig = _figure(9, 4.3)
    axis = fig.subplots()
    axis.bar([f"{hour}:00" for hour in hourly.index], hourly.values, color=NEUTRAL)
    axis.set_ylim(0, hourly.max() * 1.1)
    axis.set_ylabel(SALES_LABEL)
    axis.set_xlabel("Hour of day")
    axis.set_title(f"Which hours sell most? ({_period(df)}, all cities)")
    _thousands(axis.yaxis)
    _clean_axes(axis)
    return fig


def monthly_by_city(df):
    """Average sales per day in each month, for each city. Months have different lengths, so totals would mislead."""
    cities = _city_order(df)
    average = average_daily_sales(df, "month_name", split="city")[cities]
    width = 0.8 / len(cities)
    fig = _figure(8, 4.3)
    axis = fig.subplots()
    for position, city in enumerate(cities):
        offsets = [i + (position - (len(cities) - 1) / 2) * width for i in range(len(average))]
        bars = axis.bar(offsets, average[city], width=width, color=CITY_COLORS[city], label=city)
        axis.bar_label(bars, labels=[f"{v:,.0f}" for v in average[city]], padding=2, fontsize=8)
    axis.set_xticks(range(len(average)), average.index.astype(str))
    axis.set_ylim(0, average.to_numpy().max() * 1.25)
    axis.set_ylabel(f"Average {SALES_LABEL.lower()} per day")
    axis.set_title("Average daily sales by month and city")
    axis.legend(frameon=False, ncols=len(cities), loc="upper center", bbox_to_anchor=(0.5, 1.0))
    _thousands(axis.yaxis)
    _clean_axes(axis)
    return fig


def _stacked_shares(axis, mix, title):
    cities = list(mix.index.astype(str))
    left = pd.Series(0.0, index=mix.index)
    for color, column in zip(SEGMENT_COLORS, mix.columns):
        bars = axis.barh(cities, mix[column], left=left, color=color, label=str(column))
        axis.bar_label(bars, labels=[f"{value:.0%}" for value in mix[column]], label_type="center",
                       color=_text_on(color), fontsize=9)
        left += mix[column]
    axis.set_xlim(0, 1)
    axis.set_title(title)
    axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.0%}"))
    axis.legend(frameon=False, ncols=len(mix.columns), loc="lower center", bbox_to_anchor=(0.5, 1.1))
    axis.invert_yaxis()
    _clean_axes(axis)


def payment_and_customer_mix(df):
    """How customers pay, and who they are, in each city. Shares of sales."""
    cities = _city_order(df)
    fig = _figure(12, 3.8)
    left, right = fig.subplots(1, 2, sharey=True)
    _stacked_shares(left, sales_mix(df, "city", "payment").loc[cities], "Payment method")
    _stacked_shares(right, sales_mix(df, "city", "customer_type").loc[cities], "Customer type")
    return fig


def order_size(df):
    """How big a typical sale is."""
    mean, median = df["subtotal"].mean(), df["subtotal"].median()
    fig = _figure(8, 4.3)
    axis = fig.subplots()
    axis.hist(df["subtotal"], bins=20, color=LIGHT, edgecolor="white")
    axis.axvline(median, color=CITY_COLORS["Yangon"], linewidth=2, label=f"Median: {median:,.0f}")
    axis.axvline(mean, color=CITY_COLORS["Mandalay"], linewidth=2, linestyle="--", label=f"Average: {mean:,.0f}")
    axis.set_xlabel("Value of one sale, before tax")
    axis.set_ylabel("Number of sales")
    axis.set_title("How big is a typical sale?")
    axis.legend(frameon=False)
    _thousands(axis.xaxis)
    _clean_axes(axis)
    return fig


CHARTS = {
    "city_sales": city_sales,
    "product_by_city": product_by_city,
    "daily_trend": daily_trend,
    "weekday_pattern": weekday_pattern,
    "hourly_pattern": hourly_pattern,
    "monthly_by_city": monthly_by_city,
    "payment_and_customer_mix": payment_and_customer_mix,
    "order_size": order_size,
}


def save_all(df, directory=FIGURES_DIR):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, draw in CHARTS.items():
        draw(df).savefig(directory / f"{name}.png", dpi=130)
    return sorted(CHARTS)


def main():
    try:
        df = load_clean(RAW_DATA)
    except (DataQualityError, FileNotFoundError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    names = save_all(df)
    print(f"Saved {len(names)} charts to {FIGURES_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
