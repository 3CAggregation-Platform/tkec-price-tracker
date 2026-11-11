"""
每日 BigQuery 同步 DAG：MySQL → GCS（Raw）→ BigQuery（Fact / Dim / DataMart）

- 每天 21:30（台北），兩條爬蟲（20:00、20:30）與 21:00 的 MySQL 備份都跑完之後執行
- 用 DockerOperator 啟動專題的 image 執行 `python -m app.bigquery_sync`，跑完自動刪除 container
- container 透過 GCE VM 的 service account（tk3c-pipeline）存取 GCS、BigQuery、Secret Manager，
  不需要金鑰檔；MySQL 用唯讀帳號 superset_reader，密碼從 Secret Manager 讀取，DAG 裡沒有任何密碼
- 同一天重跑會覆蓋 GCS 檔案與 BigQuery 當天的分區，不會產生重複資料
- 另一個 task check_crawl_results 執行 `python -m app.crawl_check`，檢查當天每個平台、分類是否都有抓到資料，
  有 0 筆或沒執行的就變紅色（Airflow UI 一眼看得出哪天出問題）；和同步互不相依，檢查失敗不會擋住同步
"""
import datetime
import os

import pendulum
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator

TK3C_IMAGE = os.environ.get("TK3C_IMAGE", "pennyliu32/tk3c-price-tracker:latest")
# 加入 attachable 網路才能用服務名稱 tk3c_mysql 連到 MySQL
NETWORK = os.environ.get("TK3C_NETWORK", "tk3c_attachable_network")

DEFAULT_ARGS = {
    "owner": "tk3c",
    "retries": 2,
    "retry_delay": datetime.timedelta(minutes=10),
    "execution_timeout": datetime.timedelta(minutes=20),
}

with DAG(
    dag_id="tk3c_bigquery_sync",
    description="每天把 all_goods_daily 同步到 BigQuery（GCS raw → fact/dim → mart）",
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(2026, 11, 1, tz="Asia/Taipei"),
    schedule="30 21 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["tk3c", "bigquery"],
) as dag:
    # 兩個 task 共用的設定：MySQL 唯讀帳號，密碼從 Secret Manager 讀取
    MYSQL_ENV = {
        "DB_HOST": "tk3c_mysql",
        "DB_PORT": "3306",
        "MYSQL_DATABASE": "tk3c_price_tracker",
        "MYSQL_READER_USER": "superset_reader",
        "MYSQL_PASSWORD_SECRET": "tk3c-mysql-reader-password",
        "TZ": "Asia/Taipei",
    }
    RUN_DATE = "{{ data_interval_end.in_timezone('Asia/Taipei').to_date_string() }}"

    DockerOperator(
        task_id="sync_all_goods_daily_to_bigquery",
        image=TK3C_IMAGE,
        # 用 DAG 排程的日期（台北），補跑舊日期時也會同步正確的那一天
        command=["python", "-m", "app.bigquery_sync", "--date", RUN_DATE],
        network_mode=NETWORK,
        environment={
            **MYSQL_ENV,
            "BQ_DATASET": "tk3c_dw",
            "GCS_BUCKET": "tk3c-price-raw-fb94c850",
        },
        auto_remove=True,
        mount_tmp_dir=False,
    )

    DockerOperator(
        task_id="check_crawl_results",
        image=TK3C_IMAGE,
        command=["python", "-m", "app.crawl_check", "--date", RUN_DATE],
        network_mode=NETWORK,
        # momo 從 11/08 起被網站擋（403），先列為已知問題只印警告；恢復後改成空字串
        environment={**MYSQL_ENV, "CRAWL_CHECK_IGNORE": "momo"},
        # 爬蟲早就跑完了，重試結果也不會變
        retries=0,
        execution_timeout=datetime.timedelta(minutes=5),
        auto_remove=True,
        mount_tmp_dir=False,
    )
