-- 新增評價欄位，評價會隨時間變動，所以跟價格一樣每天記一筆
-- 燦坤網站沒有評價、PChome 沒人評價過的商品都存 NULL
USE tk3c_price_tracker;

ALTER TABLE price_history
    ADD COLUMN rating DECIMAL(2,1) NULL AFTER original_price,
    ADD COLUMN review_count INT NULL AFTER rating;
