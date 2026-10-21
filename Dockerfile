FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# 先只複製 requirements.txt，讓 Docker layer cache 生效
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 預設指令，實際跑什麼由 docker-compose.yml 的 command 覆蓋
CMD ["celery", "-A", "app.celery_app", "worker", "--loglevel=info"]