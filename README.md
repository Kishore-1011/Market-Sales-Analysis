# Market Sales Analysis

[![Notebook](https://github.com/Kishore-1011/Market-Sales-Analysis/actions/workflows/notebook.yml/badge.svg)](https://github.com/Kishore-1011/Market-Sales-Analysis/actions/workflows/notebook.yml)
![Python](https://img.shields.io/badge/Python-3.15-3776AB?logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-3.1-150458?logo=pandas&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)

An analysis of supermarket sales: how much each of three branches sold, what customers bought, and how they paid.

> **This is sample data.** The 1,000 sales are a widely shared practice dataset, not records from a real shop. The analysis shows how to explore sales data, and its findings shouldn't be read as facts about real customers.

## What the analysis shows

"Sales" means the price before the 5% tax. All the charts are drawn from the cleaned data by [`market_sales/charts.py`](market_sales/charts.py), and the full walkthrough is in [`03_sales_analysis.ipynb`](notebooks/03_sales_analysis.ipynb).

![Sales by city: Naypyitaw 105,304, Yangon 101,143 and Mandalay 101,141](reports/figures/city_sales.png)

The three cities are close: the top one is only 4.1% ahead of the lowest. Each city's strongest product line differs, though:

![Sales by product line in each city](reports/figures/product_by_city.png)

The biggest differences are in *when* people shop. Saturday averages 37% more than Monday, and 19:00 is the busiest hour:

![Average sales per day by weekday](reports/figures/weekday_pattern.png)

These are descriptions, not conclusions. Whether a difference is bigger than chance is tested in the next stage of the project. And because the data is sample data, none of it says anything about real shoppers.

## The data

[`data/raw/supermarket_sales.csv`](data/raw/supermarket_sales.csv) has one row per sale, from 1 January to 30 March 2019, at three branches (Yangon, Mandalay and Naypyitaw).

| Column | Meaning |
|---|---|
| `Invoice ID`, `Branch`, `City` | The sale and where it happened |
| `Customer type`, `Gender` | Who bought |
| `Product line` | What kind of product |
| `Unit price`, `Quantity` | Price of one item, and how many were bought |
| `Tax 5%`, `Total` | Tax on the sale, and the total paid |
| `Date`, `Time`, `Payment` | When and how it was paid |
| `Rating` | The customer's rating, from 4 to 10 |
| `cogs`, `gross income`, `gross margin percentage` | Derived from the columns above. `cogs` is really the price before tax, `gross income` is just the tax, and the margin never changes, so cleaning renames or drops them (see the [data dictionary](docs/data_dictionary.md)) |

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt

python -m market_sales.clean    # clean the raw data into data/processed/
python -m market_sales.charts   # redraw the charts in reports/figures/
pytest                          # check the cleaning, the numbers and the charts
```

Then open a notebook in Jupyter or VS Code. They work whether you start from the project folder or the `notebooks` folder:

- [`01_market_sales_exploration.ipynb`](notebooks/01_market_sales_exploration.ipynb): the original first look at the data
- [`02_data_cleaning.ipynb`](notebooks/02_data_cleaning.ipynb): how the raw file is cleaned and checked
- [`03_sales_analysis.ipynb`](notebooks/03_sales_analysis.ipynb): sales by city, product, time and customer

## Data quality

Cleaning never drops or changes anything quietly:

- Columns are only removed after the code proves they carry no extra information.
- Every rule the data should follow is checked: no missing values, unique invoice IDs, each branch in one city, sensible quantities, prices and ratings, and `subtotal + tax = total`.
- If any rule breaks, cleaning stops with a message naming every problem. Unreadable dates name the spreadsheet row.
- A test fails if the saved cleaned file is out of date with the cleaning code.

## Project structure

```
Market-Sales-Analysis/
├── market_sales/              # Reusable code
│   ├── config.py              # Paths and fixed values
│   ├── cleaning.py            # Cleaning rules and data checks
│   ├── clean.py               # python -m market_sales.clean
│   ├── analysis.py            # Sales questions, answered as tables
│   └── charts.py              # The charts
├── data/
│   ├── raw/                   # The original CSV, never edited
│   └── processed/             # The cleaned data
├── notebooks/                 # The analysis
├── docs/data_dictionary.md    # What every column means
├── tests/                     # Automated tests
├── reports/figures/           # The charts
├── requirements.txt           # Libraries the analysis needs
└── requirements-dev.txt       # Plus what's needed to run notebooks and tests
```

## Roadmap

This project is being improved in stages:

1. **Run anywhere:** folders, relative paths, pinned libraries and this README *(done)*
2. **Clean the data:** real timestamps, honest column names and automatic checks *(done)*
3. **Better questions:** sales in money, by city, product, time and customer, with one set of reusable charts *(done)*
4. **Test the findings:** use statistics to separate real differences from chance
5. **Presentation:** a clear written story, reusable code and tests
6. **Dashboard:** an interactive page with filters

## License

[MIT](LICENSE)
