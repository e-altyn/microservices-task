import numpy as np
import pandas as pd
from fastapi import HTTPException
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from common.schemas import CATEGORICAL, FEATURES, NUMERIC


def prepare(records, training=False):
    frame = pd.DataFrame(records)
    missing = [column for column in FEATURES if column not in frame]
    if missing:
        raise HTTPException(422, f"Отсутствуют обязательные колонки: {', '.join(missing)}")
    result = frame[FEATURES].copy()
    for column in NUMERIC:
        values = result[column].astype("string").str.strip().str.rstrip("%")
        result[column] = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
    for column in CATEGORICAL:
        result[column] = result[column].map(lambda value: str(value).strip() if pd.notna(value) and str(value).strip() else np.nan)
    if training:
        if "loan_status" not in frame:
            raise HTTPException(422, "Для обучения нужна колонка loan_status")
        target = frame["loan_status"].map({"Fully Paid": 0, "Charged Off": 1})
        valid = target.notna()
        result = result.loc[valid].copy()
        result["target"] = target.loc[valid].astype(int)
    if result.empty:
        raise HTTPException(422, "Нет подходящих строк. Для обучения нужны Fully Paid и Charged Off.")
    return result.reset_index(drop=True)


def pipeline(max_iter, random_state, class_weight="balanced", algorithm="LogisticRegression", random_forest=None):
    numeric = Pipeline([("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
                        ("scale", StandardScaler())])
    categorical = Pipeline([("impute", SimpleImputer(strategy="constant", fill_value="unknown")),
                            ("encode", OneHotEncoder(handle_unknown="ignore"))])
    prep = ColumnTransformer([("numeric", numeric, NUMERIC), ("categorical", categorical, CATEGORICAL)])
    if algorithm == "LogisticRegression":
        classifier = LogisticRegression(max_iter=max_iter, random_state=random_state, class_weight=class_weight)
    elif algorithm == "RandomForest":
        classifier = RandomForestClassifier(random_state=random_state, class_weight=class_weight,
                                            **(random_forest or {}))
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")
    return Pipeline([("prepare", prep), ("classifier", classifier)])
