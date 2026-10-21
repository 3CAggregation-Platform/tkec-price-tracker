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