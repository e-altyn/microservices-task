import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import joblib
from fastapi import HTTPException
from sklearn.metrics import accuracy_score, confusion_matrix, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

from common.api import call, make_app
from common.config import load_config
from common.schemas import FEATURES, ModelCreate, PredictRequest, TrainRequest
from services.ml.modeling import pipeline, prepare

log = logging.getLogger(__name__)


def create_app(config=None):
    cfg = config or load_config("ml")
    app = make_app("ML Service")
    root = Path(cfg["artifact_dir"])
    lock = threading.Lock()

    def path(model_id):
        if not re.fullmatch(r"[0-9a-f]{32}", model_id):
            raise HTTPException(404, "Модель не найдена")
        return root / f"{model_id}.json"

    def save(meta):
        root.mkdir(parents=True, exist_ok=True)
        dest = path(meta["id"])
        temporary = dest.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(meta, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        temporary.replace(dest)

    def read(model_id):
        dest = path(model_id)
        if not dest.exists():
            raise HTTPException(404, "Модель не найдена")
        meta = json.loads(dest.read_text(encoding="utf-8"))
        # A killed synchronous training request cannot resume automatically.
        if meta["status"] == "training" and not lock.locked():
            meta["status"] = "failed"
            meta["error"] = "Обучение прервано перезапуском сервиса. Повторите запрос."
        return meta

    @app.post("/models", status_code=201)
    def create(body: ModelCreate):
        meta = {"id": uuid4().hex, "name": body.name, "algorithm": body.algorithm,
                "status": "created", "created_at": datetime.now(timezone.utc).isoformat(),
                "features": FEATURES, "metrics": None, "class_weight": cfg["class_weight"]}
        save(meta)
        return meta

    @app.get("/models")
    def list_models():
        return sorted([read(p.stem) for p in root.glob("*.json")], key=lambda m: m["created_at"], reverse=True)

    @app.get("/models/{model_id}")
    def summary(model_id: str):
        return read(model_id)

    @app.post("/models/{model_id}/train")
    def train(model_id: str, body: TrainRequest):
        if not lock.acquire(blocking=False):
            raise HTTPException(409, "Сервис уже обучает модель. Дождитесь завершения.")
        meta = None
        started = False
        try:
            meta = read(model_id)
            if meta["status"] == "trained":
                raise HTTPException(409, "Модель уже обучена. Создайте новую модель для другого эксперимента.")
            dataset = call(cfg["storage_url"], f"/datasets/{body.dataset_id}", timeout=cfg["request_timeout"])
            if dataset["kind"] != "raw":
                raise HTTPException(422, "Для обучения выберите сырой датасет")
            data = prepare(dataset["records"], training=True)
            counts = data["target"].value_counts()
            if len(data) < cfg["min_training_rows"] or len(counts) != 2 or counts.min() < 4:
                raise HTTPException(422, f"Нужно минимум {cfg['min_training_rows']} строк и минимум 4 примера каждого класса")
            train_idx, test_idx = train_test_split(data.index, test_size=cfg["test_size"],
                                                   random_state=cfg["random_state"], stratify=data["target"])
            meta.update(status="training", dataset_id=body.dataset_id, error=None)
            save(meta)
            started = True
            model = pipeline(cfg["max_iter"], cfg["random_state"], cfg["class_weight"],
                             algorithm=meta["algorithm"], random_forest=cfg.get("random_forest"))
            model.fit(data.loc[train_idx, FEATURES], data.loc[train_idx, "target"])
            probabilities = model.predict_proba(data.loc[test_idx, FEATURES])[:, 1]
            predicted = (probabilities >= 0.5).astype(int)
            actual = data.loc[test_idx, "target"]
            metrics = {
                "roc_auc": float(roc_auc_score(actual, probabilities)),
                "accuracy": float(accuracy_score(actual, predicted)),
                "precision": float(precision_score(actual, predicted, zero_division=0)),
                "recall": float(recall_score(actual, predicted, zero_division=0)),
                "confusion_matrix": confusion_matrix(actual, predicted, labels=[0, 1]).tolist(),
                "train_rows": len(train_idx), "test_rows": len(test_idx),
                "excluded_rows": len(dataset["records"]) - len(data), "threshold": 0.5,
            }
            snapshot = data.copy()
            snapshot["partition"] = "train"
            snapshot.loc[test_idx, "partition"] = "test"
            # Persist normalized data, not parameters fitted on the test partition.
            records = json.loads(snapshot.to_json(orient="records"))
            processed = call(cfg["storage_url"], "/datasets", "POST", timeout=cfg["request_timeout"], json={
                "name": f"Подготовленные данные: {meta['name']}", "kind": "processed",
                "source": f"dataset:{body.dataset_id}", "is_synthetic": dataset["is_synthetic"], "records": records,
            })
            model_path = root / f"{model_id}.joblib"
            temp_path = model_path.with_suffix(".joblib.tmp")
            joblib.dump(model, temp_path)
            temp_path.replace(model_path)
            meta.update(status="trained", metrics=metrics, processed_dataset_id=processed["id"],
                        is_synthetic=dataset["is_synthetic"], source=dataset["source"],
                        trained_at=datetime.now(timezone.utc).isoformat())
            save(meta)
            return meta
        except Exception as exc:
            if started:
                meta.update(status="failed", error="Не удалось завершить обучение. Можно повторить запрос.")
                save(meta)
            if isinstance(exc, HTTPException):
                raise
            log.exception("Training failed")
            raise HTTPException(500, "Ошибка обучения. Подробности в журнале ML Service.") from exc
        finally:
            lock.release()

    @app.post("/models/{model_id}/predict")
    def predict(model_id: str, body: PredictRequest):
        meta = read(model_id)
        if meta["status"] != "trained":
            raise HTTPException(409, "Модель еще не обучена")
        frame = prepare(body.records)
        model_path = root / f"{model_id}.joblib"
        if not model_path.exists():
            raise HTTPException(503, "Артефакт модели отсутствует. Создайте и обучите новую модель.")
        model = joblib.load(model_path)
        values = model.predict_proba(frame)[:, 1]
        return {"model_id": model_id, "is_synthetic": meta["is_synthetic"], "predictions": [
            {"row": index + 1, "probability": float(value), "prediction": int(value >= 0.5)}
            for index, value in enumerate(values)
        ]}

    return app


app = create_app()
