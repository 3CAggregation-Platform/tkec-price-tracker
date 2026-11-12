import glob
import os
import re

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine

from crawler.config import (
    MYSQL_ACCOUNT,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
)

TABLE = "momo_goods_daily"
SAVE_DIR = "data"


def get_engine():
    address = (
        f"mysql+pymysql://{MYSQL_ACCOUNT}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/mydb?charset=utf8mb4"
    )
    return create_engine(address)


def to_int(value):
    """把 '$12,900'、'1,234 人評價' 這種字串挖出數字"""
    if pd.isna(value):
        return None
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def clean(df):
    df = df.copy()
    df["抓取日期"] = pd.to_datetime(df["抓取日期"]).dt.date
    df["商品編號"] = df["商品編號"].astype(str)  # 有 TP000… 英數混合，不能轉數字
    for col in ["售價", "原價", "評價數", "庫存"]:
        if col in df.columns:
            df[col] = df[col].map(to_int)
    if "評分" in df.columns:
        df["評分"] = pd.to_numeric(df["評分"], errors="coerce")
    if "銷量" in df.columns:
        df["銷量下限"] = df["銷量"].map(to_int)
    if "有政府補助" in df.columns:
        df["有政府補助"] = df["有政府補助"].astype(bool)
    return df


if __name__ == "__main__":
    files = sorted(glob.glob(os.path.join(SAVE_DIR, "*.csv")))
    logger.info(f"找到 {len(files)} 個 CSV")

    df = clean(pd.concat([pd.read_csv(f) for f in files], ignore_index=True))
    logger.info(f"共 {len(df)} 筆，{df['抓取日期'].min()} ~ {df['抓取日期'].max()}")

    df.to_sql(TABLE, con=get_engine(), if_exists="replace", index=False)
    logger.info(f"upload success：{TABLE}")