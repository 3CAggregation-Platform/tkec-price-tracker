"""
組員 momo 爬蟲的每日 Producer DAG（做法同 tk3c_producer）

- 每天 20:30（台北）用 DockerOperator 啟動組員的 image 執行 `crawler.producer_crawler_momo`，
  把 momo 四個分類（洗衣機、冰箱、電視、掃地機器人）的任務送進組員自己的 RabbitMQ（momo stack）
- 真正的爬蟲由 momo stack 的 momo-worker 執行，寫入 tk3c_mysql 的 mydb.momo_goods_daily
- 和 tk3c_producer 錯開 30 分鐘，避免同時佔用 VM 資源
"""
import datetime
import os

import pendulum
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator

# 由 docker-compose-airflow.yml 帶入，組員升版後改部署指令的 MOMO_IMAGE_VERSION
MOMO_IMAGE = os.environ.get("MOMO_IMAGE", "bihruwang/momo_crawler:0.0.2")
NETWORK = os.environ.get("TK3C_NETWORK", "tk3c_attachable_network")

DEFAULT_ARGS = {
    "owner": "momo",
    "retries": 3,
    "retry_delay": datetime.timedelta(minutes=5),
    "execution_timeout": datetime.timedelta(minutes=10),
}

with DAG(
    dag_id="momo_producer",
    description="每天把 momo 四個分類的爬蟲任務送進組員的 RabbitMQ",
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(2026, 10, 1, tz="Asia/Taipei"),
    schedule="30 20 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["momo", "producer"],
) as dag:
    DockerOperator(
        task_id="producer_momo_crawler",
        image=MOMO_IMAGE,
        command=["uv", "run", "python", "-m", "crawler.producer_crawler_momo"],
        network_mode=NETWORK,
        environment={
            "RABBITMQ_HOST": "momo_momo-rabbitmq",
            "RABBITMQ_PORT": "5672",
            "TZ": "Asia/Taipei",
        },
        private_environment={
            "WORKER_ACCOUNT": os.environ.get("MOMO_RABBITMQ_USER", ""),
            "WORKER_PASSWORD": os.environ.get("MOMO_RABBITMQ_PASS", ""),
        },
        auto_remove=True,
        mount_tmp_dir=False,
    )
