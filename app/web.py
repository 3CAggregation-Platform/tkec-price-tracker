"""
公開網站（給同學 / 一般人看的比價頁）

和 app/main.py（內部 API）分開成另一個 FastAPI app、另一個 swarm service，原因：
- 只開放追蹤清單的三個唯讀查詢，其他內部 API（/products、/price-changes …）不對外
- 用唯讀帳號 web_reader 連 MySQL，只有 watchlist、watch_price_daily 兩張表的 SELECT 權限
- 不帶 .env（裡面有 root 密碼），只給這個 service 需要的環境變數
- 關掉 /docs、/openapi.json，每個 IP 每分鐘有請求上限

啟動：uvicorn app.web:app --host 0.0.0.0 --port 8000
"""
import datetime
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Path as PathParam, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from app.main import query, watchlist_compare, watchlist_history

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="家電比價", docs_url=None, redoc_url=None, openapi_url=None)


# ===== 每個 IP 的請求上限（單一 process 的記憶體計數，service 只開 1 個副本所以夠用）=====

RATE_LIMIT = 60          # 每個 IP 在 RATE_WINDOW 秒內最多幾次 /api 請求
RATE_WINDOW = 60
_hits = defaultdict(deque)
_hits_lock = threading.Lock()


def _too_many(ip):
    now = time.monotonic()
    with _hits_lock:
        hits = _hits[ip]
        while hits and now - hits[0] > RATE_WINDOW:
            hits.popleft()
        if len(hits) >= RATE_LIMIT:
            return True
        hits.append(now)
        # 避免記憶體一直長：IP 太多時清掉已經沒有請求的
        if len(_hits) > 10000:
            for key in [k for k, v in _hits.items() if not v]:
                del _hits[key]
        return False


@app.middleware("http")
async def limit_and_headers(request: Request, call_next):
    if request.url.path.startswith("/api/") and _too_many(request.client.host if request.client else "-"):
        return JSONResponse({"detail": "請求太頻繁，請稍後再試"}, status_code=429)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"
    )
    if request.url.path.startswith("/api/"):
        # 資料一天更新一次，讓瀏覽器快取 5 分鐘
        response.headers["Cache-Control"] = "public, max-age=300"
    return response


# ===== 頁面 =====

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/app.js", include_in_schema=False)
def app_js():
    return FileResponse(STATIC_DIR / "app.js", media_type="text/javascript")


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


# ===== 資料 API（只讀追蹤清單）=====

@app.get("/api/dates")
def dates():
    """有資料的日期（新到舊），給頁面的日期選單用"""
    rows = query("SELECT DISTINCT 抓取日期 AS d FROM watch_price_daily ORDER BY d DESC LIMIT 60")
    return [r["d"] for r in rows]


@app.get("/api/compare")
def compare(
    category: Optional[str] = Query(None, max_length=20),
    date: Optional[datetime.date] = None,
):
    """每個追蹤型號在各平台的最低價，只有一個平台有賣的型號也列出"""
    return watchlist_compare(category=category, date=date, min_platforms=1)


@app.get("/api/history/{model}")
def history(model: str = PathParam(..., max_length=100)):
    """單一型號每天在各平台的最低價"""
    return watchlist_history(model)
