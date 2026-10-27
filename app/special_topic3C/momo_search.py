"""
momo 購物網爬蟲（氣炸鍋）

momo 的搜尋頁是 Next.js 產生的，商品資料以 JSON 字串嵌在 HTML 裡（goodsInfoList），
欄位和組員 momo 爬蟲用的 getCategoryGoodsV3 API 相同（SALE_PRICE、rating、ratingTimes…）。

排名的定義：依「銷量」排序（searchType=6），只取 momo「氣炸鍋」分類（cateCode），
去掉廣告商品與配件後，依序取前 20 筆
"""
import json
import re
import sys
import time
import datetime
import urllib.request as req
import urllib.parse
import urllib.error

from app.special_topic3C import airfryer_search
from app.special_topic3C.pchome_search import calc_discount, extract_model

PLATFORM = "momo"
MAX_ITEMS = 20
MAX_PAGES = 5  # 每頁約 30 筆

SEARCH_URL = "https://www.momoshop.com.tw/search/{}"
PRODUCT_URL = "https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code={}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://www.momoshop.com.tw/",
}

# cate_code：momo 搜尋結果左側的分類代碼，只保留這個分類的商品
# require_keyword：商品名稱一定要有的字
# filter_module：沿用燦坤爬蟲的配件過濾規則，各平台標準一致
CATEGORIES = {
    "氣炸鍋": {
        "keyword": "氣炸鍋",
        "cate_code": "1000300051",
        "require_keyword": "氣炸",  # 分類裡也有一般油炸鍋
        "filter_module": airfryer_search,
    },
}


def fetch_text(url, retries=3):
    """發送請求，回傳 HTML 文字；失敗會隔幾秒重試，全部失敗回傳 None"""
    request = req.Request(url, headers=HEADERS)
    for attempt in range(1, retries + 1):
        try:
            with req.urlopen(request, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            print(f"⚠️ 請求失敗，狀態碼：{e.code}，網址：{url}（第 {attempt} 次）")
        except Exception as e:
            print(f"⚠️ 請求發生錯誤：{e}，網址：{url}（第 {attempt} 次）")
        if attempt < retries:
            time.sleep(3 * attempt)
    return None


def search_page(keyword, cate_code, page):
    """抓取一頁依銷量排序的搜尋結果，回傳商品 list；請求失敗回傳 None"""
    params = urllib.parse.urlencode({"searchType": 6, "cateCode": cate_code, "cateLevel": 2, "curPage": page})
    url = f"{SEARCH_URL.format(urllib.parse.quote(keyword))}?{params}"
    print(f"正在請求 momo 第 {page} 頁：{url}")
    html = fetch_text(url)
    if html is None:
        return None

    key = '\\"goodsInfoList\\":'
    start = html.find(key)
    if start == -1:
        print("⚠️ 頁面裡找不到商品資料（goodsInfoList）")
        return []
    # JSON 被包在 JS 字串裡，先還原 \" 與 \\ 才能解析
    text = html[start + len(key):].replace('\\"', '"').replace("\\\\", "\\")
    goods, _ = json.JSONDecoder().raw_decode(text)
    return goods


def parse_money(text):
    """把 "$$5,990" 轉成 5990，抓不到回傳 None"""
    digits = re.sub(r"[^\d]", "", str(text or ""))
    return int(digits) if digits else None


def parse_model(name):
    """先用組員的規則（最後一組括號、/ 前面），不像型號時再用 PChome 的型號規則從名稱找"""
    parts = re.findall(r"[(（]([^()（）]+)[)）]", name)
    if parts:
        # 型號後面可能直接黏著中文說明，例如 GT-MGA01氣炸10種菜單
        match = re.match(r"[A-Za-z0-9\-]+", parts[-1].split("/")[0].strip())
        model = match.group() if match else ""
        if re.search(r"[A-Za-z]", model) and re.search(r"\d", model):
            return model
    return extract_model(name)


def is_excluded(goods, config):
    """廣告商品或配件不列入排名"""
    name = goods.get("goodsName", "")
    if goods.get("isAdGoods") or config["require_keyword"] not in name:
        return True
    return config["filter_module"].is_accessory(name)


def to_row(goods, rank, category, filter_module, today):
    """把 momo 的商品轉成跟其他平台一樣的欄位格式，才能共用 save_products_to_db"""
    clean_name = filter_module.strip_promo_prefix(goods["goodsName"].strip())
    price = parse_money(goods.get("SALE_PRICE"))  # 通常是數字，偶爾是 "$$1,468"
    original_price = parse_money(goods.get("goodsPriceOri"))
    rating = goods.get("rating")
    return {
        "平台": PLATFORM,
        "抓取日期": today,
        "分類": category,
        "排名": rank,
        "商品編號": goods["goodsCode"],
        "廠牌": filter_module.extract_brand(clean_name),  # 名稱開頭【】裡的文字，和組員的規則相同
        "型號": parse_model(clean_name),
        "商品名稱": clean_name,
        "折扣": calc_discount(price, original_price),
        "售價": f"${price}" if price else "",
        "原價": f"${original_price}" if original_price else "",
        "評價": float(rating) if rating else None,  # 沒人評價過的商品為空字串
        "評價數": parse_money(goods.get("ratingTimes")),  # "(3,003)" → 3003
        "商品詳細": (goods.get("goodsSubName") or "").strip(),
        "連結": PRODUCT_URL.format(goods["goodsCode"]),
    }


def run_momo_crawler(category):
    """執行指定分類的 momo 爬蟲，回傳整理好的商品資料 list"""
    config = CATEGORIES[category]
    today = datetime.date.today().strftime("%Y-%m-%d")
    results = []
    seen_codes = set()

    for page in range(1, MAX_PAGES + 1):
        goods_list = search_page(config["keyword"], config["cate_code"], page)
        if goods_list is None:
            print(f"第 {page} 頁請求失敗，停止翻頁")
            break
        if not goods_list:
            print(f"第 {page} 頁沒有商品了，停止翻頁")
            break

        added = 0
        for goods in goods_list:
            if goods["goodsCode"] in seen_codes:
                continue
            seen_codes.add(goods["goodsCode"])
            if is_excluded(goods, config):
                continue
            results.append(to_row(goods, len(results) + 1, category, config["filter_module"], today))
            added += 1
            if len(results) >= MAX_ITEMS:
                break

        print(f"第 {page} 頁新增 {added} 筆，目前累計 {len(results)} 筆")
        if len(results) >= MAX_ITEMS:
            break
        time.sleep(1.5)

    print(f"\n===== momo {category}共抓到 {len(results)} 筆 =====")
    return results


if __name__ == "__main__":
    category = sys.argv[1] if len(sys.argv) > 1 else "氣炸鍋"
    for row in run_momo_crawler(category):
        print(row["排名"], row["廠牌"], row["型號"], row["售價"], row["折扣"], row["評價"], row["評價數"], row["商品名稱"][:40])
