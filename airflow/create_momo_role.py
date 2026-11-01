"""
建立 Airflow 角色 momo：組員只能看、操作自己的 momo_producer DAG

做法：複製內建 User 角色的權限，但拿掉「所有 DAG」的權限（DAGs、DAG Dependencies），
再由 momo_producer.py 的 access_control 單獨開放 momo_producer 給這個角色。

在 VM 上執行（必須在部署含 access_control 的 DAG 之前，否則 Airflow 會因為找不到角色而無法載入 DAG）：
  docker exec -i $(docker ps -q -f name=tk3c-airflow_webserver) /dataflow/.venv/bin/python - < airflow/create_momo_role.py

重複執行不會出錯，會把權限補齊。
"""
from airflow.www.app import cached_app

ROLE = "momo"
BASE_ROLE = "User"
# 這些是「所有 DAG」的權限，有了就能看到、操作每一個 DAG（包括 tk3c_producer）
EXCLUDED_RESOURCES = {"DAGs", "DAG Dependencies"}

app = cached_app()
with app.app_context():
    sm = app.appbuilder.sm
    base = sm.find_role(BASE_ROLE)
    role = sm.find_role(ROLE) or sm.add_role(ROLE)

    added = 0
    for perm in base.permissions:
        if perm.resource.name in EXCLUDED_RESOURCES:
            continue
        if perm not in role.permissions:
            sm.add_permission_to_role(role, perm)
            added += 1

    # 保險：如果之前不小心給過「所有 DAG」的權限，拿掉
    for perm in list(role.permissions):
        if perm.resource.name in EXCLUDED_RESOURCES:
            sm.remove_permission_from_role(role, perm)

    print(f"角色 {ROLE}：新增 {added} 個權限，共 {len(sm.find_role(ROLE).permissions)} 個")
