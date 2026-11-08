FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SERVICE=ml
COPY common/requirements.txt common/requirements.txt
COPY services/ml/requirements.txt services/ml/requirements.txt
RUN pip install --no-cache-dir -r services/ml/requirements.txt
COPY common common
COPY services/ml services/ml
CMD ["python", "-m", "common.run", "ml"]
