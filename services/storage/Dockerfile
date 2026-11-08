FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SERVICE=storage
COPY common/requirements.txt common/requirements.txt
RUN pip install --no-cache-dir -r common/requirements.txt
COPY common common
COPY services/storage services/storage
CMD ["python", "-m", "common.run", "storage"]
