"""FastAPI app: dashboard, REST API, live WebSocket, background workers."""

from __future__ import annotations

import asyncio
import hmac
import mimetypes
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from hubnex.addon import setup_assist
from hubnex.casa import LayoutError
from hubnex.integrations.ha_ws import HAWatcherError
from hubnex.integrations.homeassistant import HomeAssistantError
from hubnex.config import Settings, load_org
from hubnex.context import ORIGIN
from hubnex.graph import build_graph
from hubnex.hq import HQ
from hubnex.actions import ActionClosed
from hubnex.maildesk import DraftClosed
from hubnex.scheduler import Scheduler
from hubnex.store import Store

log = logging.getLogger("hubnex")
mimetypes.add_type("application/manifest+json", ".webmanifest")
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


# Request bodies live at module level: FastAPI must resolve these annotations by name.
class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    channel: str = "dashboard"
    voice: bool = False  # the answer will be spoken (Assist): keep it short


class TaskIn(BaseModel):
    task: str = Field(min_length=1, max_length=8000)
    wait: bool = False


class DeadlineIn(BaseModel):
    title: str
    due: str
    notes: str = ""
    company: str | None = None


class TTSIn(BaseModel):
    text: str = Field(min_length=1, max_length=2500)


class ReviseIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class HAEventIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    notify: bool = True


class ServiceIn(BaseModel):
    domain: str = Field(pattern=r"^[a-z_]+$")
    service: str = Field(pattern=r"^[a-z_]+$")
    data: dict = Field(default_factory=dict)


class RoomEntityIn(BaseModel):
    entity_id: str = Field(pattern=r"^[a-z_]+\.[A-Za-z0-9_]+$")
    mode: Literal["ha", "local"] = "ha"  # move the area in Home Assistant, or only show it here


class RoomTempIn(BaseModel):
    entity_id: str | None = None  # None: back to the automatic choice


class KindIn(BaseModel):
    kind: Literal["light", "switch", "gate", "siren", "sensor"] | None = None  # None: as in Home Assistant


class LayoutIn(BaseModel):
    text: str = Field(max_length=200_000)


def create_app(settings: Settings | None = None, hq: HQ | None = None, start_workers: bool = True) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal hq
        if hq is None:
            hq = HQ(settings, load_org(settings.agents_file), Store(settings.db_path))
        await hq.load()
        app.state.hq = hq
        if start_workers and settings.trusted_proxy:  # running as a Home Assistant add-on
            await setup_assist(hq)
        workers: list[asyncio.Task] = []
        if start_workers:
            workers.append(asyncio.create_task(Scheduler(hq).run()))
            if hq.team_enabled:
                await hq.team.start()
            if hq.maildesk:
                workers.append(asyncio.create_task(hq.maildesk.loop()))
            if hq.watcher.enabled:
                workers.append(asyncio.create_task(hq.watcher.run()))
            if not settings.hq_token and not settings.trusted_proxy:
                log.warning("HQ_TOKEN non impostato: dashboard e API sono aperte a chiunque in rete!")
        await hq.log("system", f"{hq.org.boss_name} è online. {len(hq.org.agents)} agenti nel team.")
        yield
        for w in workers:
            w.cancel()
        if start_workers and hq.team_enabled:
            await hq.team.stop()
        await hq.close()

    app = FastAPI(title="HubNEX", lifespan=lifespan)

    def check_token(token: str | None, client_host: str | None) -> None:
        if settings.trusted_proxy and client_host == settings.trusted_proxy:
            return  # opened from the HA sidebar (ingress): HA already checked who you are
        for valid in (settings.hq_token, settings.internal_token):
            if valid and token and hmac.compare_digest(token, valid):
                return
        if not settings.hq_token and not settings.trusted_proxy:
            return  # standalone without a token: open (warned at startup)
        # As an add-on with no token set, only the HA sidebar may get in.
        raise HTTPException(401, "token mancante o errato")

    def auth(request: Request) -> None:
        header = request.headers.get("authorization", "")
        token = header[7:] if header.lower().startswith("bearer ") else request.query_params.get("token")
        check_token(token, request.client.host if request.client else None)

    def get_hq(request: Request) -> HQ:
        return request.app.state.hq

    # ------------------------------------------------------------- dashboard
    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(WEB_DIR / "index.html")

    @app.middleware("http")
    async def revalidate_dashboard(request: Request, call_next):
        # Browsers (and the HA app) must check for a newer dashboard after an update instead
        # of showing the cached one: "no-cache" still allows a cheap 304 when nothing changed.
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    # ------------------------------------------------------------- API
    @app.get("/api/ping", dependencies=[Depends(auth)])
    async def ping(hq: HQ = Depends(get_hq)):
        return {"name": hq.org.boss_name}

    @app.get("/api/logs", dependencies=[Depends(auth)])
    async def logs(before: int | None = None, limit: int = 25, hq: HQ = Depends(get_hq)):
        """Older activity for the dashboard's "Mostra precedenti" button."""
        return await hq.store.recent_logs(min(limit, 100), before_id=before)

    @app.get("/api/graph", dependencies=[Depends(auth)])
    async def graph(hq: HQ = Depends(get_hq)):
        return await build_graph(hq)

    @app.get("/api/state", dependencies=[Depends(auth)])
    async def state(hq: HQ = Depends(get_hq)):
        return await hq.snapshot()

    @app.post("/api/chat", dependencies=[Depends(auth)])
    async def chat(body: ChatIn, hq: HQ = Depends(get_hq)):
        reply = await hq.chat(body.channel, body.text, voice=body.voice)
        return {"reply": reply or "L'agente ha risposto direttamente nel gruppo Telegram."}

    @app.get("/api/agents/{agent_id}", dependencies=[Depends(auth)])
    async def agent_detail(agent_id: str, hq: HQ = Depends(get_hq)):
        if agent_id not in hq.agents:
            raise HTTPException(404, "agente sconosciuto")
        return {"tasks": await hq.store.agent_tasks(agent_id, 10)}

    @app.post("/api/agents/{agent_id}/task", dependencies=[Depends(auth)])
    async def assign(agent_id: str, body: TaskIn, hq: HQ = Depends(get_hq)):
        if hq.org.agent(agent_id) is None:
            raise HTTPException(404, "agente sconosciuto")
        if body.wait:
            return {"result": await hq.run_agent(agent_id, body.task, source="user")}
        hq.run_agent_background(agent_id, body.task, source="user", report=False)
        return {"status": "started"}

    @app.post("/api/deadlines", dependencies=[Depends(auth)])
    async def add_deadline(body: DeadlineIn, hq: HQ = Depends(get_hq)):
        try:
            datetime.fromisoformat(body.due)
        except ValueError:
            raise HTTPException(422, "data non valida, usa AAAA-MM-GG")
        did = await hq.store.deadline_add(body.title, body.due, body.company, None, body.notes)
        await hq.emit_deadlines()
        return {"id": did}

    @app.post("/api/deadlines/{deadline_id}/done", dependencies=[Depends(auth)])
    async def done_deadline(deadline_id: int, hq: HQ = Depends(get_hq)):
        await hq.store.deadline_done(deadline_id)
        await hq.emit_deadlines()
        return {"ok": True}

    def desk(hq: HQ):
        if hq.maildesk is None:
            raise HTTPException(503, "casella email non configurata")
        return hq.maildesk

    @app.post("/api/drafts/{draft_id}/revise", dependencies=[Depends(auth)])
    async def revise_draft(draft_id: int, body: ReviseIn, hq: HQ = Depends(get_hq)):
        d = await hq.store.draft(draft_id)
        if not d:
            raise HTTPException(404, "bozza sconosciuta")
        try:
            await desk(hq).revise(d, body.text)
        except DraftClosed:
            raise HTTPException(409, "Bozza non più attiva")
        return {"ok": True}

    @app.post("/api/drafts/{draft_id}/{action}", dependencies=[Depends(auth)])
    async def finish_draft(draft_id: int, action: Literal["send", "save", "drop"], hq: HQ = Depends(get_hq)):
        try:
            note = await desk(hq).finish(draft_id, action)
        except DraftClosed:
            raise HTTPException(409, "Bozza non più attiva")
        return {"ok": True, "note": note}

    @app.post("/api/actions/{action_id}/{decision}", dependencies=[Depends(auth)])
    async def decide_action(action_id: int, decision: Literal["ok", "no"], hq: HQ = Depends(get_hq)):
        try:
            note = await hq.actions.decide(action_id, decision == "ok")
        except ActionClosed:
            raise HTTPException(409, "Azione non più in attesa")
        except Exception as exc:
            raise HTTPException(502, str(exc))
        return {"ok": True, "note": note}

    @app.post("/api/tts", dependencies=[Depends(auth)])
    async def tts(body: TTSIn, hq: HQ = Depends(get_hq)):
        if not hq.tts_enabled:
            raise HTTPException(503, "Voce non configurata (ElevenLabs o sintesi vocale di Home Assistant)")
        try:
            audio, ctype = await hq.speak_audio(body.text)
        except Exception as exc:
            raise HTTPException(502, str(exc))
        return Response(audio, media_type=ctype)

    @app.post("/api/ha/event", dependencies=[Depends(auth)])
    async def ha_event(body: HAEventIn, hq: HQ = Depends(get_hq)):
        """Home Assistant automations push events here (rest_command) for Jarvis to handle."""
        ORIGIN.set("event")  # an automation, not the owner: Jarvis can only look and report
        reply = await hq.chat("homeassistant", f"[Evento da Home Assistant] {body.message}")
        if body.notify and reply:
            await hq.notify(f"🏠 {reply}")
        return {"reply": reply}

    # ------------------------------------------------------------- house view
    def need_ha(hq: HQ) -> None:
        if not hq.watcher.enabled:
            raise HTTPException(503, "Home Assistant non configurato")

    @app.get("/api/casa", dependencies=[Depends(auth)])
    async def casa(hq: HQ = Depends(get_hq)):
        need_ha(hq)
        return hq.casa.build()

    @app.post("/api/casa/call", dependencies=[Depends(auth)])
    async def casa_call(body: ServiceIn, hq: HQ = Depends(get_hq)):
        """A button pressed by the owner in the house view: no AI involved."""
        need_ha(hq)
        try:
            await hq.ha.call_service(body.domain, body.service, body.data, by_owner=True)
        except HomeAssistantError as exc:
            raise HTTPException(502, str(exc))
        target = body.data.get("entity_id", "")
        await hq.log("ha", f"Tu (Casa): {body.domain}.{body.service} {target if isinstance(target, str) else ', '.join(target)}", None)
        return {"ok": True}

    @app.get("/api/casa/camera/{entity_id}", dependencies=[Depends(auth)])
    async def casa_camera(entity_id: str, hq: HQ = Depends(get_hq)):
        """A frame of the camera, fetched by the add-on (works from the sidebar and outside)."""
        need_ha(hq)
        if not entity_id.startswith("camera."):
            raise HTTPException(404, "non è una telecamera")
        try:
            image, ctype = await hq.ha.camera_image(entity_id)
        except HomeAssistantError as exc:
            raise HTTPException(502, str(exc))
        # Each refresh asks for a new URL (?t=…): a short cache avoids flicker on redraws.
        return Response(image, media_type=ctype, headers={"Cache-Control": "private, max-age=30"})

    @app.get("/api/casa/camera/{entity_id}/stream", dependencies=[Depends(auth)])
    async def casa_camera_stream(entity_id: str, hq: HQ = Depends(get_hq)):
        """Live MJPEG through the add-on: used when the HA video player (HLS) isn't reachable."""
        need_ha(hq)
        if not entity_id.startswith("camera."):
            raise HTTPException(404, "non è una telecamera")
        try:
            ctype, chunks = await hq.ha.camera_stream(entity_id)
        except HomeAssistantError as exc:
            raise HTTPException(502, str(exc))
        return StreamingResponse(chunks, media_type=ctype, headers={"Cache-Control": "no-store"})

    @app.get("/api/casa/entities", dependencies=[Depends(auth)])
    async def casa_entities(q: str = "", area: str | None = None, hq: HQ = Depends(get_hq)):
        need_ha(hq)
        return hq.casa.candidates(q, area)

    @app.post("/api/casa/rooms/{area_id}/entities", dependencies=[Depends(auth)])
    async def casa_add(area_id: str, body: RoomEntityIn, hq: HQ = Depends(get_hq)):
        need_ha(hq)
        if area_id not in hq.watcher.areas:
            raise HTTPException(404, "area sconosciuta")
        if body.entity_id not in hq.watcher.states:
            raise HTTPException(404, "entità sconosciuta")
        if body.mode == "ha":
            try:
                await hq.watcher.set_area(body.entity_id, area_id)
            except HAWatcherError as exc:
                raise HTTPException(409, str(exc))
            await hq.casa.moved_in_ha(area_id, body.entity_id)
        else:
            await hq.casa.show_here(area_id, body.entity_id)
        hq.emit({"type": "casa_changed"})
        return {"ok": True}

    @app.post("/api/casa/entities/{entity_id}/kind", dependencies=[Depends(auth)])
    async def casa_kind(entity_id: str, body: KindIn, hq: HQ = Depends(get_hq)):
        need_ha(hq)
        if entity_id not in hq.watcher.states:
            raise HTTPException(404, "entità sconosciuta")
        await hq.casa.set_kind(entity_id, body.kind)
        hq.emit({"type": "casa_changed"})
        return {"ok": True}

    @app.post("/api/casa/rooms/{area_id}/temperature", dependencies=[Depends(auth)])
    async def casa_temperature(area_id: str, body: RoomTempIn, hq: HQ = Depends(get_hq)):
        need_ha(hq)
        if area_id not in hq.watcher.areas:
            raise HTTPException(404, "area sconosciuta")
        await hq.casa.set_temperature(area_id, body.entity_id)
        hq.emit({"type": "casa_changed"})
        return {"ok": True}

    @app.post("/api/casa/rooms/{area_id}/entities/{entity_id}/remove", dependencies=[Depends(auth)])
    @app.delete("/api/casa/rooms/{area_id}/entities/{entity_id}", dependencies=[Depends(auth)])
    async def casa_remove(area_id: str, entity_id: str, hq: HQ = Depends(get_hq)):
        """Taken off this room in the dashboard only: Home Assistant is left as it is."""
        need_ha(hq)
        await hq.casa.hide(area_id, entity_id)
        hq.emit({"type": "casa_changed"})
        return {"ok": True}

    @app.get("/api/casa/layout", dependencies=[Depends(auth)])
    async def casa_layout(hq: HQ = Depends(get_hq)):
        return {"text": hq.casa.layout_text(), "error": hq.casa.layout_error, "file": hq.casa.host_path(),
                "areas": sorted(a.get("name") or k for k, a in hq.watcher.areas.items())}

    @app.post("/api/casa/layout", dependencies=[Depends(auth)])
    @app.put("/api/casa/layout", dependencies=[Depends(auth)])
    async def casa_save_layout(body: LayoutIn, hq: HQ = Depends(get_hq)):
        try:
            hq.casa.save_layout(body.text)
        except LayoutError as exc:
            raise HTTPException(422, str(exc))
        rooms = sum(len(f["rooms"]) for f in hq.casa.layout["floors"])
        await hq.log("system", f"Piantina della casa salvata: {rooms} stanze in {hq.casa.host_path()}")
        hq.emit({"type": "casa_changed"})
        return {"ok": True}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        try:
            check_token(websocket.query_params.get("token"), websocket.client.host if websocket.client else None)
        except HTTPException:
            await websocket.close(code=4401)
            return
        await websocket.accept()
        hq: HQ = websocket.app.state.hq
        queue = hq.subscribe()
        try:
            await websocket.send_json({"type": "snapshot", "state": await hq.snapshot()})
            while True:
                await websocket.send_json(await queue.get())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            hq.unsubscribe(queue)

    return app


def run() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    uvicorn.run(create_app(settings), host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    run()
