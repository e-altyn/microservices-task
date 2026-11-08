from typing import Any, Literal

from pydantic import BaseModel, Field

NUMERIC = ["loan_amnt", "int_rate", "annual_inc", "dti", "revol_util"]
CATEGORICAL = ["term", "home_ownership", "purpose"]
FEATURES = NUMERIC + CATEGORICAL
CSV_COLUMNS = FEATURES + ["loan_status", "issue_d"]


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["raw", "processed"] = "raw"
    source: str = Field(default="manual", max_length=200)
    is_synthetic: bool = False
    records: list[dict[str, Any]] = Field(min_length=1, max_length=10000)


class DatasetUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ModelCreate(BaseModel):
    name: str = Field(default="Модель", min_length=1, max_length=120)
    algorithm: Literal["LogisticRegression", "RandomForest"] = "LogisticRegression"


class TrainRequest(BaseModel):
    dataset_id: str


class PredictDatasetRequest(BaseModel):
    dataset_id: str


class PredictRequest(BaseModel):
    records: list[dict[str, Any]] = Field(min_length=1, max_length=1000)


class CollectRequest(BaseModel):
    batch_number: int = Field(default=1, ge=1)
