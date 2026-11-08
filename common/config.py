import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_config(service):
    path = Path(os.environ.get("CONFIG_FILE", ROOT / "services" / service / "config.json"))
    with path.open() as handle:
        return json.load(handle)
