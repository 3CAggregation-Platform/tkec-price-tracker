-- DataMart：針對特定分析場景整理好的小表，給 Superset / Looker Studio 直接作圖
-- 每次同步後重建；資料量是 fact 的一小部分，圖表查詢又快又省

-- 同型號跨平台比價：同一天、同分類、同型號在兩個以上平台出現
CREATE OR REPLACE TABLE `{project}.{dataset}.mart_cross_platform_compare`
PARTITION BY crawl_date
OPTIONS (description = '同型號跨平台比價（每天、每型號一列）') AS
WITH p AS (
  SELECT f.crawl_date, f.category, f.model, d.platform_name, MIN(f.price) AS price
  FROM `{project}.{dataset}.fact_price_daily` f
  JOIN `{project}.{dataset}.dim_platform` d USING (platform)
  WHERE f.model IS NOT NULL
  GROUP BY f.crawl_date, f.category, f.model, d.platform_name
)
SELECT crawl_date, category, model,
       MIN(IF(platform_name = '燦坤', price, NULL))   AS price_tk3c,
       MIN(IF(platform_name = 'PChome', price, NULL)) AS price_pchome,
       MIN(IF(platform_name = 'Yahoo', price, NULL))  AS price_yahoo,
       MIN(IF(platform_name = 'momo', price, NULL))   AS price_momo,
       COUNT(*) AS platform_count,
       MIN(price) AS min_price,
       MAX(price) AS max_price,
       MAX(price) - MIN(price) AS price_gap,
       ROUND(SAFE_DIVIDE(MAX(price) - MIN(price), MIN(price)), 3) AS gap_ratio,
       IF(MAX(price) = MIN(price), '同價',
          ARRAY_AGG(platform_name ORDER BY price LIMIT 1)[OFFSET(0)]) AS cheapest_platform
FROM p
GROUP BY crawl_date, category, model
HAVING COUNT(*) >= 2;

-- 降價排行：每個平台最新一次爬蟲 vs 同一商品上一次的價格（7 天內）
CREATE OR REPLACE TABLE `{project}.{dataset}.mart_price_drop`
OPTIONS (description = '降價排行（各平台最新一次 vs 上一次）') AS
WITH h AS (
  SELECT f.*,
         LAG(price)      OVER (PARTITION BY platform, product_id ORDER BY crawl_date) AS prev_price,
         LAG(crawl_date) OVER (PARTITION BY platform, product_id ORDER BY crawl_date) AS prev_date,
         MAX(crawl_date) OVER (PARTITION BY platform) AS latest_date
  FROM `{project}.{dataset}.fact_price_daily` f
)
SELECT d.platform_name, h.category, h.model, h.product_name, h.url,
       h.prev_date, h.prev_price, h.crawl_date, h.price,
       h.prev_price - h.price AS drop_amount,
       ROUND(SAFE_DIVIDE(h.prev_price - h.price, h.prev_price), 3) AS drop_ratio
FROM h
JOIN `{project}.{dataset}.dim_platform` d USING (platform)
WHERE h.crawl_date = h.latest_date
  AND h.price < h.prev_price
  AND DATE_DIFF(h.crawl_date, h.prev_date, DAY) <= 7;

-- 價格變動統計：觀察 7 天以上的商品，變價次數與波動幅度
CREATE OR REPLACE TABLE `{project}.{dataset}.mart_price_change_stats`
OPTIONS (description = '價格變動統計（觀察 7 天以上的商品）') AS
WITH h AS (
  SELECT platform, category, product_id, crawl_date, price,
         LAG(price) OVER (PARTITION BY platform, product_id ORDER BY crawl_date) AS prev_price
  FROM `{project}.{dataset}.fact_price_daily`
)
SELECT d.platform_name, h.category, p.model, p.product_name,
       COUNT(*) AS days_observed,
       MIN(h.crawl_date) AS first_seen,
       MAX(h.crawl_date) AS last_seen,
       COUNTIF(h.price != h.prev_price) AS change_count,
       MIN(h.price) AS min_price,
       MAX(h.price) AS max_price,
       ROUND(SAFE_DIVIDE(MAX(h.price) - MIN(h.price), MAX(h.price)), 3) AS volatility
FROM h
JOIN `{project}.{dataset}.dim_platform` d USING (platform)
JOIN `{project}.{dataset}.dim_product` p USING (platform, product_id)
GROUP BY d.platform_name, h.category, p.model, p.product_name, h.platform, h.product_id
HAVING COUNT(*) >= 7;

-- 雙 11 價格檢驗：11/11 售價 vs 前 30 天，判斷是否真的比較便宜、是否先漲價再打折
CREATE OR REPLACE TABLE `{project}.{dataset}.mart_double11`
OPTIONS (description = '雙 11 價格檢驗（11/11 vs 前 30 天）') AS
WITH d11 AS (
  SELECT platform, category, product_id, price AS d11_price
  FROM `{project}.{dataset}.fact_price_daily`
  WHERE crawl_date = DATE '2026-11-11'
),
before AS (
  SELECT f.platform, f.product_id,
         COUNT(*) AS days_before,
         ROUND(AVG(f.price)) AS avg_30d,
         MIN(f.price) AS min_30d,
         MAX(IF(f.crawl_date >= DATE '2026-11-01', f.price, NULL)) AS max_10d,
         AVG(IF(f.crawl_date < DATE '2026-11-01', f.price, NULL)) AS avg_before_10d
  FROM `{project}.{dataset}.fact_price_daily` f
  WHERE f.crawl_date BETWEEN DATE '2026-10-12' AND DATE '2026-11-10'
  GROUP BY f.platform, f.product_id
)
SELECT d.platform_name, x.category, p.model, p.product_name,
       b.days_before, b.avg_30d, b.min_30d, b.max_10d, x.d11_price,
       x.d11_price - b.min_30d AS vs_min_30d,
       CASE
         WHEN x.d11_price < b.min_30d THEN '比前30天都便宜'
         WHEN x.d11_price = b.min_30d THEN '和前30天最低價相同'
         ELSE '沒有比較便宜'
       END AS verdict,
       IF(b.max_10d > b.avg_before_10d * 1.05, '是', '否') AS raised_before_d11
FROM d11 x
JOIN before b USING (platform, product_id)
JOIN `{project}.{dataset}.dim_platform` d USING (platform)
JOIN `{project}.{dataset}.dim_product` p USING (platform, product_id)
WHERE b.days_before >= 7;
