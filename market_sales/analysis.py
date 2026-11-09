"""Questions about the sales, each answered as a plain table.

"Sales" always means the subtotal: the price before the 5% tax, because tax is collected for
the government and isn't money the shop keeps. The ranking is the same with or without tax,
since the tax is a flat 5% of every sale.
"""

import pandas as pd


def sales_summary(df, by, sort=True):
    """Sales, number of sales, units, average sale and average rating for each group."""
    summary = df.groupby(by, observed=True).agg(
        sales=("subtotal", "sum"),
        orders=("invoice_id", "count"),
        units=("quantity", "sum"),
        average_order=("subtotal", "mean"),
        average_rating=("rating", "mean"),
    )
    summary["share"] = summary["sales"] / summary["sales"].sum()
    return summary.sort_values("sales", ascending=False) if sort else summary


def daily_sales(df):
    """Sales for every calendar day in the period. A day with no sales counts as zero."""
    days = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    return df.groupby("date")["subtotal"].sum().reindex(days, fill_value=0.0).rename_axis("date")


def calendar_days(df, by):
    """How many days of each weekday or month fall inside the period.

    Totals are unfair across groups with different numbers of days (February is short), so
    comparisons use sales per day instead.
    """
    days = pd.Series(pd.date_range(df["date"].min(), df["date"].max(), freq="D"))
    labels = {"weekday": days.dt.day_name(), "month_name": days.dt.month_name()}[by]
    return labels.value_counts().reindex(df[by].cat.categories, fill_value=0)


def average_daily_sales(df, by, split=None):
    """Average sales per day for each weekday or month, optionally split by another column.

    A day with no sales counts as zero. A weekday or month that never occurs in the period
    has no average, so it is left empty instead of shown as zero.
    """
    categories = df[by].cat.categories
    days = calendar_days(df, by).where(lambda counts: counts > 0)
    if split is None:
        sales = df.groupby(by, observed=True)["subtotal"].sum().reindex(categories, fill_value=0.0)
        return sales.div(days).rename("average_daily_sales")
    sales = df.groupby([by, split], observed=True)["subtotal"].sum().unstack(split, fill_value=0.0)
    return sales.reindex(categories, fill_value=0.0).div(days, axis=0)


def sales_mix(df, rows, columns):
    """Each row's sales split across the columns, as shares that add to 100%."""
    table = df.pivot_table(index=rows, columns=columns, values="subtotal", aggfunc="sum", observed=True)
    return table.div(table.sum(axis=1), axis=0)


def gap(values):
    """How much bigger the largest value is than the smallest, as a share of the smallest."""
    return float((values.max() - values.min()) / values.min())


def headline(df):
    """The overall numbers that frame everything else."""
    days = daily_sales(df)
    return {
        "sales": float(df["subtotal"].sum()),
        "orders": int(len(df)),
        "units": int(df["quantity"].sum()),
        "average_order": float(df["subtotal"].mean()),
        "median_order": float(df["subtotal"].median()),
        "average_rating": float(df["rating"].mean()),
        "days": int(len(days)),
        "average_daily_sales": float(days.mean()),
        "first_day": df["date"].min(),
        "last_day": df["date"].max(),
    }
