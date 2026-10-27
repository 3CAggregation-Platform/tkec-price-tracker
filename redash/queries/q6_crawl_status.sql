-- 最近 14 天的爬蟲執行狀態（每天應該有 8 筆：2 個平台 × 4 個分類）
SELECT
    DATE(c.run_at) AS 日期,
    CONCAT(CASE c.platform WHEN 'tk3c' THEN '燦坤' WHEN 'pchome' THEN 'PChome' WHEN 'yahoo' THEN 'Yahoo' ELSE c.platform END, ' ', c.status) AS 狀態,
    COUNT(*) AS 次數
FROM crawl_log c
WHERE c.run_at >= CURDATE() - INTERVAL 14 DAY
GROUP BY DATE(c.run_at), c.platform, c.status
ORDER BY 日期
