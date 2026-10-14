CREATE SCHEMA IF NOT EXISTS silver.sf1;
CREATE SCHEMA IF NOT EXISTS gold.sf1;

SET SESSION silver.compression_codec = 'ZSTD';
SET SESSION gold.compression_codec = 'ZSTD';

CREATE TABLE silver.sf1.large_orders
WITH (
    format = 'PARQUET',
    format_version = 2
) AS
SELECT
    orderkey,
    SUM(quantity) AS total_quantity
FROM bronze.sf1.lineitem
GROUP BY orderkey
HAVING SUM(quantity) > 300;

CREATE TABLE silver.sf1.large_order_lines
WITH (
    format = 'PARQUET',
    format_version = 2
) AS
SELECT
    c.name,
    c.custkey,
    o.orderkey,
    o.orderdate,
    o.totalprice,
    l.linenumber,
    l.quantity
FROM silver.sf1.large_orders big
JOIN bronze.sf1.orders o
    ON big.orderkey = o.orderkey
JOIN bronze.sf1.customer c
    ON c.custkey = o.custkey
JOIN bronze.sf1.lineitem l
    ON l.orderkey = o.orderkey;

CREATE TABLE gold.sf1.q18_large_volume_customer
WITH (
    format = 'PARQUET',
    format_version = 2
) AS
SELECT
    name,
    custkey,
    orderkey,
    orderdate,
    totalprice,
    SUM(quantity) AS total_quantity
FROM silver.sf1.large_order_lines
GROUP BY
    name,
    custkey,
    orderkey,
    orderdate,
    totalprice
ORDER BY
    totalprice DESC,
    orderdate
LIMIT 100;
