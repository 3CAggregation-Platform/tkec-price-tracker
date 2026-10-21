# TK3C 比價引擎（3C 搜索引擎）

爬取燦坤（tk3c.com）與 PChome 24h 的冰箱、電視、氣炸鍋、掃地機器人分類排名與價格，記錄每日價格歷史，可用於比較不同平台的價格與後續查詢價格走勢。

## 功能

- 針對兩個平台（燦坤、PChome）的四大分類（冰箱、電視、氣炸鍋、掃地機器人）自動爬取商品排名與即時價格
  - 燦坤：搜尋頁的排行榜區塊，不足 20 筆再從搜尋結果補齊
  - PChome：搜尋 API 依銷量排序，以館別代碼與分類代碼排除配件後取前 20 筆
- 使用 MySQL 儲存商品主檔與每日價格歷史，方便追蹤價格變化趨勢
- 使用 Celery 每天自動排程爬取，爬蟲失敗會自動重試
- 使用 Redash 視覺化兩個平台的價格走勢、價格比較、排行榜、降價商品與評價
- 使用 Docker Compose（開發）與 Docker Swarm（部署）容器化所有服務

## 技術架構

- **爬蟲**：Python（燦坤解析 HTML、PChome 呼叫搜尋 API）
- **排程**：Celery + RabbitMQ，Flower 監控任務
- **API**：FastAPI
- **資料庫**：MySQL 8
- **視覺化**：Redash
- **部署**：Docker Compose / Docker Swarm
- **資料表設計**：
  - `products`：商品主檔（平台、商品編號、名稱、分類等；平台 + 商品編號為唯一鍵）
  - `price_history`：每日價格歷史（依商品編號關聯，記錄每次爬取的價格、排名與評價；同一天重跑只保留最後一次）
    - `rating` / `review_count`：平均星數與評價則數，僅 PChome 有；燦坤及無人評價的商品為 NULL
  - `crawl_log`：每次爬蟲執行的結果（平台、分類、筆數、成功或沒抓到資料）

## 專案結構

```
tk3c-price-tracker/
├── app/                           # 所有 Python 程式
│   ├── main.py                    # FastAPI 查詢 API
│   ├── celery_app.py              # Celery 設定與每日排程
│   ├── tasks.py                   # Celery 爬蟲任務（含自動重試）
│   ├── db.py                      # 資料庫連線與寫入
│   └── special_topic3C/           # 爬蟲
│       ├── fridge_search.py       # 燦坤冰箱
│       ├── tv_search.py           # 燦坤電視
│       ├── airfryer_search.py     # 燦坤氣炸鍋
│       ├── robotvacuum_search.py  # 燦坤掃地機器人
│       └── pchome_search.py       # PChome 四大分類（共用燦坤的配件過濾規則）
├── database/
│   ├── init.sql                   # 資料庫初始化 schema（新建資料庫用）
│   └── migrations/                # 既有資料庫的結構變更
├── data/                          # 爬蟲單獨執行時輸出的 CSV
├── redash/
│   ├── queries/                   # 儀表板 6 個查詢的 SQL
│   └── setup_redash.py            # 透過 Redash API 建立資料來源、查詢、圖表與儀表板
├── Dockerfile
├── docker-compose.yml             # 開發用（docker compose）
├── docker-compose-swarm.yml       # 部署用（docker swarm）
├── pyproject.toml / uv.lock / requirements.txt
└── .env                           # 帳密設定（不進 git、不進 image）
```

## 如何啟動

1. 複製專案後，在根目錄建立 `.env` 檔案：

   ```
   MYSQL_ROOT_PASSWORD=your_password
   MYSQL_DATABASE=tk3c_price_tracker
   MYSQL_PASSWORD=your_password

   RABBITMQ_USER=admin
   RABBITMQ_PASS=your_password
   RABBITMQ_HOST=localhost
   RABBITMQ_PORT=5672

   # 在本機（容器外）執行程式時連資料庫用；容器內會被 docker-compose 覆蓋成 mysql:3306
   DB_HOST=127.0.0.1
   DB_PORT=13306
   ```

2. 第一次建立資料庫時，先把 `docker-compose.yml` 裡 `./database/init.sql` 那行掛載打開，建好資料表後再註解回去（單檔掛載在 Docker Desktop 重開後常失效）。

3. 啟動全部服務：

   ```bash
   docker compose up -d
   ```

4. 也可以在本機單獨執行某個爬蟲測試，不會寫入資料庫（燦坤爬蟲把結果存成 `data/` 裡的 CSV，PChome 爬蟲只印在畫面上）：

   ```bash
   python app/special_topic3C/fridge_search.py
   python -m app.special_topic3C.pchome_search 冰箱
   ```

5. 既有資料庫要套用 `database/migrations/` 裡的結構變更時：

   ```bash
   docker exec -i tk3c_mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"' < database/migrations/001_add_platform.sql
   docker exec -i tk3c_mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"' < database/migrations/002_add_rating.sql
   ```

## 常用指令

### 容器管理

```bash
# 啟動全部服務（會依 healthcheck 等 MySQL、RabbitMQ 準備好才啟動 worker / beat）
docker compose up -d

# 查看各容器狀態
docker compose ps

# 重啟 Celery（修改爬蟲或 app/tasks.py 後需要重啟才會生效）
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

排程時間：燦坤 20:00 起、PChome 20:40 起，每 10 分鐘一個分類（見 `app/celery_app.py`）。

排程時間錯過、或任務失敗時，可以手動送出任務（只補跑部分分類時，刪掉不需要的任務名稱即可）：

```bash
docker exec tk3c_celery_worker python -c "
from app.celery_app import app
for t in ['crawl_fridge', 'crawl_tv', 'crawl_airfryer', 'crawl_robotvacuum',
          'crawl_pchome_fridge', 'crawl_pchome_tv', 'crawl_pchome_airfryer', 'crawl_pchome_robotvacuum']:
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
| Redash 儀表板 | http://localhost:5005/dashboards/1-tk3c- |

## Docker Swarm 部署

開發時用 `docker-compose.yml`，部署時用 `docker-compose-swarm.yml`。兩者共用同一個資料庫 volume，切換不會遺失資料，但**不能同時執行**（port 會衝突，兩個 beat 也會重複發送排程）。

和 compose 版本的差異：

- swarm 不支援 `build`，要先 build image 並 push 到 Docker Hub
- 程式碼打包在 image 裡，沒有 `--reload`，改程式碼後要重新 build 並升版
- `.env` 不會打包進 image（見 `.dockerignore`），部署時才透過 `env_file` 帶入
- swarm 會忽略 `depends_on`，MySQL 晚啟動時由 `app/tasks.py` 的自動重試處理

### 第一次部署

```bash
# 1. 確認 swarm 已啟動（看到 Leader 即可）
docker node ls

# 2. build image，並確認 /app 裡沒有 .env
docker build -t pennyliu32/tk3c-price-tracker:0.0.1 .
docker run --rm pennyliu32/tk3c-price-tracker:0.0.1 ls -a /app

# 3. push 到 Docker Hub
docker login -u pennyliu32
docker push pennyliu32/tk3c-price-tracker:0.0.1

# 4. 建立專題用的 overlay 網路（只需建立一次）
docker network create --scope=swarm --driver=overlay tk3c_swarm_network

# 5. 停掉 compose 版本（不要加 -v，會刪掉資料庫）
docker compose down

# 6. 載入 .env 變數後部署 stack
set -a; source .env; set +a
DOCKER_IMAGE_VERSION=0.0.1 docker stack deploy --with-registry-auth -c docker-compose-swarm.yml tk3c
```

### 更新程式碼

```bash
docker build -t pennyliu32/tk3c-price-tracker:0.0.2 .
docker push pennyliu32/tk3c-price-tracker:0.0.2
set -a; source .env; set +a
DOCKER_IMAGE_VERSION=0.0.2 docker stack deploy --with-registry-auth -c docker-compose-swarm.yml tk3c
```

### 常用指令（swarm 版）

swarm 的 container 名稱會帶亂數（例如 `tk3c_mysql.1.xxxx`），所以改用 service 名稱或 `$(docker ps -q -f name=...)` 找 container。

```bash
# 查看各 service 狀態（REPLICAS 都要是 1/1）
docker stack services tk3c

# 查看爬蟲任務執行結果與錯誤
docker service logs --since 1h tk3c_celery-worker 2>&1 | grep -E "succeeded|raised|ERROR"

# 手動觸發爬蟲（補跑當天資料）
docker exec $(docker ps -q -f name=tk3c_celery-worker) python -c "
from app.celery_app import app
for t in ['crawl_fridge', 'crawl_tv', 'crawl_airfryer', 'crawl_robotvacuum',
          'crawl_pchome_fridge', 'crawl_pchome_tv', 'crawl_pchome_airfryer', 'crawl_pchome_robotvacuum']:
    print(t, app.send_task(t).id)"

# 進入 MySQL
docker exec -it $(docker ps -q -f name=tk3c_mysql) sh -c 'mysql --default-character-set=utf8mb4 -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'

# 移除 stack，改回 compose 版本
docker stack rm tk3c
docker compose up -d
```

## Redash 視覺化

使用課程部署的 Redash（swarm stack `redash`，http://localhost:5005），連到本專案的 MySQL。

### 儀表板內容

| 圖表 | 類型 | 查詢 |
|---|---|---|
| 每日平均價格走勢（用「分類」篩選） | 折線圖 | `q1_trend.sql` |
| 燦坤 vs PChome 各分類價格比較 | 長條圖 | `q2_compare.sql` |
| 今日 Top 20 排行榜（可篩選分類、平台） | 表格 | `q3_ranking.sql` |
| 最近 14 天降價商品 | 表格 | `q4_price_drop.sql` |
| PChome 銷量排名 vs 評價 | 散佈圖 | `q5_rating.sql` |
| 爬蟲每日執行狀態（正常每天 8 筆） | 堆疊長條圖 | `q6_crawl_status.sql` |

- 欄位名稱加上 `::filter`（例如 `分類::filter`）會變成篩選器，儀表板開啟了篩選器合併，最上方的「分類」會同時套用到所有圖表
- 查詢每天 21:30 自動重新整理（PChome 最後一個分類 21:10 跑完之後）；Redash 的排程時間以 UTC 儲存，所以腳本裡寫 `13:30`

### 連線方式

- Redash 和專題在不同的 swarm stack，透過本機 port 連線：`host.docker.internal:13306`
- 使用唯讀帳號 `redash_reader`（只有 SELECT 權限），密碼存在 `.env` 的 `REDASH_DB_PASSWORD`
- Redash 10 的 MySQL 驅動不支援 MySQL 8 預設的 `caching_sha2_password`，所以這個帳號使用 `mysql_native_password`

### 重新建立儀表板

Redash 重建或想還原成預設版面時，第一次需要先在 http://localhost:5005/setup 建立管理員帳號，再執行：

```bash
# 1. 建立唯讀帳號（只需一次；已存在會略過建立）
set -a; source .env; set +a
docker exec -e RP="$REDASH_DB_PASSWORD" tk3c_mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "
CREATE USER IF NOT EXISTS '\''redash_reader'\''@'\''%'\'' IDENTIFIED WITH mysql_native_password BY '\''$RP'\'';
GRANT SELECT ON tk3c_price_tracker.* TO '\''redash_reader'\''@'\''%'\'';"'

# 2. 建立資料來源、查詢、圖表與儀表板（API Key 在 Redash 個人頁面）
REDASH_API_KEY=<你的 API Key> python3 redash/setup_redash.py
```

swarm 版的 MySQL container 名稱帶亂數，第 1 步的 `tk3c_mysql` 改成 `$(docker ps -q -f name=tk3c_mysql)`。

重複執行腳本不會產生重複的查詢或儀表板，同名的會直接更新（在 Redash 網頁上手動改過的查詢內容會被覆蓋）。

## 目前進度

- [x] 完成燦坤四大分類（冰箱、電視、氣炸鍋、掃地機器人）的爬蟲程式
- [x] 新增 PChome 四大分類爬蟲與評價
- [x] MySQL 資料庫架構設計（products + price_history + crawl_log）
- [x] 排程自動化（Celery + RabbitMQ + Flower），失敗自動重試
- [x] 使用 Docker Swarm 部署
- [x] 使用 Redash 視覺化價格走勢與比價

## 未來規劃

- 品牌名稱標準化（例如「奇美CHIMEI」與「CHIMEI」統一），方便跨平台統計
- 型號標準化（統一大小寫、去除顏色代碼），讓同型號商品能跨平台比價
- 與同學蒐集的其他平台資料合併（需先約定平台名稱、分類、品牌與價格格式）