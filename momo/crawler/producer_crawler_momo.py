from crawler.crawler_momo import CATEGORIES
from crawler.tasks_crawler_momo import crawler_momo_print


def send_tasks():
    for category_name in CATEGORIES:
        crawler_momo_print.s(category_name).apply_async()
        print("已發送:", category_name)


if __name__ == "__main__":
    send_tasks()