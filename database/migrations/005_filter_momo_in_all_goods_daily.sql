USE tk3c_price_tracker;

-- all_goods_daily 的 momo 四類資料（mydb.momo_goods_daily）加上資料清洗，規則與本專案爬蟲一致：
--   1. 依名稱修正冰箱／洗衣機的分類：momo 四類爬蟲有分類錯誤（「洗衣機」分類約一半是冰箱，「冰箱」分類也有洗衣機），
--      名稱只有「冰箱」的歸冰箱、只有「洗衣機／洗脫」的歸洗衣機，再依（日期、分類、商品編號）去除重複
--      （錯放在洗衣機的冰箱同一天都已在冰箱分類；錯放在冰箱的洗衣機有一部分是洗衣機分類沒有的）
--      修正後名稱仍對不上分類的排除
--   2. 名稱需有容量（冰箱：公升/L、洗衣機：公斤/kg、電視：型/吋），同 app/special_topic3C/*_search.py 的 SIZE_PATTERN
--   3. 排除配件關鍵字：沿用各分類的 EXCLUDE_KEYWORDS，但拿掉 momo 長名稱裡也會出現在功能描述的字
--      （掃地機器人的「拖布、邊刷、集塵」、冰箱的「除霜」→ 改用「抹布、主刷、集塵袋、除霜鏟」等只有配件才用的詞）
-- 只影響查詢結果，mydb.momo_goods_daily 的原始資料不變
-- 其餘說明見 004_add_all_goods_daily_view.sql
CREATE OR REPLACE SQL SECURITY DEFINER VIEW all_goods_daily AS
SELECT 平台, 抓取日期, 分類, 商品編號, 廠牌, 型號, 商品名稱, 售價, 原價,
       銷量, 評分, 評價數, 庫存, 促銷文案, 有政府補助, 銷量下限, 排名, 連結
FROM tk3c_price_tracker.goods_daily
UNION ALL
SELECT 'momo',
       抓取日期,
       修正分類 COLLATE utf8mb4_0900_ai_ci,
       商品編號 COLLATE utf8mb4_0900_ai_ci,
       ANY_VALUE(廠牌)     COLLATE utf8mb4_0900_ai_ci,
       ANY_VALUE(型號)     COLLATE utf8mb4_0900_ai_ci,
       ANY_VALUE(商品名稱) COLLATE utf8mb4_0900_ai_ci,
       MIN(售價),
       CAST(ROUND(MIN(原價)) AS SIGNED),
       ANY_VALUE(銷量)     COLLATE utf8mb4_0900_ai_ci,
       CAST(ANY_VALUE(評分) AS DECIMAL(2,1)),
       CAST(ROUND(ANY_VALUE(評價數)) AS SIGNED),
       ANY_VALUE(庫存),
       ANY_VALUE(促銷文案) COLLATE utf8mb4_0900_ai_ci,
       ANY_VALUE(有政府補助),
       CAST(ROUND(ANY_VALUE(銷量下限)) AS SIGNED),
       NULL,
       CONCAT('https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code=', 商品編號) COLLATE utf8mb4_0900_ai_ci
FROM (
  SELECT m.*,
         CASE
           WHEN m.分類 IN ('冰箱', '洗衣機') AND m.商品名稱 REGEXP '冰箱' AND m.商品名稱 NOT REGEXP '洗衣機|洗脫' THEN '冰箱'
           WHEN m.分類 IN ('冰箱', '洗衣機') AND m.商品名稱 REGEXP '洗衣機|洗脫' AND m.商品名稱 NOT REGEXP '冰箱' THEN '洗衣機'
           ELSE m.分類
         END AS 修正分類
  FROM mydb.momo_goods_daily m
) x
WHERE CASE 修正分類
  WHEN '冰箱' THEN 商品名稱 REGEXP '冰箱' AND 商品名稱 NOT REGEXP '洗衣機|洗脫'
       AND 商品名稱 REGEXP '[0-9]+ *(公升|L)'
       AND 商品名稱 NOT REGEXP '除臭劑|保鮮盒|密封袋|分隔盒|冰箱貼|整理盒|收納盒|製冰盒|除霜鏟|溫度計|保鮮膜|清潔劑|濾網|保冷劑'
  WHEN '洗衣機' THEN 商品名稱 REGEXP '洗衣機|洗脫' AND 商品名稱 NOT REGEXP '冰箱'
       AND 商品名稱 REGEXP '[0-9]+(\\.[0-9]+)? *(公斤|kg)'
       AND 商品名稱 NOT REGEXP '洗衣袋|洗衣球|洗衣精|洗衣槽清潔|清潔劑|濾網|底座|增高架|防震墊|置物架|防塵套|進水管|排水管'
  WHEN '電視' THEN 商品名稱 REGEXP '電視|顯示器|螢幕'
       AND 商品名稱 REGEXP '[0-9]+ *(型|吋)'
       AND 商品名稱 NOT REGEXP '立架|遙控器|視訊盒|支架|腳架|電視盒|壁掛|掛架|壁架|電視架|旋臂|轉接器|訊號線|HDMI線|延長線'
  WHEN '掃地機器人' THEN 商品名稱 REGEXP '機器人|掃地機|掃拖'
       AND 商品名稱 NOT REGEXP '清潔液|清潔劑|耗材|抹布|主刷|配件|集塵袋|濾網'
  ELSE 1
END
GROUP BY 抓取日期, 修正分類, 商品編號;
