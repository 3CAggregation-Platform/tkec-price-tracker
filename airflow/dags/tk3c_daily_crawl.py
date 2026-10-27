"""
每日爬蟲 DAG：取代原本的 Celery beat 排程

- 每天 20:00（台北）開始
- 燦坤、PChome 是不同網站，兩條線同時跑；同一個網站的 4 個分類依序跑，避免同時對同一個網站送太多請求
- 每個 task 用 DockerOperator 啟動專題的 image 執行 `python -m app.run_crawl <平台> <分類>`，
  跑完自動刪除 container；失敗隔 5 分鐘重試，最多 3 次
"""
import datetime
import os

import pendulum
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator

# 由 docker-compose-airflow.yml 帶入，換版本時只要改部署指令的 TK3C_IMAGE_VERSION
TK3C_IMAGE = os.environ.get("TK3C_IMAGE", "pennyliu32/tk3c-price-tracker:latest")
# 爬蟲 container 要加入這個 attachable 網路才連得到 swarm 裡的 MySQL
NETWORK = os.environ.get("TK3C_NETWORK", "tk3c_attachable_network")

CATEGORIES = [("冰箱", "fridge"), ("電視", "tv"), ("氣炸鍋", "airfryer"), ("掃地機器人", "robotvacuum")]

DEFAULT_ARGS = {
    "owner": "tk3c",
    "retries": 3,
    "retry_delay": datetime.timedelta(minutes=5),
    "execution_timeout": datetime.timedelta(minutes=30),
}


def crawl_task(platform, category, slug):
    return DockerOperator(
        task_id=f"{platform}_{slug}",
        image=TK3C_IMAGE,
        command=["python", "-m", "app.run_crawl", platform, category],
        network_mode=NETWORK,
        environment={
            "DB_HOST": "tk3c_mysql",
            "DB_PORT": "3306",
            "MYSQL_USER": os.environ.get("MYSQL_USER", "tk3c_user"),
            "MYSQL_DATABASE": os.environ.get("MYSQL_DATABASE", "tk3c_price_tracker"),
            "TZ": "Asia/Taipei",
        },
        # 密碼放 private_environment，不會出現在 Airflow UI 的 task 參數裡
        private_environment={"MYSQL_PASSWORD": os.environ.get("MYSQL_PASSWORD", "")},
        auto_remove=True,
        # worker 本身也是 container，預設的暫存資料夾掛載在主機上找不到路徑，所以關掉
        mount_tmp_dir=False,
    )


with DAG(
    dag_id="tk3c_daily_crawl",
    description="每天爬取燦坤與 PChome 四大分類的排名與價格",
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(2026, 10, 1, tz="Asia/Taipei"),
    schedule="0 20 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["tk3c", "crawler"],
) as dag:
    for platform in ("tk3c", "pchome"):
        tasks = [crawl_task(platform, category, slug) for category, slug in CATEGORIES]
        for upstream, downstream in zip(tasks, tasks[1:]):
            upstream >> downstream
