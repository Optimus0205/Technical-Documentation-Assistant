import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS queries (
    query_id   TEXT PRIMARY KEY,
    question   TEXT NOT NULL,
    answer     TEXT NOT NULL,
    refused    INTEGER NOT NULL,
    grounded   INTEGER,
    degraded   INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
    query_id   TEXT PRIMARY KEY REFERENCES queries(query_id),
    rating     TEXT NOT NULL CHECK (rating IN ('up', 'down')),
    comment    TEXT,
    created_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.feedback_db, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db() -> None:
    with closing(_connect()) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def log_query(query_id: str, question: str, result: dict) -> None:
    grounded = result["grounded"]
    with closing(_connect()) as conn:
        conn.execute(
            "INSERT INTO queries VALUES (?, ?, ?, ?, ?, ?, ?)",
            (query_id, question, result["answer"], int(result["refused"]),
             None if grounded is None else int(grounded), int(result["degraded"]), _now()),
        )
        conn.commit()


def query_exists(query_id: str) -> bool:
    with closing(_connect()) as conn:
        return conn.execute("SELECT 1 FROM queries WHERE query_id = ?", (query_id,)).fetchone() is not None


def save_feedback(query_id: str, rating: str, comment: str | None) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            """INSERT INTO feedback (query_id, rating, comment, created_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(query_id) DO UPDATE SET
                 rating = excluded.rating, comment = excluded.comment, created_at = excluded.created_at""",
            (query_id, rating, comment, _now()),
        )
        conn.commit()


def feedback_summary() -> dict:
    with closing(_connect()) as conn:
        counts = {r["rating"]: r["n"] for r in
                  conn.execute("SELECT rating, COUNT(*) AS n FROM feedback GROUP BY rating")}
        downs = conn.execute(
            """SELECT q.question, f.comment, q.refused, q.grounded
               FROM feedback f JOIN queries q USING (query_id)
               WHERE f.rating = 'down' ORDER BY f.created_at DESC LIMIT 10"""
        ).fetchall()
    return {
        "up": counts.get("up", 0),
        "down": counts.get("down", 0),
        "recent_thumbs_down": [dict(r) for r in downs],   # candidates for the evaluation set
    }