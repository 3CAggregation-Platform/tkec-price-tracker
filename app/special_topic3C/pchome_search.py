"""
PChome 24h 爬蟲（冰箱、電視、氣炸鍋、掃地機器人）

PChome 的搜尋頁是用 JavaScript 載入商品，直接抓 HTML 拿不到資料，
所以改打網頁背後的搜尋 API，回傳的就是 JSON。

排名的定義：依「銷量」排序（sort=sale/dc），篩掉配件後，依序取前 20 筆
"""
import json
import re
import sys
import time
import datetime
import urllib.request as req
import urllib.parse
import urllib.error

from app.special_topic3C import fridge_search, tv_search, airfryer_search, robotvacuum_search

PLATFORM = "pchome"
MAX_ITEMS = 20
MAX_PAGES = 10  # 電視依銷量排序時前幾頁都是電視架，大約要翻到第 6、7 頁才湊得滿
PAGE_SIZE = 40

SEARCH_API = "https://ecshweb.pchome.com.tw/search/v4.3/all/results"
PRODUCT_URL = "https://24h.pchome.com.tw/prod/{}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://24h.pchome.com.tw/",
}

# cate_id：PChome 24h 的館別代碼（商品編號前 4 碼），用來縮小搜尋範圍
# pcate_prefix：商品分類代碼（PCateId）的前綴，用來排除同一館裡的周邊商品
#   例如電視館（DPAD）裡的電視是 109007006，電視架是 109007007
# filter_module：沿用燦坤爬蟲的配件過濾規則（EXCLUDE_KEYWORDS、SIZE_PATTERN），兩個平台標準一致
# extra_exclude：PChome 才有的雜訊，燦坤沒有這類商品
CATEGORIES = {
    "冰箱": {
        "keyword": "冰箱",
        "cate_id": "DPAC",
        "pcate_prefix": "109007001001",  # 家用冰箱；109007001002 是客房小冰箱
        "filter_module": fridge_search,
        "extra_exclude": ["車載", "車用", "車家", "露營", "行動冰箱", "保冰", "冷暖", "12V", "12v", "冷藏櫃", "保鮮櫃"],
    },
    "電視": {
        "keyword": "電視",
        "cate_id": "DPAD",
        "pcate_prefix": "109007006",
        "filter_module": tv_search,
        "extra_exclude": ["電子白板", "互動", "觸控", "閨蜜機", "可携式", "可攜式", "數位電視"],  # 商用顯示器、攜帶式小螢幕
    },
    "氣炸鍋": {
        "keyword": "氣炸鍋",
        "cate_id": "DMAG",
        "pcate_prefix": "109005009",
        "filter_module": airfryer_search,
        "extra_exclude": [],
    },
    "掃地機器人": {
        "keyword": "掃地機器人",
        "cate_id": "DMBL",
        "pcate_prefix": "109008001",  # 主機；109008002 是耗材配件
        "filter_module": robotvacuum_search,
        "extra_exclude": [],
    },
}

# 型號通常是英數混合、可能帶 - 的字串，例如 HRTN6443S、NF-HC100、SR-C09
MODEL_PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{1,6}[-]?[A-Za-z0-9]*\d[A-Za-z0-9\-]*(?:\([A-Za-z0-9]+\))?)(?![A-Za-z0-9])")


def fetch_json(url, retries=3):
    """發送請求，回傳解析後的 JSON；連線偶爾會被中斷（例如 SSL EOF），失敗會隔幾秒重試，全部失敗回傳 None"""
    request = req.Request(url, headers=HEADERS)
    for attempt in range(1, retries + 1):
        try:
            with req.urlopen(request, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"⚠️ 請求失敗，狀態碼：{e.code}，網址：{url}（第 {attempt} 次）")
        except Exception as e:
            print(f"⚠️ 請求發生錯誤：{e}，網址：{url}（第 {attempt} 次）")
        if attempt < retries:
            time.sleep(3 * attempt)
    return None


def search_page(keyword, cate_id, page):
    """抓取一頁依銷量排序的搜尋結果"""
    params = urllib.parse.urlencode({
        "q": keyword,
        "cateid": cate_id,
        "page": page,
        "pageCount": PAGE_SIZE,
        "sort": "sale/dc",
    })
    url = f"{SEARCH_API}?{params}"
    print(f"正在請求 PChome 第 {page} 頁：{url}")
    data = fetch_json(url)
    if data is None:
        return None
    return data.get("Prods") or []


def is_excluded(prod, config):
    """判斷是否為配件或不屬於這個分類的商品"""
    name = prod.get("Name", "")
    pcate_ids = prod.get("PCateId") or []
    if not any(pc.startswith(config["pcate_prefix"]) for pc in pcate_ids):
        return True
    if any(kw in name for kw in config["extra_exclude"]):
        return True
    return config["filter_module"].is_accessory(name)


def extract_model(name):
    """從商品名稱裡找出型號（PChome 搜尋 API 沒有獨立的型號欄位）"""
    candidates = [m for m in MODEL_PATTERN.findall(name) if re.search(r"[A-Za-z]", m) and len(m) >= 4]
    # 容量、尺寸這類字串不是型號，例如 4.5L、65吋前面的 4K、2000W
    candidates = [m for m in candidates if not re.fullmatch(r"\d+(\.\d+)?[A-Za-z]{1,2}", m) and not re.fullmatch(r"[A-Za-z]{1,3}\d{1,2}", m)]
    return max(candidates, key=len) if candidates else ""


def calc_discount(price, original_price):
    """把售價 / 原價換算成「89折」這種格式，跟燦坤的折扣欄位一致"""
    if not price or not original_price or price >= original_price:
        return ""
    ratio = int(price * 100 / original_price)
    return f"{ratio // 10}折" if ratio % 10 == 0 else f"{ratio}折"


def to_row(prod, rank, category, filter_module, today):
    """把 API 回傳的商品轉成跟燦坤爬蟲一樣的欄位格式，才能共用 save_products_to_db"""
    clean_name = filter_module.strip_promo_prefix(prod["Name"].strip())
    price = prod.get("Price")
    original_price = prod.get("OriginPrice")
    return {
        "平台": PLATFORM,
        "抓取日期": today,
        "分類": category,
        "排名": rank,
        "商品編號": prod["Id"],
        "廠牌": prod.get("Brand") or filter_module.extract_brand(clean_name),
        "型號": extract_model(clean_name),
        "商品名稱": clean_name,
        "折扣": calc_discount(price, original_price),
        "售價": f"${price}" if price else "",
        "原價": f"${original_price}" if original_price else "",
        "評價": prod.get("ratingValue"),  # 沒人評價過的商品 API 回傳 None
        "評價數": prod.get("reviewCount"),
        "商品詳細": prod.get("Describe", "").strip(),
        "連結": PRODUCT_URL.format(prod["Id"]),
    }


def run_pchome_crawler(category):
    """執行指定分類的 PChome 爬蟲，回傳整理好的商品資料 list"""
    config = CATEGORIES[category]
    today = datetime.date.today().strftime("%Y-%m-%d")
    results = []
    seen_ids = set()

    for page in range(1, MAX_PAGES + 1):
        prods = search_page(config["keyword"], config["cate_id"], page)
        if prods is None:
            print(f"第 {page} 頁請求失敗，停止翻頁")
            break
        if not prods:
            print(f"第 {page} 頁沒有商品了，停止翻頁")
            break

        added = 0
        for prod in prods:
            if prod["Id"] in seen_ids:
                continue
            seen_ids.add(prod["Id"])
            if is_excluded(prod, config):
                continue
            results.append(to_row(prod, len(results) + 1, category, config["filter_module"], today))
            added += 1
            if len(results) >= MAX_ITEMS:
                break

        print(f"第 {page} 頁新增 {added} 筆，目前累計 {len(results)} 筆")
        if len(results) >= MAX_ITEMS:
            break
        time.sleep(1.5)

    print(f"\n===== PChome {category}共抓到 {len(results)} 筆 =====")
    return results


if __name__ == "__main__":
    category = sys.argv[1] if len(sys.argv) > 1 else "冰箱"
    for row in run_pchome_crawler(category):
        print(row["排名"], row["廠牌"], row["型號"], row["售價"], row["折扣"], row["評價"], row["評價數"], row["商品名稱"][:40])
