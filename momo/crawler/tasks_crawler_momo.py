from sqlalchemy import text

from crawler.crawler_momo import CATEGORIES
from crawler.crawler_momo import crawler_momo as fetch_momo
from crawler.load_csv_to_mysql import clean, get_engine
from crawler.worker import app

TABLE = "momo_goods_daily"


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
    print(f"{category_name}：{len(df)} 筆")
    return len(df)


@app.task()
def crawler_momo_all():
    for category_name in CATEGORIES:
        crawler_momo_print.s(category_name).apply_async()
    return len(CATEGORIES)