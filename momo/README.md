# 台灣家電價格爬蟲（momo）

> 從 [bihruwang/ecommerce_crawler](https://github.com/bihruwang/ecommerce_crawler) 搬進本專題，只保留 momo 相關程式與資料。
> momo 自 2026/11/08 起回應 403 擋下程式存取，`data/` 保留到 11/07 的歷史資料，原本的 GitHub Actions 每日排程暫不搬過來。
> 在本目錄執行指令（`cd momo`），image 建置方式不變：`docker build -t bihruwang/momo_crawler:<版本> .`

追蹤 momo 購物網家電類商品的每日價格，用來分析價格浮動幅度與促銷週期。

## 資料來源

momo 購物網 `getCategoryGoodsV3` API，目前抓取四個分類：

| 分類 | cateCode |
|---|---|
| 洗衣機 | 2900800000 |
| 冰箱 | 2919100000 |
| 電視 | 2900900000 |
| 掃地機器人 | 2902800000 |

每個分類單次抓取 35 筆（依銷量排序）。

## 架構

採分散式架構，四個分類可同時爬取：

Producer 發送任務 → RabbitMQ 佇列 → Worker 平行執行爬蟲

- **Broker**：RabbitMQ
- **Task Queue**：Celery
- **監控**：Flower

## 執行方式

啟動 RabbitMQ 與 Flower：

    docker compose -f rabbitmq.yml up -d

啟動 worker：

    uv run celery -A crawler.worker worker --loglevel=info

發送爬蟲任務：

    uv run python crawler/producer_crawler_momo.py

結果會存成 CSV 於 `data/` 資料夾。

監控介面：
- RabbitMQ http://localhost:15672 （worker / worker）
- Flower http://localhost:5555

## 專案結構

    crawler/
    ├── crawler_momo.py              爬蟲主邏輯
    ├── tasks_crawler_momo.py        Celery 任務定義
    └── producer_crawler_momo.py     任務發送

## 擷取欄位

抓取日期、分類、商品編號、廠牌、型號、商品名稱、售價、原價、
銷量、評分、評價數、庫存、促銷文案、有政府補助

## 開發中

- [ ] 資料寫入 MySQL
- [ ] 定時自動排程
- [ ] 擴充其他通路（PChome、家樂福）
- [ ] 價格變動分析

---

專案架構基於 Tibame 分散式爬蟲課程範例（[TibameSam/crawler](https://github.com/TibameSam/crawler)）。