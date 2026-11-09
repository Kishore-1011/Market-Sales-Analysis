"""Turn the raw sales file into tidy, checked data.

Nothing is dropped or changed quietly. A column is only removed after the code proves it
carries no extra information, and every rule the data has to follow is checked, so a damaged
file stops with a message instead of producing wrong numbers.
"""

import numpy as np
import pandas as pd

from market_sales.config import MONEY_TOLERANCE, MONTHS, RATING_RANGE, TAX_RATE, WEEKDAYS

# Raw column name -> clean name. `cogs` is the price before tax, so it is called what it is.
RENAMES = {
    "Invoice ID": "invoice_id",
    "Branch": "branch",
    "City": "city",
    "Customer type": "customer_type",
    "Gender": "gender",
    "Product line": "product_line",
    "Unit price": "unit_price",
    "Quantity": "quantity",
    "Tax 5%": "tax",
    "Total": "total",
    "Date": "date",
    "Time": "time",
    "Payment": "payment",
    "cogs": "subtotal",
    "Rating": "rating",
}
DROPPED = ["gross income", "gross margin percentage"]
REQUIRED = [*RENAMES, *DROPPED]

CATEGORIES = ["branch", "city", "customer_type", "gender", "product_line", "payment"]

CLEAN_COLUMNS = [
    "invoice_id", "sold_at", "date", "month", "month_name", "weekday", "is_weekend", "hour",
    "branch", "city", "customer_type", "gender", "product_line",
    "unit_price", "quantity", "subtotal", "tax", "total", "payment", "rating",
]


class DataQualityError(ValueError):
    """The data breaks a rule it is expected to follow. The message lists every problem."""


def _spreadsheet_rows(index):
    # Row numbers as they appear in a spreadsheet, where the header is row 1.
    shown = [str(position + 2) for position in index[:5]]
    more = f" and {len(index) - 5} more" if len(index) > 5 else ""
    return ", ".join(shown) + more


def _close(a, b):
    return np.isclose(a, b, rtol=0, atol=MONEY_TOLERANCE)


def check_raw(raw):
    """Confirm the columns we are about to drop really are copies of other columns."""
    missing = [column for column in REQUIRED if column not in raw.columns]
    if missing:
        raise DataQualityError(f"Missing column(s): {', '.join(missing)}")

    problems = []
    if not _close(raw["gross income"], raw["Tax 5%"]).all():
        problems.append("'gross income' is no longer the same as 'Tax 5%', so it can't be dropped safely")
    implied = raw["gross income"] / raw["Total"] * 100
    if not np.allclose(raw["gross margin percentage"], implied, rtol=0, atol=1e-6):
        problems.append("'gross margin percentage' is no longer income divided by total")
    if raw["gross margin percentage"].nunique() != 1:
        problems.append("'gross margin percentage' now varies, so it can't be dropped safely")
    if problems:
        raise DataQualityError("; ".join(problems))


def parse_sale_times(raw):
    """Combine the separate date and time columns into one timestamp."""
    parsed = pd.to_datetime(raw["Date"] + " " + raw["Time"], format="%m/%d/%Y %H:%M", errors="coerce")
    bad = parsed.index[parsed.isna()]
    if len(bad) > 0:
        raise DataQualityError(f"Unreadable date or time in row(s): {_spreadsheet_rows(bad)}")
    return parsed


def clean_sales(raw):
    """Return the tidy table: readable names, real timestamps and the time breakdowns analysis needs."""
    check_raw(raw)
    sold_at = parse_sale_times(raw)

    clean = raw.rename(columns=RENAMES).drop(columns=DROPPED)
    clean["sold_at"] = sold_at
    clean["date"] = sold_at.dt.normalize()
    clean["month"] = sold_at.dt.month
    clean["month_name"] = pd.Categorical(
        sold_at.dt.month_name(), categories=[m for m in MONTHS if m in set(sold_at.dt.month_name())], ordered=True
    )
    clean["weekday"] = pd.Categorical(sold_at.dt.day_name(), categories=WEEKDAYS, ordered=True)
    clean["is_weekend"] = sold_at.dt.dayofweek >= 5
    clean["hour"] = sold_at.dt.hour

    for column in CATEGORIES:
        clean[column] = clean[column].astype("category")
    return clean[CLEAN_COLUMNS].sort_values("sold_at", kind="stable").reset_index(drop=True)


def find_problems(clean):
    """List every rule the clean data breaks. An empty list means the data is sound."""
    problems = []

    empty = clean.columns[clean.isna().any()].tolist()
    if empty:
        problems.append(f"Missing values in: {', '.join(empty)}")

    repeated = clean.index[clean["invoice_id"].duplicated(keep=False)]
    if len(repeated) > 0:
        problems.append(f"Invoice IDs appear more than once (rows {_spreadsheet_rows(repeated)})")

    pairs = clean.groupby("branch", observed=True)["city"].nunique()
    shared = clean.groupby("city", observed=True)["branch"].nunique()
    if (pairs > 1).any() or (shared > 1).any():
        problems.append("A branch has more than one city, or a city has more than one branch")

    if (clean["unit_price"] <= 0).any():
        problems.append("Unit price must be above zero")
    if (clean["quantity"] < 1).any() or (clean["quantity"] % 1 != 0).any():
        problems.append("Quantity must be a whole number of at least 1")

    low, high = RATING_RANGE
    if not clean["rating"].between(low, high).all():
        problems.append(f"Rating must be between {low} and {high}")

    if not _close(clean["subtotal"], clean["unit_price"] * clean["quantity"]).all():
        problems.append("Subtotal is not unit price times quantity")
    if not _close(clean["tax"], clean["subtotal"] * TAX_RATE).all():
        problems.append(f"Tax is not {TAX_RATE:.0%} of the subtotal")
    if not _close(clean["total"], clean["subtotal"] + clean["tax"]).all():
        problems.append("Total is not subtotal plus tax")

    return problems


def assert_sound(clean):
    problems = find_problems(clean)
    if problems:
        raise DataQualityError("; ".join(problems))
    return clean


def load_clean(path):
    """Read the raw CSV, clean it and check it in one step."""
    return assert_sound(clean_sales(pd.read_csv(path)))
