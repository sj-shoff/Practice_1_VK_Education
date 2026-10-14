import csv
import json
import os
import time
from datetime import date
from decimal import Decimal
from pathlib import Path
from pyspark.sql import SparkSession

if os.environ.get("LAB_SCALE", "sf1") != "sf1":
    raise ValueError("В этой работе используется SF1")
spark = SparkSession.builder.appName("practice-1-q18-bronze-sergey").getOrCreate()
out = Path("/opt/spark/results/sf1")
out.mkdir(parents=True, exist_ok=True)
counts = {}
for table, expected in (("customer", 150000), ("orders", 1500000), ("lineitem", 6001215)):
    counts[table] = spark.table("bronze.sf1." + table).count()
    assert counts[table] == expected, (table, counts[table])
    print(f"Bronze {table}: {counts[table]} строк", flush=True)
spark.table("bronze.sf1.lineitem").orderBy("orderkey", "linenumber").show(10, False)
query = Path("/opt/spark/sql/q18_source.sql").read_text().replace("tpch.sf1.", "bronze.sf1.").rstrip().rstrip(";")
started = time.perf_counter()
rows = spark.sql(query).collect()
seconds = time.perf_counter() - started
normal = [[v.isoformat() if isinstance(v, date) else float(v) if isinstance(v, Decimal) else v for v in row] for row in rows]
expected = json.loads((out / "q18_expected.json").read_text())
assert normal == expected, "Spark Bronze отличается от исходного Q18 Trino"
with (out / "spark_q18.csv").open("w", newline="") as f:
    writer = csv.writer(f, lineterminator="\n")
    writer.writerow(["name", "custkey", "orderkey", "orderdate", "totalprice", "total_quantity"])
    writer.writerows(normal)
summary = {"scale": "sf1", "source": "bronze.sf1", "bronze_counts": counts,
           "result_rows": len(rows), "matches_trino": True,
           "q18_seconds_without_startup": seconds}
(out / "spark_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
spark.sql(query).show(10, False)
print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
spark.stop()
