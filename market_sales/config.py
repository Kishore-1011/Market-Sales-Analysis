"""Paths and fixed values shared by the whole project."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RAW_DATA = ROOT / "data" / "raw" / "supermarket_sales.csv"
CLEAN_DATA = ROOT / "data" / "processed" / "sales_clean.csv"

TAX_RATE = 0.05
RATING_RANGE = (1, 10)
MONEY_TOLERANCE = 0.001

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
