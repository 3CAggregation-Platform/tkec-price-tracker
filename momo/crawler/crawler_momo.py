import json
import re
import time
import urllib.request as req
from datetime import datetime

import pandas as pd

URL = "https://www.momoshop.com.tw/api/moecapp/getCategoryGoodsV3"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "Referer": "https://www.momoshop.com.tw/categories/2900800000?sortType=6&has3P=y",
    "Origin": "https://www.momoshop.com.tw",
    "Content-Type": "application/json",
}

CATEGORIES = {
    "洗衣機": "2900800000",
    "冰箱": "2919100000",
    "電視": "2900900000",
    "掃地機器人": "2902800000",
}


def build_payload(cate_code: str) -> dict:
    """組出 momo API 要的 payload，只有 cateCode 會變"""
    return {
        "host": "momoshop",
        "data": {
            "curPage": "1",
            "cateCode": cate_code,
            "searchType": "",
            "isSpecialSortType": False,
            "cateLevel": "1",
            "salesSort": "",
            "custNo": "",
            "imgType": "webp",
            "sortType": "6",
            "priceS": "",
            "priceE": "",
            "commentRate": "",
            "brandCode": [],
            "brandName": [],
            "indexInfoList": [],
            "brandSeriesList": [],
            "ecTagNos": [],
            "first": "N",
            "freeze": "N",
            "prefere": "N",
            "NAM": "N",
            "cod": "N",
            "superstorePay": "N",
            "moCoinFeedback": "N",
            "superstoreFree": "N",
            "cp": "N",
            "video": "N",
            "stockYN": "N",
            "tvshop": "N",
            "cycle": "N",
            "cateType": "",
            "has3P": "Y",
            "discount": "N",
            "superstore": "N",
            "specialSortType": "",
            "specialGoodsType": "",
            "tempSpecialSortType": "",
            "dispCnt": "35",
            "fast58": "N",
            "moExpressYN": "N",
            "vendorSYN": "N",
            "crossBorderYN": "N",
        },
    }


def get_brand(name: str) -> str:
    """從【】裡抓廠牌"""
    m = re.search(r"【(.*?)】", name)
    return m.group(1) if m else ""


def get_model(name: str) -> str:
    """從最後一組 () 裡抓型號"""
    parts = re.findall(r"\(([^()]+)\)", name)
    if not parts:
        return ""
    return parts[-1].split("/")[0]


def fetch_goods(cate_code: str) -> list:
    """打 momo API，回傳商品清單（原始 JSON）"""
    body = json.dumps(build_payload(cate_code)).encode("utf-8")
    request = req.Request(URL, data=body, headers=HEADERS)
    response = req.urlopen(request)
    result = json.loads(response.read())
    return result["rtnGoodsData"]["goodsInfoList"]


def parse_goods(goods: list, category_name: str) -> pd.DataFrame:
    """把原始 JSON 整理成乾淨的表格"""
    today = datetime.now().strftime("%Y-%m-%d")
    rows = []
    for g in goods:
        name = g["goodsName"]
        sub = g.get("goodsSubName") or ""
        sales = g.get("totalSalesInfo") or {}

        rows.append(
            {
                "抓取日期": today,
                "分類": category_name,
                "商品編號": g["goodsCode"],
                "廠牌": get_brand(name),
                "型號": get_model(name),
                "商品名稱": name,
                "售價": g.get("SALE_PRICE"),
                "原價": g.get("goodsPriceOri"),
                "銷量": sales.get("text", ""),
                "評分": g.get("rating"),
                "評價數": g.get("ratingTimes"),
                "庫存": g.get("goodsStock"),
                "促銷文案": sub,
                "有政府補助": "補助" in sub,
            }
        )
    return pd.DataFrame(rows)


def crawler_momo(category_name: str) -> pd.DataFrame:
    """抓一個分類 —— 這就是未來的『一張任務單』"""
    cate_code = CATEGORIES[category_name]
    goods = fetch_goods(cate_code)
    df = parse_goods(goods, category_name)
    print(f"{category_name} → {len(df)} 筆")
    return df


if __name__ == "__main__":
    df = crawler_momo("洗衣機")
    print(df.head())