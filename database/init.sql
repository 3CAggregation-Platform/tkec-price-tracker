USE tk3c_price_tracker;

CREATE TABLE IF NOT EXISTS products (
    id INT PRIMARY KEY AUTO_INCREMENT,
    platform VARCHAR(20) NOT NULL DEFAULT 'tk3c',  -- tk3c / pchome
    product_code VARCHAR(50) NOT NULL,
    category VARCHAR(50) NOT NULL,
    brand VARCHAR(100),
    model VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    link VARCHAR(500),
    specs TEXT,
    first_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_platform_product_code (platform, product_code),
    INDEX idx_category (category),
    INDEX idx_platform_category (platform, category)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS price_history (
    id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL,
    crawl_date DATE NOT NULL,
    `rank` INT,
    discount VARCHAR(20),
    price DECIMAL(10,2) NOT NULL,
    original_price DECIMAL(10,2),
    rating DECIMAL(2,1),       -- 平均評價星數，燦坤沒有評價、PChome 無人評價時為 NULL
    review_count INT,          -- 評價則數
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    UNIQUE KEY uk_product_date (product_id, crawl_date),
    INDEX idx_crawl_date (crawl_date)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS crawl_log (
    id INT PRIMARY KEY AUTO_INCREMENT,
    platform VARCHAR(20) NOT NULL DEFAULT 'tk3c',
    category VARCHAR(50) NOT NULL,
    run_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    item_count INT NOT NULL DEFAULT 0,
    success_count INT NOT NULL DEFAULT 0,
    skipped_count INT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL,
    message TEXT,
    INDEX idx_category_run (category, run_at)
) ENGINE=InnoDB;
-- 和組員 momo 爬蟲的 momo_goods_daily 同格式（欄位名稱、型態相同），多了 平台、排名、連結
-- 建好後執行 python -m app.goods_daily 把既有的歷史資料轉進來
CREATE TABLE IF NOT EXISTS goods_daily (
    平台 VARCHAR(20) NOT NULL,          -- tk3c / pchome（組員的資料為 momo）
    抓取日期 DATE NOT NULL,
    分類 VARCHAR(50) NOT NULL,
    商品編號 VARCHAR(50) NOT NULL,
    廠牌 VARCHAR(100),                  -- 統一為組員的「英文 中文」寫法，例如 SAMPO 聲寶
    型號 VARCHAR(100),                  -- 去掉括號內的顏色 / 版本
    商品名稱 VARCHAR(255),
    售價 INT,
    原價 INT,
    銷量 VARCHAR(50),                   -- 只有 momo 有，我們的資料為 NULL
    評分 DECIMAL(2,1),                  -- 燦坤沒有評價，為 NULL
    評價數 INT,
    庫存 INT,                           -- 庫存、促銷文案、有政府補助、銷量下限只有 momo 有
    促銷文案 VARCHAR(255),
    有政府補助 BOOLEAN,
    銷量下限 INT,
    排名 INT,                           -- 依銷量排序的名次，momo 可用資料順序補上
    連結 VARCHAR(500),
    PRIMARY KEY (平台, 抓取日期, 商品編號),
    INDEX idx_分類_日期 (分類, 抓取日期),
    INDEX idx_型號 (型號)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
