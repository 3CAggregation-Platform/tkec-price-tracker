"""
每日爬蟲結果檢查：確認當天每個平台、每個分類都有抓到資料

    python -m app.crawl_check                    # 檢查今天（台北時間）
    python -m app.crawl_check --date 2026-11-10  # 檢查指定日期

讀 crawl_log 每個（平台, 分類）當天最後一筆紀錄：
- 沒有紀錄、status 不是 success、或抓到 0 筆 → 列為異常，程式回傳 1，Airflow task 變紅色
- 筆數比前 7 天平均少一半以上 → 只印警告，不算失敗（例如追蹤清單有些型號當天沒上架）
- CRAWL_CHECK_IGNORE 列出的平台（預設 momo，11/08 起被網站擋 403）只印警告，不算失敗

Airflow 的 tk3c_bigquery_sync DAG 每天 21:30 和 BigQuery 同步一起執行（兩個 task 互不影響，
檢查失敗不會擋住同步）。MySQL 連線沿用 app.bigquery_sync（唯讀帳號 + Secret Manager）。
"""
import argparse
import datetime
import os
import sys

from app.bigquery_sync import TAIPEI, mysql_connection

CATEGORIES = ["冰箱", "電視", "氣炸鍋", "掃地機器人", "洗衣機"]
WATCH = "追蹤清單"
# 和 app/producer.py 的 CHAINS 對應：每個平台每天應該要有的 crawl_log 紀錄
EXPECTED = {
    "tk3c": CATEGORIES + [WATCH],
    "pchome": CATEGORIES + [WATCH],
    "yahoo": CATEGORIES + [WATCH],
    "momo": ["氣炸鍋"],
}
IGNORED = {p.strip() for p in os.getenv("CRAWL_CHECK_IGNORE", "momo").split(",") if p.strip()}


def found_count(row):
    # 追蹤清單的 item_count 是型號總數（固定 85），實際找到幾個要看 success_count
    return row["success_count"] if row["category"] == WATCH else row["item_count"]


def load_logs(cursor, day):
    """回傳 {(平台, 分類): 當天最後一筆紀錄}，以及 {(平台, 分類): 前 7 天平均筆數}"""
    cursor.execute(
        """
        SELECT platform, category, run_at, item_count, success_count, status, message
        FROM crawl_log
        WHERE run_at >= %s AND run_at < %s
        ORDER BY run_at
        """,
        (day - datetime.timedelta(days=7), day + datetime.timedelta(days=1)),
    )
    today, history = {}, {}
    for row in cursor.fetchall():
        key = (row["platform"], row["category"])
        if row["run_at"].date() == day:
            today[key] = row  # 依時間排序，同一天跑兩次時留最後一筆
        elif row["status"] == "success":
            history.setdefault(key, {})[row["run_at"].date()] = found_count(row)
    averages = {key: sum(days.values()) / len(days) for key, days in history.items()}
    return today, averages


def check(day):
    conn = mysql_connection()
    try:
        with conn.cursor() as cursor:
            today, averages = load_logs(cursor, day)
            cursor.execute(
                "SELECT 平台 AS platform, COUNT(*) AS n FROM all_goods_daily WHERE 抓取日期 = %s GROUP BY 平台",
                (day,),
            )
            goods = {row["platform"]: row["n"] for row in cursor.fetchall()}
    finally:
        conn.close()

    errors, warnings = [], []
    print(f"爬蟲結果檢查 {day}")
    for platform, categories in EXPECTED.items():
        for category in categories:
            row = today.get((platform, category))
            label = f"{platform}/{category}"
            if row is None:
                problem = "沒有執行紀錄"
            elif row["status"] != "success":
                problem = f"status={row['status']}（{row['message']}）"
            elif found_count(row) == 0:
                problem = "抓到 0 筆"
            else:
                problem = None

            if problem:
                (warnings if platform in IGNORED else errors).append(f"{label}：{problem}")
                print(f"  ❌ {label}：{problem}" + ("（已知問題，不算失敗）" if platform in IGNORED else ""))
                continue

            count, avg = found_count(row), averages.get((platform, category))
            note = f"（前 7 天平均 {avg:.0f}）" if avg else ""
            if avg and count < avg / 2:
                warnings.append(f"{label}：{count} 筆，不到前 7 天平均 {avg:.0f} 的一半")
                print(f"  ⚠️ {label}：{count} 筆{note}")
            else:
                print(f"  ✅ {label}：{count} 筆{note}")

    print("all_goods_daily 當天筆數：" + "、".join(f"{p} {n}" for p, n in sorted(goods.items())) if goods else "all_goods_daily 當天沒有資料")
    if not goods:
        errors.append("all_goods_daily 當天沒有資料")

    for message in warnings:
        print(f"警告：{message}")
    if errors:
        print(f"共 {len(errors)} 項異常：")
        for message in errors:
            print(f"  - {message}")
        return 1
    print("檢查通過")
    return 0


def main():
    parser = argparse.ArgumentParser(description="檢查當天爬蟲有沒有抓到資料")
    parser.add_argument("--date", type=datetime.date.fromisoformat)
    args = parser.parse_args()
    return check(args.date or datetime.datetime.now(TAIPEI).date())


if __name__ == "__main__":
    sys.exit(main())
