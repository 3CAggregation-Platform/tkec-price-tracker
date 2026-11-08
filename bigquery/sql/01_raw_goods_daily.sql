-- Raw：GCS 上每天一個 JSON Lines 檔（gs://{bucket}/raw/all_goods_daily/dt=YYYY-MM-DD/data.jsonl）
-- 用外部資料表直接讀 GCS，不把資料搬進 BigQuery；GCS 檔案更新後，查詢結果自動跟著更新
-- dt 是從路徑解析出的分區欄位（Hive 分區），查詢時加 WHERE dt = ... 只會讀那一天的檔案
CREATE OR REPLACE EXTERNAL TABLE `{project}.{dataset}.raw_goods_daily` (
  crawl_date   DATE,
  platform     STRING,
  category     STRING,
  product_id   STRING,
  brand        STRING,
  model        STRING,
  product_name STRING,
  price        INT64,
  list_price   INT64,
  rating       FLOAT64,
  review_count INT64,
  sales_rank   INT64,
  url          STRING
)
WITH PARTITION COLUMNS (dt DATE)
OPTIONS (
  format = 'NEWLINE_DELIMITED_JSON',
  uris = ['gs://{bucket}/raw/all_goods_daily/*'],
  hive_partition_uri_prefix = 'gs://{bucket}/raw/all_goods_daily'
);
