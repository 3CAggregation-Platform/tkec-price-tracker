USE tk3c_price_tracker;

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
