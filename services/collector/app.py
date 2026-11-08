import csv
import logging
import math
from pathlib import Path

from fastapi import HTTPException

from common.api import make_app
from common.config import load_config


def create_app(config=None):
    cfg = config or load_config("collector")
    app = make_app("Collector")

    @app.get("/batches/{number}")
    def batch(number: int):
        if number < 1:
            raise HTTPException(422, "Номер батча должен быть положительным")
        path = Path(cfg["source_path"])
        if not path.is_file():
            raise HTTPException(503, "Источник данных отсутствует. Подготовьте CSV по инструкции README.")
        try:
            with path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames or "loan_status" not in reader.fieldnames:
                    raise HTTPException(422, "В источнике нет колонки loan_status")
                rows = []
                for index, row in enumerate(reader):
                    if index >= cfg["max_source_rows"]:
                        break
                    rows.append(row)
        except (OSError, UnicodeError, csv.Error) as exc:
            raise HTTPException(422, "Не удалось прочитать CSV источника") from exc
        start = (number - 1) * cfg["batch_size"]
        records = rows[start:start + cfg["batch_size"]]
        if not records:
            raise HTTPException(404, "Батч отсутствует: источник закончился")
        log_path = Path(cfg["log_path"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # Logging handles simultaneous requests within the process.
        logger = logging.getLogger(f"collector.{log_path.resolve()}")
        if not logger.handlers:
            handler = logging.FileHandler(log_path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        logger.info("batch=%s rows=%s source=%s", number, len(records), cfg["source_name"])
        return {
            "batch_number": number, "total_batches": math.ceil(len(rows) / cfg["batch_size"]),
            "source": cfg["source_name"], "is_synthetic": cfg["is_synthetic"], "records": records,
        }

    return app


app = create_app()
