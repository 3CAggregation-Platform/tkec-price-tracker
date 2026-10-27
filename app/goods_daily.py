"""
goods_daily：和組員 momo 爬蟲（bihruwang/ecommerce_crawler 的 momo_goods_daily）同格式的每日商品表

- 欄位名稱、型態、廠牌與型號寫法都照組員的格式，合併時直接 UNION / INSERT ... SELECT 即可
- 資料來源是 products + price_history，每次爬蟲寫入後由 app/db.py 自動同步當天、當分類的資料
- 組員有、我們抓不到的欄位（銷量、庫存、促銷文案、有政府補助、銷量下限）為 NULL

重建全部歷史資料：

    python -m app.goods_daily
"""
import re

# 組員 momo 資料的廠牌寫法（「英文 中文」），後面是我們這邊可能出現的其他寫法
# 比對時不分大小寫，只要原始廠牌包含任一個別名就換成組員的寫法
BRANDS = [
    ("SAMPO 聲寶", ["SAMPO", "聲寶"]),
    ("SANLUX 台灣三洋", ["SANLUX", "三洋"]),
    ("Roborock 石頭科技", ["Roborock", "石頭"]),
    ("HERAN 禾聯", ["HERAN", "禾聯"]),
    ("Panasonic 國際牌", ["Panasonic", "國際牌"]),
    ("小米", ["Xiaomi", "小米"]),
    ("Kolin 歌林", ["Kolin", "歌林"]),
    ("CHIMEI 奇美", ["CHIMEI", "奇美"]),
    ("LG 樂金", ["LG", "樂金"]),
    ("ECOVACS 科沃斯", ["ECOVACS", "科沃斯"]),
    ("TOSHIBA 東芝", ["TOSHIBA", "東芝"]),
    ("Dreame 追覓科技", ["Dreame", "追覓"]),
    ("Samsung 三星", ["Samsung", "三星"]),
    ("Whirlpool 惠而浦", ["Whirlpool", "惠而浦"]),
    ("TECO 東元", ["TECO", "東元"]),
    ("Philips 飛利浦", ["Philips", "飛利浦"]),
    ("Electrolux 伊萊克斯", ["Electrolux", "伊萊克斯"]),
    ("AmTRAN 瑞軒", ["AmTRAN", "瑞軒"]),
    ("IMARFLEX 伊瑪", ["IMARFLEX", "伊瑪"]),
    ("HITACHI 日立", ["HITACHI", "日立"]),
    ("SKYWORTH 創維", ["SKYWORTH", "創維"]),
    ("Haier 海爾", ["Haier", "海爾"]),
    ("TATUNG 大同", ["TATUNG", "大同"]),
    ("dyson 戴森", ["dyson", "戴森"]),
    # 以下組員目前的資料沒有，照同樣「英文 中文」的規則補上
    ("MITSUBISHI 三菱", ["MITSUBISHI", "三菱"]),
    ("SHARP 夏普", ["SHARP", "夏普"]),
    ("SONY 索尼", ["SONY", "索尼"]),
    ("Tefal 特福", ["Tefal", "特福"]),
    ("ZANWA 晶華", ["ZANWA", "晶華"]),
    ("CANDY 義大利", ["CANDY"]),
    ("CookPower 鍋寶", ["CookPower", "鍋寶"]),
    ("Giaretti 珈樂堤", ["Giaretti", "珈樂堤"]),
    ("SONGEN 松井", ["SONGEN", "松井"]),
    ("BOSCH 博世", ["BOSCH", "博世"]),
    ("SANSUI 山水", ["SANSUI", "山水"]),
]


def normalize_brand(brand):
    """把「聲寶SAMPO」「SAMPO」「新品優惠國際牌Panasonic」等寫法統一成組員的「SAMPO 聲寶」"""
    if not brand:
        return None
    lowered = brand.lower()
    for name, aliases in BRANDS:
        if any(alias.lower() in lowered for alias in aliases):
            return name
    return brand.strip()


def normalize_model(model):
    """去掉括號內的顏色 / 版本（SR-C48GDV(P2) → SR-C48GDV），和組員從商品名稱括號抓出的型號對得上"""
    if not model:
        return None
    model = re.sub(r"[(（][^()（）]*[)）]", "", model)
    return re.sub(r"\s+", "", model).upper() or None


def model_from_name(name):
    """抓不到型號時，用組員的規則：商品名稱最後一組 () 裡、第一個 / 前面的文字"""
    parts = re.findall(r"\(([^()]+)\)", name or "")
    return normalize_model(parts[-1].split("/")[0]) if parts else None


def to_int(value):
    return int(value) if value is not None else None


def sync_goods_daily(cursor, platform, category, crawl_date):
    """把 products + price_history 某平台、分類、日期的資料整理成組員格式，覆蓋寫入 goods_daily"""
    cursor.execute(
        """
        SELECT h.crawl_date, p.category, p.product_code, p.brand, p.model, p.name,
               h.price, h.original_price, h.rating, h.review_count, h.`rank`, p.link
        FROM price_history h
        JOIN products p ON p.id = h.product_id
        WHERE p.platform = %s AND p.category = %s AND h.crawl_date = %s
        """,
        (platform, category, crawl_date),
    )
    rows = [
        (
            platform, crawl_date_, category_, code, normalize_brand(brand),
            normalize_model(model) or model_from_name(name), name,
            to_int(price), to_int(original_price), rating, review_count, rank, link,
        )
        for crawl_date_, category_, code, brand, model, name, price, original_price, rating, review_count, rank, link
        in cursor.fetchall()
    ]

    # 和 price_history 一樣：同一天重跑只保留最後一次
    cursor.execute(
        "DELETE FROM goods_daily WHERE 平台 = %s AND 分類 = %s AND 抓取日期 = %s",
        (platform, category, crawl_date),
    )
    cursor.executemany(
        """
        INSERT INTO goods_daily (平台, 抓取日期, 分類, 商品編號, 廠牌, 型號, 商品名稱,
                                 售價, 原價, 評分, 評價數, 排名, 連結)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )
    return len(rows)


def main():
    from app.db import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT p.platform, p.category, h.crawl_date
                FROM price_history h JOIN products p ON p.id = h.product_id
                ORDER BY h.crawl_date
                """
            )
            total = 0
            for platform, category, crawl_date in cursor.fetchall():
                total += sync_goods_daily(cursor, platform, category, crawl_date)
        conn.commit()
        print(f"✅ goods_daily 重建完成，共 {total} 筆")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
