"""
執行單一平台、單一分類的爬蟲並寫入資料庫，給 Airflow 的 DockerOperator 呼叫：

    python -m app.run_crawl tk3c 冰箱
    python -m app.run_crawl pchome 掃地機器人

沒抓到資料或寫入失敗時以非 0 結束，Airflow 會把這個 task 標成失敗並依設定重試
（Celery 版的重試邏輯在 app/tasks.py，兩者擇一使用）
"""
import sys

from app.db import save_products_to_db, log_crawl_run
from app.special_topic3C.fridge_search import run_fridge_crawler
from app.special_topic3C.tv_search import run_tv_crawler
from app.special_topic3C.airfryer_search import run_airfryer_crawler
from app.special_topic3C.robotvacuum_search import run_robotvacuum_crawler
from app.special_topic3C.pchome_search import run_pchome_crawler, CATEGORIES as PCHOME_CATEGORIES

TK3C_CRAWLERS = {
    "冰箱": run_fridge_crawler,
    "電視": run_tv_crawler,
    "氣炸鍋": run_airfryer_crawler,
    "掃地機器人": run_robotvacuum_crawler,
}

PLATFORM_NAMES = {"tk3c": "燦坤", "pchome": "PChome"}


def get_crawler(platform, category):
    if platform == "tk3c" and category in TK3C_CRAWLERS:
        return TK3C_CRAWLERS[category]
    if platform == "pchome" and category in PCHOME_CATEGORIES:
        return lambda: run_pchome_crawler(category)
    raise SystemExit(f"不支援的平台或分類：{platform} {category}")


def main(platform, category):
    crawler = get_crawler(platform, category)
    label = f"{PLATFORM_NAMES[platform]}{category}"

    data = crawler()
    if not data:
        log_crawl_run(category, 0, 0, 0, "no_data", "沒有抓到任何資料", platform)
        print(f"❌ {label}沒有抓到任何資料")
        return 1

    success, skipped = save_products_to_db(data)
    message = f"{label}爬蟲完成，共 {len(data)} 筆，成功寫入 {success} 筆，略過 {skipped} 筆"
    log_crawl_run(category, len(data), success, skipped, "success", message, platform)
    print(f"✅ {message}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("用法：python -m app.run_crawl <tk3c|pchome> <冰箱|電視|氣炸鍋|掃地機器人>")
    sys.exit(main(sys.argv[1], sys.argv[2]))
