from typing import Optional

from fastapi import FastAPI, HTTPException
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
