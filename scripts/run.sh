#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p artifacts/sf1

docker compose run --rm tools prepare
docker compose up -d minio postgres lakekeeper
docker compose run --rm tools init
docker compose up -d trino

for attempt in $(seq 1 90); do
  if docker compose exec -T trino trino --execute 'SELECT 1' >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" -eq 90 ]; then
    echo 'Trino не стал доступен' >&2
    exit 1
  fi
  sleep 2
done

for sql in 01_bronze 02_silver_gold 03_compression; do
  docker compose exec -T trino trino --user sergey --file "/work/sql/$sql.sql" 2>&1 \
    | tee "artifacts/sf1/$sql.log"
done

docker compose run --rm tools verify | tee artifacts/sf1/verify.log
docker compose run --rm tools measure > artifacts/sf1/measure.log
docker compose run --rm --entrypoint sh tools \
  -c 'pip install --quiet -r scripts/requirements-inspect.txt && python scripts/inspect_parquet.py' \
  > artifacts/sf1/parquet_inspection.log 2>&1

docker compose run --rm tools benchmark --repeats 5 | tee artifacts/sf1/benchmark.log
docker compose run --rm tools snapshots | tee artifacts/sf1/snapshots.log

bash scripts/download_jars.sh
docker compose run --rm spark 2>&1 | tee artifacts/sf1/spark.log

docker compose ps -a > artifacts/sf1/docker_ps.txt
