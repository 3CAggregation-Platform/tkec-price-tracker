# 參考課程 dataflow 的 gce.with.env.cache.Dockerfile：用老師已裝好 Airflow 2.7.3 的 image 當底，
# 只放入本專題的 DAG，不用重裝套件，build 只要幾秒
FROM linsamtw/tibame_dataflow:0.0.7

# 不使用課程範例的 DAG，改讀本專題的 DAG 資料夾
COPY dags /dataflow/tk3c_dags
ENV AIRFLOW__CORE__DAGS_FOLDER=/dataflow/tk3c_dags
