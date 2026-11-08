-- Dim：平台與商品維度表，每次同步後重建（資料量小，重建比增量更新簡單）
CREATE OR REPLACE TABLE `{project}.{dataset}.dim_platform`
OPTIONS (description = '平台維度：顯示名稱與圖表固定配色') AS
SELECT * FROM UNNEST([
  STRUCT('tk3c' AS platform, '燦坤' AS platform_name, 'https://www.tk3c.com' AS site, '#D2621A' AS color),
  STRUCT('pchome', 'PChome', 'https://24h.pchome.com.tw', '#3B7DD8'),
  STRUCT('yahoo', 'Yahoo', 'https://tw.buy.yahoo.com', '#7B3FA0'),
  STRUCT('momo', 'momo', 'https://www.momoshop.com.tw', '#1B6B4A')
]);

-- 商品維度：每個平台的每個商品一筆，名稱、型號等取最近一次的值
CREATE OR REPLACE TABLE `{project}.{dataset}.dim_product`
CLUSTER BY platform, category
OPTIONS (description = '商品維度：最新名稱、型號、首次與最近出現日期') AS
WITH latest AS (
  SELECT platform, product_id, category, brand, model, product_name, url
  FROM `{project}.{dataset}.fact_price_daily`
  QUALIFY ROW_NUMBER() OVER (PARTITION BY platform, product_id ORDER BY crawl_date DESC) = 1
),
stats AS (
  SELECT platform, product_id,
         MIN(crawl_date) AS first_seen,
         MAX(crawl_date) AS last_seen,
         COUNT(*) AS days_observed
  FROM `{project}.{dataset}.fact_price_daily`
  GROUP BY platform, product_id
)
SELECT l.*, s.first_seen, s.last_seen, s.days_observed
FROM latest l
JOIN stats s USING (platform, product_id);
