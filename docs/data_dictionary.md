# Data dictionary

The cleaned data is in [`data/processed/sales_clean.csv`](../data/processed/sales_clean.csv), created from the untouched original in `data/raw/` by `python -m market_sales.clean`.

The data is sample data, not records from a real shop.

## Columns

| Column | Type | Meaning |
|---|---|---|
| `invoice_id` | text | Unique ID of the sale |
| `sold_at` | date and time | When the sale happened (the original `Date` and `Time` combined) |
| `date` | date | The day of the sale |
| `month` | number | Month number, 1 to 3 in this data |
| `month_name` | ordered category | January, February or March |
| `weekday` | ordered category | Monday to Sunday, in calendar order |
| `is_weekend` | true/false | True for Saturday and Sunday |
| `hour` | number | Hour of the day, 10 to 20 in this data |
| `branch` | category | A, B or C |
| `city` | category | Yangon (A), Mandalay (B) or Naypyitaw (C) |
| `customer_type` | category | Member or Normal |
| `gender` | category | Female or Male |
| `product_line` | category | One of six product lines |
| `unit_price` | number | Price of one item, from 10.08 to 99.96 |
| `quantity` | whole number | Items bought, from 1 to 10 |
| `subtotal` | number | `unit_price` times `quantity`, before tax (called `cogs` in the original) |
| `tax` | number | 5% of the subtotal (called `Tax 5%` in the original) |
| `total` | number | `subtotal` plus `tax`, what the customer paid |
| `payment` | category | Cash, Credit card or Ewallet |
| `rating` | number | The customer's rating, from 4 to 10 |

## What changed from the original

| Original | Now | Why |
|---|---|---|
| `cogs` | `subtotal` | It's the price before tax, not a cost of goods |
| `Tax 5%` | `tax` | A clearer name |
| `gross income` | removed | Identical to the tax, so it's not income or profit |
| `gross margin percentage` | removed | The same value (4.76%) in every row |
| `Date`, `Time` | `sold_at`, `date`, `hour` | Text turned into real timestamps |

No profit or cost figures exist in this data, so profit can't be analysed.

## Rules the data must follow

These are checked every time the data is cleaned, and cleaning stops with a message if any is broken:

- No missing values, and every invoice ID appears once
- Each branch belongs to exactly one city
- Quantity is a whole number of at least 1, and unit price is above zero
- Rating is between 1 and 10
- `subtotal` = `unit_price` x `quantity`
- `tax` = 5% of `subtotal`
- `total` = `subtotal` + `tax`
