"""
Superset 設定：放在 /app/pythonpath，啟動時自動載入

- SECRET_KEY 從環境變數讀（.env 的 SUPERSET_SECRET_KEY），不能用預設值，否則 Superset 拒絕啟動
- metadata（帳號、圖表、dashboard 設定）存在 volume 裡的 SQLite，不另外架資料庫
- 介面預設繁體中文
"""
import os

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = "sqlite:////app/superset_home/superset.db?check_same_thread=false"

BABEL_DEFAULT_LOCALE = "zh_TW"
LANGUAGES = {
    "zh_TW": {"flag": "tw", "name": "繁體中文"},
    "en": {"flag": "us", "name": "English"},
}

# 圖表查詢結果快取 1 小時（爬蟲一天只跑一次，不需要即時）
DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 3600,
}
