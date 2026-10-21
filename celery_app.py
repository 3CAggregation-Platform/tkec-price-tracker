import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT", "5672")

BROKER_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}//"

app = Celery(
    "tk3c",
    broker=BROKER_URL,
    backend="rpc://",
    include=["tasks"],
)

app.conf.timezone = "Asia/Taipei"
app.conf.enable_utc = False

from celery.schedules import crontab

app.conf.beat_schedule = {
    "crawl-fridge-daily": {
        "task": "crawl_fridge",
        "schedule": crontab(hour=20, minute=0),  # 每天晚上 20:00
    },
    "crawl-tv-daily": {
        "task": "crawl_tv",
        "schedule": crontab(hour=20, minute=10),  # 錯開時間，避免同時打網站
    },
    "crawl-airfryer-daily": {
        "task": "crawl_airfryer",
        "schedule": crontab(hour=20, minute=20),
    },
    "crawl-robotvacuum-daily": {
        "task": "crawl_robotvacuum",
        "schedule": crontab(hour=20, minute=30),
    },
    # PChome 接在燦坤後面，同樣每 10 分鐘一類
    "crawl-pchome-fridge-daily": {
        "task": "crawl_pchome_fridge",
        "schedule": crontab(hour=20, minute=40),
    },
    "crawl-pchome-tv-daily": {
        "task": "crawl_pchome_tv",
        "schedule": crontab(hour=20, minute=50),
    },
    "crawl-pchome-airfryer-daily": {
        "task": "crawl_pchome_airfryer",
        "schedule": crontab(hour=21, minute=0),
    },
    "crawl-pchome-robotvacuum-daily": {
        "task": "crawl_pchome_robotvacuum",
        "schedule": crontab(hour=21, minute=10),
    },
}