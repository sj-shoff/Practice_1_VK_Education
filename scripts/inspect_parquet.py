"""Проверяет кодек в метаданных каждого активного Parquet-файла."""

import json

import pyarrow.fs as fs
import pyarrow.parquet as parquet

from lab_tools import OUT, query

s3 = fs.S3FileSystem(
    access_key="minioadmin",
    secret_key="minioadmin",
    endpoint_override="minio:9000",
    scheme="http",
    region="us-east-1",
)

tables = {
    **{
        f"bronze.{schema}.{table}": codec
        for schema, codec in (
            ("sf1", "ZSTD"),
            ("sf1_gzip", "GZIP"),
            ("sf1_zstd", "ZSTD"),
        )
        for table in ("customer", "orders", "lineitem")
    },
    "silver.sf1.large_orders": "ZSTD",
    "silver.sf1.large_order_lines": "ZSTD",
    "gold.sf1.q18_large_volume_customer": "ZSTD",
}

records = []

for table, expected in tables.items():
    catalog, schema, name = table.split(".")
    files = query(
        f'SELECT file_path FROM {catalog}.{schema}."{name}$files" WHERE content = 0'
    )["rows"]
    assert files, f"У таблицы {table} нет файлов данных"

    for (path,) in files:
        with s3.open_input_file(path.removeprefix("s3://")) as stream:
            metadata = parquet.ParquetFile(stream).metadata
            codecs = sorted(
                {
                    metadata.row_group(group).column(column).compression
                    for group in range(metadata.num_row_groups)
                    for column in range(metadata.num_columns)
                }
            )

        assert codecs == [expected], (table, codecs, expected)
        records.append(
            {
                "table": table,
                "path": path,
                "format": "PARQUET",
                "codecs": codecs,
                "rows": metadata.num_rows,
            }
        )

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "parquet_codecs.json").write_text(
    json.dumps(records, ensure_ascii=False, indent=2)
)
print(
    f"Проверены {len(records)} активных Parquet-файлов: кодеки GZIP/ZSTD соответствуют SQL."
)
