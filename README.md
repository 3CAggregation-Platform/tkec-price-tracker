# TK3C 比價引擎（3C 搜索引擎）

爬取燦坤（tk3c.com）、PChome 24h 與 Yahoo 購物中心的冰箱、電視、氣炸鍋、掃地機器人、洗衣機，以及 momo 的氣炸鍋分類排名與價格，記錄每日價格歷史，可用於比較不同平台的價格與後續查詢價格走勢。

## 功能

- 自動爬取各平台、各分類前 20 名的商品排名與即時價格：

  | 平台 | 分類 | 排名來源 |
  |---|---|---|
  | 燦坤 | 冰箱、電視、氣炸鍋、掃地機器人、洗衣機 | 搜尋頁的排行榜區塊，不足 20 筆再從搜尋結果補齊 |
  | PChome | 冰箱、電視、氣炸鍋、掃地機器人、洗衣機 | 搜尋 API 依銷量排序，以館別代碼與分類代碼排除配件 |
  | momo | 氣炸鍋 | 搜尋頁依銷量排序（只取 momo「氣炸鍋」分類），排除廣告商品 |
  | Yahoo 購物中心 | 冰箱、電視、氣炸鍋、掃地機器人、洗衣機 | 搜尋頁依銷量排序，只保留 Yahoo 分類符合的商品（逐層比對分類路徑，例如電視要在「電視 > 電視」，不含「電視 > 電視配件」），再用燦坤的配件規則過濾 |

  各平台共用燦坤爬蟲的配件過濾規則（排除關鍵字、名稱需有容量），標準一致
- 追蹤清單：固定一批熱門型號（`watchlist`，目前 85 個），每天到燦坤、PChome、Yahoo 用型號搜尋，記錄各平台最低價（`watch_price_daily`），見[追蹤清單](#追蹤清單)
- 使用 MySQL 儲存商品主檔與每日價格歷史，方便追蹤價格變化趨勢
- 使用 Airflow 每天自動排程爬取（DockerOperator 啟動爬蟲 container），失敗會自動重試，可在網頁上查看每次執行的狀態與 log
- 使用 Redash 視覺化兩個平台的價格走勢、價格比較、排行榜、降價商品與評價
- 使用 Docker Compose（開發）與 Docker Swarm（部署）容器化所有服務
- 部署在 GCP Compute Engine VM 上 24 小時執行，筆電關機也會每天自動爬取

## 技術架構

- **爬蟲**：Python（燦坤解析 HTML、PChome 呼叫搜尋 API、momo / Yahoo 解析搜尋頁內嵌的 JSON）
- **排程**：Airflow（swarm 部署）；Celery + RabbitMQ 保留給手動補爬，Flower 監控任務
- **API**：FastAPI
- **資料庫**：MySQL 8
- **視覺化**：Redash
- **部署**：Docker Compose（本機開發）/ Docker Swarm（GCP Compute Engine VM）
- **資料表設計**：
  - `products`：商品主檔（平台、商品編號、名稱、分類等；平台 + 商品編號為唯一鍵）
  - `price_history`：每日價格歷史（依商品編號關聯，記錄每次爬取的價格、排名與評價；同一天重跑只保留最後一次）
    - `rating` / `review_count`：平均星數與評價則數，PChome、momo、Yahoo 有；燦坤及無人評價的商品為 NULL
  - `crawl_log`：每次爬蟲執行的結果（平台、分類、筆數、成功或沒抓到資料）
  - `goods_daily`：與 momo 四類資料（`mydb.momo_goods_daily`）同格式的每日商品表（中文欄位），每次爬蟲寫入後自動同步，見[與 momo 四類資料整合](#與-momo-四類資料整合)
  - `watchlist` / `watch_price_daily`：追蹤清單的型號與每日各平台最低價（中文欄位），見[追蹤清單](#追蹤清單)
  - `all_goods_daily`（view）：`goods_daily` + `mydb.momo_goods_daily`（經清洗），四平台比價、圖表、BigQuery 同步都查這個

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
│   ├── watchlist.py               # 追蹤清單：讀 watchlist → 各平台用型號搜尋 → 寫入 watch_price_daily
│   ├── goods_daily.py             # 轉成與 momo 四類資料相同的中文欄位格式（品牌、型號統一寫法）並同步到 goods_daily
│   ├── bigquery_sync.py           # MySQL → GCS → BigQuery 每日同步（Airflow tk3c_bigquery_sync 21:30）
│   └── special_topic3C/           # 爬蟲
│       ├── fridge_search.py       # 燦坤冰箱
│       ├── tv_search.py           # 燦坤電視
│       ├── airfryer_search.py     # 燦坤氣炸鍋
│       ├── robotvacuum_search.py  # 燦坤掃地機器人
│       ├── washer_search.py       # 燦坤洗衣機
│       ├── pchome_search.py       # PChome 五個分類（共用燦坤的配件過濾規則）
│       ├── momo_search.py         # momo 氣炸鍋
│       ├── yahoo_search.py        # Yahoo 購物中心五大分類
│       └── watch_search.py        # 追蹤清單：用型號搜尋燦坤、PChome、Yahoo 並比對型號
├── database/
│   ├── init.sql                   # 資料庫初始化 schema（新建資料庫用）
│   ├── backup_mysql.sh            # VM 每日 mysqldump 備份（cron 執行，保留 14 天）
│   └── migrations/                # 既有資料庫的結構變更
├── data/                          # 爬蟲單獨執行時輸出的 CSV
├── airflow/
│   ├── dags/tk3c_producer.py      # 每日 Producer DAG
│   ├── dags/tk3c_bigquery_sync.py # 每日 BigQuery 同步 DAG（21:30）
│   ├── Dockerfile                 # 以課程的 tibame_dataflow image 為底，加入本專題的 DAG
│   └── docker-compose-airflow.yml # Airflow swarm stack
├── bigquery/sql/                  # BigQuery 分層：01 raw 外部表、02 fact、03 載入去重、04 dim、05 mart
├── superset/
│   ├── Dockerfile                 # 官方 Superset 5.0 image 加裝 MySQL（pymysql）與 BigQuery（sqlalchemy-bigquery）driver
│   ├── superset_config.py         # SECRET_KEY、SQLite metadata、繁體中文介面
│   ├── docker-compose-superset.yml # Superset swarm stack（port 8088）
│   └── export/                    # 匯出的 dashboard、圖表、dataset 設定（YAML）
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

本機開發時用 `localhost`；正式環境在 GCP VM 上，把 `localhost` 換成 VM 的外部 IP（需先開防火牆，見[GCP 部署](#gcp-部署)）。

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
- 每個網站各送一條 Celery chain（共 19 個任務）：不同網站同時跑，同一個網站的分類依序跑，最後跑該網站的追蹤清單（燦坤 5 類約 6 分鐘＋追蹤清單約 10 分鐘，其他網站各約 5 分鐘），進度看 Flower（http://localhost:5555）
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

## GCP 部署

正式環境是 GCP Compute Engine 上的一台 VM，`tk3c` 與 `tk3c-airflow` 兩個 swarm stack 都跑在上面，每天 20:00 自動爬取，不需要開著筆電。

| 項目 | 設定 |
|---|---|
| VM 名稱 | `consumer-electronics-price-search-engine` |
| 機型 | e2-standard-2（2 vCPU、8 GB RAM）＋ 4 GB swap |
| 磁碟 | 24 GB |
| Swarm | 單節點，節點加上 `airflow=true` 標籤 |
| Image | 從 Docker Hub 拉 `pennyliu32/tk3c-price-tracker`、`pennyliu32/tk3c-airflow` |

平常不開發時，筆電不需要開 Docker 或 VS Code；只有要改爬蟲時才在本機開發，build 新 image 推上 Docker Hub 後再到 VM 更新。

### 第一次部署到 VM

在 GCP 主控台用瀏覽器 SSH 連進 VM 後：

```bash
# 1. 安裝 Docker、啟動 swarm、加上 airflow 標籤
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # 重新登入後生效
docker swarm init
docker node update --label-add airflow=true $(docker node ls -q)

# 2. 加 4 GB swap（Airflow + MySQL + 爬蟲在 8 GB 機器上比較保險）
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 3. 取得程式碼；.env 不在 git 裡，用 SSH 視窗右上角的「上傳檔案」傳到 VM 再搬進專案
git clone https://github.com/3CAggregation-Platform/tkec-price-tracker.git tk3c-price-tracker
cd tk3c-price-tracker
mv ~/.env .

# 4. 建立 overlay 網路後部署（步驟同上方「Docker Swarm 部署」與「Airflow 排程」）
docker network create --scope=swarm --driver=overlay tk3c_swarm_network
docker network create --scope=swarm --driver=overlay --attachable tk3c_attachable_network
set -a; source .env; set +a
DOCKER_IMAGE_VERSION=<版本> docker stack deploy --with-registry-auth -c docker-compose-swarm.yml tk3c
# 建立 airflow 資料庫與帳號（見「Airflow 排程 → 第一次部署」第 2 步）後：
AIRFLOW_IMAGE_VERSION=<版本> TK3C_IMAGE_VERSION=<版本> \
  docker stack deploy --with-registry-auth -c airflow/docker-compose-airflow.yml tk3c-airflow
```

### 搬移既有資料

本機的歷史資料用 mysqldump 匯出再匯入 VM（Airflow 的 metadata 不用搬，在 VM 上重新建立即可）：

```bash
# 本機：匯出
docker exec $(docker ps -q -f name=tk3c_mysql) sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --databases "$MYSQL_DATABASE"' > tk3c_dump.sql

# 上傳 tk3c_dump.sql 到 VM 後，在 VM 上匯入
docker exec -i $(docker ps -q -f name=tk3c_mysql) sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"' < tk3c_dump.sql
```

搬完後本機的 stack 要移除（`docker stack rm tk3c tk3c-airflow`），避免兩邊同時爬。資料 volume 會保留。

### 更新程式

```bash
# 本機：build 新版並推上 Docker Hub
docker build -t pennyliu32/tk3c-price-tracker:<新版本> .
docker push pennyliu32/tk3c-price-tracker:<新版本>
git push

# VM：拉最新程式碼後重新部署
cd ~/tk3c-price-tracker && git pull
set -a; source .env; set +a
DOCKER_IMAGE_VERSION=<新版本> docker stack deploy --with-registry-auth -c docker-compose-swarm.yml tk3c
AIRFLOW_IMAGE_VERSION=<版本> TK3C_IMAGE_VERSION=<新版本> \
  docker stack deploy --with-registry-auth -c airflow/docker-compose-airflow.yml tk3c-airflow
```

### 確認爬蟲有正常執行

爬蟲 20:00 開始，約 20:45 後檢查：

```bash
# 1. 服務狀態：都要是 1/1（celery-beat 是 0/0，排程已交給 Airflow）
docker service ls

# 2. 今天的爬蟲結果：run_at 是今天 20:xx、status 成功、success_count > 0 就正常
docker exec $(docker ps -q -f name=tk3c_mysql) sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "SELECT platform, category, run_at, item_count, success_count, status FROM crawl_log ORDER BY run_at DESC LIMIT 20;"'

# 3. 有問題時看 worker log
docker service logs --since 2h tk3c_celery-worker 2>&1 | tail -50
```

- `run_at` 停在昨天以前：Airflow 沒有觸發，檢查 `docker stack services tk3c-airflow`
- 有紀錄但失敗或 0 筆：爬蟲本身出錯（網站改版或被擋），看 `crawl_log.message`

### 資料庫備份

兩層備份，都保留 14 天：

| 層 | 內容 | 時間（台灣） | 用途 |
|---|---|---|---|
| mysqldump | `tk3c_price_tracker`、`mydb`（momo 四類資料）、`airflow` 各一個 `.sql.gz`，存在 VM 的 `~/backups` | 每天 21:00（兩個爬蟲都跑完後） | 單獨還原某個資料庫、資料被誤刪時救回 |
| 磁碟快照 | 整顆 VM 磁碟（快照排程 `default-schedule-1`，region `us-east1`） | 每天 18:00 起 | VM 或磁碟壞掉時整台還原；`~/backups` 也會一起被快照到 VM 之外 |

**mysqldump 排程**（腳本 `database/backup_mysql.sh`，VM 時區是 UTC，所以 cron 寫 13:00）：

```bash
mkdir -p ~/backups
(crontab -l 2>/dev/null; echo "0 13 * * * $HOME/tk3c-price-tracker/database/backup_mysql.sh >> $HOME/backups/backup.log 2>&1") | crontab -
crontab -l                     # 確認排程
tail ~/backups/backup.log      # 每次備份的紀錄
```

**從 mysqldump 還原**某個資料庫（會覆蓋該資料庫現有的表）：

```bash
gunzip -c ~/backups/tk3c_price_tracker_<日期>.sql.gz | \
  docker exec -i $(docker ps -q -f name=tk3c_mysql) sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"'
```

**磁碟快照**：在 GCP 主控台「Compute Engine → 快照」可以看到每天的快照；要還原時從快照建立新磁碟，再用它建立新 VM。

```bash
# 把快照排程掛到磁碟上（只需一次，本機有 gcloud 時）
gcloud compute disks add-resource-policies consumer-electronics-price-search-engine \
  --zone us-east1-c --resource-policies default-schedule-1
```

### 防火牆（開放管理介面）

GCP 預設不開放這些 port，要在「VPC 網路 → 防火牆 → 建立虛擬私有雲防火牆規則」新增：

| 欄位 | 設定 |
|---|---|
| 流量方向 / 動作 | 輸入 / 允許 |
| 目標 | 網路中的所有執行個體 |
| 來源 IPv4 範圍 | **只填自己的 IP**，例如 `x.x.x.x/32`（可到 https://api.ipify.org 查） |
| 通訊協定和通訊埠 | TCP `8080,15672,5555,8090,8088`（phpMyAdmin、RabbitMQ、Flower、Airflow、Superset，需要哪個開哪個） |

- 不要用 `0.0.0.0/0`：phpMyAdmin 可用 root 登入，Flower 沒有密碼，開放給所有人很危險
- 換網路（家裡、學校、手機熱點）後 IP 會變，要回來更新來源範圍

## BigQuery 資料倉儲

由組員負責：每天 21:30 由 Airflow 的 `tk3c_bigquery_sync` DAG 把 `all_goods_daily` 同步到 GCS 與 BigQuery（Raw → Fact / Dim → DataMart），程式在 `app/bigquery_sync.py`、`bigquery/sql/`。架構圖、分層設計、權限與操作方式見組員 repo 的說明。

## Superset 視覺化

[Apache Superset](https://superset.apache.org/) 部署在同一台 VM，用唯讀帳號 `superset_reader` 查 `tk3c_price_tracker`，圖表主要用 view `all_goods_daily`（四個平台，含 momo 四類資料）；另外連 BigQuery `tk3c_dw` 讀 DataMart。

| 項目 | 設定 |
|---|---|
| 版本 | `apache/superset:5.0.0` + pymysql + sqlalchemy-bigquery，在 VM 上 build 成 `tk3c-superset:0.0.3`（約 3.7 GB，不推 Docker Hub） |
| metadata | 帳號、連線、圖表、dashboard 存在 volume `superset_superset_home` 的 SQLite；VM 每日快照會一起備份 |
| 記憶體 | 上限 1.5 GB，平常約 300 MB |
| 帳密 | VM `.env` 的 `SUPERSET_SECRET_KEY`、`SUPERSET_ADMIN_PASSWORD`（登入帳號 `admin`）、`SUPERSET_DB_PASSWORD`（`superset_reader` 的密碼） |
| 帳號 | 新增帳號：`docker exec $(docker ps -q -f name=superset_superset) superset fab create-user --role Admin --username <帳號> --firstname <名> --lastname <姓> --email <email> --password <密碼>` |

### 第一次部署（VM 上，在 repo 根目錄）

```bash
# 1. .env 加上三組隨機密碼（只做一次）
{ echo "SUPERSET_SECRET_KEY=$(openssl rand -base64 42 | tr -d '\n')"
  echo "SUPERSET_ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=\n')"
  echo "SUPERSET_DB_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=\n')"; } >> .env
set -a && . ./.env && set +a

# 2. 建立唯讀帳號（all_goods_daily 是 SQL SECURITY DEFINER 的 view，不需要 mydb 的權限；SHOW VIEW 讓 Superset 讀得到 view 的欄位）
docker exec $(docker ps -q -f name=tk3c_mysql) sh -c "mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -e \"CREATE USER IF NOT EXISTS 'superset_reader'@'%' IDENTIFIED BY '$SUPERSET_DB_PASSWORD'; GRANT SELECT, SHOW VIEW ON tk3c_price_tracker.* TO 'superset_reader'@'%';\""

# 3. build image 並部署（image 很大，build 前確認磁碟還有 5 GB 以上）
docker build -t tk3c-superset:0.0.3 superset
docker stack deploy -c superset/docker-compose-superset.yml superset

# 4. 初始化 metadata 與管理者帳號
C=$(docker ps -q -f name=superset_superset)
docker exec $C superset db upgrade
docker exec $C superset fab create-admin --username admin --firstname Admin --lastname User --email admin@example.com --password "$SUPERSET_ADMIN_PASSWORD"
docker exec $C superset init
```

- 不要對 VM 下 `docker image prune -a`：Superset 的 image 是本地 build，沒推 Docker Hub，刪掉就要重新 build

### 連線方式

防火牆沒有開 8088，從本機用 SSH tunnel 連（這個指令會一直停著，另開一個終端機執行，用完按 Ctrl+C）：

```bash
gcloud compute ssh consumer-electronics-price-search-engine --zone us-east1-c -- -N -L 8088:localhost:8088
```

瀏覽器開 http://localhost:8088 ，帳號 `admin`。要給其他人看時再把 `8088` 加進上方防火牆規則。

在 Superset 新增資料庫連線（設定 → 資料庫連線 → + 資料庫 → MySQL → 改用 SQLAlchemy URI）：

```
mysql+pymysql://superset_reader:<SUPERSET_DB_PASSWORD>@tk3c_mysql:3306/tk3c_price_tracker?charset=utf8mb4
```

`charset=utf8mb4` 一定要加，否則中文欄位和商品名稱會變亂碼。

BigQuery 連線（設定 → 資料庫連線 → + 資料庫 → Google BigQuery → 改用 SQLAlchemy URI）：

```
bigquery://project-fb94c850-2c44-43c2-afe/tk3c_dw
```

不用上傳 service account 金鑰：Superset 容器透過 VM 的 metadata server 取得 VM service account `tk3c-pipeline` 的憑證（Application Default Credentials），它有 `tk3c_dw` 的讀寫與 BigQuery Job User 權限。Superset 只拿來查 `mart_*` 表；BigQuery 依掃描量計費，每張 mart 都很小（MB 等級），免費額度內。

### Dashboard 備份與還原

圖表、dataset、dashboard 的設定存在 volume 的 SQLite，另外匯出成 YAML 放在 `superset/export/` 進 git（資料庫密碼會被遮成 `XXXXXXXXXX`）。目前內容：dashboard「家電比價」（分類、型號篩選器；型號只作用在「單一型號各平台價格」）與 15 張圖：
  - 「每日比價」分頁：追蹤型號跨平台比價（今天，`watch_price_daily` 的 virtual dataset，燦坤／PChome／Yahoo 並排、最便宜平台、價差率）、四平台平均售價走勢、同型號跨平台比價（最新一天）、四平台售價分布（近 7 天，箱形圖）、單一型號各平台價格、降價排行（最近一次 vs 上一次）、降幅排行（BigQuery `mart_price_drop`，降 3% 以上依降幅排序）
  - 「長期分析」分頁：價格變動排行（觀察 7 天以上）、雙11價格檢驗（11/11 售價 vs 前 30 天，含「雙11前先漲價」判斷）、最便宜平台次數（BigQuery `mart_cross_platform_compare`，同型號在兩個以上平台時哪個平台最便宜）
  - 「規格分析」分頁（組員製作，virtual dataset「家電規格價格」從商品名稱抓容量／尺寸與類型）：洗衣機、冰箱、氣炸鍋容量 vs 售價，電視尺寸 vs 售價（排除 24 吋以下），掃地機器人功能 vs 售價（箱形圖；名稱沒有吸力規格）

```bash
# 匯出（VM 上）：改完 dashboard 後執行，再把 zip 解開覆蓋 superset/export/ 並 commit
C=$(docker ps -q -f name=superset_superset)
docker exec $C superset export-dashboards -f /tmp/dashboards.zip
docker cp $C:/tmp/dashboards.zip ~/dashboards.zip && docker exec $C rm /tmp/dashboards.zip

# 還原（新的 Superset，已完成上方第一次部署）：把 superset/export/ 打包成 zip 匯入
cd superset/export && zip -r /tmp/dashboards.zip . && cd -
docker cp /tmp/dashboards.zip $C:/tmp/dashboards.zip
docker exec $C superset import-dashboards -p /tmp/dashboards.zip -u admin
```

匯入後到「Settings → Database Connections」編輯 MySQL 連線，把 URI 裡的 `XXXXXXXXXX` 換回 `SUPERSET_DB_PASSWORD`；BigQuery 連線沒有密碼，匯入後直接可用。

## Redash 視覺化

使用課程部署的 Redash（swarm stack `redash`，http://localhost:5005），連到本專案的 MySQL。

> 資料庫搬到 GCP VM 後，筆電上的 Redash 已移除，視覺化改用 Superset（見上方）。以下為原本在本機的設定方式。

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

## 追蹤清單

前 20 名排行榜只抓得到各平台當天最熱賣的商品，不同平台重疊的型號很少，跨平台比價的圖常常沒資料。追蹤清單固定一批熱門型號，每天到每個平台用型號搜尋，同一個型號就能天天比價。

| 項目 | 說明 |
|---|---|
| 清單 | `watchlist`（分類、廠牌、型號、啟用），初始 85 個：2026-10-10～11-09 在兩個以上平台出現過的型號（`database/migrations/006_add_watchlist.sql`） |
| 結果 | `watch_price_daily`：每天、每平台、每型號一筆最低價，`符合筆數` 為找到幾個賣場；同一天重跑只保留最後一次 |
| 平台 | 燦坤、PChome、Yahoo；momo 擋程式存取，不爬 |
| 排程 | 接在各平台排行榜爬蟲後面（`app/producer.py`），同一個網站依序跑，不會同時送太多請求 |
| 型號比對 | 去掉 `-`、空白、括號後比對：PChome 看商品名稱、Yahoo 看型號欄位與名稱、燦坤搜尋結果沒有型號，進前 3 個商品頁看「產品型號」；7 碼以上的型號允許 3 碼以內的顏色後綴（`NR-B171TV` ↔ `NR-B171TV-S1`） |
| 排除 | 分類要符合（PChome 分類代碼、Yahoo 分類路徑，和排行榜相同），名稱有該分類的配件關鍵字、「適用」「相容」，或福利品、盒損、展示機、二手、整新的不算 |

```bash
# 建立資料表與初始清單（VM 上，只需一次）
docker exec -i $(docker ps -q -f name=tk3c_mysql) sh -c 'mysql --default-character-set=utf8mb4 -uroot -p"$MYSQL_ROOT_PASSWORD"' < database/migrations/006_add_watchlist.sql

# 手動執行某個平台（VM 上，不經過 RabbitMQ）
docker run --rm --network tk3c_attachable_network --env-file .env -e DB_HOST=tk3c_mysql -e DB_PORT=3306 -e TZ=Asia/Taipei \
  pennyliu32/tk3c-price-tracker:<版本> python -m app.watchlist pchome   # tk3c / pchome / yahoo，--limit 5 只跑前 5 個

# 單一型號測試（不寫資料庫）
python -m app.special_topic3C.watch_search pchome 冰箱 HRE-B1261U
```

```sql
-- 新增 / 停用追蹤型號（型號寫法和 goods_daily.型號 相同：大寫、去掉括號）
INSERT INTO watchlist (分類, 廠牌, 型號) VALUES ('掃地機器人', 'Roborock 石頭科技', 'Q8MAX');
UPDATE watchlist SET 啟用 = FALSE WHERE 型號 = 'SR-C07';

-- 今天各型號在各平台的最低價
SELECT 分類, 型號, 平台, 售價, 符合筆數 FROM watch_price_daily WHERE 抓取日期 = CURDATE() ORDER BY 分類, 型號, 售價;
```

## 與 momo 四類資料整合

momo 的冰箱、電視、洗衣機、掃地機器人由獨立的 momo 爬蟲寫入同一台 MySQL 的 `mydb.momo_goods_daily`。本專案以這張表的中文欄位格式為準，另外產生一張同格式的 `goods_daily`：

| 欄位 | 說明 |
|---|---|
| 平台 | `tk3c` / `pchome` / `yahoo` / `momo` |
| 抓取日期、分類、商品編號、商品名稱 | 與 `momo_goods_daily` 相同 |
| 廠牌 | 統一為「英文 中文」寫法，例如燦坤的「聲寶SAMPO」、PChome 的「SAMPO」都改成「SAMPO 聲寶」（對照表在 `app/goods_daily.py` 的 `BRANDS`） |
| 型號 | 去掉括號內的顏色 / 版本（`SR-C48GDV(P2)` → `SR-C48GDV`）；沒有型號時從商品名稱最後一組括號抓 |
| 售價、原價、評分、評價數 | 與 `momo_goods_daily` 相同（整數價格；燦坤沒有評價為 NULL） |
| 銷量、庫存、促銷文案、有政府補助、銷量下限 | 只有 momo 有，本專案為 NULL |
| 排名、連結 | 本專案多出的欄位，momo 的排名可用資料順序（依銷量排序）補上 |

```bash
# 第一次建立：建表後把既有歷史資料轉進來（之後每次爬蟲會自動同步，不用再跑）
docker exec -i $(docker ps -q -f name=tk3c_mysql) sh -c 'mysql --default-character-set=utf8mb4 -uroot -p"$MYSQL_ROOT_PASSWORD"' < database/migrations/003_add_goods_daily.sql
uv run python -m app.goods_daily
```

`mydb.momo_goods_daily` 不搬進 `goods_daily`，而是用 view `all_goods_daily` 把兩張表合在一起，momo 每天 20:30 爬完就查得到，不用另外同步：

```bash
# 建立 view（只要跑一次；mydb.momo_goods_daily 要先存在）
docker exec -i $(docker ps -q -f name=tk3c_mysql) sh -c 'mysql --default-character-set=utf8mb4 -uroot -p"$MYSQL_ROOT_PASSWORD"' < database/migrations/004_add_all_goods_daily_view.sql
docker exec -i $(docker ps -q -f name=tk3c_mysql) sh -c 'mysql --default-character-set=utf8mb4 -uroot -p"$MYSQL_ROOT_PASSWORD"' < database/migrations/005_filter_momo_in_all_goods_daily.sql  # 加上 momo 資料清洗（取代 004 的 view 定義）
```

- 欄位和 `goods_daily` 相同；momo 四類資料的 `平台` 為 `momo`、`排名` 為 NULL、`連結` 由商品編號組成
- `momo_goods_daily` 的文字欄位 collation（`utf8mb4_unicode_ci`）在 view 裡統一轉成 `utf8mb4_0900_ai_ci`，double 欄位轉成 INT
- view 為 `SQL SECURITY DEFINER`，Redash / Superset 的唯讀帳號只要有 `tk3c_price_tracker.all_goods_daily` 的 SELECT 權限，不需要 `mydb` 的權限
- `momo_goods_daily` 整張重新匯入的期間，view 查不到 momo 四類資料
- momo 四類資料在 view 裡套用與本專案相同的清洗規則（`database/migrations/005_filter_momo_in_all_goods_daily.sql`）：依名稱修正冰箱／洗衣機的分類並去除重複（原始資料有分類錯誤，例如「洗衣機」約一半是冰箱）、名稱需有容量、排除配件關鍵字；`mydb.momo_goods_daily` 原始資料不變

```sql
-- 同型號跨平台比價
SELECT 型號, 平台, 售價 FROM all_goods_daily
WHERE 抓取日期 = CURDATE() AND 型號 IN (
    SELECT 型號 FROM all_goods_daily WHERE 抓取日期 = CURDATE() GROUP BY 型號 HAVING COUNT(DISTINCT 平台) > 1
)
ORDER BY 型號, 售價;
```

## 目前進度

- [x] 完成燦坤四大分類（冰箱、電視、氣炸鍋、掃地機器人）的爬蟲程式
- [x] 新增 PChome 四大分類爬蟲與評價
- [x] 燦坤、PChome 新增洗衣機；新增 momo、Yahoo 購物中心氣炸鍋爬蟲
- [x] Yahoo 購物中心擴充為五大分類（冰箱、電視、氣炸鍋、掃地機器人、洗衣機）
- [x] MySQL 資料庫架構設計（products + price_history + crawl_log）
- [x] 排程自動化（Celery + RabbitMQ + Flower），失敗自動重試
- [x] 使用 Docker Swarm 部署
- [x] 使用 Airflow 取代 Celery beat 排程每日爬蟲
- [x] 使用 Redash 視覺化價格走勢與比價
- [x] 部署到 GCP Compute Engine VM，24 小時自動排程爬取
- [x] 整合 momo 四類資料（view `all_goods_daily`），並在 view 裡修正分類、排除配件
- [x] 使用 Superset 建立「家電比價」dashboard（每日比價、長期分析兩個分頁）
- [x] 追蹤清單：85 個熱門型號每天到燦坤、PChome、Yahoo 用型號搜尋
- [x] BigQuery 資料倉儲（組員負責）：GCS raw → fact / dim → DataMart，Airflow 每日同步

## 未來規劃

- 追蹤清單同步到 BigQuery，並在 Superset 加上追蹤型號的跨平台比價圖
- Superset 用 BigQuery DataMart 建圖表、Looker Studio 報表
- momo 自 2026/11/08 起擋下程式存取（403），目前保留歷史資料、不繞過防護
- PChome 商品名稱沒有括號的型號抓取規則（目前約一半抓不到型號）