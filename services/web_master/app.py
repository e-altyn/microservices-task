import csv
import io

import httpx
from fastapi import HTTPException, Response, UploadFile

from common.api import call, make_app
from common.config import load_config
from common.schemas import (
    FEATURES, CollectRequest, DatasetCreate, DatasetUpdate, ModelCreate,
    PredictDatasetRequest, PredictRequest, TrainRequest,
)


def create_app(config=None):
    cfg = config or load_config("web_master")
    app = make_app("Web Master")

    def storage(path, method="GET", **kwargs):
        return call(cfg["storage_url"], path, method, timeout=cfg["request_timeout"], **kwargs)

    def ml(path, method="GET", **kwargs):
        return call(cfg["ml_url"], path, method, timeout=cfg["request_timeout"], **kwargs)

    @app.get("/api/system")
    def system():
        result = {}
        for name in ("collector", "storage", "ml"):
            try:
                result[name] = call(cfg[f"{name}_url"], "/health", timeout=2)["status"]
            except (httpx.RequestError, HTTPException):
                result[name] = "unavailable"
        return result

    @app.post("/api/datasets/collect", status_code=201)
    def collect(body: CollectRequest):
        batch = call(cfg["collector_url"], f"/batches/{body.batch_number}", timeout=cfg["request_timeout"])
        item = storage("/datasets", "POST", json={
            "name": f"Батч {body.batch_number}", "source": batch["source"],
            "is_synthetic": batch["is_synthetic"], "records": batch["records"],
        })
        return {**item, "batch_number": body.batch_number, "total_batches": batch["total_batches"]}

    @app.get("/api/datasets")
    def list_datasets():
        return storage("/datasets")

    @app.post("/api/datasets", status_code=201)
    def create_dataset(body: DatasetCreate):
        return storage("/datasets", "POST", json=body.model_dump())

    @app.get("/api/datasets/{dataset_id}")
    def get_dataset(dataset_id: str):
        return storage(f"/datasets/{dataset_id}")

    @app.patch("/api/datasets/{dataset_id}")
    def update_dataset(dataset_id: str, body: DatasetUpdate):
        return storage(f"/datasets/{dataset_id}", "PATCH", json=body.model_dump())

    @app.delete("/api/datasets/{dataset_id}", status_code=204)
    def delete_dataset(dataset_id: str):
        # Successful DELETE has an empty body.
        with httpx.Client(timeout=cfg["request_timeout"]) as client:
            response = client.delete(cfg["storage_url"] + f"/datasets/{dataset_id}")
        if response.is_error:
            raise HTTPException(response.status_code, response.json().get("detail", "Ошибка удаления"))
        return Response(status_code=204)

    @app.post("/api/models", status_code=201)
    def create_model(body: ModelCreate):
        return ml("/models", "POST", json=body.model_dump())

    @app.get("/api/models")
    def list_models():
        return ml("/models")

    @app.get("/api/models/{model_id}")
    def summary(model_id: str):
        return ml(f"/models/{model_id}")

    @app.post("/api/models/{model_id}/train")
    def train(model_id: str, body: TrainRequest):
        return ml(f"/models/{model_id}/train", "POST", json=body.model_dump())

    @app.post("/api/models/{model_id}/predict")
    def predict(model_id: str, body: PredictRequest):
        return ml(f"/models/{model_id}/predict", "POST", json=body.model_dump())

    @app.post("/api/models/{model_id}/predict-dataset")
    def predict_dataset(model_id: str, body: PredictDatasetRequest):
        dataset = storage(f"/datasets/{body.dataset_id}")
        if dataset["kind"] != "raw":
            raise HTTPException(422, "Для прогноза выберите сырой батч данных")
        if len(dataset["records"]) > 1000:
            raise HTTPException(422, "Максимум 1000 строк для одного прогноза. Выберите меньший батч.")
        records = [{key: value for key, value in row.items() if key in FEATURES}
                   for row in dataset["records"]]
        request = PredictRequest(records=records)
        result = ml(f"/models/{model_id}/predict", "POST", json=request.model_dump())
        return {**result, "dataset_id": dataset["id"], "dataset_name": dataset["name"]}

    @app.post("/api/models/{model_id}/predict-csv")
    async def predict_csv(model_id: str, file: UploadFile):
        content = await file.read(cfg["max_upload_bytes"] + 1)
        await file.close()
        if len(content) > cfg["max_upload_bytes"]:
            raise HTTPException(413, "CSV слишком большой (максимум 2 МБ)")
        try:
            reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), strict=True)
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise HTTPException(422, "CSV должен содержать уникальные имена колонок")
            rows = []
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise HTTPException(422, "Число полей CSV не соответствует заголовку")
                rows.append(row)
                if len(rows) > 1000:
                    raise HTTPException(422, "Максимум 1000 строк для одного прогноза")
            body = PredictRequest(records=rows)
        except (UnicodeError, csv.Error, ValueError) as exc:
            raise HTTPException(422, "Некорректный CSV. Используйте UTF-8, запятую и минимум одну строку.") from exc
        return ml(f"/models/{model_id}/predict", "POST", json=body.model_dump())

    return app


app = create_app()
