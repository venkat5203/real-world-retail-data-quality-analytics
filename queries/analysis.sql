-- Example analysis queries (SQLite, clean_transactions table)
-- 1) Monthly revenue and row volume
SELECT InvoiceMonth, COUNT(*) AS row_count, ROUND(SUM(Revenue),2) AS revenue
FROM clean_transactions GROUP BY InvoiceMonth ORDER BY InvoiceMonth;
-- 2) Revenue by country
SELECT Country, COUNT(*) AS rows, ROUND(SUM(Revenue),2) AS revenue
FROM clean_transactions GROUP BY Country ORDER BY revenue DESC;
-- 3) Top products
SELECT StockCode, Description, SUM(Quantity) AS units, ROUND(SUM(Revenue),2) AS revenue
FROM clean_transactions GROUP BY StockCode, Description ORDER BY revenue DESC LIMIT 20;
-- 4) Customer concentration
SELECT CustomerID, COUNT(*) AS rows, ROUND(SUM(Revenue),2) AS revenue
FROM clean_transactions WHERE CustomerID IS NOT NULL GROUP BY CustomerID ORDER BY revenue DESC LIMIT 20;
