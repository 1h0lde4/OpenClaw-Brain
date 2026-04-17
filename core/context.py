"""
core/context.py — SQLite-backed conversation and entity memory.
"""
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "context.sqlite"


@dataclass
class Turn:
    id: int
    timestamp: float
    query: str
    modules_used: list[str]
    answer: str


class ContextMemory:
    def __init__(self):
        self._lock = threading.Lock()
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._init_db()

    def _init_db(self):
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS turns (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp    REAL    NOT NULL,
                    query        TEXT    NOT NULL,
                    modules_used TEXT    NOT NULL,
                    answer       TEXT    NOT NULL
                );
                CREATE TABLE IF NOT EXISTS entities (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    turn_id INTEGER NOT NULL,
                    type    TEXT    NOT NULL,
                    value   TEXT    NOT NULL,
                    FOREIGN KEY(turn_id) REFERENCES turns(id)
                );
                CREATE TABLE IF NOT EXISTS preferences (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
            self._conn.commit()

    def save(self, query: str, modules_used: list[str], answer: str,
             entities: Optional[dict] = None):
        from .privacy import privacy
        if not privacy.can_save_history():
            return
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO turns (timestamp, query, modules_used, answer) VALUES (?,?,?,?)",
                (time.time(), query, json.dumps(modules_used), answer),
            )
            turn_id = cur.lastrowid
            if entities:
                for etype, values in entities.items():
                    if isinstance(values, list):
                        for v in values:
                            cur.execute(
                                "INSERT INTO entities (turn_id, type, value) VALUES (?,?,?)",
                                (turn_id, etype, str(v)),
                            )
                    else:
                        cur.execute(
                            "INSERT INTO entities (turn_id, type, value) VALUES (?,?,?)",
                            (turn_id, etype, str(values)),
                        )
            self._conn.commit()

    def last_n(self, n: int = 10) -> list[Turn]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT id, timestamp, query, modules_used, answer "
                "FROM turns ORDER BY id DESC LIMIT ?", (n,)
            )
            rows = cur.fetchall()
        return [
            Turn(r[0], r[1], r[2], json.loads(r[3]), r[4])
            for r in reversed(rows)
        ]

    def get_entity(self, etype: str, limit: int = 5) -> list[str]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT value FROM entities WHERE type=? "
                "ORDER BY id DESC LIMIT ?", (etype, limit)
            )
            return [r[0] for r in cur.fetchall()]

    def boost_module(self, module_name: str, recent_turns: int = 3) -> float:
        """Return a confidence boost if this module was used recently."""
        turns = self.last_n(recent_turns)
        for t in turns:
            if module_name in t.modules_used:
                return 0.1
        return 0.0

    def format_for_prompt(self, n: int = 5) -> str:
        turns = self.last_n(n)
        if not turns:
            return ""
        lines = []
        for t in turns:
            lines.append(f"User: {t.query}")
            lines.append(f"Assistant: {t.answer}")
        return "\n".join(lines)


context_memory = ContextMemory()
