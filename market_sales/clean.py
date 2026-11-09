"""Clean the raw sales file and save the result.

Run with: python -m market_sales.clean
"""

import sys

from market_sales.cleaning import DataQualityError, load_clean
from market_sales.config import CLEAN_DATA, RAW_DATA


def main():
    try:
        clean = load_clean(RAW_DATA)
    except (DataQualityError, FileNotFoundError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    CLEAN_DATA.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(CLEAN_DATA, index=False, date_format="%Y-%m-%d %H:%M", lineterminator="\n")
    print(f"Cleaned {len(clean):,} sales ({clean['sold_at'].min():%d %b %Y} to {clean['sold_at'].max():%d %b %Y})")
    print(f"Wrote {CLEAN_DATA.relative_to(CLEAN_DATA.parents[2])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
