import pymysql

from app.celery_app import app
from app.db import save_products_to_db, log_crawl_run
from app.special_topic3C.fridge_search import run_fridge_crawler
from app.special_topic3C.tv_search import run_tv_crawler
from app.special_topic3C.airfryer_search import run_airfryer_crawler
from app.special_topic3C.robotvacuum_search import run_robotvacuum_crawler
from app.special_topic3C.washer_search import run_washer_crawler
from app.special_topic3C.pchome_search import run_pchome_crawler
from app.special_topic3C.momo_search import run_momo_crawler
from app.special_topic3C.yahoo_search import run_yahoo_crawler
from app.watchlist import run_watchlist

MAX_RETRIES = 3
RETRY_DELAY = 300  # 失敗後隔 5 分鐘重試


PLATFORM_NAMES = {"tk3c": "燦坤", "pchome": "PChome", "momo": "momo", "yahoo": "Yahoo"}


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


@app.task(name="crawl_washer", bind=True, max_retries=MAX_RETRIES)
def crawl_washer(self):
    return run_crawl_task(self, "洗衣機", run_washer_crawler)


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


@app.task(name="crawl_pchome_washer", bind=True, max_retries=MAX_RETRIES)
def crawl_pchome_washer(self):
    return run_crawl_task(self, "洗衣機", lambda: run_pchome_crawler("洗衣機"), "pchome")


@app.task(name="crawl_momo_airfryer", bind=True, max_retries=MAX_RETRIES)
def crawl_momo_airfryer(self):
    return run_crawl_task(self, "氣炸鍋", lambda: run_momo_crawler("氣炸鍋"), "momo")


@app.task(name="crawl_yahoo_airfryer", bind=True, max_retries=MAX_RETRIES)
def crawl_yahoo_airfryer(self):
    return run_crawl_task(self, "氣炸鍋", lambda: run_yahoo_crawler("氣炸鍋"), "yahoo")


@app.task(name="crawl_yahoo_fridge", bind=True, max_retries=MAX_RETRIES)
def crawl_yahoo_fridge(self):
    return run_crawl_task(self, "冰箱", lambda: run_yahoo_crawler("冰箱"), "yahoo")

@app.task(name="crawl_yahoo_tv", bind=True, max_retries=MAX_RETRIES)
def crawl_yahoo_tv(self):
    return run_crawl_task(self, "電視", lambda: run_yahoo_crawler("電視"), "yahoo")

@app.task(name="crawl_yahoo_robotvacuum", bind=True, max_retries=MAX_RETRIES)
def crawl_yahoo_robotvacuum(self):
    return run_crawl_task(self, "掃地機器人", lambda: run_yahoo_crawler("掃地機器人"), "yahoo")

@app.task(name="crawl_yahoo_washer", bind=True, max_retries=MAX_RETRIES)
def crawl_yahoo_washer(self):
    return run_crawl_task(self, "洗衣機", lambda: run_yahoo_crawler("洗衣機"), "yahoo")


# 追蹤清單：固定型號到各平台搜尋（app/watchlist.py），接在各平台排行榜後面跑
def run_watch_task(task, platform):
    try:
        total, saved, failed, message = run_watchlist(platform)
    except pymysql.err.OperationalError as e:
        print(f"⚠️ {platform} 追蹤清單連不上資料庫，{RETRY_DELAY} 秒後重試（第 {task.request.retries + 1} 次）：{e}")
        raise task.retry(exc=e, countdown=RETRY_DELAY)
    # 一筆都沒找到通常是網站暫時連不上，整批重跑；部分型號沒找到是正常的（該平台沒賣）
    if not saved and task.request.retries < task.max_retries:
        print(f"⚠️ {message}，{RETRY_DELAY} 秒後重試（第 {task.request.retries + 1} 次）")
        raise task.retry(countdown=RETRY_DELAY)
    return message


@app.task(name="crawl_watch_tk3c", bind=True, max_retries=MAX_RETRIES)
def crawl_watch_tk3c(self):
    return run_watch_task(self, "tk3c")


@app.task(name="crawl_watch_pchome", bind=True, max_retries=MAX_RETRIES)
def crawl_watch_pchome(self):
    return run_watch_task(self, "pchome")


@app.task(name="crawl_watch_yahoo", bind=True, max_retries=MAX_RETRIES)
def crawl_watch_yahoo(self):
    return run_watch_task(self, "yahoo")
