-- 各平台最新一天的 Top 20 排行榜
WITH latest AS (
    SELECT p.platform, MAX(h.crawl_date) AS crawl_date
    FROM price_history h JOIN products p ON p.id = h.product_id
    GROUP BY p.platform
)
SELECT
    p.category AS `分類::filter`,
    CASE p.platform WHEN 'tk3c' THEN '燦坤' ELSE 'PChome' END AS `平台::filter`,
    h.`rank` AS 排名,
    p.brand AS 品牌,
    p.name AS 商品名稱,
    h.price AS 售價,
    h.original_price AS 原價,
    h.discount AS 折扣,
    h.rating AS 評價,
    h.review_count AS 評價數,
    h.crawl_date AS 抓取日期,
    p.link AS 連結
FROM price_history h
JOIN products p ON p.id = h.product_id
JOIN latest l ON l.platform = p.platform AND l.crawl_date = h.crawl_date
ORDER BY p.category, p.platform, h.`rank`
