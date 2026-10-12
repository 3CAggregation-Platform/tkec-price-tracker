import pymysql

from celery_app import app
from db import save_products_to_db, log_crawl_run
from special_topic3C.fridge_search import run_fridge_crawler
from special_topic3C.tv_search import run_tv_crawler
from special_topic3C.airfryer_search import run_airfryer_crawler
from special_topic3C.robotvacuum_search import run_robotvacuum_crawler

MAX_RETRIES = 3
RETRY_DELAY = 300  # 失敗後隔 5 分鐘重試


def run_crawl_task(task, category, crawler):
    """
    執行爬蟲並寫入資料庫，遇到以下狀況會自動重試（最多 MAX_RETRIES 次）：
    - 資料庫連不上（例如 MySQL 比 worker 晚啟動）
    - 沒抓到任何資料（例如官網暫時連不上）
    """
    try:
        data = crawler()

        if not data:
            if task.request.retries < task.max_retries:
                print(f"⚠️ {category}沒有抓到資料，{RETRY_DELAY} 秒後重試（第 {task.request.retries + 1} 次）")
                raise task.retry(countdown=RETRY_DELAY)
            log_crawl_run(category, 0, 0, 0, "no_data", "沒有抓到任何資料")
            return f"{category}爬蟲完成，但沒有抓到任何資料"

        success, skipped = save_products_to_db(data)
        message = f"{category}爬蟲完成，共 {len(data)} 筆，成功寫入 {success} 筆，略過 {skipped} 筆"
        log_crawl_run(category, len(data), success, skipped, "success", message)
        return message

    except pymysql.err.OperationalError as e:
        print(f"⚠️ {category}連不上資料庫，{RETRY_DELAY} 秒後重試（第 {task.request.retries + 1} 次）：{e}")
        raise task.retry(exc=e, countdown=RETRY_DELAY)


@app.task(name="crawl_fridge", bind=True, max_retries=MAX_RETRIES)
def crawl_fridge(self):
    return run_crawl_task(self, "冰箱", run_fridge_crawler)


@app.task(name="crawl_tv", bind=True, max_retries=MAX_RETRIES)
def crawl_tv(self):
    return run_crawl_task(self, "電視", run_tv_crawler)


@app.task(name="crawl_airfryer", bind=True, max_retries=MAX_RETRIES)
def crawl_airfryer(self):
    return run_crawl_task(self, "氣炸鍋", run_airfryer_crawler)


@app.task(name="crawl_robotvacuum", bind=True, max_retries=MAX_RETRIES)
def crawl_robotvacuum(self):
    return run_crawl_task(self, "掃地機器人", run_robotvacuum_crawler)
