"""Actions on other programs, always confirmed by the owner (like email drafts).

An agent asks for something that changes data in a connected program: it becomes a pending
action, shown in the Telegram group and in the dashboard with ✅ Conferma / ❌ Annulla. Only on
✅ it runs. Two clicks never run it twice (the action is claimed atomically).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Awaitable, Callable

from hubnex.context import CURRENT_CHAT
from hubnex.i18n import tr, tr_sys

if TYPE_CHECKING:
    from hubnex.hq import HQ

log = logging.getLogger("hubnex.actions")

# kind -> runs the action's payload, returns a short note for the owner
Executor = Callable[[dict], Awaitable[str]]


class ActionClosed(Exception):
    def __str__(self) -> str:
        return tr("Azione non più in attesa")


def action_buttons(action_id: int):
    return [[(f"✅ {tr_sys('Conferma')}", f"a:{action_id}:ok"), (f"❌ {tr_sys('Annulla')}", f"a:{action_id}:no")]]


class ActionDesk:
    def __init__(self, hq: "HQ"):
        self.hq = hq
        self.executors: dict[str, Executor] = {}

    async def propose(self, kind: str, agent_id: str | None, summary: str, payload: dict, label: str) -> str:
        """Show the action for confirmation; returns what the agent is told."""
        aid = await self.hq.store.action_add(kind, agent_id, summary, payload)
        team = self.hq.team
        chat = CURRENT_CHAT.get() or (team.home_chat if self.hq.team_enabled else None)
        if chat and self.hq.team_enabled:
            who = tr_sys("{name} propone", name=self.hq.agent_name(agent_id)) if agent_id and agent_id in self.hq.agents else tr_sys("Proposta")
            posted = await team.post(None, f"🛠 {label.upper()} #{aid} — {who}:\n\n{summary}", chat, action_buttons(aid))
            if posted:
                await self.hq.store.action_set_message(aid, *posted)
        await self.hq.log("action", tr_sys("Proposta #{aid}: {summary}", aid=aid, summary=summary), agent_id)
        await self.hq.emit_actions()
        return f"Azione #{aid} mostrata al proprietario per conferma. NON è ancora stata eseguita."

    async def decide(self, action_id: int, confirm: bool) -> str:
        a = await self.hq.store.action(action_id)
        if not a or not await self.hq.store.action_claim(action_id):
            raise ActionClosed()
        if not confirm:
            await self._close(a, "rejected", f"❌ {tr_sys('annullata')}")
            return "Annullata"
        try:
            run = self.executors.get(a["kind"])
            if run is None:
                raise RuntimeError(tr("nessuno sa eseguire azioni '{a}' (connettore rimosso?)", a=a['kind']))
            note = await run(a["payload"])
        except Exception as exc:
            log.exception("action %s failed", action_id)
            await self._close(a, "failed", f"⚠️ {tr_sys('non riuscita: {exc}', exc=exc)}")
            raise
        await self._close(a, "done", note)
        await self.hq.note(f"Il proprietario ha confermato: {a['summary'].splitlines()[0]} ({note}).")
        return note

    async def _close(self, a: dict, status: str, note: str) -> None:
        await self.hq.store.action_close(a["id"], status, note)
        await self.hq.emit_actions()
        await self.hq.log("action", tr_sys("Azione #{id}: {note}", id=a["id"], note=note), a.get("agent_id"))
        if self.hq.team_enabled and a.get("chat_id"):
            await self.hq.team.set_buttons(None, a["chat_id"], a["msg_id"], None)
            await self.hq.team.post(None, tr_sys("Azione #{id}: {note}", id=a["id"], note=note), a["chat_id"], reply_to=a["msg_id"])
