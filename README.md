# TK3C 比價引擎（3C 搜索引擎）

爬取燦坤（tk3c.com）與 PChome 24h 的冰箱、電視、氣炸鍋、掃地機器人、洗衣機，以及 momo、Yahoo 購物中心的氣炸鍋分類排名與價格，記錄每日價格歷史，可用於比較不同平台的價格與後續查詢價格走勢。

## 功能

- 自動爬取各平台、各分類前 20 名的商品排名與即時價格：

  | 平台 | 分類 | 排名來源 |
  |---|---|---|
  | 燦坤 | 冰箱、電視、氣炸鍋、掃地機器人、洗衣機 | 搜尋頁的排行榜區塊，不足 20 筆再從搜尋結果補齊 |
  | PChome | 冰箱、電視、氣炸鍋、掃地機器人、洗衣機 | 搜尋 API 依銷量排序，以館別代碼與分類代碼排除配件 |
  | momo | 氣炸鍋 | 搜尋頁依銷量排序（只取 momo「氣炸鍋」分類），排除廣告商品 |
  | Yahoo 購物中心 | 氣炸鍋 | 搜尋頁依銷量排序，只保留 Yahoo 分類為「氣炸鍋/油炸鍋」的商品 |

  各平台共用燦坤爬蟲的配件過濾規則（排除關鍵字、名稱需有容量），標準一致
- 使用 MySQL 儲存商品主檔與每日價格歷史，方便追蹤價格變化趨勢
- 使用 Airflow 每天自動排程爬取（DockerOperator 啟動爬蟲 container），失敗會自動重試，可在網頁上查看每次執行的狀態與 log
- 使用 Redash 視覺化兩個平台的價格走勢、價格比較、排行榜、降價商品與評價
- 使用 Docker Compose（開發）與 Docker Swarm（部署）容器化所有服務

## 技術架構

- **爬蟲**：Python（燦坤解析 HTML、PChome 呼叫搜尋 API、momo / Yahoo 解析搜尋頁內嵌的 JSON）
- **排程**：Airflow（swarm 部署）；Celery + RabbitMQ 保留給手動補爬，Flower 監控任務
- **API**：FastAPI
- **資料庫**：MySQL 8
- **視覺化**：Redash
- **部署**：Docker Compose / Docker Swarm
- **資料表設計**：
  - `products`：商品主檔（平台、商品編號、名稱、分類等；平台 + 商品編號為唯一鍵）
  - `price_history`：每日價格歷史（依商品編號關聯，記錄每次爬取的價格、排名與評價；同一天重跑只保留最後一次）
    - `rating` / `review_count`：平均星數與評價則數，PChome、momo、Yahoo 有；燦坤及無人評價的商品為 NULL
  - `crawl_log`：每次爬蟲執行的結果（平台、分類、筆數、成功或沒抓到資料）
  - `goods_daily`：和組員 momo 資料同格式的每日商品表（中文欄位），每次爬蟲寫入後自動同步，用來合併三個平台，見[與組員資料合併](#與組員資料合併)

## 專案結構

```
tk3c-price-tracker/
├── app/                           # 所有 Python 程式
│   ├── main.py                    # FastAPI 查詢 API
│   ├── celery_app.py              # Celery 設定（beat 排程在 swarm 已停用，改由 Airflow 負責）
│   ├── tasks.py                   # Celery 爬蟲任務（含自動重試）
│   ├── producer.py                # 把 8 個爬蟲任務送進 RabbitMQ，給 Airflow DockerOperator 呼叫
│   ├── run_crawl.py               # 不經過 RabbitMQ，直接執行單一平台 + 分類的爬蟲（手動測試用）
│   ├── db.py                      # 資料庫連線與寫入
│   ├── goods_daily.py             # 轉成組員 momo 格式（品牌、型號統一寫法）並同步到 goods_daily
│   └── special_topic3C/           # 爬蟲
│       ├── fridge_search.py       # 燦坤冰箱
│       ├── tv_search.py           # 燦坤電視
│       ├── airfryer_search.py     # 燦坤氣炸鍋
│       ├── robotvacuum_search.py  # 燦坤掃地機器人
│       ├── washer_search.py       # 燦坤洗衣機
│       ├── pchome_search.py       # PChome 五個分類（共用燦坤的配件過濾規則）
│       ├── momo_search.py         # momo 氣炸鍋
│       └── yahoo_search.py        # Yahoo 購物中心氣炸鍋
├── database/
│   ├── init.sql                   # 資料庫初始化 schema（新建資料庫用）
│   └── migrations/                # 既有資料庫的結構變更
├── data/                          # 爬蟲單獨執行時輸出的 CSV
├── airflow/
│   ├── dags/tk3c_producer.py      # 每日 Producer DAG
│   ├── Dockerfile                 # 以課程的 tibame_dataflow image 為底，加入本專題的 DAG
│   └── docker-compose-airflow.yml # Airflow swarm stack
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

4. 也可以在本機單獨執行某個爬蟲測試，不會寫入資料庫（燦坤爬蟲把結果存成 `data/` 裡的 CSV，PChome、momo、Yahoo 爬蟲只印在畫面上）：

   ```bash
   python app/special_topic3C/fridge_search.py
   python -m app.special_topic3C.pchome_search 冰箱
   python -m app.special_topic3C.momo_search 氣炸鍋
   python -m app.special_topic3C.yahoo_search 氣炸鍋
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

每日排程由 Airflow 負責（見下方「Airflow 排程」）。以下是 Celery 版的手動補爬方式，Airflow 上也可以直接在網頁重跑（見「Airflow 排程」）。

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
| Airflow（帳號 admin，密碼見 `.env` 的 `AIRFLOW_ADMIN_PASSWORD`） | http://localhost:8090 |

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
# Airflow 和它啟動的爬蟲 container 用這個 attachable 網路連 MySQL
docker network create --scope=swarm --driver=overlay --attachable tk3c_attachable_network

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

## Airflow 排程

每日爬蟲由 Airflow 的 `tk3c_producer` DAG 定期把任務送進 RabbitMQ，swarm 版的 `celery-beat` 已設為 0 個副本，避免同一分類一天被爬兩次。

```
Airflow（每天 20:00）→ DockerOperator 執行 python -m app.producer → RabbitMQ → tk3c_celery-worker 爬蟲 → MySQL
```

- 參考課程 `dataflow` 的 `ProducerScheduler`：image 以 `linsamtw/tibame_dataflow:0.0.7`（Airflow 2.7.3）為底，只加入本專題的 DAG；用 DockerOperator 啟動 `pennyliu32/tk3c-price-tracker` 執行 producer，跑完自動刪除 container
- producer container 和 `tk3c_rabbitmq` 都在 `tk3c_attachable_network`，所以送得進任務（RabbitMQ 同時也在 `tk3c_swarm_network` 給 celery-worker 用）
- 每個網站各送一條 Celery chain（共 12 個任務）：不同網站同時跑，同一個網站的分類依序跑（燦坤 5 類約 6 分鐘，其他網站 1 分鐘內），進度看 Flower（http://localhost:5555）
- Airflow 只負責送任務，送成功就是綠色；爬蟲失敗的重試在 `app/tasks.py`（隔 5 分鐘，最多 3 次）
- metadata 存在本專題 MySQL 的 `airflow` 資料庫（專用帳號 `airflow`，只能存取這個資料庫）
- 帳密、金鑰都由 `.env` 的 `AIRFLOW_*` 在部署時帶入，不會打包進 image

### 第一次部署

```bash
# 1. 在 .env 加上 AIRFLOW_DB_PASSWORD、AIRFLOW_FERNET_KEY、AIRFLOW_SECRET_KEY、AIRFLOW_ADMIN_PASSWORD（隨機產生）
set -a; source .env; set +a

# 2. 建立 metadata 資料庫與專用帳號
docker exec -e AP="$AIRFLOW_DB_PASSWORD" $(docker ps -q -f name=tk3c_mysql) sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "
CREATE DATABASE IF NOT EXISTS airflow CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '\''airflow'\''@'\''%'\'' IDENTIFIED BY '\''$AP'\'';
GRANT ALL PRIVILEGES ON airflow.* TO '\''airflow'\''@'\''%'\'';"'

# 3. 確認節點有 airflow 標籤（課程設定過就不用再做）
docker node update --label-add airflow=true $(docker node ls -q)

# 4. build Airflow image 後部署（TK3C_IMAGE_VERSION 是爬蟲要用的專題 image 版本）
docker build -t pennyliu32/tk3c-airflow:0.0.2 airflow
AIRFLOW_IMAGE_VERSION=0.0.2 TK3C_IMAGE_VERSION=0.0.4 \
  docker stack deploy --with-registry-auth -c airflow/docker-compose-airflow.yml tk3c-airflow
```

DAG 部署後會自動啟用，而且會馬上補跑「最近一次」的排程（`catchup=False` 只是不補跑更早的），所以部署當下會先跑一輪。

### 常用操作

```bash
# 各 service 狀態（initdb、create-user 跑完是 0/1 Complete，屬正常）
docker stack services tk3c-airflow

# 手動觸發一次（網頁上按 DAG 右邊的 ▶ 也可以）
docker exec $(docker ps -q -f name=tk3c-airflow_scheduler) /dataflow/.venv/bin/airflow dags trigger tk3c_producer

# 只重跑某一個分類：直接執行該分類（不經過 RabbitMQ）
docker exec $(docker ps -q -f name=tk3c_celery-worker) python -m app.run_crawl tk3c 冰箱

# 專題 image 升版後，Airflow 要跟著改用新版（只需重新部署 Airflow stack）
AIRFLOW_IMAGE_VERSION=0.0.2 TK3C_IMAGE_VERSION=<新版本> \
  docker stack deploy --with-registry-auth -c airflow/docker-compose-airflow.yml tk3c-airflow
```

改回 Celery 排程：在 Airflow 暫停 `tk3c_producer`，並把 `docker-compose-swarm.yml` 裡 `celery-beat` 的 `replicas` 改回 1 後重新部署（兩個不能同時開）。

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
- 查詢每天 21:30 自動重新整理（Airflow 的爬蟲約 20:05 跑完）；Redash 的排程時間以 UTC 儲存，所以腳本裡寫 `13:30`

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

## 與組員資料合併

組員的 momo 爬蟲（[bihruwang/ecommerce_crawler](https://github.com/bihruwang/ecommerce_crawler)）存成 `momo_goods_daily` 表，本專案以組員的格式為主，另外產生一張同格式的 `goods_daily`：

| 欄位 | 說明 |
|---|---|
| 平台 | `tk3c` / `pchome`（組員的資料為 `momo`） |
| 抓取日期、分類、商品編號、商品名稱 | 和組員相同 |
| 廠牌 | 統一為組員的「英文 中文」寫法，例如燦坤的「聲寶SAMPO」、PChome 的「SAMPO」都改成「SAMPO 聲寶」（對照表在 `app/goods_daily.py` 的 `BRANDS`） |
| 型號 | 去掉括號內的顏色 / 版本（`SR-C48GDV(P2)` → `SR-C48GDV`）；沒有型號時用組員的規則，從商品名稱最後一組括號抓 |
| 售價、原價、評分、評價數 | 和組員相同（整數價格；燦坤沒有評價為 NULL） |
| 銷量、庫存、促銷文案、有政府補助、銷量下限 | 只有 momo 有，本專案為 NULL |
| 排名、連結 | 本專案多出的欄位，momo 的排名可用資料順序（依銷量排序）補上 |

```bash
# 第一次建立：建表後把既有歷史資料轉進來（之後每次爬蟲會自動同步，不用再跑）
docker exec -i $(docker ps -q -f name=tk3c_mysql) sh -c 'mysql --default-character-set=utf8mb4 -uroot -p"$MYSQL_ROOT_PASSWORD"' < database/migrations/003_add_goods_daily.sql
uv run python -m app.goods_daily
```

把組員的資料匯進同一張表（組員的 `momo_goods_daily` 先匯入本專案資料庫）：

```sql
INSERT INTO goods_daily (平台, 抓取日期, 分類, 商品編號, 廠牌, 型號, 商品名稱, 售價, 原價,
                         銷量, 評分, 評價數, 庫存, 促銷文案, 有政府補助, 銷量下限)
SELECT 'momo', 抓取日期, 分類, 商品編號, 廠牌, 型號, 商品名稱, 售價, 原價,
       銷量, 評分, 評價數, 庫存, 促銷文案, 有政府補助, 銷量下限
FROM momo_goods_daily;

-- 同型號跨平台比價
SELECT 型號, 平台, 售價 FROM goods_daily
WHERE 抓取日期 = CURDATE() AND 型號 IN (
    SELECT 型號 FROM goods_daily WHERE 抓取日期 = CURDATE() GROUP BY 型號 HAVING COUNT(DISTINCT 平台) > 1
)
ORDER BY 型號, 售價;
```

## 目前進度

- [x] 完成燦坤四大分類（冰箱、電視、氣炸鍋、掃地機器人）的爬蟲程式
- [x] 新增 PChome 四大分類爬蟲與評價
- [x] 燦坤、PChome 新增洗衣機；新增 momo、Yahoo 購物中心氣炸鍋爬蟲
- [x] MySQL 資料庫架構設計（products + price_history + crawl_log）
- [x] 排程自動化（Celery + RabbitMQ + Flower），失敗自動重試
- [x] 使用 Docker Swarm 部署
- [x] 使用 Airflow 取代 Celery beat 排程每日爬蟲
- [x] 使用 Redash 視覺化價格走勢與比價
- [x] 產生和組員 momo 資料同格式的 `goods_daily`（品牌、型號統一寫法）

## 未來規劃

- 組員的 momo 資料匯入 `goods_daily`，Redash 加上三平台比價
- PChome 商品名稱沒有括號的型號抓取規則（目前約一半抓不到型號）