SELECT
    'null_customer' AS check_name,
    COUNT(*) AS violations
FROM bronze.sf1.customer
WHERE custkey IS NULL
    OR name IS NULL

UNION ALL

SELECT
    'null_orders',
    COUNT(*)
FROM bronze.sf1.orders
WHERE orderkey IS NULL
    OR custkey IS NULL
    OR orderdate IS NULL
    OR totalprice IS NULL

UNION ALL

SELECT
    'null_lineitem',
    COUNT(*)
FROM bronze.sf1.lineitem
WHERE orderkey IS NULL
    OR linenumber IS NULL
    OR quantity IS NULL

UNION ALL

SELECT
    'duplicate_order_lines',
    COUNT(*)
FROM (
    SELECT
        orderkey,
        linenumber
    FROM bronze.sf1.lineitem
    GROUP BY
        orderkey,
        linenumber
    HAVING COUNT(*) > 1
)

UNION ALL

SELECT
    'orphan_orders',
    COUNT(*)
FROM bronze.sf1.orders o
LEFT JOIN bronze.sf1.customer c
    ON c.custkey = o.custkey
WHERE c.custkey IS NULL

UNION ALL

SELECT
    'orphan_lineitem',
    COUNT(*)
FROM bronze.sf1.lineitem l
LEFT JOIN bronze.sf1.orders o
    ON o.orderkey = l.orderkey
WHERE o.orderkey IS NULL

UNION ALL

SELECT
    'gold_quantity_not_large',
    COUNT(*)
FROM gold.sf1.q18_large_volume_customer
WHERE total_quantity <= 300

UNION ALL

SELECT
    'duplicate_gold_orders',
    COUNT(*)
FROM (
    SELECT orderkey
    FROM gold.sf1.q18_large_volume_customer
    GROUP BY orderkey
    HAVING COUNT(*) > 1
)

UNION ALL

SELECT
    'silver_quantity_mismatch',
    COUNT(*)
FROM silver.sf1.large_orders b
JOIN (
    SELECT
        orderkey,
        SUM(quantity) q
    FROM silver.sf1.large_order_lines
    GROUP BY orderkey
) l
    ON b.orderkey = l.orderkey
WHERE b.total_quantity <> l.q;
