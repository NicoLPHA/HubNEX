"""FastAPI app: dashboard, REST API, live WebSocket, background workers."""

from __future__ import annotations

import asyncio
import json
import base64
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
from hubnex.casa import SUGGEST_SCHEMA, LayoutError, clean_suggestion, downsample, suggest_prompt
from hubnex.llm import complete
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


class CardIn(BaseModel):
    id: str | None = Field(default=None, pattern=r"^c[0-9]{1,4}$")
    name: str = Field(max_length=60)
    entities: list[str] = Field(min_length=1, max_length=12)
    size: Literal["small", "wide"] = "wide"
    group: str | None = Field(default=None, pattern=r"^[a-z]{1,20}$")  # the room's group it sits in (None: of its first entity)


class OrderIn(BaseModel):
    items: list[str] = Field(max_length=300)


class DisplayIn(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    size: Literal["small", "wide"] | None = None


class LayoutIn(BaseModel):
    text: str = Field(max_length=200_000)


class PlanRoomIn(BaseModel):
    area: str = Field(min_length=1, max_length=80)
    x: float
    y: float
    w: float
    h: float
    outline: bool = False


class PlanFloorIn(BaseModel):
    name: str = Field(default="Piano", max_length=60)
    aspect: float = 1.4
    image: str | None = None
    rooms: list[PlanRoomIn] = Field(default_factory=list, max_length=80)


class PlanIn(BaseModel):
    floors: list[PlanFloorIn] = Field(max_length=10)
    outside: list[str] = Field(default_factory=list)
    energy: dict[str, str] = Field(default_factory=dict)


class SuggestIn(BaseModel):
    image: str


# What a Home Assistant user who is not an administrator may do from the house view: the
# devices' own services, as in Home Assistant itself (never e.g. hassio.* or recorder.*).
HOUSE_DOMAINS = {
    "light", "switch", "fan", "cover", "climate", "lock", "alarm_control_panel", "media_player",
    "scene", "script", "button", "input_button", "input_boolean", "input_select", "input_number",
    "select", "number", "vacuum", "valve", "siren", "humidifier", "water_heater", "lawn_mower",
    "input_datetime", "time", "date", "datetime", "input_text", "text",
}
HOUSE_EVENTS = {"ha", "casa_changed"}


def house_service(domain: str, service: str) -> bool:
    if domain == "homeassistant":
        return service in ("turn_on", "turn_off", "toggle")
    return domain in HOUSE_DOMAINS


def house_only(state: dict) -> dict:
    """The snapshot for whoever only gets the house: no team, activity, mail or spending."""
    return {
        "role": "casa",
        "boss": state["boss"],
        "version": state["version"],
        "companies": [], "agents": [], "routines": {}, "logs": [], "deadlines": [], "drafts": [], "actions": [],
        "stats": {k: 0 for k in state["stats"]},
        "integrations": {"home_assistant": state["integrations"]["home_assistant"], "telegram": False,
                         "voice": False, "mail": False, "connectors": []},
    }


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

    async def role_of(client_host: str | None, headers) -> str:
        """"full", or "casa" for a Home Assistant user who is not an administrator: the sidebar
        panel is open to every user, so the add-on checks who is asking (Supervisor headers)."""
        if not (settings.trusted_proxy and client_host == settings.trusted_proxy) or settings.non_admin_access == "completo":
            return "full"  # the token was checked already
        user = headers.get("x-remote-user-id")
        watcher = app.state.hq.watcher
        try:
            if watcher.enabled and not watcher.ready.is_set():
                await asyncio.wait_for(watcher.ready.wait(), 10)  # just started
            if user and await watcher.is_admin(user):
                return "full"
        except Exception as exc:
            log.warning("Non so se l'utente %s è amministratore (%s): solo Casa", user, exc)
        return "casa"

    async def auth(request: Request) -> str:
        header = request.headers.get("authorization", "")
        token = header[7:] if header.lower().startswith("bearer ") else request.query_params.get("token")
        host = request.client.host if request.client else None
        check_token(token, host)
        return await role_of(host, request.headers)

    async def full(role: str = Depends(auth)) -> None:
        if role != "full":
            raise HTTPException(403, "riservato agli amministratori di Home Assistant")

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

    @app.get("/api/logs", dependencies=[Depends(full)])
    async def logs(before: int | None = None, limit: int = 25, hq: HQ = Depends(get_hq)):
        """Older activity for the dashboard's "Mostra precedenti" button."""
        return await hq.store.recent_logs(min(limit, 100), before_id=before)

    @app.get("/api/graph", dependencies=[Depends(full)])
    async def graph(hq: HQ = Depends(get_hq)):
        return await build_graph(hq)

    @app.get("/api/state", dependencies=[Depends(full)])
    async def state(hq: HQ = Depends(get_hq)):
        return await hq.snapshot()

    @app.post("/api/chat", dependencies=[Depends(full)])
    async def chat(body: ChatIn, hq: HQ = Depends(get_hq)):
        reply = await hq.chat(body.channel, body.text, voice=body.voice)
        return {"reply": reply or "L'agente ha risposto direttamente nel gruppo Telegram."}

    @app.get("/api/agents/{agent_id}", dependencies=[Depends(full)])
    async def agent_detail(agent_id: str, hq: HQ = Depends(get_hq)):
        if agent_id not in hq.agents:
            raise HTTPException(404, "agente sconosciuto")
        return {"tasks": await hq.store.agent_tasks(agent_id, 10)}

    @app.post("/api/agents/{agent_id}/task", dependencies=[Depends(full)])
    async def assign(agent_id: str, body: TaskIn, hq: HQ = Depends(get_hq)):
        if hq.org.agent(agent_id) is None:
            raise HTTPException(404, "agente sconosciuto")
        if body.wait:
            return {"result": await hq.run_agent(agent_id, body.task, source="user")}
        hq.run_agent_background(agent_id, body.task, source="user", report=False)
        return {"status": "started"}

    @app.post("/api/deadlines", dependencies=[Depends(full)])
    async def add_deadline(body: DeadlineIn, hq: HQ = Depends(get_hq)):
        try:
            datetime.fromisoformat(body.due)
        except ValueError:
            raise HTTPException(422, "data non valida, usa AAAA-MM-GG")
        did = await hq.store.deadline_add(body.title, body.due, body.company, None, body.notes)
        await hq.emit_deadlines()
        return {"id": did}

    @app.post("/api/deadlines/{deadline_id}/done", dependencies=[Depends(full)])
    async def done_deadline(deadline_id: int, hq: HQ = Depends(get_hq)):
        await hq.store.deadline_done(deadline_id)
        await hq.emit_deadlines()
        return {"ok": True}

    def desk(hq: HQ):
        if hq.maildesk is None:
            raise HTTPException(503, "casella email non configurata")
        return hq.maildesk

    @app.post("/api/drafts/{draft_id}/revise", dependencies=[Depends(full)])
    async def revise_draft(draft_id: int, body: ReviseIn, hq: HQ = Depends(get_hq)):
        d = await hq.store.draft(draft_id)
        if not d:
            raise HTTPException(404, "bozza sconosciuta")
        try:
            await desk(hq).revise(d, body.text)
        except DraftClosed:
            raise HTTPException(409, "Bozza non più attiva")
        return {"ok": True}

    @app.post("/api/drafts/{draft_id}/{action}", dependencies=[Depends(full)])
    async def finish_draft(draft_id: int, action: Literal["send", "save", "drop"], hq: HQ = Depends(get_hq)):
        try:
            note = await desk(hq).finish(draft_id, action)
        except DraftClosed:
            raise HTTPException(409, "Bozza non più attiva")
        return {"ok": True, "note": note}

    @app.post("/api/actions/{action_id}/{decision}", dependencies=[Depends(full)])
    async def decide_action(action_id: int, decision: Literal["ok", "no"], hq: HQ = Depends(get_hq)):
        try:
            note = await hq.actions.decide(action_id, decision == "ok")
        except ActionClosed:
            raise HTTPException(409, "Azione non più in attesa")
        except Exception as exc:
            raise HTTPException(502, str(exc))
        return {"ok": True, "note": note}

    @app.post("/api/tts", dependencies=[Depends(full)])
    async def tts(body: TTSIn, hq: HQ = Depends(get_hq)):
        if not hq.tts_enabled:
            raise HTTPException(503, "Voce non configurata (ElevenLabs o sintesi vocale di Home Assistant)")
        try:
            audio, ctype = await hq.speak_audio(body.text)
        except Exception as exc:
            raise HTTPException(502, str(exc))
        return Response(audio, media_type=ctype)

    @app.post("/api/ha/event", dependencies=[Depends(full)])
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
    async def casa_call(body: ServiceIn, hq: HQ = Depends(get_hq), role: str = Depends(auth)):
        """A button pressed by the owner in the house view: no AI involved."""
        need_ha(hq)
        if role != "full" and not house_service(body.domain, body.service):
            raise HTTPException(403, f"{body.domain}.{body.service}: riservato agli amministratori di Home Assistant")
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

    @app.get("/api/casa/history", dependencies=[Depends(auth)])
    async def casa_history(e: str, hours: int = 24, hq: HQ = Depends(get_hq)):
        """The last day of the sensors on a room page, for their little charts."""
        need_ha(hq)
        eids = [x for x in e.split(",") if x in hq.casa.shown][:20]  # only what the house shows
        if not eids:
            return {}
        try:
            raw = await hq.ha.history(eids, max(1, min(hours, 72)))
        except HomeAssistantError as exc:
            raise HTTPException(502, str(exc))
        return {eid: downsample(points) for eid, points in raw.items()}

    @app.get("/api/casa/entities", dependencies=[Depends(full)])
    async def casa_entities(q: str = "", area: str | None = None, all: bool = False, hq: HQ = Depends(get_hq)):
        need_ha(hq)
        return hq.casa.candidates(q, area, include_here=all)

    @app.post("/api/casa/rooms/{area_id}/entities", dependencies=[Depends(full)])
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

    @app.post("/api/casa/entities/{entity_id}/kind", dependencies=[Depends(full)])
    async def casa_kind(entity_id: str, body: KindIn, hq: HQ = Depends(get_hq)):
        need_ha(hq)
        if entity_id not in hq.watcher.states:
            raise HTTPException(404, "entità sconosciuta")
        await hq.casa.set_kind(entity_id, body.kind)
        hq.emit({"type": "casa_changed"})
        return {"ok": True}

    @app.post("/api/casa/rooms/{area_id}/cards", dependencies=[Depends(full)])
    async def casa_card(area_id: str, body: CardIn, hq: HQ = Depends(get_hq)):
        """A card composed in "Modifica stanza" (e.g. the stove: switch, start and stop time)."""
        need_ha(hq)
        if area_id not in hq.watcher.areas:
            raise HTTPException(404, "area sconosciuta")
        unknown = [e for e in body.entities if e not in hq.watcher.states]
        if unknown:
            raise HTTPException(422, f"entità sconosciute: {', '.join(unknown)}")
        card_id = await hq.casa.save_card(area_id, body.id, body.name, body.entities, body.size, body.group)
        hq.emit({"type": "casa_changed"})
        return {"ok": True, "id": card_id}

    @app.post("/api/casa/rooms/{area_id}/cards/{card_id}/remove", dependencies=[Depends(full)])
    async def casa_card_delete(area_id: str, card_id: str, hq: HQ = Depends(get_hq)):
        need_ha(hq)
        await hq.casa.delete_card(area_id, card_id)
        hq.emit({"type": "casa_changed"})
        return {"ok": True}

    @app.post("/api/casa/rooms/{area_id}/order", dependencies=[Depends(full)])
    async def casa_order(area_id: str, body: OrderIn, hq: HQ = Depends(get_hq)):
        need_ha(hq)
        if area_id not in hq.watcher.areas:
            raise HTTPException(404, "area sconosciuta")
        await hq.casa.set_order(area_id, body.items)
        hq.emit({"type": "casa_changed"})
        return {"ok": True}

    @app.post("/api/casa/entities/{entity_id}/display", dependencies=[Depends(full)])
    async def casa_display(entity_id: str, body: DisplayIn, hq: HQ = Depends(get_hq)):
        """Rename or resize an entity's card in HubNEX only."""
        need_ha(hq)
        if entity_id not in hq.watcher.states:
            raise HTTPException(404, "entità sconosciuta")
        sent = body.model_fields_set
        await hq.casa.set_display(entity_id, body.name, body.size, rename="name" in sent, resize="size" in sent)
        hq.emit({"type": "casa_changed"})
        return {"ok": True}

    @app.post("/api/casa/rooms/{area_id}/temperature", dependencies=[Depends(full)])
    async def casa_temperature(area_id: str, body: RoomTempIn, hq: HQ = Depends(get_hq)):
        need_ha(hq)
        if area_id not in hq.watcher.areas:
            raise HTTPException(404, "area sconosciuta")
        await hq.casa.set_temperature(area_id, body.entity_id)
        hq.emit({"type": "casa_changed"})
        return {"ok": True}

    @app.post("/api/casa/rooms/{area_id}/entities/{entity_id}/remove", dependencies=[Depends(full)])
    @app.delete("/api/casa/rooms/{area_id}/entities/{entity_id}", dependencies=[Depends(full)])
    async def casa_remove(area_id: str, entity_id: str, hq: HQ = Depends(get_hq)):
        """Taken off this room in the dashboard only: Home Assistant is left as it is."""
        need_ha(hq)
        await hq.casa.hide(area_id, entity_id)
        hq.emit({"type": "casa_changed"})
        return {"ok": True}

    @app.get("/api/casa/layout", dependencies=[Depends(full)])
    async def casa_layout(hq: HQ = Depends(get_hq)):
        return {"text": hq.casa.layout_text(), "error": hq.casa.layout_error, "file": hq.casa.host_path(),
                "areas": sorted(a.get("name") or k for k, a in hq.watcher.areas.items())}

    @app.post("/api/casa/layout", dependencies=[Depends(full)])
    @app.put("/api/casa/layout", dependencies=[Depends(full)])
    async def casa_save_layout(body: LayoutIn, hq: HQ = Depends(get_hq)):
        try:
            hq.casa.save_layout(body.text)
        except LayoutError as exc:
            raise HTTPException(422, str(exc))
        rooms = sum(len(f["rooms"]) for f in hq.casa.layout["floors"])
        await hq.log("system", f"Piantina della casa salvata: {rooms} stanze in {hq.casa.host_path()}")
        hq.emit({"type": "casa_changed"})
        return {"ok": True}

    @app.get("/api/casa/plan", dependencies=[Depends(full)])
    async def casa_plan(hq: HQ = Depends(get_hq)):
        """The floor plan as data, for the visual editor."""
        hq.casa.layout_text()
        return {**hq.casa.layout, "error": hq.casa.layout_error,
                "areas": sorted(a.get("name") or k for k, a in hq.watcher.areas.items())}

    @app.post("/api/casa/plan", dependencies=[Depends(full)])
    async def casa_plan_save(body: PlanIn, hq: HQ = Depends(get_hq)):
        try:
            hq.casa.save_layout_data(body.model_dump())
        except LayoutError as exc:
            raise HTTPException(422, str(exc))
        rooms = sum(len(f.rooms) for f in body.floors)
        await hq.log("system", f"Piantina della casa salvata dall'editor: {rooms} stanze")
        hq.emit({"type": "casa_changed"})
        return {"ok": True}

    @app.post("/api/casa/plan-image", dependencies=[Depends(full)])
    async def casa_plan_image_upload(request: Request, floor: int = 1, hq: HQ = Depends(get_hq)):
        """A photo, image or PDF of the plan (raw body)."""
        data = await request.body()
        try:
            name, aspect = await asyncio.to_thread(hq.casa.save_plan_image, max(1, min(floor, 10)), data)
        except LayoutError as exc:
            raise HTTPException(422, str(exc))
        return {"image": name, "aspect": aspect}

    @app.get("/api/casa/plan-image/{name}", dependencies=[Depends(auth)])
    async def casa_plan_image(name: str, hq: HQ = Depends(get_hq)):
        path = hq.casa.plan_image_path(name)
        if not path:
            raise HTTPException(404, "immagine non trovata")
        return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})

    @app.post("/api/casa/plan-suggest", dependencies=[Depends(full)])
    async def casa_plan_suggest(body: SuggestIn, hq: HQ = Depends(get_hq)):
        """Claude looks at the plan and proposes the rooms (to check in the editor)."""
        path = hq.casa.plan_image_path(body.image)
        if not path:
            raise HTTPException(404, "carica prima la planimetria")
        areas = sorted(a.get("name") or k for k, a in hq.watcher.areas.items())
        image = base64.b64encode(path.read_bytes()).decode()
        try:
            raw = await complete(
                hq.client,
                model=hq.settings.model,
                system="Leggi planimetrie di abitazioni e ne ricavi le stanze come rettangoli.",
                prompt=[
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image}},
                    {"type": "text", "text": suggest_prompt(areas)},
                ],
                effort="medium",
                schema=SUGGEST_SCHEMA,
                on_usage=hq.on_usage,
            )
            rooms = clean_suggestion(json.loads(raw), areas)
        except Exception as exc:
            raise HTTPException(502, f"proposta non riuscita: {exc}")
        await hq.log("system", f"Proposta della piantina: {len(rooms)} stanze riconosciute")
        return {"rooms": rooms}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        try:
            check_token(websocket.query_params.get("token"), websocket.client.host if websocket.client else None)
        except HTTPException:
            await websocket.close(code=4401)
            return
        role = await role_of(websocket.client.host if websocket.client else None, websocket.headers)
        await websocket.accept()
        hq: HQ = websocket.app.state.hq
        queue = hq.subscribe()
        try:
            state = await hq.snapshot()
            await websocket.send_json({"type": "snapshot", "state": state if role == "full" else house_only(state)})
            while True:
                event = await queue.get()
                if role == "full" or event.get("type") in HOUSE_EVENTS:
                    await websocket.send_json(event)
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
