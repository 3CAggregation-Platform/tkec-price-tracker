-- Raw → Fact：先刪除這段日期的分區，再從 raw 重新寫入
-- BigQuery 沒有 Primary Key，所以用「整段日期刪除再寫入」確保同一天重跑不會重複，
-- 並以 QUALIFY 在同一天、同平台、同分類、同商品編號中只保留一筆（取最低價）
DELETE FROM `{project}.{dataset}.fact_price_daily`
WHERE crawl_date BETWEEN @start_date AND @end_date;

INSERT INTO `{project}.{dataset}.fact_price_daily`
  (crawl_date, platform, category, product_id, brand, model, product_name,
   price, list_price, rating, review_count, sales_rank, url, loaded_at)
SELECT crawl_date, platform, category, product_id, brand, NULLIF(TRIM(model), ''), product_name,
       price, list_price, rating, review_count, sales_rank, url, CURRENT_TIMESTAMP()
FROM `{project}.{dataset}.raw_goods_daily`
WHERE dt BETWEEN @start_date AND @end_date
  AND price IS NOT NULL
  AND product_id IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY crawl_date, platform, category, product_id ORDER BY price) = 1;
