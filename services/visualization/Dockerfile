FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SERVICE=visualization
COPY common/requirements.txt common/requirements.txt
RUN pip install --no-cache-dir -r common/requirements.txt
COPY common common
COPY services/visualization services/visualization
CMD ["python", "-m", "common.run", "visualization"]
