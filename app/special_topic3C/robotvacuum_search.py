import urllib.request as req
import urllib.error
import urllib.parse
import http.cookiejar
import ssl
import re
import time
import csv
import datetime
from bs4 import BeautifulSoup

MAX_ITEMS = 20
OUTPUT_FILE = "data/tk3c_robotvacuum_top20.csv"
CATEGORY = "掃地機器人"
SEARCH_KEYWORD = "掃地機器人"

EXCLUDE_KEYWORDS = ["濾網", "邊刷", "主刷", "滾刷", "組件", "拖布", "集塵袋", "集塵盒", "電池", "充電座", "清潔劑", "清潔液", "消耗品", "配件包", "抹布", "尘勺", "耗材", "模塊", "模組", "專用"]

REQUIRE_SIZE_IN_NAME = False
SIZE_PATTERN = re.compile(r"$^")  # 不會用到，保留變數避免程式其他地方參照出錯

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.tk3c.com/",
}

cookie_jar = http.cookiejar.CookieJar()
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
opener = req.build_opener(
    req.HTTPCookieProcessor(cookie_jar),
    req.HTTPSHandler(context=ctx)
)


def fetch_url(url):
    """發送請求，回傳解碼後的 HTML 文字，失敗回傳 None"""
    url = urllib.parse.quote(url, safe=":/?&=@")
    request = req.Request(url, headers=HEADERS)
    try:
        resp = opener.open(request)
        return resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        print(f"⚠️ 請求失敗，狀態碼：{e.code}，網址：{url}")
        return None
    except Exception as e:
        print(f"⚠️ 請求發生錯誤：{e}，網址：{url}")
        return None


def is_accessory(name):
    """判斷商品名稱是否為配件（該排除）"""
    for kw in EXCLUDE_KEYWORDS:
        if kw in name:
            return True
    if REQUIRE_SIZE_IN_NAME and not SIZE_PATTERN.search(name):
        return True
    return False


def normalize_link(link):
    """把連結標準化，方便比對是否重複"""
    if not link:
        return None
    match = re.search(r"product/(\d+)", link)
    return match.group(1) if match else link


# 常見品牌清單，用於比對商品名稱中是否包含已知品牌（無視位置與前綴文字），
# 處理像「夜間偷殺BenQ」這種行銷詞黏著品牌名、前面規則都抓不到的情況
KNOWN_BRANDS = [
    "BenQ", "SONY", "索尼", "SAMSUNG", "三星", "LG", "Panasonic", "國際牌",
    "SHARP", "夏普", "TOSHIBA", "Toshiba", "東芝", "PHILIPS", "飛利浦",
    "CHIMEI", "奇美", "SAMPO", "聲寶", "TCL", "JVC", "HERAN", "禾聯",
    "SANLUX", "台灣三洋", "SANYO", "三洋", "HITACHI", "日立", "AOC",
    "Roborock", "石頭", "Xiaomi", "小米", "DJI", "eufy", "Dyson",
    "Electrolux", "伊萊克斯", "TECO", "東元", "SONGEN", "松井",
    "Tefal", "特福", "PRINCESS", "Giaretti", "大家源", "Oster",
]


# 網站有時會在商品名稱最前面加上限時促銷字樣（例如「只殺今天」「夜間偷殺」），
# 這些字會直接黏在廠牌前面，若不先剝除，會被誤判成廠牌的一部分
PROMO_PREFIXES = ["只殺今天", "夜間偷殺", "限時搶購", "限量搶購", "只殺一天"]


def strip_promo_prefix(name):
    """剝除商品名稱開頭黏著的行銷詞，避免污染廠牌判斷"""
    stripped = True
    while stripped:
        stripped = False
        for prefix in PROMO_PREFIXES:
            if name.startswith(prefix):
                name = name[len(prefix):]
                stripped = True
    return name


def extract_brand(name):
    """從商品名稱裡拆解出廠牌"""
    name = strip_promo_prefix(name)

    bracket_match = re.match(r"^【([^】]+)】", name)
    if bracket_match:
        return bracket_match.group(1).strip()

    # 格式二：中文開頭 + 英文字（中間可能有空格也可能沒有，例如「聲寶SAMPO」或「國際牌 Panasonic」）
    match = re.match(r"^([\u4e00-\u9fa5]+)\s*([A-Za-z][A-Za-z0-9]*)", name)
    if match:
        return f"{match.group(1)}{match.group(2)}"

    match = re.match(r"^([A-Za-z][A-Za-z0-9]*)", name)
    if match:
        return match.group(1)

    # 格式四：中文開頭 + 數字（中間可能有空格也可能沒有，例如「大家源5L」或「台灣三洋 129公升」）
    match = re.match(r"^([\u4e00-\u9fa5]+?)\s*\d", name)
    if match:
        return match.group(1)

    # 前面規則都抓不到時，改用已知品牌清單，直接在名稱中搜尋是否包含這些品牌關鍵字
    for brand in KNOWN_BRANDS:
        if brand in name:
            return brand

    return ""


def parse_price(price_text):
    """把「89折$62910」這種格式，拆解成折扣和售價兩個欄位"""
    if not price_text or price_text == "N/A":
        return "", ""

    discount_match = re.search(r"(\d+折)", price_text)
    discount = discount_match.group(1) if discount_match else ""

    price_match = re.search(r"\$\s*([\d,]+)", price_text)
    price = "$" + price_match.group(1) if price_match else ""

    return discount, price


def search_top_ranking(keyword):
    """從排行榜輪播區塊，抓取 Top1~TopN 的商品"""
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://www.tk3c.com/search.aspx?q={encoded_keyword}&ec=idx-search"
    print(f"正在請求搜尋頁面：{url}")

    content = fetch_url(url)
    if not content:
        return [], None

    soup = BeautifulSoup(content, "html.parser")

    slider = soup.find(class_=re.compile(r"^productSlider"))
    if not slider:
        print("⚠️ 找不到排行榜區塊")
        return [], url

    topbox_list = slider.find_all(class_="topBox")
    print(f"排行榜區塊找到 {len(topbox_list)} 筆有排名的商品")

    results = []
    for topbox in topbox_list:
        item_container = topbox.parent

        rank_text = topbox.get_text(strip=True)
        rank = int(rank_text) if rank_text.isdigit() else None

        name_el = item_container.find(class_="proName")
        name = name_el.get_text(strip=True) if name_el else "N/A"

        price_el = item_container.find(class_="price")
        price = price_el.get_text(strip=True) if price_el else "N/A"

        link_el = item_container.find_parent("a")
        link = link_el.get("href") if link_el else None
        if link:
            link = urllib.parse.urljoin(url, link)

        results.append({
            "rank": rank,
            "name": name,
            "price": price,
            "link": link
        })

    results.sort(key=lambda x: x["rank"])
    return results, url


def get_more_products(base_url_no_page, existing_links, need_count, max_pages=5):
    """
    從一般搜尋結果列表中，必要時自動翻頁，抓取不重複的商品，補齊到需要的數量
    """
    extra_results = []
    page = 1

    while len(extra_results) < need_count and page <= max_pages:
        page_url = base_url_no_page if page == 1 else f"{base_url_no_page}&p={page}"
        print(f"\n正在抓取第 {page} 頁補齊用商品：{page_url}")

        content = fetch_url(page_url)
        if not content:
            print(f"第 {page} 頁請求失敗，停止翻頁")
            break

        soup = BeautifulSoup(content, "html.parser")
        items = soup.find_all(class_=re.compile(r"^prod_item"))
        print(f"第 {page} 頁找到 {len(items)} 個商品卡片")

        if len(items) == 0:
            print(f"第 {page} 頁沒有商品了，停止翻頁")
            break

        found_new_on_this_page = 0

        for item in items:
            if len(extra_results) >= need_count:
                break

            name_el = item.find("a")
            name = "N/A"
            if name_el:
                name = name_el.get("title", "").strip()
                if not name:
                    img_el = name_el.find("img")
                    if img_el:
                        name = img_el.get("alt", "").strip()
                if not name:
                    name = name_el.get_text(strip=True)

            if name == "N/A" or not name:
                continue

            link = name_el.get("href") if name_el else None
            if link:
                link = urllib.parse.urljoin(page_url, link)
            normalized = normalize_link(link)

            if normalized in existing_links:
                continue

            if is_accessory(name):
                print(f"  （排除配件：{name}）")
                continue

            price_el = item.find(class_=re.compile(r"price", re.I))
            price = price_el.get_text(strip=True) if price_el else "N/A"

            extra_results.append({
                "name": name,
                "price": price,
                "link": link
            })
            existing_links.add(normalized)
            found_new_on_this_page += 1

        print(f"第 {page} 頁新增了 {found_new_on_this_page} 筆商品，目前累計補齊 {len(extra_results)} 筆")

        if found_new_on_this_page == 0:
            print(f"第 {page} 頁沒有新增任何商品，可能已經到底，停止翻頁")
            break

        page += 1

    print(f"\n最終補齊了 {len(extra_results)} 筆不重複的商品")
    return extra_results


def fetch_product_details(link):
    """進到商品詳情頁，抓取規格清單、商品編號、型號、原價"""
    result = {"specs": [], "product_code": "", "model": "", "original_price": ""}

    if not link:
        return result

    content = fetch_url(link)
    if not content:
        return result

    soup = BeautifulSoup(content, "html.parser")

    spec_list = soup.find("ul", {"data-testid": "product-func-list"})
    if spec_list:
        result["specs"] = [li.get_text(strip=True) for li in spec_list.find_all("li")]

    page_text = soup.get_text()

    code_match = re.search(r"貨號[：:]\s*([A-Za-z0-9]+)", page_text)
    if code_match:
        result["product_code"] = code_match.group(1)

    model_match = re.search(r"產品型號[：:]\s*([A-Za-z0-9\-]+(?:[\(（][^\)）]*[\)）])?)", page_text)
    if model_match:
        result["model"] = model_match.group(1)

    orig_price_match = re.search(r"會員價[^\d]{0,10}(\d{1,3}(?:,\d{3})*)", page_text)
    if orig_price_match:
        result["original_price"] = "$" + orig_price_match.group(1)

    return result


def enrich_with_details(products, category):
    """整合每筆商品的完整資料，包含拆解廠牌、拆解折扣售價、抓取規格"""
    enriched = []
    today = datetime.date.today().strftime("%Y-%m-%d")

    for i, p in enumerate(products, 1):
        print(f"\n[{i}/{len(products)}] 正在抓取詳細資料：{p['name']}（排名：{p['rank']}）")
        details = fetch_product_details(p["link"])

        specs_text = " ｜ ".join(details["specs"]) if details["specs"] else ""
        clean_name = strip_promo_prefix(p["name"])
        brand = extract_brand(clean_name)
        discount, price = parse_price(p["price"])

        row = {
            "抓取日期": today,
            "分類": category,
            "排名": p["rank"],
            "商品編號": details["product_code"],
            "廠牌": brand,
            "型號": details["model"],
            "商品名稱": clean_name,
            "折扣": discount,
            "售價": price,
            "原價": details["original_price"],
            "商品詳細": specs_text,
            "連結": p["link"],
        }

        enriched.append(row)
        time.sleep(1.5)

    return enriched


def save_to_csv(data, filename):
    if not data:
        print("沒有資料可儲存")
        return

    fieldnames = ["抓取日期", "分類", "排名", "商品編號", "廠牌", "型號", "商品名稱", "折扣", "售價", "原價", "商品詳細", "連結"]

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    print(f"\n已儲存 {len(data)} 筆資料到 {filename}")


def run_robotvacuum_crawler():
    """執行掃地機器人爬蟲，回傳整理好的商品資料 list"""
    top_products, base_url = search_top_ranking(SEARCH_KEYWORD)
    print(f"\n===== 官網排名商品共 {len(top_products)} 筆 =====")

    existing_links = {normalize_link(p["link"]) for p in top_products}

    need_count = MAX_ITEMS - len(top_products)
    if need_count > 0 and base_url:
        extra_products = get_more_products(base_url, existing_links, need_count)
        next_rank = len(top_products) + 1
        for p in extra_products:
            p["rank"] = next_rank
            next_rank += 1
    else:
        extra_products = []

    all_products = top_products + extra_products
    print(f"\n===== 共湊到 {len(all_products)} 筆商品，開始抓取各商品詳細資料 =====")

    products_with_details = enrich_with_details(all_products, CATEGORY)

    return products_with_details


if __name__ == "__main__":
    data = run_robotvacuum_crawler()
    save_to_csv(data, OUTPUT_FILE)