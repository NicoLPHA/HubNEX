"""Backup and restore of everything HubNEX knows: the database (memory and neural map,
deadlines, chat, house settings, energy panel…) and the configuration folder (agents.yaml,
casa.yaml, floor plan images). The add-on's options (API keys) are not included.

A restore is staged next to the database and applied on the next start, before anything opens
the database: so it never swaps files under a running HubNEX."""

from __future__ import annotations

import io
import json
import shutil
import sqlite3
import tempfile
import time
import zipfile
from pathlib import Path
from hubnex.i18n import tr

PENDING = "restore-pending"
OLD = ".prima-del-ripristino"
SKIP = (".db", ".db-wal", ".db-shm", ".db-journal", "options.json", "assist_token")  # what a restore replaced, kept just in case
MAX_BACKUP = 200 * 1024 * 1024
MAX_FILE = 30 * 1024 * 1024
DB_NAME = "db/hubnex.db"


class BackupError(Exception):
    pass


def _safe_name(name: str) -> bool:
    return bool(name) and "/" not in name and "\\" not in name and not name.startswith(".") and name not in ("..",)


def config_files(config_dir: Path) -> list[Path]:
    """The files of the configuration folder worth keeping (no hidden files, no folders)."""
    if not config_dir.is_dir():
        return []
    return sorted(
        p for p in config_dir.iterdir()
        if p.is_file() and _safe_name(p.name) and p.stat().st_size <= MAX_FILE and not p.name.endswith(OLD)
        and not p.name.endswith(SKIP)  # the database travels on its own, consistent copy
    )


def make_backup(db_path: str, config_dir: Path, version: str) -> bytes:
    """A zip with a consistent copy of the database and the configuration files."""
    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "hubnex.db"
        if Path(db_path).exists():
            src = sqlite3.connect(db_path)
            dst = sqlite3.connect(copy)
            try:
                src.backup(dst)  # a consistent snapshot even while HubNEX writes
            finally:
                dst.close()
                src.close()
        files = config_files(config_dir)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", json.dumps({
                "app": "hubnex", "version": version, "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "database": copy.exists(), "config": [p.name for p in files],
            }, indent=2))
            if copy.exists():
                z.write(copy, DB_NAME)
            for p in files:
                z.write(p, f"config/{p.name}")
    return buf.getvalue()


def stage_restore(data: bytes, db_path: str) -> dict:
    """Check a backup and set it aside for the next start. Returns its manifest."""
    if len(data) > MAX_BACKUP:
        raise BackupError(tr("file troppo grande"))
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise BackupError(tr("non è un backup di HubNEX (zip non valido)")) from exc
    with z:
        try:
            manifest = json.loads(z.read("manifest.json"))
        except (KeyError, ValueError) as exc:
            raise BackupError(tr("non è un backup di HubNEX (manca il manifesto)")) from exc
        if manifest.get("app") != "hubnex":
            raise BackupError(tr("non è un backup di HubNEX"))
        entries = []
        for info in z.infolist():
            if info.is_dir() or info.filename == "manifest.json":
                continue
            if info.filename == DB_NAME:
                entries.append(info)
                continue
            folder, _, name = info.filename.partition("/")
            if folder != "config" or not _safe_name(name) or info.file_size > MAX_FILE:
                raise BackupError(tr("file inatteso nel backup: {a}", a=info.filename))
            entries.append(info)
        pending = Path(db_path).parent / PENDING
        shutil.rmtree(pending, ignore_errors=True)
        (pending / "config").mkdir(parents=True)
        for info in entries:
            target = pending / ("hubnex.db" if info.filename == DB_NAME else info.filename)
            target.write_bytes(z.read(info))
        db = pending / "hubnex.db"
        if db.exists():
            try:
                conn = sqlite3.connect(db)
                ok = conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                conn.close()
            except sqlite3.Error:
                ok = False
            if not ok:
                shutil.rmtree(pending, ignore_errors=True)
                raise BackupError(tr("il database nel backup è danneggiato"))
        (pending / "manifest.json").write_text(json.dumps(manifest))
    return manifest


def apply_pending_restore(db_path: str, config_dir: Path) -> dict | None:
    """At start, before the database is opened: put a staged backup in place. The files it
    replaces are kept with a .prima-del-ripristino suffix. Returns the manifest, or None."""
    pending = Path(db_path).parent / PENDING
    if not (pending / "manifest.json").exists():
        return None
    manifest = json.loads((pending / "manifest.json").read_text())
    db = Path(db_path)
    if (pending / "hubnex.db").exists():
        for suffix in ("", "-wal", "-shm"):
            old = Path(f"{db}{suffix}")
            if old.exists():
                old.replace(Path(f"{db}{suffix}{OLD}"))
        db.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pending / "hubnex.db"), db)
    config_dir.mkdir(parents=True, exist_ok=True)
    for f in (pending / "config").iterdir():
        target = config_dir / f.name
        if target.exists():
            target.replace(config_dir / f"{f.name}{OLD}")
        shutil.move(str(f), target)
    shutil.rmtree(pending, ignore_errors=True)
    return manifest
