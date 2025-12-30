# Advanced SQL Patterns

## Query Optimization

### Index Usage

Indexes speed up queries but slow down writes. Create indexes on:

- Primary and foreign key columns
- Columns frequently used in WHERE clauses
- Columns used in ORDER BY
- Columns used in JOIN conditions

```sql
-- Create index
CREATE INDEX idx_customers_city ON customers(city);

-- Create composite index
CREATE INDEX idx_orders_customer_date ON orders(customer_id, order_date);
```

### Avoid These Anti-Patterns

```sql
-- BAD: Function on indexed column
SELECT * FROM orders WHERE YEAR(order_date) = 2024

-- GOOD: Range query uses index
SELECT * FROM orders
WHERE order_date >= '2024-01-01' AND order_date < '2025-01-01'

-- BAD: Leading wildcard
SELECT * FROM customers WHERE name LIKE '%smith'

-- GOOD: Trailing wildcard uses index
SELECT * FROM customers WHERE name LIKE 'Smith%'

-- BAD: OR conditions on different columns
SELECT * FROM products WHERE name = 'Widget' OR category = 'Tools'

-- GOOD: UNION of indexed queries
SELECT * FROM products WHERE name = 'Widget'
UNION
SELECT * FROM products WHERE category = 'Tools'
```

## Common Table Expressions (CTEs)

CTEs improve readability for complex queries:

```sql
WITH monthly_sales AS (
    SELECT
        customer_id,
        strftime('%Y-%m', order_date) AS month,
        SUM(total) AS monthly_total
    FROM orders
    GROUP BY customer_id, strftime('%Y-%m', order_date)
),
customer_stats AS (
    SELECT
        customer_id,
        AVG(monthly_total) AS avg_monthly,
        MAX(monthly_total) AS best_month
    FROM monthly_sales
    GROUP BY customer_id
)
SELECT
    c.name,
    cs.avg_monthly,
    cs.best_month
FROM customers c
JOIN customer_stats cs ON c.id = cs.customer_id
ORDER BY cs.avg_monthly DESC
```

## Recursive Queries

For hierarchical data (e.g., categories, org charts):

```sql
-- Find all subcategories of 'Electronics'
WITH RECURSIVE category_tree AS (
    -- Base case
    SELECT id, name, parent_id, 1 as level
    FROM categories
    WHERE name = 'Electronics'

    UNION ALL

    -- Recursive case
    SELECT c.id, c.name, c.parent_id, ct.level + 1
    FROM categories c
    JOIN category_tree ct ON c.parent_id = ct.id
)
SELECT * FROM category_tree;
```

## Pivot Tables

Transform rows to columns:

```sql
-- Sales by product per quarter
SELECT
    product_id,
    SUM(CASE WHEN quarter = 1 THEN total ELSE 0 END) AS Q1,
    SUM(CASE WHEN quarter = 2 THEN total ELSE 0 END) AS Q2,
    SUM(CASE WHEN quarter = 3 THEN total ELSE 0 END) AS Q3,
    SUM(CASE WHEN quarter = 4 THEN total ELSE 0 END) AS Q4
FROM (
    SELECT
        product_id,
        total,
        ((CAST(strftime('%m', order_date) AS INTEGER) - 1) / 3) + 1 AS quarter
    FROM orders
)
GROUP BY product_id
```

## Gap Analysis

Find missing sequences:

```sql
-- Find missing order IDs
SELECT t1.id + 1 AS missing_start,
       MIN(t2.id) - 1 AS missing_end
FROM orders t1
JOIN orders t2 ON t1.id < t2.id
WHERE t1.id + 1 NOT IN (SELECT id FROM orders)
GROUP BY t1.id
```

## Deduplication

Remove or identify duplicates:

```sql
-- Find duplicate customers by email
SELECT email, COUNT(*) as count
FROM customers
GROUP BY email
HAVING COUNT(*) > 1

-- Keep only the first occurrence (by id)
DELETE FROM customers
WHERE id NOT IN (
    SELECT MIN(id)
    FROM customers
    GROUP BY email
)
```

## Date Ranges and Gaps

Generate date series and find gaps:

```sql
-- SQLite: Generate date series using recursive CTE
WITH RECURSIVE dates AS (
    SELECT DATE('2024-01-01') AS date
    UNION ALL
    SELECT DATE(date, '+1 day')
    FROM dates
    WHERE date < DATE('2024-12-31')
)
SELECT d.date
FROM dates d
LEFT JOIN orders o ON DATE(o.order_date) = d.date
WHERE o.id IS NULL
```

## Batch Processing

Process large datasets in chunks:

```sql
-- Update in batches of 1000
UPDATE products
SET last_updated = CURRENT_TIMESTAMP
WHERE id IN (
    SELECT id FROM products
    WHERE last_updated IS NULL
    LIMIT 1000
)
```

## Dialect Differences

| Feature | SQLite | PostgreSQL | MySQL |
|---------|--------|------------|-------|
| String concat | `\|\|` | `\|\|` | `CONCAT()` |
| Date format | `strftime()` | `TO_CHAR()` | `DATE_FORMAT()` |
| Limit/Offset | `LIMIT n OFFSET m` | `LIMIT n OFFSET m` | `LIMIT m, n` |
| Upsert | `INSERT OR REPLACE` | `ON CONFLICT DO UPDATE` | `ON DUPLICATE KEY UPDATE` |
| Boolean | 0/1 | TRUE/FALSE | 0/1 or TRUE/FALSE |
