from sqlalchemy import text

from crawler.crawler_momo import CATEGORIES
from crawler.crawler_momo import crawler_momo as fetch_momo
from crawler.load_csv_to_mysql import clean, get_engine
from crawler.worker import app

TABLE = "momo_goods_daily"
SHARED = "tk3c_price_tracker.goods_daily"
PRODUCT_URL = "https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code="


def sync_to_shared(engine, today, category_name):
    """把今天這個分類的資料同步到團隊共用表；失敗只印警告，不影響爬蟲任務。"""
    sql = text(f"""
        INSERT IGNORE INTO {SHARED} (
            平台, 抓取日期, 分類, 商品編號, 廠牌, 型號, 商品名稱, 連結,
            售價, 原價, 銷量, 銷量下限, 評分, 評價數, 庫存, 促銷文案, 有政府補助
        )
        SELECT
            'momo', 抓取日期, 分類, 商品編號, 廠牌, 型號, 商品名稱,
            CONCAT(:url, 商品編號),
            售價, CAST(原價 AS SIGNED), 銷量, CAST(銷量下限 AS SIGNED),
            評分, CAST(評價數 AS SIGNED), 庫存, 促銷文案, 有政府補助
        FROM {TABLE}
        WHERE 抓取日期 = :d AND 分類 = :c AND 商品編號 IS NOT NULL
    """)
    try:
        with engine.begin() as conn:
            result = conn.execute(
                sql, {"url": PRODUCT_URL, "d": today, "c": category_name}
            )
        print(f"{category_name}：同步 {result.rowcount} 筆到 {SHARED}")
    except Exception as e:
        print(f"警告：{category_name} 同步到 {SHARED} 失敗：{e}")


@app.task()
def crawler_momo_print(category_name: str):
    df = clean(fetch_momo(category_name))
    today = df["抓取日期"].iloc[0]
    engine = get_engine()

    # 先刪掉今天這個分類的舊資料，這樣跑幾次都只會留一份
    with engine.begin() as conn:
        conn.execute(
            text(f"DELETE FROM {TABLE} WHERE 抓取日期 = :d AND 分類 = :c"),
            {"d": today, "c": category_name},
        )

    df.to_sql(TABLE, con=engine, if_exists="append", index=False)
    sync_to_shared(engine, today, category_name)
    print(f"{category_name}：{len(df)} 筆")
    return len(df)


@app.task()
def crawler_momo_all():
    for category_name in CATEGORIES:
        crawler_momo_print.s(category_name).apply_async()
    return len(CATEGORIES)