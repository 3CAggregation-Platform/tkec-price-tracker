-- 每日平均價格走勢：用「分類」篩選，比較兩個平台
SELECT
    h.crawl_date AS 日期,
    p.category AS `分類::filter`,
    CASE p.platform WHEN 'tk3c' THEN '燦坤' ELSE 'PChome' END AS 平台,
    ROUND(AVG(h.price)) AS 平均價格
FROM price_history h
JOIN products p ON p.id = h.product_id
GROUP BY h.crawl_date, p.category, p.platform
ORDER BY h.crawl_date
