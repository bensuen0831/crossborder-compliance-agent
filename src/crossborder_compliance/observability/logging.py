from __future__ import annotations
import json, logging
from datetime import datetime, timezone

class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"timestamp":datetime.now(timezone.utc).isoformat(),"level":record.levelname,"logger":record.name,"message":record.getMessage()},ensure_ascii=False)

def configure_logging(level=logging.INFO):
    h=logging.StreamHandler(); h.setFormatter(JsonFormatter()); root=logging.getLogger(); root.handlers=[h]; root.setLevel(level)
