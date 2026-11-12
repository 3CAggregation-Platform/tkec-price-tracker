import os

from crawler.crawler_momo import CATEGORIES
from crawler.crawler_momo import crawler_momo as fetch_momo

SAVE_DIR = "data"

if __name__ == "__main__":
    os.makedirs(SAVE_DIR, exist_ok=True)
    for category_name in CATEGORIES:
        df = fetch_momo(category_name)
        today = df["抓取日期"].iloc[0]
        path = os.path.join(SAVE_DIR, f"{today}_{category_name}.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"{category_name}：{len(df)} 筆 → {path}")
