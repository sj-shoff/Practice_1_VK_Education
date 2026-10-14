#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

printf '\033[1;36mПрактическая №1 — TPC-H Q18, SF1\033[0m\n'
printf 'Атряхин Сергей Александрович\n\n'

case "${1:?Нужен раздел: services, verify, benchmark или spark}" in
  services)
    printf 'Сервисы учебного lakehouse\n\n'
    set -x
    docker ps --filter label=com.docker.compose.project=p1q18 \
      --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
    set +x
    ;;

  verify)
    printf 'Сверка Gold с исходным Q18 и проверки качества\n\n'
    set -x
    TRINO_URL=http://127.0.0.1:8080 python3 scripts/lab_tools.py verify
    docker compose exec -T trino trino --user sergey --output-format ALIGNED \
      --file /work/sql/05_quality.sql
    set +x
    ;;

  benchmark)
    printf 'Фактические сохранённые замеры GZIP и ZSTD\n\n'
    set -x
    cat artifacts/sf1/benchmark.log
    set +x
    ;;

  spark)
    printf 'Сохранённый результат выполненного запуска Spark\n\n'
    set -x
    rg --no-line-number '^Bronze' artifacts/sf1/spark.log
    python3 -m json.tool artifacts/sf1/spark_summary.json
    head -6 artifacts/sf1/spark_q18.csv
    set +x
    ;;

  *)
    printf 'Неизвестный раздел\n' >&2
    exit 1
    ;;
esac

printf '\nКоманды завершились успешно.\n'

# Оставить PTY открытым до снятия скриншота; браузер работает только на чтение.
sleep 300
