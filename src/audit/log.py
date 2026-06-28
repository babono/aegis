"""Append-only audit log (the examiner's replay record).

Two independent guarantees that no row is ever changed after insertion:

1. Database-enforced immutability — BEFORE UPDATE and BEFORE DELETE triggers
   RAISE(ABORT). There is no code path in the system that issues UPDATE/DELETE;
   even if one were added, the database itself refuses. (constraint: append-only)

2. Tamper-evidence — each row stores the SHA-256 of (prev_hash + canonical
   payload). Altering any historical row breaks the chain for every row after
   it, which the `verify_chain()` check detects. This is what an examiner
   replays to confirm the log was not quietly edited.

Events recorded cover the full run: graph construction, figure computation,
reconciliation, configuration change, and export.
"""
from __future__ import annotations

import os
import sqlite3
from typing import Any, Optional

from src.util import canonical_json, sha256

GENESIS = "0" * 64


class AuditLog:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                seq         INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT    NOT NULL,
                run_id      TEXT    NOT NULL,
                firm        TEXT,
                event       TEXT    NOT NULL,   -- e.g. GRAPH_CONSTRUCTED, FIGURE_COMPUTED
                trigger     TEXT    NOT NULL,   -- what caused the event
                payload     TEXT    NOT NULL,   -- canonical-JSON data captured
                retention   TEXT    NOT NULL,   -- retention class (per guidelines 5.1)
                prev_hash   TEXT    NOT NULL,
                row_hash    TEXT    NOT NULL
            );
            """
        )
        # Immutability enforced by the database, not merely by convention.
        cur.execute(
            """
            CREATE TRIGGER IF NOT EXISTS audit_no_update
            BEFORE UPDATE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'audit_log is append-only: UPDATE forbidden');
            END;
            """
        )
        cur.execute(
            """
            CREATE TRIGGER IF NOT EXISTS audit_no_delete
            BEFORE DELETE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'audit_log is append-only: DELETE forbidden');
            END;
            """
        )
        self.conn.commit()

    def _last_hash(self) -> str:
        row = self.conn.execute(
            "SELECT row_hash FROM audit_log ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else GENESIS

    def record(
        self,
        *,
        ts: str,
        run_id: str,
        event: str,
        trigger: str,
        data: Any,
        retention: str = "7y",
        firm: Optional[str] = None,
    ) -> str:
        """Append one event. `ts` is supplied by the caller (frozen run clock)
        so replays are reproducible. Returns the new row hash."""
        prev = self._last_hash()
        payload = canonical_json(data)
        row_hash = sha256(prev + canonical_json(
            {"ts": ts, "run_id": run_id, "firm": firm, "event": event,
             "trigger": trigger, "payload": payload, "retention": retention}
        ))
        self.conn.execute(
            "INSERT INTO audit_log (ts, run_id, firm, event, trigger, payload, "
            "retention, prev_hash, row_hash) VALUES (?,?,?,?,?,?,?,?,?)",
            (ts, run_id, firm, event, trigger, payload, retention, prev, row_hash),
        )
        self.conn.commit()
        return row_hash

    def verify_chain(self) -> bool:
        """Recompute the hash chain end-to-end; True iff nothing was altered."""
        prev = GENESIS
        for row in self.conn.execute(
            "SELECT ts, run_id, firm, event, trigger, payload, retention, "
            "prev_hash, row_hash FROM audit_log ORDER BY seq ASC"
        ):
            ts, run_id, firm, event, trigger, payload, retention, prev_hash, row_hash = row
            if prev_hash != prev:
                return False
            expected = sha256(prev + canonical_json(
                {"ts": ts, "run_id": run_id, "firm": firm, "event": event,
                 "trigger": trigger, "payload": payload, "retention": retention}
            ))
            if expected != row_hash:
                return False
            prev = row_hash
        return True

    def events(self) -> list[dict]:
        cols = ["seq", "ts", "run_id", "firm", "event", "trigger", "payload", "retention"]
        return [
            dict(zip(cols, r))
            for r in self.conn.execute(
                "SELECT seq, ts, run_id, firm, event, trigger, payload, retention "
                "FROM audit_log ORDER BY seq ASC"
            )
        ]

    def close(self) -> None:
        self.conn.close()
