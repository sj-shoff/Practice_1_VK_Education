SELECT
    'bronze.sf1.customer' AS table_name,
    COUNT(*) AS rows
FROM bronze.sf1.customer;

SELECT
    'bronze.sf1.customer' AS table_name,
    SUM(file_size_in_bytes) AS bytes,
    SUM(file_size_in_bytes) / 1048576.0 AS mib
FROM bronze.sf1."customer$files"
WHERE content = 0;

SHOW CREATE TABLE bronze.sf1.customer;

SELECT
    'bronze.sf1.orders' AS table_name,
    COUNT(*) AS rows
FROM bronze.sf1.orders;

SELECT
    'bronze.sf1.orders' AS table_name,
    SUM(file_size_in_bytes) AS bytes,
    SUM(file_size_in_bytes) / 1048576.0 AS mib
FROM bronze.sf1."orders$files"
WHERE content = 0;

SHOW CREATE TABLE bronze.sf1.orders;

SELECT
    'bronze.sf1.lineitem' AS table_name,
    COUNT(*) AS rows
FROM bronze.sf1.lineitem;

SELECT
    'bronze.sf1.lineitem' AS table_name,
    SUM(file_size_in_bytes) AS bytes,
    SUM(file_size_in_bytes) / 1048576.0 AS mib
FROM bronze.sf1."lineitem$files"
WHERE content = 0;

SHOW CREATE TABLE bronze.sf1.lineitem;

SELECT
    'silver.sf1.large_orders' AS table_name,
    COUNT(*) AS rows
FROM silver.sf1.large_orders;

SELECT
    'silver.sf1.large_orders' AS table_name,
    SUM(file_size_in_bytes) AS bytes,
    SUM(file_size_in_bytes) / 1048576.0 AS mib
FROM silver.sf1."large_orders$files"
WHERE content = 0;

SHOW CREATE TABLE silver.sf1.large_orders;

SELECT
    'silver.sf1.large_order_lines' AS table_name,
    COUNT(*) AS rows
FROM silver.sf1.large_order_lines;

SELECT
    'silver.sf1.large_order_lines' AS table_name,
    SUM(file_size_in_bytes) AS bytes,
    SUM(file_size_in_bytes) / 1048576.0 AS mib
FROM silver.sf1."large_order_lines$files"
WHERE content = 0;

SHOW CREATE TABLE silver.sf1.large_order_lines;

SELECT
    'gold.sf1.q18_large_volume_customer' AS table_name,
    COUNT(*) AS rows
FROM gold.sf1.q18_large_volume_customer;

SELECT
    'gold.sf1.q18_large_volume_customer' AS table_name,
    SUM(file_size_in_bytes) AS bytes,
    SUM(file_size_in_bytes) / 1048576.0 AS mib
FROM gold.sf1."q18_large_volume_customer$files"
WHERE content = 0;

SHOW CREATE TABLE gold.sf1.q18_large_volume_customer;
