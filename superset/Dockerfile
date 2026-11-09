# Superset 官方 image 沒有 MySQL / BigQuery driver：
#   pymysql             → 連 tk3c_mysql（每日比價 dashboard）
#   sqlalchemy-bigquery → 連 BigQuery tk3c_dw 的 DataMart；認證用 VM 的 service account（ADC），image 裡不放金鑰
FROM apache/superset:5.0.0

USER root
RUN uv pip install --python /app/.venv/bin/python --no-cache pymysql==1.1.1 sqlalchemy-bigquery==1.11.0
COPY superset_config.py /app/pythonpath/superset_config.py
USER superset
