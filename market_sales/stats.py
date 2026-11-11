"""Which of the differences in the sales data are real, and which could just be chance?

A difference between two groups can appear by luck alone, and the more groups there are, the
easier it is to find a big-looking gap. So every claim here gets a p-value (how often chance
alone would produce a difference this large), an effect size (how large it is), and, because
many tests are run at once, a p-value adjusted for that.

Run with: python -m market_sales.stats
"""

import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from market_sales.analysis import daily_sales
from market_sales.cleaning import DataQualityError, load_clean
from market_sales.config import RAW_DATA, ROOT

RESULTS_PATH = ROOT / "reports" / "statistical_tests.csv"

SEED = 0
PERMUTATIONS = 10_000
BOOTSTRAPS = 5_000
ALPHA = 0.05
POWER = 0.8


@dataclass(frozen=True)
class TestResult:
    id: str
    family: str
    question: str
    test: str
    n: int
    statistic: float
    p_value: float
    effect_size: float
    effect_name: str


# --- Building blocks ---

def chi_square_equal(counts):
    """Are these counts spread evenly? Returns (statistic, p-value, effect size w)."""
    counts = np.asarray(counts, dtype=float)
    statistic, p_value = scipy_stats.chisquare(counts)
    return float(statistic), float(p_value), float(np.sqrt(statistic / counts.sum()))


def chi_square_independence(table):
    """Do two categories go together more than chance explains? Returns (statistic, p-value, Cramer's V).

    The p-value uses SciPy's usual small-table correction. The effect size is worked out without
    it, so that two categories that are perfectly linked score exactly 1.
    """
    table = np.asarray(table, dtype=float)
    statistic, p_value, _, _ = scipy_stats.chi2_contingency(table)
    uncorrected = scipy_stats.chi2_contingency(table, correction=False)[0]
    smaller_side = min(table.shape) - 1
    return float(statistic), float(p_value), float(np.sqrt(uncorrected / (table.sum() * smaller_side)))


def kruskal(groups):
    """Do several groups differ in size of value? Rank-based, so a few big sales can't mislead it.

    Returns (statistic, p-value, epsilon-squared effect size).
    """
    statistic, p_value = scipy_stats.kruskal(*groups)
    total = sum(len(group) for group in groups)
    return float(statistic), float(p_value), float(np.clip(statistic / (total - 1), 0, 1))


def mann_whitney(first, second):
    """Do two groups differ in size of value? Returns (statistic, p-value, rank-biserial effect size)."""
    statistic, p_value = scipy_stats.mannwhitneyu(first, second, alternative="two-sided")
    effect = 1 - 2 * statistic / (len(first) * len(second))
    return float(statistic), float(p_value), float(abs(effect))


def spearman(first, second):
    """Do two measures rise and fall together? Returns (correlation, p-value, correlation)."""
    result = scipy_stats.spearmanr(first, second)
    return float(result.statistic), float(result.pvalue), float(abs(result.statistic))


def _group_values(values, codes, groups, use_mean):
    totals = np.bincount(codes, weights=values, minlength=groups)
    return totals / np.bincount(codes, minlength=groups) if use_mean else totals


def _relative_gap(values):
    return (values.max() - values.min()) / values.min()


def permutation_gap(values, codes, groups, use_mean=False, permutations=PERMUTATIONS, seed=SEED):
    """Is the gap between the best and worst group bigger than chance produces?

    The labels are shuffled many times. Each time the best-versus-worst gap is measured. If
    shuffling often gives a gap as large as the real one, the real gap isn't evidence of anything.
    This also accounts for the fact that picking the best and worst of several groups always
    makes a gap look bigger than a typical pair would.

    Returns (observed gap, p-value, the gaps seen after shuffling).
    """
    values = np.asarray(values, dtype=float)
    codes = np.asarray(codes)
    rng = np.random.default_rng(seed)
    observed = _relative_gap(_group_values(values, codes, groups, use_mean))
    shuffled = np.array([
        _relative_gap(_group_values(values, rng.permutation(codes), groups, use_mean))
        for _ in range(permutations)
    ])
    p_value = (1 + np.sum(shuffled >= observed)) / (1 + permutations)
    return float(observed), float(p_value), shuffled


def holm_adjust(p_values):
    """Raise p-values to account for running many tests at once (Holm's method).

    With 20 tests, one is expected to look significant by luck alone. This keeps the chance of
    even one false alarm across all of them at the stated level.
    """
    p_values = np.asarray(p_values, dtype=float)
    count = len(p_values)
    order = np.argsort(p_values)
    adjusted = np.empty(count)
    running_max = 0.0
    for rank, index in enumerate(order):
        running_max = max(running_max, (count - rank) * p_values[index])
        adjusted[index] = min(1.0, running_max)
    return adjusted


def bootstrap_interval(values, confidence=0.95, resamples=BOOTSTRAPS, seed=SEED):
    """A range the true average probably falls in, from resampling the data."""
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), size=(resamples, len(values)))].mean(axis=1)
    tail = (1 - confidence) / 2
    low, high = np.quantile(means, [tail, 1 - tail])
    return float(low), float(high)


def minimum_detectable_difference(spread, first_size, second_size, alpha=ALPHA, power=POWER):
    """The smallest gap between two group averages this much data could reliably detect.

    A test that finds nothing only means "no difference larger than this" when the data is small.
    """
    z = scipy_stats.norm.ppf(1 - alpha / 2) + scipy_stats.norm.ppf(power)
    return float(z * spread * np.sqrt(1 / first_size + 1 / second_size))


# --- The tests ---

def _by(df, column, value="subtotal"):
    return [group[value].to_numpy() for _, group in df.groupby(column, observed=True)]


def _counts(df, column):
    return df.groupby(column, observed=True).size().to_numpy()


def _codes(series):
    codes, uniques = pd.factorize(series, sort=True)
    return codes, len(uniques)


def _daily_table(df):
    daily = daily_sales(df)
    return pd.DataFrame({
        "sales": daily.to_numpy(),
        "weekday": daily.index.day_name(),
        "month": daily.index.month_name(),
        "day_number": np.arange(len(daily)),
        "is_weekend": daily.index.dayofweek >= 5,
    })


def run_all(df, permutations=PERMUTATIONS):
    """Run every test and return one row per question, with adjusted p-values and a plain verdict."""
    results = []

    def add(id, family, question, test, n, outcome, effect_name):
        statistic, p_value, effect = outcome
        results.append(TestResult(id, family, question, test, int(n), statistic, p_value, effect, effect_name))

    def gap_outcome(values, labels, use_mean=False):
        codes, groups = _codes(labels)
        observed, p_value, _ = permutation_gap(values, codes, groups, use_mean, permutations)
        return observed, p_value, observed

    daily = _daily_table(df)
    sales = df["subtotal"].to_numpy()

    # Cities
    add("city_orders", "City", "Do the cities make the same number of sales?", "Chi-square, even split",
        len(df), chi_square_equal(_counts(df, "city")), "Cohen's w")
    add("city_order_size", "City", "Does the average sale differ between cities?", "Kruskal-Wallis",
        len(df), kruskal(_by(df, "city")), "epsilon-squared")
    add("city_total_gap", "City", "Is the gap between the best and worst city's total sales more than chance?",
        "Permutation, best vs worst", len(df), gap_outcome(sales, df["city"]), "relative gap")
    add("city_rating", "City", "Do customers rate the cities differently?", "Kruskal-Wallis",
        len(df), kruskal(_by(df, "city", "rating")), "epsilon-squared")

    # Product lines
    add("product_orders", "Product line", "Are some product lines bought more often?", "Chi-square, even split",
        len(df), chi_square_equal(_counts(df, "product_line")), "Cohen's w")
    add("product_order_size", "Product line", "Does the average sale differ between product lines?", "Kruskal-Wallis",
        len(df), kruskal(_by(df, "product_line")), "epsilon-squared")
    add("product_total_gap", "Product line",
        "Is the gap between the best and worst line's total sales more than chance?",
        "Permutation, best vs worst", len(df), gap_outcome(sales, df["product_line"]), "relative gap")
    add("product_rating", "Product line", "Do customers rate product lines differently?", "Kruskal-Wallis",
        len(df), kruskal(_by(df, "product_line", "rating")), "epsilon-squared")
    add("product_by_city", "Product line", "Does each city really favour different product lines?",
        "Chi-square, independence", len(df),
        chi_square_independence(pd.crosstab(df["city"], df["product_line"])), "Cramer's V")

    # Time
    add("weekday_daily_sales", "Time", "Do daily sales differ by day of the week?", "Kruskal-Wallis",
        len(daily), kruskal([part["sales"].to_numpy() for _, part in daily.groupby("weekday")]), "epsilon-squared")
    add("weekday_gap", "Time", "Is the gap between the best and worst weekday more than chance?",
        "Permutation, best vs worst", len(daily), gap_outcome(daily["sales"], daily["weekday"], use_mean=True),
        "relative gap")
    add("weekend", "Time", "Do weekend days sell more than weekdays?", "Mann-Whitney",
        len(daily), mann_whitney(daily.loc[daily["is_weekend"], "sales"], daily.loc[~daily["is_weekend"], "sales"]),
        "rank-biserial")
    add("month_daily_sales", "Time", "Do daily sales differ between months?", "Kruskal-Wallis",
        len(daily), kruskal([part["sales"].to_numpy() for _, part in daily.groupby("month")]), "epsilon-squared")
    add("trend", "Time", "Are daily sales rising or falling over the period?", "Spearman",
        len(daily), spearman(daily["day_number"], daily["sales"]), "correlation")
    add("hour_orders", "Time", "Are some hours of the day busier than others?", "Chi-square, even split",
        len(df), chi_square_equal(_counts(df, "hour")), "Cohen's w")
    add("hour_total_gap", "Time", "Is the gap between the best and worst hour's total sales more than chance?",
        "Permutation, best vs worst", len(df), gap_outcome(sales, df["hour"]), "relative gap")
    add("hour_order_size", "Time", "Does the average sale differ by hour?", "Kruskal-Wallis",
        len(df), kruskal(_by(df, "hour")), "epsilon-squared")

    # Customers
    member, normal = (df.loc[df["customer_type"] == kind, "subtotal"] for kind in ("Member", "Normal"))
    add("customer_type", "Customers", "Do members spend more per sale than other customers?", "Mann-Whitney",
        len(df), mann_whitney(member, normal), "rank-biserial")
    female, male = (df.loc[df["gender"] == kind, "subtotal"] for kind in ("Female", "Male"))
    add("gender", "Customers", "Do women and men spend differently per sale?", "Mann-Whitney",
        len(df), mann_whitney(female, male), "rank-biserial")
    add("payment_by_city", "Customers", "Does the way people pay differ between cities?", "Chi-square, independence",
        len(df), chi_square_independence(pd.crosstab(df["city"], df["payment"])), "Cramer's V")
    add("customer_by_city", "Customers", "Does the mix of members and others differ between cities?",
        "Chi-square, independence", len(df),
        chi_square_independence(pd.crosstab(df["city"], df["customer_type"])), "Cramer's V")
    add("rating_vs_spend", "Customers", "Do happier customers spend more?", "Spearman",
        len(df), spearman(df["rating"], df["subtotal"]), "correlation")

    table = pd.DataFrame(results)
    table["p_adjusted"] = holm_adjust(table["p_value"])
    table["verdict"] = np.select(
        [table["p_adjusted"] < ALPHA, table["p_value"] < ALPHA],
        ["Real difference", "Possible, not convincing"],
        default="No evidence of a difference",
    )
    return table


def detectable_differences(df):
    """How big a difference each comparison could have detected. Anything smaller could be hiding in the noise."""
    daily = daily_sales(df)
    per_weekday = len(daily) / 7
    city_sizes = df.groupby("city", observed=True).size()
    rows = [
        ("Average sale: one city vs another", df["subtotal"].std(), city_sizes.iloc[0], city_sizes.iloc[-1],
         df["subtotal"].mean()),
        ("Average sale: members vs others", df["subtotal"].std(), (df["customer_type"] == "Member").sum(),
         (df["customer_type"] == "Normal").sum(), df["subtotal"].mean()),
        ("Average sale: women vs men", df["subtotal"].std(), (df["gender"] == "Female").sum(),
         (df["gender"] == "Male").sum(), df["subtotal"].mean()),
        ("Daily sales: one weekday vs another", daily.std(), per_weekday, per_weekday, daily.mean()),
        ("Daily sales: weekend vs weekdays", daily.std(), (daily.index.dayofweek >= 5).sum(),
         (daily.index.dayofweek < 5).sum(), daily.mean()),
    ]
    table = pd.DataFrame(rows, columns=["comparison", "spread", "first_group", "second_group", "average"])
    table["smallest_detectable"] = [
        minimum_detectable_difference(row.spread, row.first_group, row.second_group) for row in table.itertuples()
    ]
    table["as_share_of_average"] = table["smallest_detectable"] / table["average"]
    return table[["comparison", "smallest_detectable", "as_share_of_average"]]


# --- Can these tests find a real difference at all? ---

CITY_LIFTS = (0.0, 0.05, 0.10, 0.20, 0.30)
WEEKDAY_LIFTS = (0.0, 0.10, 0.25, 0.50, 1.00)


def power_city_order_size(df, lifts=CITY_LIFTS, repetitions=200, seed=SEED):
    """How often a real boost to one city's average sale is noticed.

    Each trial draws a fresh set of sales from the real ones, raises one city's sales by `lift`,
    and runs the same test used above. A lift of 0 shows how often it raises a false alarm.
    """
    codes, groups = _codes(df["city"])
    base = df["subtotal"].to_numpy()
    rng = np.random.default_rng(seed)
    rows = []
    for lift in lifts:
        detected = 0
        for _ in range(repetitions):
            values = rng.choice(base, size=len(base))
            values = np.where(codes == 0, values * (1 + lift), values)
            p_value = scipy_stats.kruskal(*[values[codes == k] for k in range(groups)]).pvalue
            detected += p_value < ALPHA
        rows.append((lift, detected / repetitions))
    return pd.DataFrame(rows, columns=["lift", "detected"])


def power_weekday(df, lifts=WEEKDAY_LIFTS, repetitions=200, permutations=500, seed=SEED):
    """How often a real boost to Saturday's sales is noticed, by each of the two weekday tests."""
    daily = _daily_table(df)
    codes, groups = _codes(daily["weekday"])
    saturday = (daily["weekday"] == "Saturday").to_numpy()
    base = daily["sales"].to_numpy()
    rng = np.random.default_rng(seed)
    rows = []
    for lift in lifts:
        kruskal_hits = gap_hits = 0
        for _ in range(repetitions):
            values = rng.choice(base, size=len(base))
            values = np.where(saturday, values * (1 + lift), values)
            kruskal_hits += scipy_stats.kruskal(*[values[codes == k] for k in range(groups)]).pvalue < ALPHA
            _, p_value, _ = permutation_gap(values, codes, groups, True, permutations, int(rng.integers(2**31)))
            gap_hits += p_value < ALPHA
        rows.append((lift, kruskal_hits / repetitions, gap_hits / repetitions))
    return pd.DataFrame(rows, columns=["lift", "kruskal_detected", "gap_detected"])


def save_results(table, path=RESULTS_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    rounded = table.copy()
    for column in ["statistic", "effect_size"]:
        rounded[column] = rounded[column].round(4)
    for column in ["p_value", "p_adjusted"]:
        rounded[column] = rounded[column].round(6)
    rounded.to_csv(path, index=False, lineterminator="\n")


def main():
    try:
        df = load_clean(RAW_DATA)
    except (DataQualityError, FileNotFoundError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    table = run_all(df)
    save_results(table)
    print(f"{'question':<62}{'p':>9}{'adjusted':>10}  verdict")
    for row in table.itertuples():
        print(f"{row.question[:60]:<62}{row.p_value:>9.4f}{row.p_adjusted:>10.4f}  {row.verdict}")
    print(f"\nWrote {RESULTS_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
