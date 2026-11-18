import json
import sqlite3
from datetime import datetime, timezone

from .common import DATA

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,            -- source:native_id
  source TEXT, company TEXT, title TEXT, location TEXT, url TEXT,
  salary_text TEXT, salary_max INTEGER, posted_at TEXT,
  description TEXT,
  first_seen TEXT,
  status TEXT DEFAULT 'new',      -- new|filtered|scored|queued|applied|skipped|error
  filter_reason TEXT,
  judgments TEXT,                 -- raw TypeSafe answers (JSON), reused on rescore
  composite REAL, tier TEXT,
  queue_dir TEXT
);
CREATE TABLE IF NOT EXISTS questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  section TEXT, key TEXT, prompt TEXT,
  telegram_msg_id INTEGER,
  asked_at TEXT, answered_at TEXT, answer TEXT
);
CREATE TABLE IF NOT EXISTS labels (job_id TEXT PRIMARY KEY, label INTEGER, note TEXT, labeled_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DATA.mkdir(exist_ok=True)
    db = sqlite3.connect(DATA / "jobs.db")
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def upsert_new(db, job: dict) -> bool:
    """Insert unseen job. Returns True when new."""
    cur = db.execute(
        "INSERT OR IGNORE INTO jobs (id, source, company, title, location, url, salary_text, salary_max,"
        " posted_at, description, first_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (job["id"], job["source"], job["company"], job["title"], job["location"], job["url"],
         job.get("salary_text"), job.get("salary_max"), job.get("posted_at"), job["description"], now()),
    )
    return cur.rowcount == 1


def kv_get(db, k, default=None):
    row = db.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return json.loads(row["v"]) if row else default


def kv_set(db, k, v) -> None:
    db.execute("INSERT OR REPLACE INTO kv (k, v) VALUES (?, ?)", (k, json.dumps(v)))
