-- 2025-2026 Retail Transactions and Stocks Data
-- SQL examples use the clean_transactions and clean_inventory SQLite tables.

-- 1) Monthly sales and units
SELECT year_month,
       COUNT(*) AS source_rows,
       ROUND(SUM(sales_amount), 2) AS sales_amount,
       ROUND(SUM(quantity), 2) AS units_sold
FROM clean_transactions
GROUP BY year_month
ORDER BY year_month;

-- 2) Sales by store
SELECT store_id,
       COUNT(*) AS source_rows,
       ROUND(SUM(sales_amount), 2) AS sales_amount,
       ROUND(SUM(quantity), 2) AS units_sold
FROM clean_transactions
GROUP BY store_id
ORDER BY sales_amount DESC;

-- 3) Top products by sales amount
SELECT sku_id, product_description,
       ROUND(SUM(quantity), 2) AS units_sold,
       ROUND(SUM(sales_amount), 2) AS sales_amount
FROM clean_transactions
GROUP BY sku_id, product_description
ORDER BY sales_amount DESC
LIMIT 20;

-- 4) Returns are kept visible and separately identified
SELECT is_return_flag,
       COUNT(*) AS source_rows,
       ROUND(SUM(sales_amount), 2) AS sales_amount,
       ROUND(SUM(quantity), 2) AS units
FROM clean_transactions
GROUP BY is_return_flag;

-- 5) Sales by channel
SELECT sales_channel,
       COUNT(*) AS source_rows,
       ROUND(SUM(sales_amount), 2) AS sales_amount
FROM clean_transactions
GROUP BY sales_channel
ORDER BY sales_amount DESC;

-- 6) Latest inventory snapshot by store
SELECT store_id,
       COUNT(DISTINCT sku_id) AS skus,
       ROUND(SUM(on_hand), 2) AS units_on_hand
FROM clean_inventory
WHERE date = (SELECT MAX(date) FROM clean_inventory)
GROUP BY store_id
ORDER BY units_on_hand DESC;
