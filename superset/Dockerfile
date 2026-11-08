# Superset 官方 image 沒有 MySQL driver，加裝 pymysql 才連得到 tk3c_mysql
FROM apache/superset:5.0.0

USER root
RUN uv pip install --python /app/.venv/bin/python --no-cache pymysql==1.1.1
COPY superset_config.py /app/pythonpath/superset_config.py
USER superset
