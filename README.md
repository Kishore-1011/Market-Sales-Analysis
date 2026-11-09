# Market Sales Analysis

[![Notebook](https://github.com/Kishore-1011/Market-Sales-Analysis/actions/workflows/notebook.yml/badge.svg)](https://github.com/Kishore-1011/Market-Sales-Analysis/actions/workflows/notebook.yml)
![Python](https://img.shields.io/badge/Python-3.15-3776AB?logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-3.1-150458?logo=pandas&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)

An analysis of supermarket sales: how much each of three branches sold, what customers bought, and how they paid.

> **This is sample data.** The 1,000 sales are a widely shared practice dataset, not records from a real shop. The analysis shows how to explore sales data, and its findings shouldn't be read as facts about real customers.

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
| `cogs`, `gross income`, `gross margin percentage` | Derived from the columns above; see the notes in the roadmap below |

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
jupyter nbconvert --to notebook --execute --inplace notebooks/01_market_sales_exploration.ipynb
```

Or open `notebooks/01_market_sales_exploration.ipynb` in Jupyter or VS Code. It works whether you start from the project folder or the `notebooks` folder.

## Project structure

```
Market-Sales-Analysis/
├── data/raw/                  # The original CSV, never edited
├── notebooks/                 # The analysis
├── reports/                   # Charts and findings (coming)
├── requirements.txt           # Libraries the analysis needs
└── requirements-dev.txt       # Plus what's needed to run the notebook
```

## Roadmap

This project is being improved in stages:

1. **Run anywhere:** folders, relative paths, pinned libraries and this README *(done)*
2. **Clean the data:** parse dates and times, rename misleading columns and check the arithmetic
3. **Better questions:** compare sales in money rather than counts, by city, product, time and customer
4. **Test the findings:** use statistics to separate real differences from chance
5. **Presentation:** a clear written story, reusable code and tests
6. **Dashboard:** an interactive page with filters

## License

[MIT](LICENSE)
