"""
Producer：把每日爬蟲任務送進 RabbitMQ，由 tk3c stack 的 celery-worker 取出執行
（參考課程 crawler/producer_crawler_finmind_duplicate.py）

    python -m app.producer

Airflow 的 tk3c_producer DAG 每天 20:00 用 DockerOperator 執行這支程式。
燦坤、PChome 各送一條 chain：同一個網站的 4 個分類依序爬，避免同時對同一個網站送太多請求；
兩個網站則可以同時跑。每個 task 失敗時的重試邏輯在 app/tasks.py。
"""
from celery import chain

from app.tasks import (
    crawl_fridge,
    crawl_tv,
    crawl_airfryer,
    crawl_robotvacuum,
    crawl_pchome_fridge,
    crawl_pchome_tv,
    crawl_pchome_airfryer,
    crawl_pchome_robotvacuum,
)

CHAINS = {
    "燦坤": [crawl_fridge, crawl_tv, crawl_airfryer, crawl_robotvacuum],
    "PChome": [crawl_pchome_fridge, crawl_pchome_tv, crawl_pchome_airfryer, crawl_pchome_robotvacuum],
}


def main():
    for platform, tasks in CHAINS.items():
        # .si() 是不接收上一個 task 回傳值的 signature，只用來決定執行順序
        result = chain(*(task.si() for task in tasks)).apply_async()
        print(f"send {platform} tasks: {[task.name for task in tasks]} ({result.id})")


if __name__ == "__main__":
    main()
