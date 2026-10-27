-- 各平台最新一天的價格比較
WITH latest AS (
    SELECT p.platform, MAX(h.crawl_date) AS crawl_date
    FROM price_history h JOIN products p ON p.id = h.product_id
    GROUP BY p.platform
)
SELECT
    p.category AS 分類,
    CASE p.platform WHEN 'tk3c' THEN '燦坤' WHEN 'pchome' THEN 'PChome' WHEN 'yahoo' THEN 'Yahoo' ELSE p.platform END AS 平台,
    ROUND(AVG(h.price)) AS 平均價格,
    MIN(h.price) AS 最低價格,
    MAX(h.price) AS 最高價格,
    COUNT(*) AS 商品數
FROM price_history h
JOIN products p ON p.id = h.product_id
JOIN latest l ON l.platform = p.platform AND l.crawl_date = h.crawl_date
GROUP BY p.category, p.platform
ORDER BY p.category, 平台
