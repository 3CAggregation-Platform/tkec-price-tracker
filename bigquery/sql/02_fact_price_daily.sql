-- Fact：每個平台、每個商品、每天一筆價格，依抓取日期分區、依平台與分類叢集
-- 只在第一次建立；之後每天由 03_load_fact.sql 覆蓋當天的分區
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.fact_price_daily` (
  crawl_date   DATE   NOT NULL OPTIONS (description = '抓取日期'),
  platform     STRING NOT NULL OPTIONS (description = '平台代碼：tk3c / pchome / yahoo / momo'),
  category     STRING NOT NULL OPTIONS (description = '分類：冰箱、電視、氣炸鍋、掃地機器人、洗衣機'),
  product_id   STRING NOT NULL OPTIONS (description = '平台上的商品編號'),
  brand        STRING OPTIONS (description = '品牌（統一為「英文 中文」）'),
  model        STRING OPTIONS (description = '型號（去掉顏色、版本）'),
  product_name STRING OPTIONS (description = '商品名稱'),
  price        INT64  NOT NULL OPTIONS (description = '售價（元）'),
  list_price   INT64  OPTIONS (description = '原價（元）'),
  rating       FLOAT64 OPTIONS (description = '平均評分'),
  review_count INT64  OPTIONS (description = '評價數'),
  sales_rank   INT64  OPTIONS (description = '依銷量的排名（momo 四類爬蟲沒有）'),
  url          STRING OPTIONS (description = '商品頁連結'),
  loaded_at    TIMESTAMP NOT NULL OPTIONS (description = '寫入 BigQuery 的時間')
)
PARTITION BY crawl_date
CLUSTER BY platform, category
OPTIONS (description = '每日商品價格（來源：MySQL all_goods_daily，經 GCS raw_goods_daily）');
