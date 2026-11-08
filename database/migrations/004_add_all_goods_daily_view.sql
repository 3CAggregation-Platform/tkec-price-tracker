USE tk3c_price_tracker;

-- all_goods_daily：本專案的 goods_daily + 組員 momo 爬蟲的 mydb.momo_goods_daily，三平台比價、圖表都查這個 view
-- 用 view 不搬資料，組員每天 20:30 爬完就查得到，不用另外同步
-- 注意：
--   1. 組員表的 collation 是 utf8mb4_unicode_ci，goods_daily 是 utf8mb4_0900_ai_ci，文字欄位統一轉成 0900_ai_ci，
--      否則 UNION / 跨平台比對型號會出現 Illegal mix of collations
--   2. 組員表的 原價、評價數、銷量下限 是 double，轉成和 goods_daily 一樣的 INT
--   3. 組員目前沒有爬氣炸鍋（momo 氣炸鍋是本專案自己的爬蟲），分類不重疊；組員之後若也爬氣炸鍋，會出現兩份 momo 氣炸鍋
--   4. SQL SECURITY DEFINER：查詢的帳號只要有這個 view 的 SELECT 權限就好，不需要 mydb 的權限
CREATE OR REPLACE SQL SECURITY DEFINER VIEW all_goods_daily AS
SELECT 平台, 抓取日期, 分類, 商品編號, 廠牌, 型號, 商品名稱, 售價, 原價,
       銷量, 評分, 評價數, 庫存, 促銷文案, 有政府補助, 銷量下限, 排名, 連結
FROM tk3c_price_tracker.goods_daily
UNION ALL
SELECT 'momo',
       抓取日期,
       分類     COLLATE utf8mb4_0900_ai_ci,
       商品編號 COLLATE utf8mb4_0900_ai_ci,
       廠牌     COLLATE utf8mb4_0900_ai_ci,
       型號     COLLATE utf8mb4_0900_ai_ci,
       商品名稱 COLLATE utf8mb4_0900_ai_ci,
       售價,
       CAST(ROUND(原價) AS SIGNED),
       銷量     COLLATE utf8mb4_0900_ai_ci,
       CAST(評分 AS DECIMAL(2,1)),
       CAST(ROUND(評價數) AS SIGNED),
       庫存,
       促銷文案 COLLATE utf8mb4_0900_ai_ci,
       有政府補助,
       CAST(ROUND(銷量下限) AS SIGNED),
       NULL,
       CONCAT('https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code=', 商品編號) COLLATE utf8mb4_0900_ai_ci
FROM mydb.momo_goods_daily;
