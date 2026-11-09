"""
追蹤清單爬蟲：拿固定的型號（watchlist）到燦坤、PChome、Yahoo 搜尋，找出每個平台這個型號的最低價

前 20 名排行榜只抓得到各平台當天最熱賣的商品，不同平台重疊的型號很少，跨平台比價的圖常常沒資料；
追蹤清單固定一批型號每天到每個平台搜尋，同一個型號就能天天比價。

比對規則（避免把配件、相近型號算進來）：
- 型號比對：去掉 - 和空白、轉大寫後，商品名稱（Yahoo 另外看型號欄位、燦坤看商品頁的「產品型號」）裡
  要有一段英數字和型號相同；型號 7 碼以上時允許差 3 碼以內的顏色 / 版本後綴（NR-B171TV ↔ NR-B171TV-S1）
- 分類比對：PChome 看商品分類代碼、Yahoo 看分類路徑，沿用排行榜爬蟲的設定
- 配件：沿用排行榜爬蟲各分類的排除關鍵字，另外排除「適用」「相容」（濾網、遙控器常寫「適用 XX 型號」）
  與福利品、盒損、展示機、二手、整新（非全新品和新品比價不公平）；
  不檢查名稱裡有沒有容量，型號比對已經足夠確定是本體
- 同型號有多個賣場（PChome、Yahoo 常見）取最低價，並記錄符合的賣場數
- momo 自 2026/11/08 起擋下程式存取，不爬

單獨測試：python -m app.special_topic3C.watch_search pchome 冰箱 HRE-B1261U
"""
import re
import sys
import json
import time
import datetime
import urllib.parse

from bs4 import BeautifulSoup

from app.special_topic3C import pchome_search, yahoo_search
from app.special_topic3C import airfryer_search as tk3c  # 燦坤五個分類的請求、商品頁解析程式相同，用其中一個即可
from app.goods_daily import normalize_brand, normalize_model

REQUEST_DELAY = 1.5
TK3C_MAX_DETAILS = 3  # 燦坤搜尋結果的名稱沒有型號，最多進前 3 個商品頁確認
EXTRA_EXCLUDE = ["適用", "相容", "福利品", "福利機", "盒損", "展示機", "二手", "整新"]  # 配件、非全新品不和新品比價


def model_key(text):
    """比對用：去掉括號內容（顏色 / 版本）、- 和空白，轉大寫"""
    return re.sub(r"[^A-Z0-9]", "", (normalize_model(text) or "").upper())


def model_matches(target, text):
    """text（商品名稱或型號欄位）裡有沒有一段英數字等於 target 型號"""
    target_key = model_key(target)
    if not target_key or not text:
        return False
    for token in re.findall(r"[A-Z0-9][A-Z0-9\-]*", text.upper()):
        key = token.replace("-", "")
        if key == target_key:
            return True
        # 顏色 / 版本後綴：NR-B171TV-S1 ↔ NR-B171TV；短型號（NA221 ↔ NA2210）不放寬
        longer, shorter = (key, target_key) if len(key) > len(target_key) else (target_key, key)
        if len(shorter) >= 7 and longer.startswith(shorter) and len(longer) - len(shorter) <= 3:
            return True
    return False


def is_accessory(name, category):
    """排行榜爬蟲各分類的排除關鍵字 + 適用 / 相容"""
    module = pchome_search.CATEGORIES[category]["filter_module"]
    return any(kw in name for kw in module.EXCLUDE_KEYWORDS + EXTRA_EXCLUDE)


def to_int(value):
    try:
        return int(float(value)) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def make_row(platform, item, category, model, brand, match_count, today):
    return {
        "抓取日期": today,
        "平台": platform,
        "分類": category,
        "型號": model,
        "商品編號": item["code"],
        "廠牌": normalize_brand(brand) or brand,
        "商品名稱": item["name"][:255],
        "售價": item["price"],
        "原價": item.get("original_price"),
        "符合筆數": match_count,
        "連結": item["link"],
    }


def search_pchome(category, model):
    """PChome 搜尋 API，回傳符合的商品 list（未排序）；請求失敗回傳 None"""
    config = pchome_search.CATEGORIES[category]
    params = urllib.parse.urlencode({"q": model, "page": 1, "pageCount": 40})
    data = pchome_search.fetch_json(f"{pchome_search.SEARCH_API}?{params}")
    if data is None:
        return None
    items = []
    for prod in data.get("Prods") or []:
        name = prod.get("Name", "")
        if not any(pc.startswith(config["pcate_prefix"]) for pc in prod.get("PCateId") or []):
            continue
        if not model_matches(model, name) or is_accessory(name, category):
            continue
        price = to_int(prod.get("Price"))
        if not price:
            continue
        items.append({
            "code": prod["Id"],
            "name": name.strip(),
            "price": price,
            "original_price": to_int(prod.get("OriginPrice")),
            "link": pchome_search.PRODUCT_URL.format(prod["Id"]),
        })
    return items


def search_yahoo(category, model):
    """Yahoo 搜尋頁（相關度排序的第一頁），回傳符合的商品 list；請求失敗回傳 None"""
    config = yahoo_search.CATEGORIES[category]
    html = yahoo_search.fetch_text(f"{yahoo_search.SEARCH_URL}?{urllib.parse.urlencode({'p': model})}")
    if html is None:
        return None
    match = yahoo_search.DATA_PATTERN.search(html)
    if not match:
        return []
    items = []
    for hit in json.loads(match.group(1))["search"]["ecsearch"].get("hits") or []:
        name = hit.get("ec_title", "")
        cats = hit.get("ec_catnamefull", "").split("\t")[1:]
        if tuple(cats[:len(config["cat_prefix"])]) != config["cat_prefix"]:
            continue
        if any(cat in config["exclude_cats"] for cat in cats):
            continue
        if not (model_matches(model, hit.get("ec_model")) or model_matches(model, name)):
            continue
        if is_accessory(name, category):
            continue
        price = to_int(hit.get("ec_price"))
        if not price:
            continue
        items.append({
            "code": hit["ec_productid"],
            "name": name.strip(),
            "price": price,
            "original_price": to_int(hit.get("ec_listprice")),
            "link": hit.get("ec_item_url"),
        })
    return items


def search_tk3c(category, model):
    """燦坤搜尋頁的名稱沒有型號，進前幾個商品頁比對「產品型號」；請求失敗回傳 None"""
    url = f"https://www.tk3c.com/search.aspx?q={urllib.parse.quote(model)}"
    html = tk3c.fetch_url(url)
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")
    items = []
    checked = 0
    for card in soup.find_all(class_=re.compile(r"^prod_item")):
        if checked >= TK3C_MAX_DETAILS:
            break
        title = card.find(class_="title")
        link_el = title.find("a") if title else None
        if not link_el or not link_el.get("href"):
            continue
        name = (link_el.get("title") or link_el.get_text(strip=True)).strip()
        if is_accessory(name, category):
            continue
        link = urllib.parse.urljoin(url, link_el["href"]).split("?")[0]  # 去掉 ?p=1&kw=...，和排行榜的連結一致
        checked += 1
        time.sleep(REQUEST_DELAY)
        details = tk3c.fetch_product_details(link)
        if not model_matches(model, details["model"]) or not details["product_code"]:
            continue
        price_el = card.find(class_="price")
        _, price_text = tk3c.parse_price(price_el.get_text(strip=True) if price_el else "")
        price = to_int(price_text.replace("$", "").replace(",", ""))
        if not price:
            continue
        items.append({
            "code": details["product_code"],
            "name": tk3c.strip_promo_prefix(name),
            "price": price,
            "original_price": to_int(details["original_price"].replace("$", "").replace(",", "")),
            "link": link,
        })
    return items


SEARCHERS = {"tk3c": search_tk3c, "pchome": search_pchome, "yahoo": search_yahoo}
PLATFORMS = list(SEARCHERS)


def run_watch_crawler(platform, watchlist):
    """
    watchlist：[(分類, 廠牌, 型號), ...]
    回傳 (rows, failed)：rows 是每個找到的型號一筆（最低價），failed 是請求失敗的型號數
    """
    search = SEARCHERS[platform]
    today = datetime.date.today().strftime("%Y-%m-%d")
    rows, failed = [], 0
    for i, (category, brand, model) in enumerate(watchlist, 1):
        items = search(category, model)
        if items is None:
            failed += 1
            print(f"[{i}/{len(watchlist)}] ⚠️ {model} 請求失敗")
        elif not items:
            print(f"[{i}/{len(watchlist)}] {model} 沒找到")
        else:
            best = min(items, key=lambda x: x["price"])
            rows.append(make_row(platform, best, category, model, brand, len(items), today))
            print(f"[{i}/{len(watchlist)}] {model} 找到 {len(items)} 筆，最低 {best['price']}：{best['name'][:40]}")
        time.sleep(REQUEST_DELAY)
    print(f"\n===== {platform} 追蹤清單 {len(watchlist)} 個型號，找到 {len(rows)} 個，失敗 {failed} 個 =====")
    return rows, failed


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("用法：python -m app.special_topic3C.watch_search <tk3c|pchome|yahoo> <分類> <型號>")
    platform_, category_, model_ = sys.argv[1:]
    for row in run_watch_crawler(platform_, [(category_, None, model_)])[0]:
        print(row)
