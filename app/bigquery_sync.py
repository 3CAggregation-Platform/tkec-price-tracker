"""
MySQL → GCS → BigQuery 每日同步（Raw → Fact / Dim → DataMart）

    python -m app.bigquery_sync                         # 同步今天（台北時間）
    python -m app.bigquery_sync --date 2026-11-08       # 同步指定日期
    python -m app.bigquery_sync --start 2026-09-12 --end 2026-11-08   # 補歷史資料

流程：
1. Extract：從 MySQL 的 all_goods_daily 讀出每天的資料，存成 JSON Lines 上傳到
   gs://<bucket>/raw/all_goods_daily/dt=YYYY-MM-DD/data.jsonl（同一天重跑會覆蓋同一個檔案）
2. Raw：BigQuery 外部資料表 raw_goods_daily 直接讀 GCS 的檔案
3. Fact：刪除 fact_price_daily 這段日期的分區，再從 raw 寫入並去重（BigQuery 沒有 Primary Key）
4. Dim / DataMart：重建 dim_platform、dim_product 與 mart_* 表

在 GCE VM 上用 VM 的 service account（tk3c-pipeline）存取 GCS、BigQuery、Secret Manager，
不需要下載金鑰；MySQL 用唯讀帳號，密碼從 Secret Manager 讀取。
Airflow 的 tk3c_bigquery_sync DAG 每天 21:30 用 DockerOperator 執行。
"""
import argparse
import datetime
import json
import os
import pathlib
import sys
from decimal import Decimal

import pymysql
from google.cloud import bigquery, storage

SQL_DIR = pathlib.Path(__file__).resolve().parent.parent / "bigquery" / "sql"
TAIPEI = datetime.timezone(datetime.timedelta(hours=8))

DATASET = os.getenv("BQ_DATASET", "tk3c_dw")
BUCKET = os.getenv("GCS_BUCKET", "tk3c-price-raw-fb94c850")
RAW_PREFIX = "raw/all_goods_daily"

# all_goods_daily 的中文欄位 → 資料倉儲的英文欄位
COLUMNS = {
    "抓取日期": "crawl_date",
    "平台": "platform",
    "分類": "category",
    "商品編號": "product_id",
    "廠牌": "brand",
    "型號": "model",
    "商品名稱": "product_name",
    "售價": "price",
    "原價": "list_price",
    "評分": "rating",
    "評價數": "review_count",
    "排名": "sales_rank",
    "連結": "url",
}


def mysql_password():
    """優先用環境變數（本機測試），否則從 Secret Manager 讀取"""
    if os.getenv("MYSQL_READER_PASSWORD"):
        return os.environ["MYSQL_READER_PASSWORD"]
    from google.cloud import secretmanager
    project = os.getenv("GCP_PROJECT") or bigquery.Client().project
    secret = os.getenv("MYSQL_PASSWORD_SECRET", "tk3c-mysql-reader-password")
    name = f"projects/{project}/secrets/{secret}/versions/latest"
    return secretmanager.SecretManagerServiceClient().access_secret_version(name=name).payload.data.decode()


def mysql_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "tk3c_mysql"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("MYSQL_READER_USER", "superset_reader"),
        password=mysql_password(),
        database=os.getenv("MYSQL_DATABASE", "tk3c_price_tracker"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def to_json_value(value):
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def extract_to_gcs(start, end):
    """把每天的資料上傳成一個 JSON Lines 檔，回傳 {日期: 筆數}"""
    select = ", ".join(f"`{zh}`" for zh in COLUMNS)
    with mysql_connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            f"SELECT {select} FROM all_goods_daily WHERE 抓取日期 BETWEEN %s AND %s ORDER BY 抓取日期",
            (start, end),
        )
        rows = cursor.fetchall()

    by_date = {}
    for row in rows:
        record = {en: to_json_value(row[zh]) for zh, en in COLUMNS.items()}
        by_date.setdefault(record["crawl_date"], []).append(json.dumps(record, ensure_ascii=False))

    bucket = storage.Client().bucket(BUCKET)
    for day, lines in sorted(by_date.items()):
        blob = bucket.blob(f"{RAW_PREFIX}/dt={day}/data.jsonl")
        blob.upload_from_string("\n".join(lines) + "\n", content_type="application/x-ndjson")
        print(f"  GCS gs://{BUCKET}/{blob.name}：{len(lines)} 筆")
    return {day: len(lines) for day, lines in by_date.items()}


def run_sql(client, filename, params=None):
    sql = (SQL_DIR / filename).read_text(encoding="utf-8").format(
        project=client.project, dataset=DATASET, bucket=BUCKET
    )
    config = bigquery.QueryJobConfig(query_parameters=params or [])
    job = client.query(sql, job_config=config)
    job.result()
    print(f"  BigQuery {filename} 完成（處理 {job.total_bytes_processed or 0:,} bytes）")


def sync(start, end):
    print(f"===== BigQuery 同步 {start} ~ {end} =====")
    counts = extract_to_gcs(start, end)
    if not counts:
        print("MySQL 沒有這段日期的資料，不更新 BigQuery")
        return 0

    client = bigquery.Client()
    run_sql(client, "01_raw_goods_daily.sql")
    run_sql(client, "02_fact_price_daily.sql")
    run_sql(client, "03_load_fact.sql", [
        bigquery.ScalarQueryParameter("start_date", "DATE", start),
        bigquery.ScalarQueryParameter("end_date", "DATE", end),
    ])
    run_sql(client, "04_dim.sql")
    run_sql(client, "05_marts.sql")

    fact = client.query(
        f"SELECT COUNT(*) AS n FROM `{client.project}.{DATASET}.fact_price_daily` "
        "WHERE crawl_date BETWEEN @s AND @e",
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("s", "DATE", start),
            bigquery.ScalarQueryParameter("e", "DATE", end),
        ]),
    ).result()
    loaded = next(iter(fact)).n
    print(f"===== 完成：MySQL {sum(counts.values())} 筆 → fact_price_daily {loaded} 筆（{len(counts)} 天）=====")
    return loaded


def main():
    parser = argparse.ArgumentParser(description="MySQL → GCS → BigQuery 同步")
    parser.add_argument("--date", type=datetime.date.fromisoformat)
    parser.add_argument("--start", type=datetime.date.fromisoformat)
    parser.add_argument("--end", type=datetime.date.fromisoformat)
    args = parser.parse_args()

    if args.start or args.end:
        start, end = args.start, args.end or datetime.datetime.now(TAIPEI).date()
    else:
        start = end = args.date or datetime.datetime.now(TAIPEI).date()
    if not start or start > end:
        parser.error("請指定正確的 --start / --end")

    loaded = sync(start, end)
    return 0 if loaded else 1


if __name__ == "__main__":
    sys.exit(main())
