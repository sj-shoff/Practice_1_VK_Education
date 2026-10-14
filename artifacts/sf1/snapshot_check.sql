-- Атряхин Сергей Александрович. Time travel и schema evolution
SELECT
 (SELECT count(*) FROM silver.sf1.snapshot_demo_20261014120847) AS restored_rows,
 (SELECT count(*) FROM silver.sf1.snapshot_demo_20261014120847 FOR VERSION AS OF 7037684878226293102) AS snapshot_rows,
 (SELECT count(*) FROM silver.sf1.snapshot_demo_20261014120847 WHERE source_note IS NULL) AS nullable_rows;
