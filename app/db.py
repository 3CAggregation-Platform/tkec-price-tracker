import os
import re
import pymysql
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 13306)),  # 對應你 docker-compose 裡的 "13306:3306"
    "user": os.getenv("MYSQL_USER", "tk3c_user"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "charset": "utf8mb4",
}


def get_connection():
    return pymysql.connect(**DB_CONFIG)


def parse_money(text):
    """把 "$62,910" 或 "" 轉成 float，抓不到就回傳 None"""
    if not text:
        return None
    match = re.search(r"[\d,]+", text)
    if not match:
        return None
    return float(match.group().replace(",", ""))


def save_products_to_db(rows):
    """
    把爬蟲回傳的 list[dict]（欄位為中文 key）寫進 products + price_history
    回傳 (success_count, skipped_count)
    """
    conn = get_connection()
    success = 0
    skipped = 0

    try:
        with conn.cursor() as cursor:
            for row in rows:
                product_code = row.get("商品編號")
                if not product_code:
                    print(f"⚠️ 略過（無商品編號）：{row.get('商品名稱')}")
                    skipped += 1
                    continue

                # 1. Upsert products（同一個商品編號在不同平台是不同商品）
                platform = row.get("平台", "tk3c")
                cursor.execute(
                    """
                    INSERT INTO products (platform, product_code, category, brand, model, name, link, specs)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        category = VALUES(category),
                        brand = VALUES(brand),
                        model = VALUES(model),
                        name = VALUES(name),
                        link = VALUES(link),
                        specs = VALUES(specs)
                    """,
                    (
                        platform,
                        product_code,
                        row.get("分類"),
                        row.get("廠牌"),
                        row.get("型號"),
                        row.get("商品名稱"),
                        row.get("連結"),
                        row.get("商品詳細"),
                    ),
                )

                cursor.execute(
                    "SELECT id FROM products WHERE platform = %s AND product_code = %s",
                    (platform, product_code),
                )
                product_id = cursor.fetchone()[0]

                # 2. Upsert price_history
                price = parse_money(row.get("售價"))
                if price is None:
                    print(f"⚠️ 略過價格寫入（無售價）：{row.get('商品名稱')}")
                    skipped += 1
                    continue

                cursor.execute(
                    """
                    INSERT INTO price_history (product_id, crawl_date, `rank`, discount, price, original_price)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        `rank` = VALUES(`rank`),
                        discount = VALUES(discount),
                        price = VALUES(price),
                        original_price = VALUES(original_price)
                    """,
                    (
                        product_id,
                        row.get("抓取日期"),
                        row.get("排名"),
                        row.get("折扣"),
                        price,
                        parse_money(row.get("原價")),
                    ),
                )
                success += 1

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ 寫入資料庫發生錯誤：{e}")
        raise
    finally:
        conn.close()

    return success, skipped

def log_crawl_run(category, item_count, success_count, skipped_count, status, message="", platform="tk3c"):
    """記錄一次爬蟲執行結果，不管資料內容有沒有變動都會寫入一筆"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO crawl_log (platform, category, item_count, success_count, skipped_count, status, message)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (platform, category, item_count, success_count, skipped_count, status, message),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ 寫入 crawl_log 發生錯誤：{e}")
        raise
    finally:
        conn.close()