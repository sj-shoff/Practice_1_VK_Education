CREATE SCHEMA IF NOT EXISTS bronze.sf1;

SET SESSION bronze.compression_codec = 'ZSTD';

CREATE TABLE bronze.sf1.customer
WITH (
    format = 'PARQUET',
    format_version = 2
) AS
SELECT
    custkey,
    name
FROM tpch.sf1.customer;

CREATE TABLE bronze.sf1.orders
WITH (
    format = 'PARQUET',
    format_version = 2
) AS
SELECT
    orderkey,
    custkey,
    orderdate,
    totalprice
FROM tpch.sf1.orders;

CREATE TABLE bronze.sf1.lineitem
WITH (
    format = 'PARQUET',
    format_version = 2
) AS
SELECT
    orderkey,
    linenumber,
    quantity
FROM tpch.sf1.lineitem;
