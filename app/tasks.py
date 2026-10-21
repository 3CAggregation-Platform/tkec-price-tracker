import pymysql

from app.celery_app import app
from app.db import save_products_to_db, log_crawl_run
from app.special_topic3C.fridge_search import run_fridge_crawler
from app.special_topic3C.tv_search import run_tv_crawler
from app.special_topic3C.airfryer_search import run_airfryer_crawler
from app.special_topic3C.robotvacuum_search import run_robotvacuum_crawler
from app.special_topic3C.pchome_search import run_pchome_crawler

MAX_RETRIES = 3
RETRY_DELAY = 300  # 失敗後隔 5 分鐘重試


PLATFORM_NAMES = {"tk3c": "燦坤", "pchome": "PChome"}


def run_crawl_task(task, category, crawler, platform="tk3c"):
    """
    執行爬蟲並寫入資料庫，遇到以下狀況會自動重試（最多 MAX_RETRIES 次）：
    - 資料庫連不上（例如 MySQL 比 worker 晚啟動）
    - 沒抓到任何資料（例如官網暫時連不上）
    """
    label = f"{PLATFORM_NAMES[platform]}{category}"
    try:
        data = crawler()

        if not data:
            if task.request.retries < task.max_retries:
                print(f"⚠️ {label}沒有抓到資料，{RETRY_DELAY} 秒後重試（第 {task.request.retries + 1} 次）")
                raise task.retry(countdown=RETRY_DELAY)
            log_crawl_run(category, 0, 0, 0, "no_data", "沒有抓到任何資料", platform)
            return f"{label}爬蟲完成，但沒有抓到任何資料"

        success, skipped = save_products_to_db(data)
        message = f"{label}爬蟲完成，共 {len(data)} 筆，成功寫入 {success} 筆，略過 {skipped} 筆"
        log_crawl_run(category, len(data), success, skipped, "success", message, platform)
        return message

    except pymysql.err.OperationalError as e:
        print(f"⚠️ {label}連不上資料庫，{RETRY_DELAY} 秒後重試（第 {task.request.retries + 1} 次）：{e}")
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


@app.task(name="crawl_pchome_fridge", bind=True, max_retries=MAX_RETRIES)
def crawl_pchome_fridge(self):
    return run_crawl_task(self, "冰箱", lambda: run_pchome_crawler("冰箱"), "pchome")


@app.task(name="crawl_pchome_tv", bind=True, max_retries=MAX_RETRIES)
def crawl_pchome_tv(self):
    return run_crawl_task(self, "電視", lambda: run_pchome_crawler("電視"), "pchome")


@app.task(name="crawl_pchome_airfryer", bind=True, max_retries=MAX_RETRIES)
def crawl_pchome_airfryer(self):
    return run_crawl_task(self, "氣炸鍋", lambda: run_pchome_crawler("氣炸鍋"), "pchome")


@app.task(name="crawl_pchome_robotvacuum", bind=True, max_retries=MAX_RETRIES)
def crawl_pchome_robotvacuum(self):
    return run_crawl_task(self, "掃地機器人", lambda: run_pchome_crawler("掃地機器人"), "pchome")
