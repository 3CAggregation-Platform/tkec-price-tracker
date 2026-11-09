"""
追蹤清單：讀 watchlist → 各平台用型號搜尋 → 寫入 watch_price_daily

每日排程：app/producer.py 把 crawl_watch_<平台> 接在各平台排行榜爬蟲後面（同一個網站依序跑）
手動執行（不經過 RabbitMQ）：

    python -m app.watchlist pchome
    python -m app.watchlist tk3c --limit 5   # 只跑前 5 個型號，測試用
"""
import argparse

from app.db import get_connection, log_crawl_run
from app.special_topic3C.watch_search import PLATFORMS, run_watch_crawler

CATEGORY_LABEL = "追蹤清單"  # 寫進 crawl_log.category


def load_watchlist(limit=None):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 分類, 廠牌, 型號 FROM watchlist WHERE 啟用 ORDER BY 分類, id")
            rows = list(cursor.fetchall())
    finally:
        conn.close()
    return rows[:limit] if limit else rows


def save_watch_prices(platform, rows):
    """同一天重跑時先刪掉這個平台當天的資料，只保留最後一次"""
    if not rows:
        return 0
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM watch_price_daily WHERE 平台 = %s AND 抓取日期 = %s",
                (platform, rows[0]["抓取日期"]),
            )
            cursor.executemany(
                """
                INSERT INTO watch_price_daily (抓取日期, 平台, 分類, 型號, 商品編號, 廠牌, 商品名稱, 售價, 原價, 符合筆數, 連結)
                VALUES (%(抓取日期)s, %(平台)s, %(分類)s, %(型號)s, %(商品編號)s, %(廠牌)s, %(商品名稱)s,
                        %(售價)s, %(原價)s, %(符合筆數)s, %(連結)s)
                """,
                rows,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return len(rows)


def run_watchlist(platform, limit=None):
    """回傳 (watchlist 型號數, 找到筆數, 請求失敗數, 訊息)"""
    watchlist = load_watchlist(limit)
    rows, failed = run_watch_crawler(platform, watchlist)
    saved = save_watch_prices(platform, rows)
    message = f"{platform} 追蹤清單 {len(watchlist)} 個型號，找到 {saved} 個，請求失敗 {failed} 個"
    status = "success" if saved else "no_data"
    log_crawl_run(CATEGORY_LABEL, len(watchlist), saved, len(watchlist) - saved, status, message, platform)
    return len(watchlist), saved, failed, message


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="追蹤清單爬蟲")
    parser.add_argument("platform", choices=PLATFORMS)
    parser.add_argument("--limit", type=int, help="只跑前 N 個型號（測試用）")
    args = parser.parse_args()
    total, saved, failed, message = run_watchlist(args.platform, args.limit)
    print(("✅ " if saved else "❌ ") + message)
    raise SystemExit(0 if saved else 1)
