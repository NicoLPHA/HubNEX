"""SQLite persistence: activity log, agent tasks, deadlines, memory notes, chat history."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    agent_id TEXT,
    kind TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    task TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    result TEXT,
    created REAL NOT NULL,
    finished REAL
);
CREATE TABLE IF NOT EXISTS deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    due TEXT NOT NULL,
    company TEXT,
    agent_id TEXT,
    notes TEXT,
    done INTEGER NOT NULL DEFAULT 0,
    notified INTEGER NOT NULL DEFAULT 0,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    scope TEXT NOT NULL,
    topic TEXT NOT NULL,
    content TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid INTEGER NOT NULL,
    body TEXT NOT NULL,
    reply_all INTEGER NOT NULL DEFAULT 0,
    to_addr TEXT NOT NULL,
    subject TEXT NOT NULL,
    chat_id INTEGER,
    msg_id INTEGER,
    status TEXT NOT NULL DEFAULT 'open',
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    agent_id TEXT,
    summary TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    result TEXT,
    chat_id INTEGER,
    msg_id INTEGER,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS usage_daily (
    day TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    model TEXT NOT NULL,
    calls INTEGER NOT NULL DEFAULT 0,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    cost REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (day, agent_id, model)
);
CREATE TABLE IF NOT EXISTS chat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    channel TEXT NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._conn.commit()
        self._lock = asyncio.Lock()

    def _migrate(self) -> None:
        """Columns added after the first release (existing databases lack them)."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(memory)")}
        if "agent_id" not in cols:
            self._conn.execute("ALTER TABLE memory ADD COLUMN agent_id TEXT")

    async def _run(self, sql: str, params: tuple = (), *, fetch: bool = False) -> Any:
        async with self._lock:
            def work():
                cur = self._conn.execute(sql, params)
                self._conn.commit()
                if fetch:
                    return [dict(r) for r in cur.fetchall()]
                return cur.lastrowid

            return await asyncio.to_thread(work)

    # --- Claude spend, one row per day, agent and model --------------------
    async def usage_add(self, day: str, agent_id: str, model: str, tokens_in: int, tokens_out: int, cost: float) -> None:
        await self._run(
            "INSERT INTO usage_daily (day, agent_id, model, calls, tokens_in, tokens_out, cost) VALUES (?,?,?,1,?,?,?) "
            "ON CONFLICT(day, agent_id, model) DO UPDATE SET calls=calls+1, tokens_in=tokens_in+excluded.tokens_in, "
            "tokens_out=tokens_out+excluded.tokens_out, cost=cost+excluded.cost",
            (day, agent_id, model, tokens_in, tokens_out, cost),
        )

    async def usage_by(self, column: str, since: str, until: str = "9999") -> list[dict]:
        """Spend from day `since` to `until` (included) grouped by day, agent_id or model."""
        if column not in ("day", "agent_id", "model"):
            raise ValueError(column)
        return await self._run(
            f"SELECT {column} AS key, SUM(calls) AS calls, SUM(tokens_in) AS tokens_in, SUM(tokens_out) AS tokens_out, "
            f"SUM(cost) AS cost FROM usage_daily WHERE day >= ? AND day <= ? GROUP BY {column} ORDER BY "
            + ("day" if column == "day" else "cost DESC"),
            (since, until),
            fetch=True,
        )

    # --- log -------------------------------------------------------------
    async def log(self, kind: str, text: str, agent_id: str | None = None) -> dict:
        ts = time.time()
        rid = await self._run(
            "INSERT INTO logs (ts, agent_id, kind, text) VALUES (?,?,?,?)", (ts, agent_id, kind, text)
        )
        return {"id": rid, "ts": ts, "agent_id": agent_id, "kind": kind, "text": text}

    async def recent_logs(self, limit: int = 80, before_id: int | None = None) -> list[dict]:
        if before_id:
            rows = await self._run(
                "SELECT * FROM logs WHERE id < ? ORDER BY id DESC LIMIT ?", (before_id, limit), fetch=True
            )
        else:
            rows = await self._run("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,), fetch=True)
        return list(reversed(rows))

    # --- tasks -----------------------------------------------------------
    async def task_start(self, agent_id: str, task: str, source: str) -> int:
        return await self._run(
            "INSERT INTO tasks (agent_id, task, source, status, created) VALUES (?,?,?,?,?)",
            (agent_id, task, source, "running", time.time()),
        )

    async def task_finish(self, task_id: int, status: str, result: str) -> None:
        await self._run(
            "UPDATE tasks SET status=?, result=?, finished=? WHERE id=?",
            (status, result, time.time(), task_id),
        )

    async def agent_tasks(self, agent_id: str, limit: int = 10) -> list[dict]:
        return await self._run(
            "SELECT * FROM tasks WHERE agent_id=? ORDER BY id DESC LIMIT ?", (agent_id, limit), fetch=True
        )

    async def task_counts(self) -> dict[str, int]:
        rows = await self._run(
            "SELECT agent_id, COUNT(*) AS n FROM tasks WHERE status='done' GROUP BY agent_id", fetch=True
        )
        return {r["agent_id"]: r["n"] for r in rows}

    # --- deadlines -------------------------------------------------------
    async def deadline_add(
        self, title: str, due: str, company: str | None = None, agent_id: str | None = None, notes: str = ""
    ) -> int:
        return await self._run(
            "INSERT INTO deadlines (title, due, company, agent_id, notes, created) VALUES (?,?,?,?,?,?)",
            (title, due, company, agent_id, notes, time.time()),
        )

    async def deadlines(self, include_done: bool = False) -> list[dict]:
        where = "" if include_done else "WHERE done=0"
        return await self._run(f"SELECT * FROM deadlines {where} ORDER BY due ASC", fetch=True)

    async def deadline_done(self, deadline_id: int) -> None:
        await self._run("UPDATE deadlines SET done=1 WHERE id=?", (deadline_id,))

    async def deadline_mark_notified(self, deadline_id: int) -> None:
        await self._run("UPDATE deadlines SET notified=1 WHERE id=?", (deadline_id,))

    # --- memory ----------------------------------------------------------
    async def remember(self, scope: str, topic: str, content: str, agent_id: str | None = None) -> int:
        return await self._run(
            "INSERT INTO memory (ts, scope, topic, content, agent_id) VALUES (?,?,?,?,?)",
            (time.time(), scope, topic, content, agent_id),
        )

    # --- neural map ------------------------------------------------------
    async def memories(self, limit: int = 400) -> list[dict]:
        return await self._run("SELECT * FROM memory ORDER BY id DESC LIMIT ?", (limit,), fetch=True)

    async def recent_tasks(self, limit: int = 200) -> list[dict]:
        return await self._run(
            "SELECT id, agent_id, task, status, result, created FROM tasks ORDER BY id DESC LIMIT ?", (limit,), fetch=True
        )

    async def recall(self, query: str, scope: str | None = None, limit: int = 10) -> list[dict]:
        like = f"%{query}%"
        if scope:
            return await self._run(
                "SELECT * FROM memory WHERE scope IN (?, 'global') AND (topic LIKE ? OR content LIKE ?) "
                "ORDER BY id DESC LIMIT ?",
                (scope, like, like, limit),
                fetch=True,
            )
        return await self._run(
            "SELECT * FROM memory WHERE topic LIKE ? OR content LIKE ? ORDER BY id DESC LIMIT ?",
            (like, like, limit),
            fetch=True,
        )

    async def memory_count(self) -> int:
        rows = await self._run("SELECT COUNT(*) AS n FROM memory", fetch=True)
        return rows[0]["n"]

    # --- chat history ----------------------------------------------------
    async def chat_add(self, channel: str, role: str, text: str) -> None:
        await self._run(
            "INSERT INTO chat (ts, channel, role, text) VALUES (?,?,?,?)", (time.time(), channel, role, text)
        )

    async def chat_history(self, channel: str, limit: int = 20) -> list[dict]:
        rows = await self._run(
            "SELECT role, text FROM chat WHERE channel=? ORDER BY id DESC LIMIT ?", (channel, limit), fetch=True
        )
        return list(reversed(rows))

    # --- key/value state --------------------------------------------------
    async def get(self, key: str, default: Any = None) -> Any:
        rows = await self._run("SELECT value FROM kv WHERE key=?", (key,), fetch=True)
        return json.loads(rows[0]["value"]) if rows else default

    async def put(self, key: str, value: Any) -> None:
        await self._run(
            "INSERT INTO kv (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)),
        )

    # --- email drafts awaiting approval -------------------------------------
    async def draft_add(self, uid: int, body: str, reply_all: bool, to_addr: str, subject: str) -> int:
        return await self._run(
            "INSERT INTO drafts (uid, body, reply_all, to_addr, subject, created) VALUES (?,?,?,?,?,?)",
            (uid, body, int(reply_all), to_addr, subject, time.time()),
        )

    async def draft_set_message(self, draft_id: int, chat_id: int, msg_id: int) -> None:
        await self._run("UPDATE drafts SET chat_id=?, msg_id=? WHERE id=?", (chat_id, msg_id, draft_id))

    async def draft(self, draft_id: int) -> dict | None:
        rows = await self._run("SELECT * FROM drafts WHERE id=?", (draft_id,), fetch=True)
        return rows[0] if rows else None

    async def draft_by_message(self, chat_id: int, msg_id: int) -> dict | None:
        rows = await self._run(
            "SELECT * FROM drafts WHERE chat_id=? AND msg_id=? AND status='open'", (chat_id, msg_id), fetch=True
        )
        return rows[0] if rows else None

    async def draft_claim(self, draft_id: int) -> bool:
        """Atomically take an open draft for an action, so two clicks can't send it twice."""
        async with self._lock:
            def work():
                cur = self._conn.execute("UPDATE drafts SET status='busy' WHERE id=? AND status='open'", (draft_id,))
                self._conn.commit()
                return cur.rowcount == 1

            return await asyncio.to_thread(work)

    async def draft_close(self, draft_id: int, status: str) -> None:
        await self._run("UPDATE drafts SET status=? WHERE id=?", (status, draft_id))

    async def drafts_open(self) -> list[dict]:
        return await self._run("SELECT * FROM drafts WHERE status='open' ORDER BY id DESC", fetch=True)

    # --- actions on connected programs awaiting confirmation -----------------
    async def action_add(self, kind: str, agent_id: str | None, summary: str, payload: dict) -> int:
        return await self._run(
            "INSERT INTO actions (kind, agent_id, summary, payload, created) VALUES (?,?,?,?,?)",
            (kind, agent_id, summary, json.dumps(payload), time.time()),
        )

    async def action(self, action_id: int) -> dict | None:
        rows = await self._run("SELECT * FROM actions WHERE id=?", (action_id,), fetch=True)
        if not rows:
            return None
        row = rows[0]
        row["payload"] = json.loads(row["payload"])
        return row

    async def action_set_message(self, action_id: int, chat_id: int, msg_id: int) -> None:
        await self._run("UPDATE actions SET chat_id=?, msg_id=? WHERE id=?", (chat_id, msg_id, action_id))

    async def action_claim(self, action_id: int) -> bool:
        """Atomically take an open action, so two clicks can't run it twice."""
        async with self._lock:
            def work():
                cur = self._conn.execute("UPDATE actions SET status='busy' WHERE id=? AND status='open'", (action_id,))
                self._conn.commit()
                return cur.rowcount == 1

            return await asyncio.to_thread(work)

    async def action_close(self, action_id: int, status: str, result: str | None = None) -> None:
        await self._run("UPDATE actions SET status=?, result=? WHERE id=?", (status, result, action_id))

    async def actions_open(self) -> list[dict]:
        rows = await self._run(
            "SELECT id, kind, agent_id, summary, created FROM actions WHERE status='open' ORDER BY id DESC", fetch=True
        )
        return rows
