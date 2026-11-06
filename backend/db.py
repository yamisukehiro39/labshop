import json
import os
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

def connect():
    # DATABASE_URL only for local development and tests. AWS uses a root-created file.
    if os.getenv("DATABASE_URL"):
        return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row, connect_timeout=5)
    cfg = json.loads(Path(os.getenv("DB_CONFIG", "/etc/labshop/db.json")).read_text())
    return psycopg.connect(**cfg, row_factory=dict_row, connect_timeout=5)
