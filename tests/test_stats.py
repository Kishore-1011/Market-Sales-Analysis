import numpy as np
import pandas as pd
import pytest

from market_sales import stats
from market_sales.cleaning import clean_sales
from market_sales.config import RAW_DATA
from market_sales.stats import (
    RESULTS_PATH,
    bootstrap_interval,
    chi_square_equal,
    chi_square_independence,
    holm_adjust,
    kruskal,
    mann_whitney,
    minimum_detectable_difference,
    permutation_gap,
    power_city_order_size,
    power_weekday,
    run_all,
    spearman,
)


@pytest.fixture(scope="module")
def real():
    return clean_sales(pd.read_csv(RAW_DATA))


@pytest.fixture(scope="module")
def results(real):
    return run_all(real, permutations=2_000)


# --- Each test, on cases where the right answer is known ---

def test_even_counts_show_no_imbalance():
    statistic, p_value, effect = chi_square_equal([100, 100, 100])
    assert statistic == 0 and p_value == pytest.approx(1.0) and effect == 0


def test_lopsided_counts_are_flagged_as_a_big_effect():
    _, p_value, effect = chi_square_equal([180, 10, 10])
    assert p_value < 1e-10 and effect > 0.5


def test_independent_categories_show_no_link():
    _, p_value, effect = chi_square_independence([[50, 50], [50, 50]])
    assert p_value == pytest.approx(1.0) and effect == 0


def test_perfectly_linked_categories_have_cramers_v_of_one():
    _, p_value, effect = chi_square_independence([[50, 0], [0, 50]])
    assert p_value < 1e-10 and effect == pytest.approx(1.0, abs=0.02)


def test_kruskal_separates_groups_that_really_differ():
    groups = [np.arange(30) + shift for shift in (0, 100, 200)]
    _, p_value, effect = kruskal(groups)
    assert p_value < 1e-10 and 0.8 < effect <= 1.0


def test_kruskal_sees_nothing_in_identical_groups():
    group = np.arange(30)
    _, p_value, effect = kruskal([group, group.copy(), group.copy()])
    assert p_value > 0.9 and effect < 0.01


def test_mann_whitney_effect_is_near_one_for_separated_groups_and_zero_for_identical_ones():
    assert mann_whitney(np.arange(20), np.arange(20) + 100)[2] == pytest.approx(1.0)
    assert mann_whitney(np.arange(20), np.arange(20))[2] == pytest.approx(0.0, abs=0.01)


def test_spearman_of_a_perfect_relationship():
    rho, p_value, effect = spearman(np.arange(30), np.arange(30) * 3 + 1)
    assert rho == pytest.approx(1.0) and effect == pytest.approx(1.0) and p_value < 1e-10


# --- The shuffling test ---

def test_shuffling_finds_a_gap_that_is_really_there():
    values = np.array([1.0] * 20 + [10.0] * 20)
    codes = np.array([0] * 20 + [1] * 20)
    observed, p_value, _ = permutation_gap(values, codes, 2, permutations=2_000)
    assert observed == pytest.approx(9.0)
    assert p_value < 0.01


def test_shuffling_finds_nothing_in_pure_noise():
    rng = np.random.default_rng(5)
    values = rng.normal(100, 10, 200)
    codes = np.tile(np.arange(4), 50)
    _, p_value, _ = permutation_gap(values, codes, 4, use_mean=True, permutations=2_000)
    assert p_value > 0.05


def test_shuffling_is_repeatable_and_a_p_value_is_never_zero():
    values = np.array([1.0] * 10 + [100.0] * 10)
    codes = np.array([0] * 10 + [1] * 10)
    first = permutation_gap(values, codes, 2, permutations=500, seed=3)
    again = permutation_gap(values, codes, 2, permutations=500, seed=3)
    assert first[:2] == again[:2]
    assert first[1] >= 1 / 501


def test_the_gap_is_measured_against_the_smallest_group():
    values = np.array([100.0, 100.0, 150.0, 150.0])
    observed, _, _ = permutation_gap(values, np.array([0, 0, 1, 1]), 2, permutations=10)
    assert observed == pytest.approx(0.5)


def test_means_and_totals_differ_when_group_sizes_differ():
    values = np.array([10.0, 10.0, 10.0, 10.0, 10.0, 10.0])
    codes = np.array([0, 0, 0, 0, 1, 1])
    assert permutation_gap(values, codes, 2, use_mean=False, permutations=5)[0] == pytest.approx(1.0)
    assert permutation_gap(values, codes, 2, use_mean=True, permutations=5)[0] == pytest.approx(0.0)


# --- Adjusting for many tests ---

def test_holm_matches_the_worked_example():
    assert holm_adjust([0.01, 0.04, 0.03]).tolist() == pytest.approx([0.03, 0.06, 0.06])


def test_adjusted_p_values_are_never_smaller_than_the_originals_or_above_one():
    raw = np.array([0.001, 0.2, 0.049, 0.8, 0.5])
    adjusted = holm_adjust(raw)
    assert (adjusted >= raw).all() and (adjusted <= 1).all()


def test_a_single_test_is_not_adjusted():
    assert holm_adjust([0.03]).tolist() == [0.03]


def test_adjustment_keeps_the_order_of_the_tests():
    raw = np.array([0.04, 0.001, 0.2])
    assert list(np.argsort(holm_adjust(raw))) == list(np.argsort(raw))


# --- Ranges and how much data is needed ---

def test_the_interval_contains_the_average_and_is_repeatable():
    values = np.random.default_rng(1).normal(50, 5, 300)
    low, high = bootstrap_interval(values)
    assert low < values.mean() < high
    assert (low, high) == bootstrap_interval(values)


def test_more_data_gives_a_narrower_interval():
    rng = np.random.default_rng(2)
    small = bootstrap_interval(rng.normal(50, 5, 50))
    large = bootstrap_interval(rng.normal(50, 5, 2_000))
    assert large[1] - large[0] < small[1] - small[0]


def test_the_smallest_detectable_difference_matches_the_formula():
    assert minimum_detectable_difference(1, 100, 100) == pytest.approx(0.3962, abs=0.001)


def test_four_times_the_data_halves_the_smallest_detectable_difference():
    assert minimum_detectable_difference(1, 400, 400) == pytest.approx(
        minimum_detectable_difference(1, 100, 100) / 2)


# --- The tests are trustworthy: few false alarms, and real differences get found ---

def test_a_pure_noise_comparison_raises_false_alarms_about_five_percent_of_the_time():
    rng = np.random.default_rng(11)
    alarms = sum(
        stats.kruskal([rng.exponential(300, 150) for _ in range(3)])[1] < 0.05 for _ in range(400)
    )
    assert 0.02 <= alarms / 400 <= 0.09


def test_shuffling_also_raises_about_five_percent_false_alarms():
    rng = np.random.default_rng(12)
    codes = np.tile(np.arange(5), 20)
    alarms = sum(
        permutation_gap(rng.exponential(100, 100), codes, 5, True, 300, seed=i)[1] < 0.05 for i in range(120)
    )
    assert alarms / 120 <= 0.12


def test_a_planted_city_boost_is_found_more_often_the_bigger_it_is(real):
    power = power_city_order_size(real, lifts=(0.0, 0.3), repetitions=60)
    assert power.loc[0, "detected"] <= 0.2
    assert power.loc[1, "detected"] >= 0.8


def test_a_planted_saturday_boost_is_found_when_it_is_large(real):
    power = power_weekday(real, lifts=(0.0, 1.0), repetitions=40, permutations=200)
    assert power.loc[0, "gap_detected"] <= 0.25
    assert power.loc[1, "gap_detected"] >= 0.8


# --- The real data ---

def test_every_question_is_tested_once(results):
    assert results["id"].is_unique and len(results) == 22


def test_p_values_are_valid_and_adjustment_only_raises_them(results):
    assert results["p_value"].between(0, 1).all()
    assert (results["p_adjusted"] >= results["p_value"]).all()
    assert (results["p_adjusted"] <= 1).all()


def test_effect_sizes_are_on_their_scales(results):
    assert (results["effect_size"] >= 0).all()
    assert (results["effect_size"] <= 1.5).all()


def test_verdicts_follow_the_adjusted_p_values(results):
    real_ones = results["verdict"] == "Real difference"
    assert (results.loc[real_ones, "p_adjusted"] < 0.05).all()
    assert (results.loc[~real_ones, "p_adjusted"] >= 0.05).all()


def test_results_are_repeatable(real):
    pd.testing.assert_frame_equal(run_all(real, permutations=300), run_all(real, permutations=300))


def test_testing_leaves_the_data_alone(real):
    before = real.copy()
    run_all(real, permutations=100)
    pd.testing.assert_frame_equal(real, before)


def test_the_saved_results_match_a_fresh_run(real):
    saved = pd.read_csv(RESULTS_PATH)
    fresh = run_all(real)
    assert saved["id"].tolist() == fresh["id"].tolist()
    assert saved["p_value"].to_numpy() == pytest.approx(fresh["p_value"].to_numpy(), abs=1e-5)
    assert saved["verdict"].tolist() == fresh["verdict"].tolist()


def test_detectable_differences_table(real):
    table = stats.detectable_differences(real)
    assert len(table) == 5
    assert (table["smallest_detectable"] > 0).all()
    city = table.loc[table["comparison"].str.contains("one city"), "as_share_of_average"].iloc[0]
    weekday = table.loc[table["comparison"].str.contains("one weekday"), "as_share_of_average"].iloc[0]
    assert weekday > city  # far fewer days than sales, so far less is detectable
