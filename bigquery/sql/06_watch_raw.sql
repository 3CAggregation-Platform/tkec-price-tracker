-- 追蹤清單 Raw：GCS 上每天一個 JSON Lines 檔（gs://{bucket}/raw/watch_price_daily/dt=YYYY-MM-DD/data.jsonl）
-- 來源是 MySQL watch_price_daily（固定型號每天到各平台搜尋的最低價），做法同 01_raw_goods_daily.sql
CREATE OR REPLACE EXTERNAL TABLE `{project}.{dataset}.raw_watch_price_daily` (
  crawl_date   DATE,
  platform     STRING,
  category     STRING,
  model        STRING,
  product_id   STRING,
  brand        STRING,
  product_name STRING,
  price        INT64,
  list_price   INT64,
  match_count  INT64,
  url          STRING
)
WITH PARTITION COLUMNS (dt DATE)
OPTIONS (
  format = 'NEWLINE_DELIMITED_JSON',
  uris = ['gs://{bucket}/raw/watch_price_daily/*'],
  hive_partition_uri_prefix = 'gs://{bucket}/raw/watch_price_daily'
);

-- 追蹤清單 Fact：每天、每平台、每型號一筆最低價，依抓取日期分區
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.fact_watch_price_daily` (
  crawl_date   DATE   NOT NULL OPTIONS (description = '抓取日期'),
  platform     STRING NOT NULL OPTIONS (description = '平台代碼：tk3c / pchome / yahoo'),
  category     STRING NOT NULL OPTIONS (description = '分類'),
  model        STRING NOT NULL OPTIONS (description = '追蹤的型號（watchlist）'),
  product_id   STRING NOT NULL OPTIONS (description = '最低價賣場的商品編號'),
  brand        STRING OPTIONS (description = '品牌'),
  product_name STRING OPTIONS (description = '最低價賣場的商品名稱'),
  price        INT64  NOT NULL OPTIONS (description = '最低售價（元）'),
  list_price   INT64  OPTIONS (description = '原價（元）'),
  match_count  INT64  OPTIONS (description = '符合型號的賣場數'),
  url          STRING OPTIONS (description = '商品頁連結'),
  loaded_at    TIMESTAMP NOT NULL OPTIONS (description = '寫入 BigQuery 的時間')
)
PARTITION BY crawl_date
CLUSTER BY category, model
OPTIONS (description = '追蹤清單：固定型號每天在各平台的最低價');
