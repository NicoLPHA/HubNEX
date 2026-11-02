"""Add-on only: plug Jarvis into Assist with no manual steps.

1. Install/update the `hubnex` custom integration into Home Assistant's config folder.
2. Announce ourselves through Supervisor discovery, so HA offers "HubNEX discovered"
   with the address and token already filled in.
"""

from __future__ import annotations

import asyncio
import filecmp
import logging
import os
import shutil
import socket
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from hubnex.i18n import tr_sys

if TYPE_CHECKING:
    from hubnex.hq import HQ

log = logging.getLogger("hubnex.addon")

INTEGRATION_SRC = Path(__file__).resolve().parent.parent / "integration" / "hubnex"
HA_CONFIG = Path("/homeassistant")


def install_integration(src: Path = INTEGRATION_SRC, ha_config: Path = HA_CONFIG) -> bool:
    """Copy the integration into custom_components. True if HA needs a restart to load it."""
    if not ha_config.is_dir():
        return False
    dest = ha_config / "custom_components" / "hubnex"
    if dest.is_dir() and not _differs(src, dest):
        return False
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__"))
    log.info("Integrazione Assist installata in %s", dest)
    return True


def _differs(a: Path, b: Path) -> bool:
    cmp = filecmp.dircmp(a, b, ignore=["__pycache__"])
    if cmp.left_only or cmp.right_only or cmp.diff_files or cmp.funny_files:
        return True
    return any(_differs(a / d, b / d) for d in cmp.common_dirs)


async def announce(token: str, port: int) -> None:
    supervisor = os.environ.get("SUPERVISOR_TOKEN")
    if not supervisor or not token:
        return
    payload = {"service": "hubnex", "config": {"host": socket.gethostname(), "port": port, "token": token}}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "http://supervisor/discovery", json=payload, headers={"Authorization": f"Bearer {supervisor}"}
        )
    if r.status_code >= 400:
        log.warning("Discovery verso Home Assistant fallita: %s %s", r.status_code, r.text[:200])


async def setup_assist(hq: "HQ") -> None:
    s = hq.settings
    try:
        if s.install_assist_integration and install_integration():
            for _ in range(20):  # Home Assistant's language, to write the notice in it
                if hq.watcher.language or s.language in ("it", "en"):
                    break
                await asyncio.sleep(0.5)
            msg = tr_sys(
                "L'integrazione **HubNEX** per Assist è stata installata o aggiornata. "
                "Riavvia Home Assistant, poi in Impostazioni → Dispositivi e servizi conferma "
                "*HubNEX* e sceglilo come agente di conversazione del tuo assistente vocale."
            )
            await hq.ha.call_service(
                "persistent_notification", "create", {"title": "HubNEX", "message": msg, "notification_id": "hubnex_assist"}
            )
    except Exception:
        log.exception("Installazione integrazione Assist fallita")
    try:
        await announce(s.internal_token, 8765)
    except Exception:
        log.exception("Discovery verso Home Assistant fallita")
