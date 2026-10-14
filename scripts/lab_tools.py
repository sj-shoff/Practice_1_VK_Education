import argparse
import csv
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SCALE = os.environ.get("LAB_SCALE", "sf1")
if SCALE != "sf1":
    raise ValueError("Для этой практической выбран только SF1: LAB_SCALE=sf1.")
FACTOR = int(SCALE[2:])
OUT = ROOT / "artifacts" / SCALE
TRINO = os.environ.get("TRINO_URL", "http://trino:8080").rstrip("/")
LAKE = os.environ.get("LAKEKEEPER_URL", "http://lakekeeper:8181").rstrip("/")


def api(url, method="GET", body=None, headers=None):
    request = Request(url, data=body, method=method, headers=headers or {})
    try:
        with urlopen(request, timeout=120) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")


def query(sql):
    started = time.perf_counter()
    status, body = api(TRINO + "/v1/statement", "POST", sql.strip().rstrip(";").encode(),
                       {"X-Trino-User": "sergey", "Content-Type": "text/plain; charset=utf-8"})
    rows, columns, stats, query_id = [], [], {}, None
    while True:
        if status != 200:
            raise RuntimeError(f"Trino HTTP {status}: {body}")
        page = json.loads(body)
        query_id = page.get("id", query_id)
        if page.get("error"):
            error = page["error"]
            raise RuntimeError(f"{query_id}: {error.get('errorName')}: {error.get('message')}")
        if "columns" in page:
            columns = [column["name"] for column in page["columns"]]
        rows.extend(page.get("data", []))
        stats = page.get("stats", stats)
        if not page.get("nextUri"):
            break
        status, body = api(page["nextUri"], headers={"X-Trino-User": "sergey"})
    return {"id": query_id, "rows": rows, "columns": columns, "stats": stats,
            "wall_seconds": time.perf_counter() - started}


def save_json(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def save_csv(name, headers, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)


def prepare():
    required_sql = ("01_bronze.sql", "02_silver_gold.sql", "03_compression.sql",
                    "04_measurements.sql", "05_quality.sql", "q18_source.sql")
    for name in required_sql:
        path = ROOT / "sql" / name
        if not path.is_file():
            raise RuntimeError(f"Отсутствует SQL-файл: {path}")
        if "__SCALE__" in path.read_text(encoding="utf-8"):
            raise RuntimeError(f"В {name} остался шаблон масштаба; нужен готовый SQL для SF1.")
    save_json("selected_scale.json", {"scale": SCALE, "factor": FACTOR})
    print(f"SQL подготовлен для {SCALE}. Схемы: bronze.{SCALE}, silver.{SCALE}, gold.{SCALE}.")


def initialize():
    for attempt in range(60):
        try:
            health_status, _ = api(LAKE + "/health")
            if health_status == 200:
                break
        except URLError:
            pass
        if attempt == 59:
            raise RuntimeError("Lakekeeper не стал доступен. Проверь docker compose logs lakekeeper.")
        time.sleep(2)
    body = json.dumps({"accept-terms-of-use": True}).encode()
    status, text = api(LAKE + "/management/v1/bootstrap", "POST", body,
                       {"Content-Type": "application/json"})
    already = any(word in text.lower() for word in ["alreadybootstrapped", "already bootstrapped",
                                                     "not open for bootstrap"])
    if status not in (200, 204) and not already:
        raise RuntimeError(f"Bootstrap HTTP {status}: {text}")
    print("Lakekeeper инициализирован.")
    for layer in ("bronze", "silver", "gold"):
        status, text = api(LAKE + "/catalog/v1/config?" + urlencode({"warehouse": layer}))
        if status == 200:
            print(f"Warehouse {layer} уже существует.")
            continue
        payload = {"warehouse-name": layer, "project-id": "00000000-0000-0000-0000-000000000000",
                   "storage-profile": {"type": "s3", "bucket": layer, "key-prefix": "",
                                       "endpoint": "http://minio:9000", "region": "us-east-1",
                                       "path-style-access": True, "flavor": "s3-compat", "sts-enabled": False},
                   "storage-credential": {"type": "s3", "credential-type": "access-key",
                                          "access-key-id": "minioadmin", "secret-access-key": "minioadmin"}}
        status, text = api(LAKE + "/management/v1/warehouse", "POST", json.dumps(payload).encode(),
                           {"Content-Type": "application/json"})
        if status not in (200, 201):
            raise RuntimeError(f"Warehouse {layer}: HTTP {status}: {text}")
        print(f"Warehouse {layer} создан: {text}")


def source_sql():
    return (ROOT / "sql/q18_source.sql").read_text(encoding="utf-8").strip().rstrip(";")


def bronze_sql(codec):
    return source_sql().replace(f"tpch.{SCALE}.", f"bronze.{SCALE}_{codec.lower()}.")


def verify():
    source_result = query(source_sql())
    save_json("source_query.json", source_result)
    expected = source_result["rows"]
    actual = query(f"SELECT * FROM gold.{SCALE}.q18_large_volume_customer "
                   "ORDER BY totalprice DESC, orderdate")["rows"]
    if expected != actual:
        raise RuntimeError("Gold отличается от исходного Q18 на tpch.")
    counts = {}
    for table, base_count in [("customer", 150000), ("orders", 1500000), ("lineitem", 6001215)]:
        n = query(f"SELECT count(*) FROM bronze.{SCALE}.{table}")["rows"][0][0]
        counts[table] = n
        if n != base_count * FACTOR:
            raise RuntimeError(f"Bronze {table}: {n}, ожидалось {base_count * FACTOR}.")
    save_json("q18_expected.json", expected)
    save_csv("q18_gold.csv", ["name", "custkey", "orderkey", "orderdate", "totalprice", "total_quantity"], actual)
    quality = query((ROOT / "sql/05_quality.sql").read_text())["rows"]
    if any(row[1] != 0 for row in quality):
        raise RuntimeError(f"Нарушены проверки качества: {quality}")
    save_json("quality_checks.json", quality)
    save_json("verification.json", {"scale": SCALE, "bronze_counts": counts,
                                   "gold_matches_source": True, "gold_rows": len(actual)})
    print(f"Gold полностью совпадает с исходным Q18: {len(actual)} строк. Bronze: {counts}.")


def benchmark(repeats):
    if repeats < 3:
        raise ValueError("Нужно минимум три измеряемых повтора.")
    expected = query(source_sql())["rows"]
    for codec in ("GZIP", "ZSTD"):
        for _ in range(2):
            if query(bronze_sql(codec))["rows"] != expected:
                raise RuntimeError(f"Результат Bronze {codec} не совпадает с Q18.")
    records = []
    for run in range(1, repeats + 1):
        order = ("GZIP", "ZSTD") if run % 2 else ("ZSTD", "GZIP")
        for codec in order:
            result = query(bronze_sql(codec))
            if result["rows"] != expected:
                raise RuntimeError(f"Результат {codec} изменился в повторе {run}.")
            records.append([SCALE, codec, run, result["id"], result["wall_seconds"],
                            result["stats"].get("elapsedTimeMillis"), len(result["rows"])])
            print(f"{codec}, повтор {run}: {result['wall_seconds']:.4f} с", flush=True)
    save_csv("benchmark_runs.csv", ["scale", "codec", "run", "query_id", "client_wall_seconds",
                                    "trino_elapsed_ms", "result_rows"], records)
    summaries = []
    for codec in ("GZIP", "ZSTD"):
        seconds = [row[4] for row in records if row[1] == codec]
        bytes_total = 0
        for table in ("customer", "orders", "lineitem"):
            data = query(f'SELECT coalesce(sum(file_size_in_bytes), 0) '
                         f'FROM bronze.{SCALE}_{codec.lower()}."{table}$files" WHERE content = 0')
            bytes_total += data["rows"][0][0]
        summaries.append([SCALE, codec, repeats, statistics.median(seconds), min(seconds), max(seconds),
                          bytes_total, bytes_total / 1048576])
    save_csv("benchmark_summary.csv", ["scale", "codec", "repeats", "median_client_wall_seconds",
                                       "min_seconds", "max_seconds", "active_data_bytes", "active_data_mib"], summaries)
    print("Сводка:")
    for row in summaries:
        print(f"{row[1]}: медиана {row[3]:.4f} с, активные данные {row[7]:.2f} MiB.")


def snapshots():
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    table = f"silver.{SCALE}.snapshot_demo_{suffix}"
    query(f"CREATE TABLE {table} WITH (format = 'PARQUET') AS "
          f"SELECT * FROM silver.{SCALE}.large_order_lines ORDER BY orderkey, linenumber LIMIT 20")
    count_before = query(f"SELECT count(*) FROM {table}")["rows"][0][0]
    if count_before == 0:
        raise RuntimeError("В Silver нет строк для демонстрации.")
    schema, name = table.split(".")[1:]
    files_sql = f'SELECT file_path FROM silver.{schema}."{name}$files" ORDER BY file_path'
    files_before = query(files_sql)["rows"]
    query(f"ALTER TABLE {table} ADD COLUMN note VARCHAR")
    query(f"ALTER TABLE {table} RENAME COLUMN note TO source_note")
    if query(files_sql)["rows"] != files_before:
        raise RuntimeError("Изменение схемы неожиданно переписало файлы данных.")
    null_count = query(f"SELECT count(*) FROM {table} WHERE source_note IS NULL")["rows"][0][0]
    if null_count != count_before:
        raise RuntimeError("Новые nullable-колонки должны иметь NULL у старых строк.")
    rows_before = query(f"SELECT * FROM {table} ORDER BY orderkey, linenumber")["rows"]
    snap = query(f'SELECT snapshot_id FROM silver.{schema}."{name}$snapshots" '
                 'ORDER BY committed_at DESC LIMIT 1')["rows"][0][0]
    query(f"DELETE FROM {table}")
    deleted_count = query(f"SELECT count(*) FROM {table}")["rows"][0][0]
    historical_count = query(f"SELECT count(*) FROM {table} FOR VERSION AS OF {snap}")["rows"][0][0]
    restore = f"ALTER TABLE {table} EXECUTE rollback_to_snapshot({snap});\n"
    query(restore)
    restored_count = query(f"SELECT count(*) FROM {table}")["rows"][0][0]
    if query(f"SELECT * FROM {table} ORDER BY orderkey, linenumber")["rows"] != rows_before:
        raise RuntimeError("После rollback содержимое строк отличается от исходного.")
    if deleted_count != 0 or historical_count != count_before or restored_count != count_before:
        raise RuntimeError("Демонстрация восстановления не прошла проверку.")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "restore_snapshot.sql").write_text(restore, encoding="utf-8")
    details = {"table": table, "snapshot_id": snap, "count_before": count_before,
               "count_after_delete": deleted_count, "count_from_historical_snapshot": historical_count,
               "count_after_restore": restored_count, "nullable_column": "source_note",
               "schema_change_kept_data_files": True, "restored_rows_match": True}
    save_json("snapshot_demo.json", details)
    print(json.dumps(details, ensure_ascii=False, indent=2))


def measure():
    tables = ["bronze.sf1.customer", "bronze.sf1.orders", "bronze.sf1.lineitem",
              "silver.sf1.large_orders", "silver.sf1.large_order_lines",
              "gold.sf1.q18_large_volume_customer"]
    result = []
    for table in tables:
        catalog, schema, name = table.split(".")
        count = query(f"SELECT count(*) FROM {table}")["rows"][0][0]
        files = query(f'SELECT count(*), sum(file_size_in_bytes) FROM {catalog}.{schema}."{name}$files" WHERE content=0')["rows"][0]
        ddl = query(f"SHOW CREATE TABLE {table}")["rows"][0][0]
        result.append({"table": table, "rows": count, "files": files[0], "bytes": files[1], "mib": files[1]/1048576, "ddl": ddl})
    save_json("layer_measurements.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Инструменты практической Q18")
    parser.add_argument("action", choices=["prepare", "init", "verify", "benchmark", "snapshots", "measure"])
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "init":
        initialize()
    elif args.action == "verify":
        verify()
    elif args.action == "benchmark":
        benchmark(args.repeats)
    elif args.action == "measure":
        measure()
    else:
        snapshots()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ОШИБКА: {error}", file=sys.stderr)
        sys.exit(1)
