# Практическая работа №1 — Lakehouse, вариант 3 (TPC-H Q18)

**Выполнил:** Атряхин Сергей Александрович.

**Масштаб:** `sf1`.

**Отчёт:** [отчет.md](отчет.md).

Фактический результат: 57 заказов в Gold, 399 позиций в Silver; Gold и Spark совпали с исходным Q18. При пяти повторах медиана GZIP — 0,6449 с, ZSTD — 0,5267 с. [Результаты и доказательства](artifacts/sf1).

Q18 выбирает заказы, в которых суммарное количество товара больше 300, и возвращает до 100 заказов по убыванию стоимости, затем по дате. Одна строка результата соответствует заказу, а один клиент может встречаться несколько раз.

## Устройство проекта

```text
tpch.sf1 → bronze.sf1.customer / orders / lineitem
         → silver.sf1.large_orders → silver.sf1.large_order_lines
         → gold.sf1.q18_large_volume_customer
```

Данные и метаданные файлов Iceberg хранятся в трёх S3-бакетах Silo (совместимого форка MinIO). Lakekeeper предоставляет REST-каталог, PostgreSQL хранит служебное состояние каталога. Trino генерирует TPC-H и выполняет SQL. Spark читает тот же Bronze через Iceberg REST и S3, без обращения к Trino.

В Bronze сохранены нужные Q18 исходные поля, включая `linenumber` для проверки уникальности позиций. Значения и число исходных строк не изменяются. Silver сначала выделяет ключи крупных заказов, затем сохраняет их позиции вместе с данными клиентов и заказов. Gold агрегирует количество по заказу. Все основные таблицы — Iceberg v2, Parquet, ZSTD, без партиций.

SF1 выбран, чтобы обработать 150 000 клиентов, 1 500 000 заказов и 6 001 215 позиций на локальном ноутбуке и выполнить несколько полных повторов. Партиционирование не помогает запросу без фильтра по дате; для небольших выбранных таблиц оно увеличило бы число файлов.

## Воспроизведение

Требуются Docker с Compose, доступ к реестрам образов, Maven Central и PyPI, свободные порты `8080`, `8181`, `9000`, `9001`. На стенде Docker имеет 6 CPU и около 9,7 GiB памяти; Trino и Spark ограничены 4 GiB каждый. Spark запускается после замеров Trino.

Для **первоначально пустого учебного стенда**:

```bash
bash scripts/run.sh
```

Скрипт создаёт таблицы через `CREATE TABLE AS SELECT`; повторная загрузка поверх существующих таблиц намеренно завершается ошибкой, чтобы не перезаписать данные. Проверки и эксперименты можно повторять отдельно:

```bash
docker compose run --rm tools verify
docker compose run --rm tools measure
docker compose run --rm tools benchmark --repeats 5
docker compose run --rm tools snapshots
docker compose run --rm spark
```

Последовательность первого запуска вручную:

```bash
docker compose run --rm tools prepare
docker compose up -d minio postgres lakekeeper
docker compose run --rm tools init
docker compose up -d trino
# Дождаться, пока SELECT 1 выполнится успешно.
docker compose exec -T trino trino --user sergey --execute 'SELECT 1'
docker compose exec -T trino trino --user sergey --file /work/sql/01_bronze.sql
docker compose exec -T trino trino --user sergey --file /work/sql/02_silver_gold.sql
docker compose exec -T trino trino --user sergey --file /work/sql/03_compression.sql
docker compose run --rm tools verify
docker compose run --rm tools measure
docker compose run --rm tools benchmark --repeats 5
docker compose run --rm tools snapshots
bash scripts/download_jars.sh
docker compose run --rm spark
```

Дополнительная проверка фактических кодеков файлов:

```bash
docker compose run --rm --entrypoint sh tools \
  -c 'pip install --quiet -r scripts/requirements-inspect.txt && python scripts/inspect_parquet.py'
```

`download_jars.sh` получает два JAR Iceberg 1.7.1 из Maven Central и проверяет SHA-256. JAR и Docker-тома не включены в Git. Фактические результаты и логи лежат в [artifacts/sf1](artifacts/sf1), снимки экрана — в `artifacts/screenshots`.

## Подключение DBeaver

- Драйвер: Trino.
- JDBC URL: `jdbc:trino://localhost:8080`.
- Пользователь: `sergey`, пароль не задан.

Чтение витрины с явной сортировкой:

```sql
SELECT name, custkey, orderkey, orderdate, totalprice, total_quantity
FROM gold.sf1.q18_large_volume_customer
ORDER BY totalprice DESC, orderdate;
```

Порядок строк не является свойством хранения Iceberg, поэтому `ORDER BY` нужен и при чтении материализованной витрины.

## Проверки

`verify` сравнивает все строки и порядок Gold с исходным Q18 на `tpch.sf1`, проверяет число строк Bronze, NULL, дубли, ссылочную целостность, порог количества и согласованность агрегации Silver. `benchmark` проверяет совпадение ответа для каждой копии и каждого повтора. Эксперимент со снимками использует отдельную демонстрационную таблицу Silver, проверяет чтение исторического снимка и полное восстановление 20 строк. Spark сравнивает весь результат Q18 из Bronze с эталоном Trino.

Размер — сумма `file_size_in_bytes` активных файлов данных из `$files` (`content = 0`), в MiB. Метаданные и исторические файлы в этот размер не входят. Для сравнения кодеков создаются отдельные схемы `bronze.sf1_gzip` и `bronze.sf1_zstd` с одинаковыми колонками и данными; основной Bronze не изменяется.

Время в сводке — медиана пяти измеряемых запусков после двух прогревочных запусков каждого кодека. Очерёдность GZIP/ZSTD чередуется. Сохраняются идентификаторы запросов, время получения результата клиентом и `elapsedTimeMillis` Trino. Эти замеры характеризуют локальный прогретый стенд и не являются промышленным TPC-H benchmark.

## Сервисы и сохранение данных

- Trino: <http://localhost:8080>.
- Silo Console: <http://localhost:9001>, учебные реквизиты `minioadmin` / `minioadmin`.
- Lakekeeper: <http://localhost:8181>.

Порты опубликованы только на `127.0.0.1`. Учебные реквизиты предназначены для этого локального стенда. Остановка с сохранением Docker-томов:

```bash
docker compose stop
```

## Источники

Шаблон отчёта и запрос варианта 3 предоставлены в задании. За основу конфигурации стека, REST-клиента и эксперимента со снимками взят [пример практической работы](https://github.com/1KrAiDoN1/Practice_1_VK_Education); SQL, слои, проверки, Spark-запрос и результаты адаптированы к Q18. Чужие результаты и скриншоты не используются.

- [Silo: совместимый форк MinIO](https://github.com/pgsty/silo).
- [Trino 476: Iceberg connector](https://github.com/trinodb/trino/blob/476/docs/src/main/sphinx/connector/iceberg.md).
- [Apache Iceberg: настройка Spark](https://iceberg.apache.org/docs/1.7.1/spark-configuration/).
