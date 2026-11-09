import pandas as pd
import pytest

from market_sales.config import RAW_DATA


@pytest.fixture(scope="session")
def raw():
    return pd.read_csv(RAW_DATA)


def make_raw(**changes):
    """One valid raw row, with any column changed. Used to test one rule at a time."""
    row = {
        "Invoice ID": "111-11-1111", "Branch": "A", "City": "Yangon", "Customer type": "Member",
        "Gender": "Female", "Product line": "Health and beauty", "Unit price": 10.0, "Quantity": 2,
        "Tax 5%": 1.0, "Total": 21.0, "Date": "1/5/2019", "Time": "13:08", "Payment": "Cash",
        "cogs": 20.0, "gross margin percentage": 4.761904762, "gross income": 1.0, "Rating": 8.0,
    }
    row.update(changes)
    return pd.DataFrame([row])
