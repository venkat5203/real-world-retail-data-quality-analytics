-- SQLite examples for the products_current_2026 table.
SELECT primary_category, COUNT(*) AS products,
       ROUND(AVG(completeness_pct), 1) AS avg_completeness_pct
FROM products_current_2026 GROUP BY primary_category ORDER BY products DESC;

SELECT
  SUM(CASE WHEN product_name = '' THEN 1 ELSE 0 END) AS missing_name,
  SUM(CASE WHEN brands = '' THEN 1 ELSE 0 END) AS missing_brand,
  SUM(CASE WHEN categories = '' THEN 1 ELSE 0 END) AS missing_category,
  SUM(CASE WHEN ingredients_text = '' THEN 1 ELSE 0 END) AS missing_ingredients
FROM products_current_2026;

SELECT substr(last_modified_at_utc, 1, 7) AS modified_month,
       COUNT(*) AS products_updated
FROM products_current_2026 GROUP BY modified_month ORDER BY modified_month;

SELECT barcode, product_name, invalid_nutrient_values
FROM products_current_2026
WHERE invalid_nutrient_values > 0
ORDER BY invalid_nutrient_values DESC, product_name;

SELECT barcode, product_name, primary_brand, primary_category,
       completeness_pct, last_modified_at_utc
FROM products_current_2026
ORDER BY last_modified_epoch DESC, completeness_pct DESC
LIMIT 25;
