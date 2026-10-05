# TK3C 比價引擎（3C 搜索引擎）

爬取燦坤（tk3c.com）的冰箱、電視、氣炸鍋、掃地機器人分類排名與價格，記錄每日價格歷史，可用於後續查詢價格走勢。

## 功能

- 針對四大分類（冰箱、電視、氣炸鍋、掃地機器人）自動爬取商品排名與即時價格
- 使用 MySQL 儲存商品主檔與每日價格歷史，方便追蹤價格變化趨勢
- 使用 Docker 容器化資料庫，方便部署與環境一致性

## 技術架構

- **爬蟲**：Python
- **資料庫**：MySQL（透過 Docker 啟動）
- **資料表設計**：
  - `products`：商品主檔（商品編號、名稱、分類等）
  - `price_history`：每日價格歷史（依商品編號關聯，記錄每次爬取的價格與時間）

## 專案結構

```
tk3c-price-tracker/
├── special_topic3C/
│   ├── fridge_search.py       # 冰箱分類爬蟲
│   ├── tv_search.py           # 電視分類爬蟲
│   ├── airfryer_search.py     # 氣炸鍋分類爬蟲
│   └── robotvacuum_search.py  # 掃地機器人分類爬蟲
├── docker-compose.yml         # MySQL 容器設定
├── init.sql                   # 資料庫初始化 schema
└── .gitignore
```

## 如何啟動

1. 複製專案後，在根目錄建立 `.env` 檔案，設定資料庫帳密：

   ```
   MYSQL_ROOT_PASSWORD=your_password
   MYSQL_DATABASE=tk3c_price_tracker
   ```

2. 啟動 MySQL 容器：

   ```bash
   docker-compose up -d
   ```

3. 執行對應分類的爬蟲程式，例如：

   ```bash
   python special_topic3C/fridge_search.py
   ```

## 常用指令

### 容器管理

```bash
# 啟動全部服務（會依 healthcheck 等 MySQL、RabbitMQ 準備好才啟動 worker / beat）
docker compose up -d

# 查看各容器狀態
docker compose ps

# 重啟 Celery（修改爬蟲或 tasks.py 後需要重啟才會生效）
docker compose restart celery-worker celery-beat

# 檢查 docker-compose.yml 格式是否正確
docker compose config -q

# 把重啟策略套用到已在執行的容器（不需重建）
docker update --restart unless-stopped tk3c_rabbitmq tk3c_flower
```

### 查看 log

```bash
# 爬蟲任務執行結果與錯誤
docker logs --since 1h tk3c_celery_worker 2>&1 | grep -E "succeeded|raised|ERROR"

# 排程送出任務的紀錄
docker logs --since 1h tk3c_celery_beat

# MySQL 啟動狀況
docker logs --tail 20 tk3c_mysql
```

### 手動觸發爬蟲（補跑當天資料）

排程時間錯過、或任務失敗時，可以手動送出任務：

```bash
docker exec tk3c_celery_worker python -c "
from celery_app import app
for t in ['crawl_fridge', 'crawl_tv', 'crawl_airfryer', 'crawl_robotvacuum']:
    print(t, app.send_task(t).id)"
```

### 查詢資料庫

```bash
# 進入 MySQL
docker exec -it tk3c_mysql sh -c 'mysql --default-character-set=utf8mb4 -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'
```

進入後常用的查詢：

```sql
-- 最近的爬蟲執行紀錄
SELECT id, category, run_at, item_count, success_count, status FROM crawl_log ORDER BY id DESC LIMIT 10;

-- 今天各分類寫入幾筆價格
SELECT p.category, COUNT(*) FROM price_history h JOIN products p ON p.id = h.product_id
WHERE h.crawl_date = CURDATE() GROUP BY p.category;

-- 刪除誤抓的商品（先刪價格歷史，再刪商品）
DELETE FROM price_history WHERE product_id = <商品 id>;
DELETE FROM products WHERE id = <商品 id>;
```

### 管理介面網址

| 服務 | 網址 |
|---|---|
| API 文件 | http://localhost:8001/docs 、 http://localhost:8001/redoc |
| phpMyAdmin | http://localhost:8080 |
| Flower（Celery 任務監控） | http://localhost:5555 |
| RabbitMQ 管理介面 | http://localhost:15672 |

## 目前進度

- [x] 完成冰箱、電視、氣炸鍋、掃地機器人四大分類的爬蟲程式
- [x] MySQL 資料庫架構設計（products + price_history）
- [x] 排程自動化（規劃使用 Celery + RabbitMQ + Flower）
- [ ] 價格走勢查詢介面

## 未來規劃

- 使用 Celery + Redis 建立每日自動排程機制
- 使用 Flower 監控排程執行狀況
- 開發簡易查詢介面，呈現商品歷史價格走勢圖