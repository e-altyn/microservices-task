import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, Response

from common.api import make_app
from common.config import load_config
from common.schemas import DatasetCreate, DatasetUpdate


def create_app(config=None):
    cfg = config or load_config("storage")
    app = make_app("Storage")

    @contextmanager
    def connect():
        path = Path(cfg["database_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE IF NOT EXISTS datasets (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
            source TEXT NOT NULL, is_synthetic INTEGER NOT NULL,
            created_at TEXT NOT NULL, row_count INTEGER NOT NULL, records TEXT NOT NULL
        )""")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def metadata(row):
        return {key: (bool(row[key]) if key == "is_synthetic" else row[key])
                for key in row.keys() if key != "records"}

    @app.post("/datasets", status_code=201)
    def create(body: DatasetCreate):
        item = {"id": uuid4().hex, **body.model_dump(exclude={"records"}),
                "created_at": datetime.now(timezone.utc).isoformat(), "row_count": len(body.records)}
        with connect() as conn:
            conn.execute("INSERT INTO datasets VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (item["id"], item["name"], item["kind"], item["source"], item["is_synthetic"],
                          item["created_at"], item["row_count"], json.dumps(body.records, allow_nan=False)))
        return item

    @app.get("/datasets")
    def list_datasets():
        with connect() as conn:
            rows = conn.execute("SELECT id,name,kind,source,is_synthetic,created_at,row_count FROM datasets ORDER BY created_at DESC").fetchall()
        return [metadata(row) for row in rows]

    @app.get("/datasets/{dataset_id}")
    def read(dataset_id: str):
        with connect() as conn:
            row = conn.execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Датасет не найден")
        return {**metadata(row), "records": json.loads(row["records"])}

    @app.patch("/datasets/{dataset_id}")
    def update(dataset_id: str, body: DatasetUpdate):
        with connect() as conn:
            result = conn.execute("UPDATE datasets SET name=? WHERE id=?", (body.name, dataset_id))
            if not result.rowcount:
                raise HTTPException(404, "Датасет не найден")
        return read(dataset_id)

    @app.delete("/datasets/{dataset_id}", status_code=204)
    def delete(dataset_id: str):
        with connect() as conn:
            result = conn.execute("DELETE FROM datasets WHERE id=?", (dataset_id,))
            if not result.rowcount:
                raise HTTPException(404, "Датасет не найден")
        return Response(status_code=204)

    return app


app = create_app()
