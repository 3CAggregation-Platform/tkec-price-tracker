-- 新增 PChome 後，商品和爬蟲紀錄都要分得出是哪個平台
-- 既有資料都是燦坤，所以預設值設為 tk3c
USE tk3c_price_tracker;

ALTER TABLE products
    ADD COLUMN platform VARCHAR(20) NOT NULL DEFAULT 'tk3c' AFTER id,
    DROP INDEX uk_product_code,
    ADD UNIQUE KEY uk_platform_product_code (platform, product_code),
    ADD INDEX idx_platform_category (platform, category);

ALTER TABLE crawl_log
    ADD COLUMN platform VARCHAR(20) NOT NULL DEFAULT 'tk3c' AFTER id;
