"""
Yahoo 購物中心爬蟲（氣炸鍋）

搜尋頁的商品資料以 JSON 放在 <script id="isoredux-data"> 裡（search.ecsearch.hits），
有獨立的品牌（ec_brand）、型號（ec_model）、售價、原價、評價欄位。

排名的定義：依「銷量」排序（sort=-sales），只保留 Yahoo 分類為「氣炸鍋/油炸鍋」的商品
（關鍵字搜尋也會出現炸雞、烘焙紙、電器架），去掉配件後依序取前 20 筆
"""
import json
import re
import sys
import time
import datetime
import urllib.parse

from app.special_topic3C import airfryer_search
from app.special_topic3C.momo_search import fetch_text
from app.special_topic3C.pchome_search import calc_discount, extract_model

PLATFORM = "yahoo"
MAX_ITEMS = 20
MAX_PAGES = 5  # 每頁 60 筆

SEARCH_URL = "https://tw.buy.yahoo.com/search/product"
DATA_PATTERN = re.compile(r'<script id="isoredux-data" type="mime/invalid">(.*?)</script>', re.S)

# cat_path：Yahoo 分類全名（ec_catnamefull，以 tab 分隔）裡要出現的分類
# require_keyword：商品名稱一定要有的字
# filter_module：沿用燦坤爬蟲的配件過濾規則，各平台標準一致
CATEGORIES = {
    "氣炸鍋": {
        "keyword": "氣炸鍋",
        "cat_path": "氣炸鍋/油炸鍋",
        "require_keyword": "氣炸",  # 這個分類也包含一般油炸鍋
        "filter_module": airfryer_search,
    },
}


def search_page(keyword, page):
    """抓取一頁依銷量排序的搜尋結果，回傳商品 list；請求失敗回傳 None"""
    params = urllib.parse.urlencode({"p": keyword, "sort": "-sales", "pg": page})
    url = f"{SEARCH_URL}?{params}"
    print(f"正在請求 Yahoo 第 {page} 頁：{url}")
    html = fetch_text(url)
    if html is None:
        return None
    match = DATA_PATTERN.search(html)
    if not match:
        print("⚠️ 頁面裡找不到商品資料（isoredux-data）")
        return []
    data = json.loads(match.group(1))
    return data["search"]["ecsearch"].get("hits") or []


def is_excluded(hit, config):
    """不屬於這個分類的商品或配件不列入排名"""
    name = hit.get("ec_title", "")
    if config["cat_path"] not in hit.get("ec_catnamefull", "").split("\t"):
        return True
    if config["require_keyword"] not in name:
        return True
    return config["filter_module"].is_accessory(name)


def to_int(value):
    """把 "1699.0"、"" 轉成 1699 / None"""
    try:
        return int(float(value)) if value not in (None, "") else None
    except ValueError:
        return None


def clean_brand(brand, name, filter_module):
    """賣家沒填品牌時 Yahoo 會給「其他品牌」，改從商品名稱拆"""
    if not brand or brand == "其他品牌":
        return filter_module.extract_brand(name)
    return brand


def clean_model(model, name):
    """賣家填的型號可能是「--」或一次列好幾個（AF-6201/OAF-6201、A(綠) 、B(黑)），只取第一個"""
    model = re.split(r"[\s、/,，]", (model or "").strip())[0]
    if re.search(r"[A-Za-z0-9]", model):
        return model
    return extract_model(name)


def to_row(hit, rank, category, filter_module, today):
    """把 Yahoo 的商品轉成跟其他平台一樣的欄位格式，才能共用 save_products_to_db"""
    clean_name = filter_module.strip_promo_prefix(hit["ec_title"].strip())
    price = to_int(hit.get("ec_price"))
    original_price = to_int(hit.get("ec_listprice"))
    rating_count = to_int(hit.get("ec_rating_count"))
    return {
        "平台": PLATFORM,
        "抓取日期": today,
        "分類": category,
        "排名": rank,
        "商品編號": hit["ec_productid"],  # 商品頁網址上的編號
        "廠牌": clean_brand(hit.get("ec_brand"), clean_name, filter_module),
        "型號": clean_model(hit.get("ec_model"), clean_name),
        "商品名稱": clean_name,
        "折扣": calc_discount(price, original_price),
        "售價": f"${price}" if price else "",
        "原價": f"${original_price}" if original_price else "",
        "評價": float(hit["ec_global_rating"]) if rating_count else None,  # 沒人評價時評分欄位是 0 或空字串
        "評價數": rating_count or None,
        "商品詳細": (hit.get("ec_description") or "").strip(),
        "連結": hit.get("ec_item_url"),
    }


def run_yahoo_crawler(category):
    """執行指定分類的 Yahoo 爬蟲，回傳整理好的商品資料 list"""
    config = CATEGORIES[category]
    today = datetime.date.today().strftime("%Y-%m-%d")
    results = []
    seen_ids = set()

    for page in range(1, MAX_PAGES + 1):
        hits = search_page(config["keyword"], page)
        if hits is None:
            print(f"第 {page} 頁請求失敗，停止翻頁")
            break
        if not hits:
            print(f"第 {page} 頁沒有商品了，停止翻頁")
            break

        added = 0
        for hit in hits:
            if hit["ec_productid"] in seen_ids:
                continue
            seen_ids.add(hit["ec_productid"])
            if is_excluded(hit, config):
                continue
            results.append(to_row(hit, len(results) + 1, category, config["filter_module"], today))
            added += 1
            if len(results) >= MAX_ITEMS:
                break

        print(f"第 {page} 頁新增 {added} 筆，目前累計 {len(results)} 筆")
        if len(results) >= MAX_ITEMS:
            break
        time.sleep(1.5)

    print(f"\n===== Yahoo {category}共抓到 {len(results)} 筆 =====")
    return results


if __name__ == "__main__":
    category = sys.argv[1] if len(sys.argv) > 1 else "氣炸鍋"
    for row in run_yahoo_crawler(category):
        print(row["排名"], row["廠牌"], row["型號"], row["售價"], row["折扣"], row["評價"], row["評價數"], row["商品名稱"][:40])
