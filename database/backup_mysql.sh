#!/usr/bin/env bash
# 每日備份 tk3c_mysql：本專題 tk3c_price_tracker、組員 momo 的 mydb、Airflow metadata
# 每個資料庫各存一個 .sql.gz 到 ~/backups，超過 KEEP_DAYS 天的自動刪除
#
# VM 上用 cron 每天 13:00 UTC（台灣 21:00，tk3c 20:00、momo 20:30 都跑完後）執行：
#   0 13 * * * /home/<使用者>/tk3c-price-tracker/database/backup_mysql.sh >> /home/<使用者>/backups/backup.log 2>&1
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
DATABASES="tk3c_price_tracker mydb airflow"

mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d_%H%M)
CONTAINER=$(docker ps -q -f name=tk3c_mysql | head -1)
if [ -z "$CONTAINER" ]; then
  echo "$(date -Is) 找不到 tk3c_mysql 容器，備份失敗" >&2
  exit 1
fi

for DB in $DATABASES; do
  OUT="$BACKUP_DIR/${DB}_${STAMP}.sql.gz"
  # --single-transaction：InnoDB 不鎖表也能取得一致的快照，爬蟲寫入中也能備份
  docker exec "$CONTAINER" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot \
      --single-transaction --routines --triggers --events --default-character-set=utf8mb4 \
      --databases "$1"' sh "$DB" | gzip > "$OUT.tmp"
  mv "$OUT.tmp" "$OUT"
  echo "$(date -Is) $DB → $OUT ($(du -h "$OUT" | cut -f1))"
done

find "$BACKUP_DIR" -name '*.sql.gz' -mtime +"$KEEP_DAYS" -delete
