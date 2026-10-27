"""
每日爬蟲 Producer DAG（參考課程 dataflow/dags/producer_scheduler.py）

- 每天 20:00（台北）用 DockerOperator 啟動專題的 image 執行 `python -m app.producer`，
  把 8 個爬蟲任務送進 RabbitMQ，跑完自動刪除 container
- 真正的爬蟲由 tk3c stack 的 celery-worker 從 RabbitMQ 取出執行，進度看 Flower（http://localhost:5555）
- 這個 DAG 只負責「送任務」，送成功就是綠色；爬蟲本身的重試在 app/tasks.py
"""
import datetime
import os

import pendulum
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator

# 由 docker-compose-airflow.yml 帶入，換版本時只要改部署指令的 TK3C_IMAGE_VERSION
TK3C_IMAGE = os.environ.get("TK3C_IMAGE", "pennyliu32/tk3c-price-tracker:latest")
# producer container 要加入這個 attachable 網路才連得到 swarm 裡的 RabbitMQ
NETWORK = os.environ.get("TK3C_NETWORK", "tk3c_attachable_network")

DEFAULT_ARGS = {
    "owner": "tk3c",
    "retries": 3,
    "retry_delay": datetime.timedelta(minutes=5),
    "execution_timeout": datetime.timedelta(minutes=10),
}

with DAG(
    dag_id="tk3c_producer",
    description="每天把燦坤與 PChome 四大分類的爬蟲任務送進 RabbitMQ",
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(2026, 10, 1, tz="Asia/Taipei"),
    schedule="0 20 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["tk3c", "producer"],
) as dag:
    DockerOperator(
        task_id="producer_tk3c_crawler",
        image=TK3C_IMAGE,
        command=["python", "-m", "app.producer"],
        network_mode=NETWORK,
        environment={
            "RABBITMQ_HOST": "tk3c_rabbitmq",
            "RABBITMQ_PORT": "5672",
            "TZ": "Asia/Taipei",
        },
        # 帳密放 private_environment，不會出現在 Airflow UI 的 task 參數裡
        private_environment={
            "RABBITMQ_USER": os.environ.get("RABBITMQ_USER", ""),
            "RABBITMQ_PASS": os.environ.get("RABBITMQ_PASS", ""),
        },
        auto_remove=True,
        # worker 本身也是 container，預設的暫存資料夾掛載在主機上找不到路徑，所以關掉
        mount_tmp_dir=False,
    )
