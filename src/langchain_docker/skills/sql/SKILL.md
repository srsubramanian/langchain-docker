---
name: write_sql
description: "Write and execute SQL queries against the database"
category: database
version: "1.0.0"

# Tool configurations - gated tools that require this skill
tool_configs:
  - name: sql_query
    description: "Execute a SQL query against the database. In read-only mode, only SELECT queries are allowed."
    method: execute_query
    args:
      - name: query
        type: string
        description: "The SQL query to execute"
        required: true

  - name: sql_list_tables
    description: "List all available tables in the database."
    method: list_tables
    args: []

  - name: sql_get_samples
    description: "Get sample rows from database tables to understand data structure."
    method: load_details
    args:
      - name: resource
        type: string
        description: "Resource to load"
        required: false
        default: "samples"

# Resource configurations - Level 3 content
resource_configs:
  - name: samples
    description: "Sample rows from each database table (generated dynamically)"
    dynamic: true
    method: get_sample_rows

  - name: examples
    description: "SQL query examples for common patterns"
    file: examples.md

  - name: patterns
    description: "Common SQL patterns and anti-patterns"
    file: patterns.md
---

# SQL Skill

## Core Purpose

Write and execute SQL queries to retrieve, analyze, and manipulate data from relational databases.
This skill provides database introspection, query construction, and result interpretation capabilities.

## Guidelines

### Query Best Practices

- **Always use explicit column names** - Avoid `SELECT *` in production queries
- **Use appropriate JOINs** - Choose INNER, LEFT, RIGHT, or FULL based on data requirements
- **Use LIMIT** - Prevent large result sets that may overwhelm the response
- **Format queries for readability** - Use proper indentation and line breaks
- **Explain results clearly** - Help users understand what the data means

### Safety Considerations

- Validate user input before including in queries
- Be cautious with DELETE and UPDATE operations
- Always back up data before bulk modifications
- Use transactions for multi-step operations

### Performance Tips

- Use indexes on frequently queried columns
- Avoid functions on indexed columns in WHERE clauses
- Use EXISTS instead of IN for large subqueries
- Consider query execution plans for complex queries

## Query Patterns

### Basic Patterns

| Pattern | SQL |
|---------|-----|
| Count records | `SELECT COUNT(*) FROM table_name` |
| Filter data | `SELECT ... WHERE condition` |
| Sort results | `SELECT ... ORDER BY column DESC` |
| Limit results | `SELECT ... LIMIT n` |
| Distinct values | `SELECT DISTINCT column FROM table` |

### Join Patterns

| Pattern | SQL |
|---------|-----|
| Inner join | `SELECT ... FROM t1 JOIN t2 ON t1.id = t2.fk` |
| Left join | `SELECT ... FROM t1 LEFT JOIN t2 ON t1.id = t2.fk` |
| Multiple joins | `SELECT ... FROM t1 JOIN t2 ON ... JOIN t3 ON ...` |

### Aggregation Patterns

| Pattern | SQL |
|---------|-----|
| Group by | `SELECT col, SUM(val) FROM t GROUP BY col` |
| Having clause | `SELECT col, COUNT(*) FROM t GROUP BY col HAVING COUNT(*) > 5` |
| Multiple aggregates | `SELECT col, SUM(a), AVG(b), MAX(c) FROM t GROUP BY col` |

## Common Functions

### String Functions

```sql
-- Concatenation
SELECT CONCAT(first_name, ' ', last_name) AS full_name FROM users

-- Substring
SELECT SUBSTRING(description, 1, 100) AS short_desc FROM products

-- Case conversion
SELECT UPPER(name), LOWER(email) FROM customers
```

### Date Functions

```sql
-- Current date/time
SELECT CURRENT_DATE, CURRENT_TIMESTAMP

-- Date arithmetic (syntax varies by dialect)
SELECT * FROM orders WHERE order_date >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)

-- Extract parts
SELECT YEAR(order_date), MONTH(order_date) FROM orders
```

### Numeric Functions

```sql
-- Rounding
SELECT ROUND(price, 2) FROM products

-- Absolute value
SELECT ABS(balance) FROM accounts

-- Conditional aggregation
SELECT
    SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END) as completed_total
FROM orders
```

## Error Handling

When queries fail, check for:

1. **Syntax errors** - Missing commas, quotes, or keywords
2. **Invalid column/table names** - Verify schema matches
3. **Type mismatches** - Ensure comparisons use compatible types
4. **NULL handling** - Use IS NULL instead of = NULL
5. **Permission issues** - Verify read/write access
