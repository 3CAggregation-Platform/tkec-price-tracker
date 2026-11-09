import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.openapi.docs import get_redoc_html

from app.db import get_connection

# FastAPI 內建的 /redoc 預設載入 redoc@next，但這個版本在 CDN 上已下架（404），
# 會導致頁面空白，所以關掉內建路由，改用固定版本號自己接
app = FastAPI(title="TK3C 比價 API", redoc_url=None)


@app.get("/redoc", include_in_schema=False)
def redoc():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2/bundles/redoc.standalone.js",
    )


def query(sql, params=None):
    """執行查詢並回傳 list[dict]，欄位名稱取自 cursor.description"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
    finally:
        conn.close()
    return [dict(zip(columns, row)) for row in rows]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/products")
def list_products(category: Optional[str] = None, platform: Optional[str] = None):
    """列出所有商品，可用 ?category=電視 篩選分類、?platform=pchome 篩選平台（tk3c / pchome）"""
    conditions = []
    params = []
    if category:
        conditions.append("category = %s")
        params.append(category)
    if platform:
        conditions.append("platform = %s")
        params.append(platform)
    where = f"WHERE {' AND '.join(conditions)} " if conditions else ""
    return query(
        "SELECT id, platform, product_code, category, brand, model, name, link, "
        f"first_seen_at, updated_at FROM products {where}ORDER BY id",
        params,
    )


@app.get("/products/{product_id}/price-history")
def product_price_history(product_id: int):
    """回傳單一商品的完整價格歷史，依抓取日期排序"""
    product = query("SELECT id FROM products WHERE id = %s", (product_id,))
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    return query(
        "SELECT crawl_date, `rank`, discount, price, original_price, rating, review_count "
        "FROM price_history WHERE product_id = %s ORDER BY crawl_date",
        (product_id,),
    )


@app.get("/price-changes")
def price_changes():
    """列出所有曾經變動過價格的紀錄（比較每個商品前後兩次抓取的價格）"""
    return query(
        """
        SELECT
            p.id AS product_id,
            p.platform,
            p.category,
            p.brand,
            p.name,
            t.crawl_date,
            t.prev_price,
            t.price,
            (t.price - t.prev_price) AS price_diff
        FROM (
            SELECT
                product_id,
                crawl_date,
                price,
                LAG(price) OVER (PARTITION BY product_id ORDER BY crawl_date) AS prev_price
            FROM price_history
        ) t
        JOIN products p ON p.id = t.product_id
        WHERE t.prev_price IS NOT NULL AND t.price <> t.prev_price
        ORDER BY t.crawl_date DESC
        """
    )


# ===== 追蹤清單（watchlist / watch_price_daily，見 app/watchlist.py）=====

PLATFORM_LABELS = {"tk3c": "燦坤", "pchome": "PChome", "yahoo": "Yahoo"}


@app.get("/watchlist", tags=["追蹤清單"])
def list_watchlist(category: Optional[str] = None, include_disabled: bool = False):
    """追蹤清單的型號，可用 ?category=冰箱 篩選分類；預設只列出啟用中的型號"""
    conditions, params = [], []
    if category:
        conditions.append("分類 = %s")
        params.append(category)
    if not include_disabled:
        conditions.append("啟用")
    where = f"WHERE {' AND '.join(conditions)} " if conditions else ""
    rows = query(f"SELECT 分類, 廠牌, 型號, 啟用 FROM watchlist {where}ORDER BY 分類, id", params)
    return [
        {"category": r["分類"], "brand": r["廠牌"], "model": r["型號"], "enabled": bool(r["啟用"])}
        for r in rows
    ]


@app.get("/watchlist/compare", tags=["追蹤清單"])
def watchlist_compare(
    category: Optional[str] = None,
    date: Optional[datetime.date] = None,
    min_platforms: int = Query(2, ge=1, le=3, description="至少幾個平台有價格才列出"),
):
    """
    追蹤型號跨平台比價：每個型號一筆，列出各平台最低價、最便宜的平台與價差，依價差比例由大到小排序。
    不指定 date 時用最新一天的資料。
    """
    if date is None:
        latest = query("SELECT MAX(抓取日期) AS d FROM watch_price_daily")
        date = latest[0]["d"] if latest else None
        if date is None:
            return {"date": None, "count": 0, "items": []}

    conditions, params = ["抓取日期 = %s"], [date]
    if category:
        conditions.append("分類 = %s")
        params.append(category)
    rows = query(
        f"SELECT 分類, 型號, 廠牌, 平台, 售價, 商品名稱, 連結 FROM watch_price_daily "
        f"WHERE {' AND '.join(conditions)} ORDER BY 分類, 型號, 售價",
        params,
    )

    by_model = {}
    for r in rows:
        item = by_model.setdefault(r["型號"], {"category": r["分類"], "model": r["型號"], "brand": r["廠牌"], "prices": {}})
        item["prices"][r["平台"]] = {"price": r["售價"], "name": r["商品名稱"], "url": r["連結"]}

    items = []
    for item in by_model.values():
        prices = {p: v["price"] for p, v in item["prices"].items()}
        if len(prices) < min_platforms:
            continue
        low, high = min(prices.values()), max(prices.values())
        cheapest = [PLATFORM_LABELS[p] for p in PLATFORM_LABELS if prices.get(p) == low]
        item.update({
            "min_price": low,
            "max_price": high,
            "price_gap": high - low,
            "gap_ratio": round((high - low) / low, 3) if low else None,
            "cheapest_platform": "同價" if low == high and len(prices) > 1 else "、".join(cheapest),
        })
        items.append(item)
    items.sort(key=lambda x: x["gap_ratio"] or 0, reverse=True)
    return {"date": date, "count": len(items), "items": items}


@app.get("/watchlist/{model}/history", tags=["追蹤清單"])
def watchlist_history(model: str):
    """單一追蹤型號每天在各平台的最低價（例如 /watchlist/KZ-WA06K/history）"""
    watched = query("SELECT 分類, 廠牌, 型號 FROM watchlist WHERE 型號 = %s", (model,))
    if not watched:
        raise HTTPException(status_code=404, detail="這個型號不在追蹤清單裡")
    rows = query(
        "SELECT 抓取日期, 平台, 售價, 原價, 符合筆數, 商品名稱, 連結 FROM watch_price_daily "
        "WHERE 型號 = %s ORDER BY 抓取日期, 平台",
        (model,),
    )
    return {
        "category": watched[0]["分類"],
        "brand": watched[0]["廠牌"],
        "model": watched[0]["型號"],
        "history": [
            {"date": r["抓取日期"], "platform": r["平台"], "price": r["售價"], "list_price": r["原價"],
             "match_count": r["符合筆數"], "name": r["商品名稱"], "url": r["連結"]}
            for r in rows
        ],
    }
