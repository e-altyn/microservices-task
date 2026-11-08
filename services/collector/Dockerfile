FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SERVICE=collector
COPY common/requirements.txt common/requirements.txt
RUN pip install --no-cache-dir -r common/requirements.txt
COPY common common
COPY services/collector services/collector
CMD ["python", "-m", "common.run", "collector"]
