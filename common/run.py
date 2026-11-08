import sys

import uvicorn

from common.config import load_config

if __name__ == "__main__":
    service = sys.argv[1]
    cfg = load_config(service)
    uvicorn.run(f"services.{service}.app:app", host=cfg["host"], port=cfg["port"])
