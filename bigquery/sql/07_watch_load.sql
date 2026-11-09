-- 追蹤清單 Raw → Fact：和 03_load_fact.sql 一樣先刪除這段日期的分區再寫入，
-- 並以 QUALIFY 確保同一天、同平台、同型號只有一筆
DELETE FROM `{project}.{dataset}.fact_watch_price_daily`
WHERE crawl_date BETWEEN @start_date AND @end_date;

INSERT INTO `{project}.{dataset}.fact_watch_price_daily`
  (crawl_date, platform, category, model, product_id, brand, product_name,
   price, list_price, match_count, url, loaded_at)
SELECT crawl_date, platform, category, model, product_id, brand, product_name,
       price, list_price, match_count, url, CURRENT_TIMESTAMP()
FROM `{project}.{dataset}.raw_watch_price_daily`
WHERE dt BETWEEN @start_date AND @end_date
  AND price IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY crawl_date, platform, model ORDER BY price) = 1;
