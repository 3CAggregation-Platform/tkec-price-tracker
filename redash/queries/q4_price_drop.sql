-- 最近 14 天內降價的商品（和前一次抓到的價格比較）
SELECT
    t.crawl_date AS 日期,
    CASE p.platform WHEN 'tk3c' THEN '燦坤' WHEN 'pchome' THEN 'PChome' WHEN 'yahoo' THEN 'Yahoo' ELSE p.platform END AS 平台,
    p.category AS `分類::filter`,
    p.name AS 商品名稱,
    t.prev_price AS 原本價格,
    t.price AS 目前價格,
    t.prev_price - t.price AS 降價金額,
    ROUND((t.prev_price - t.price) / t.prev_price * 100, 1) AS `降幅(%)`,
    p.link AS 連結
FROM (
    SELECT product_id, crawl_date, price,
           LAG(price) OVER (PARTITION BY product_id ORDER BY crawl_date) AS prev_price
    FROM price_history
) t
JOIN products p ON p.id = t.product_id
WHERE t.prev_price IS NOT NULL
  AND t.price < t.prev_price
  AND t.crawl_date >= CURDATE() - INTERVAL 14 DAY
ORDER BY t.crawl_date DESC, `降幅(%)` DESC
