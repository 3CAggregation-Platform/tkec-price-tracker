"""
透過 Redash API 建立（或更新）TK3C 比價儀表板：資料來源、6 個查詢與圖表、儀表板

用法（在專案根目錄執行）：
    set -a; source .env; set +a
    REDASH_API_KEY=<Redash 個人頁面的 API Key> python redash/setup_redash.py

重複執行不會建出重複的東西：同名的資料來源、查詢、儀表板會直接更新
"""
import json
import os
import time
import urllib.request

BASE = os.getenv("REDASH_URL", "http://127.0.0.1:5005")
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "queries")
KEY = os.environ["REDASH_API_KEY"]
DB_PASSWORD = os.environ["REDASH_DB_PASSWORD"]


def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={
        "Authorization": f"Key {KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        text = resp.read().decode()
        return json.loads(text) if text else None


def sql(name):
    return open(os.path.join(HERE, name), encoding="utf-8").read()


# 每天 21:30（台北）重新整理，在 PChome 最後一個分類 21:10 跑完之後；Redash 排程時間用 UTC
DAILY = {"interval": 86400, "time": "13:30", "day_of_week": None, "until": None}

# 1. 資料來源
ds = next((d for d in api("GET", "/api/data_sources") if d["name"] == "TK3C 比價資料庫"), None)
if not ds:
    ds = api("POST", "/api/data_sources", {
        "name": "TK3C 比價資料庫",
        "type": "mysql",
        "options": {"host": "host.docker.internal", "port": 13306, "user": "redash_reader",
                    "passwd": DB_PASSWORD, "db": "tk3c_price_tracker"},
    })
print("data source", ds["id"])
test = api("POST", f"/api/data_sources/{ds['id']}/test")
print("connection test", test)


def chart(series_type, mapping, x_type="category", stacking=None, extra=None):
    opts = {
        "globalSeriesType": series_type,
        "columnMapping": mapping,
        "xAxis": {"type": x_type, "labels": {"enabled": True}},
        "yAxis": [{"type": "linear"}, {"type": "linear", "opposite": True}],
        "legend": {"enabled": True, "placement": "auto"},
        "series": {"stacking": stacking, "error_y": {"type": "data", "visible": True}},
        "seriesOptions": {}, "valuesOptions": {}, "showDataLabels": series_type == "column",
    }
    opts.update(extra or {})
    return opts


QUERIES = [
    {"key": "trend", "name": "每日平均價格走勢", "file": "q1_trend.sql",
     "desc": "用上方「分類」篩選，比較燦坤與 PChome 每天的平均價格",
     "viz": ("CHART", "價格走勢", chart("line", {"日期": "x", "平均價格": "y", "平台": "series"}, x_type="datetime"))},
    {"key": "compare", "name": "燦坤 vs PChome 各分類價格比較", "file": "q2_compare.sql",
     "desc": "各平台最新一天 Top 20 的平均價格",
     "viz": ("CHART", "平均價格比較", chart("column", {"分類": "x", "平均價格": "y", "平台": "series"}))},
    {"key": "ranking", "name": "今日 Top 20 排行榜", "file": "q3_ranking.sql",
     "desc": "各平台最新一天的排名；評價只有 PChome 有", "viz": None},
    {"key": "drop", "name": "最近 14 天降價商品", "file": "q4_price_drop.sql",
     "desc": "和同一商品前一次抓到的價格相比", "viz": None},
    {"key": "rating", "name": "PChome 銷量排名 vs 評價", "file": "q5_rating.sql",
     "desc": "只列出有評價的商品；評價數少的星數參考價值較低",
     "viz": ("CHART", "排名 vs 評價", chart("scatter", {"排名": "x", "評價": "y", "分類": "series"}, x_type="linear"))},
    {"key": "status", "name": "爬蟲每日執行狀態", "file": "q6_crawl_status.sql",
     "desc": "每天應該有 8 筆（2 平台 × 4 分類）；連不上資料庫的失敗不會被記錄",
     "viz": ("CHART", "執行狀態", chart("column", {"日期": "x", "次數": "y", "狀態": "series"}, x_type="category", stacking="normal"))},
]

existing = {q["name"]: q for q in api("GET", "/api/queries?page_size=100")["results"]}
widgets = {}
for q in QUERIES:
    body = {"name": q["name"], "query": sql(q["file"]), "data_source_id": ds["id"],
            "description": q["desc"], "schedule": DAILY, "options": {"parameters": []}}
    if q["name"] in existing:
        query = api("POST", f"/api/queries/{existing[q['name']]['id']}", body)
    else:
        query = api("POST", "/api/queries", body)
    api("POST", f"/api/queries/{query['id']}", {"is_draft": False})
    # 先執行一次，儀表板打開時就有資料
    job = api("POST", f"/api/queries/{query['id']}/results", {"max_age": 0})
    for _ in range(30):
        if "query_result" in job:
            break
        j = api("GET", f"/api/jobs/{job['job']['id']}")["job"]
        if j["status"] in (3, 4):
            if j["status"] == 4:
                raise SystemExit(f"{q['name']} 執行失敗：{j['error']}")
            break
        time.sleep(1)

    full = api("GET", f"/api/queries/{query['id']}")
    table = next(v for v in full["visualizations"] if v["type"] == "TABLE")
    if q["viz"]:
        vtype, vname, vopts = q["viz"]
        viz = next((v for v in full["visualizations"] if v["name"] == vname), None)
        body = {"query_id": query["id"], "type": vtype, "name": vname, "options": vopts}
        viz = api("POST", f"/api/visualizations/{viz['id']}", body) if viz else api("POST", "/api/visualizations", body)
        widgets[q["key"]] = viz["id"]
    else:
        widgets[q["key"]] = table["id"]
    print("query", query["id"], q["name"])

# 2. 儀表板（6 欄寬的格線）
LAYOUT = [
    ("trend", 0, 0, 3, 8), ("compare", 3, 0, 3, 8),
    ("ranking", 0, 8, 6, 12),
    ("drop", 0, 20, 6, 9),
    ("rating", 0, 29, 3, 8), ("status", 3, 29, 3, 8),
]
dash = next((d for d in api("GET", "/api/dashboards?page_size=100")["results"] if d["name"] == "TK3C 比價儀表板"), None)
if dash:
    for w in api("GET", f"/api/dashboards/{dash['id']}").get("widgets", []):
        api("DELETE", f"/api/widgets/{w['id']}")
else:
    dash = api("POST", "/api/dashboards", {"name": "TK3C 比價儀表板"})
for key, col, row, sx, sy in LAYOUT:
    api("POST", "/api/widgets", {
        "dashboard_id": dash["id"], "visualization_id": widgets[key], "text": "", "width": 1,
        "options": {"position": {"col": col, "row": row, "sizeX": sx, "sizeY": sy}, "parameterMappings": {}},
    })
api("POST", f"/api/dashboards/{dash['id']}", {"is_draft": False, "dashboard_filters_enabled": True})
print("dashboard", f"{BASE}/dashboards/{dash['id']}-{dash['slug']}")
