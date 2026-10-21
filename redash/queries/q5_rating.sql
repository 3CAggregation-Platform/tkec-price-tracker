-- PChome 最新一天：銷量排名 vs 評價（只看有評價的商品）
SELECT
    h.`rank` AS 排名,
    h.rating AS 評價,
    h.review_count AS 評價數,
    p.category AS 分類,
    p.name AS 商品名稱
FROM price_history h
JOIN products p ON p.id = h.product_id
WHERE p.platform = 'pchome'
  AND h.rating IS NOT NULL
  AND h.crawl_date = (
      SELECT MAX(h2.crawl_date) FROM price_history h2
      JOIN products p2 ON p2.id = h2.product_id WHERE p2.platform = 'pchome'
  )
ORDER BY p.category, h.`rank`
