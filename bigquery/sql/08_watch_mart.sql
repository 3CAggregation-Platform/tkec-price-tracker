-- 追蹤型號跨平台比價：每天、每型號一列，兩個以上平台有價格才列入
-- 和 mart_cross_platform_compare 的差別：這裡是固定型號主動搜尋，每天可比價的型號約 80 個（排行榜重疊約 10 個）
CREATE OR REPLACE TABLE `{project}.{dataset}.mart_watch_compare`
PARTITION BY crawl_date
OPTIONS (description = '追蹤型號跨平台比價（每天、每型號一列）') AS
WITH p AS (
  SELECT f.crawl_date, f.category, f.model, f.brand, d.platform_name, f.price,
         MIN(f.price) OVER (PARTITION BY f.crawl_date, f.model) AS min_price_all
  FROM `{project}.{dataset}.fact_watch_price_daily` f
  JOIN `{project}.{dataset}.dim_platform` d USING (platform)
)
SELECT crawl_date, category, model,
       ANY_VALUE(brand) AS brand,
       MIN(IF(platform_name = '燦坤', price, NULL))   AS price_tk3c,
       MIN(IF(platform_name = 'PChome', price, NULL)) AS price_pchome,
       MIN(IF(platform_name = 'Yahoo', price, NULL))  AS price_yahoo,
       COUNT(*) AS platform_count,
       MIN(price) AS min_price,
       MAX(price) AS max_price,
       MAX(price) - MIN(price) AS price_gap,
       ROUND(SAFE_DIVIDE(MAX(price) - MIN(price), MIN(price)), 3) AS gap_ratio,
       -- 同價時列出所有最低價平台（例如「PChome、Yahoo」），三個平台都同價為「同價」
       IF(MAX(price) = MIN(price), '同價',
          ARRAY_TO_STRING(ARRAY_AGG(IF(price = min_price_all, platform_name, NULL) IGNORE NULLS
                                    ORDER BY CASE platform_name WHEN '燦坤' THEN 1 WHEN 'PChome' THEN 2 ELSE 3 END), '、')) AS cheapest_platform
FROM p
GROUP BY crawl_date, category, model
HAVING COUNT(*) >= 2;
