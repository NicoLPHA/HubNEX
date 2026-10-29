"""Settings (from environment) and the HQ org chart (from agents.yaml)."""

from __future__ import annotations

import json
import os
import secrets
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader so we don't need python-dotenv. Real env wins."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# Home Assistant add-on: options from the add-on UI -> the env vars the app already reads.
# Option names match the original Jarvis add-on, so its configuration can be copied over.
ADDON_OPTIONS = {
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "model_jarvis": "HUBNEX_MODEL",
    "model_mail": "HUBNEX_MODEL_MAIL",
    "hq_token": "HQ_TOKEN",
    "telegram_token_jarvis": "TELEGRAM_TOKEN_JARVIS",
    "telegram_token_mail": "TELEGRAM_TOKEN_MAIL",
    "allowed_chat_id": "TELEGRAM_ALLOWED_CHAT_ID",
    "allowed_user_id": "TELEGRAM_ALLOWED_USER_ID",
    "telegram_voice_replies": "TELEGRAM_VOICE_REPLIES",
    "imap_host": "MAIL_IMAP_HOST",
    "imap_port": "MAIL_IMAP_PORT",
    "smtp_host": "MAIL_SMTP_HOST",
    "smtp_port": "MAIL_SMTP_PORT",
    "mail_user": "MAIL_USER",
    "mail_password": "MAIL_PASSWORD",
    "mail_from_name": "MAIL_FROM_NAME",
    "mail_signature": "MAIL_SIGNATURE",
    "check_interval_minutes": "MAIL_CHECK_INTERVAL_MINUTES",
    "notify_min_priority": "MAIL_NOTIFY_MIN_PRIORITY",
    "elevenlabs_api_key": "ELEVENLABS_API_KEY",
    "elevenlabs_voice_id": "ELEVENLABS_VOICE_ID",
    "elevenlabs_model": "ELEVENLABS_MODEL",
    "voice_tts_entity": "VOICE_TTS_ENTITY",
    "ha_blocked_services": "HA_BLOCKED_SERVICES",
    "install_assist_integration": "HUBNEX_INSTALL_ASSIST",
    "anthropic_credit_usd": "ANTHROPIC_CREDIT_USD",
}
# The Supervisor's ingress proxy: requests from here were already authenticated by HA.
INGRESS_PROXY_IP = "172.30.32.2"
DEFAULT_AGENTS = Path(__file__).resolve().parent.parent / "config" / "agents.yaml"
DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_MAIL_MODEL = "claude-haiku-5-5"


def _load_addon_options(options_file: str = "/data/options.json", config_dir: str = "/config") -> bool:
    """When running as a Home Assistant add-on, configure everything from the add-on.

    Returns True if we are an add-on. HA's API is reached through the Supervisor with the
    token it injects, the database lives in /data (backed up with HA) and agents.yaml in the
    add-on config folder (editable with File editor / Samba as /addon_configs/..._hubnex).
    """
    opts_path = Path(options_file)
    if not opts_path.exists():
        return False
    opts = json.loads(opts_path.read_text())
    for key, env in ADDON_OPTIONS.items():
        value = opts.get(key)
        if isinstance(value, list):
            value = ",".join(str(v) for v in value)
        if value not in (None, ""):
            os.environ[env] = str(value).lower() if isinstance(value, bool) else str(value)
    if os.environ.get("SUPERVISOR_TOKEN"):
        os.environ.setdefault("HA_URL", "http://supervisor/core")
        os.environ.setdefault("HA_TOKEN", os.environ["SUPERVISOR_TOKEN"])
    os.environ.setdefault("HUBNEX_DB", "/data/hubnex.db")
    # Token the Assist integration uses to talk to us: generated once, handed to HA through
    # Supervisor discovery, so the owner never has to copy it.
    token_file = opts_path.parent / "assist_token"
    if not token_file.exists():
        token_file.write_text(secrets.token_urlsafe(32))
    os.environ.setdefault("HUBNEX_INTERNAL_TOKEN", token_file.read_text().strip())
    agents = Path(config_dir) / "agents.yaml"
    if Path(config_dir).is_dir() and not agents.exists():
        shutil.copy(DEFAULT_AGENTS, agents)
    os.environ.setdefault("HUBNEX_AGENTS_FILE", str(agents if agents.exists() else DEFAULT_AGENTS))
    if Path(config_dir).is_dir():  # the floor plan must survive updates: keep it in /config
        os.environ.setdefault("HUBNEX_CASA_FILE", str(Path(config_dir) / "casa.yaml"))
    return True


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "si", "sì"}


@dataclass
class MailSettings:
    """Work mailbox (IMAP/SMTP over SSL)."""

    user: str = ""
    password: str = ""
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 465
    from_name: str = ""
    signature: str = ""
    check_interval_minutes: int = 5
    notify_min_priority: str = "media"  # bassa | media | alta

    @property
    def enabled(self) -> bool:
        return bool(self.user and self.password and self.imap_host and self.smtp_host)


@dataclass
class Settings:
    model: str = DEFAULT_MODEL  # Jarvis and every agent without its own model
    model_mail: str = DEFAULT_MAIL_MODEL  # the mail agent
    anthropic_credit_usd: float = 0.0  # prepaid credit to count down from (0 = just show spend)
    hq_token: str = ""
    internal_token: str = ""  # used by the Assist integration (add-on only)
    install_assist_integration: bool = False
    port: int = 8765
    ha_url: str = ""
    ha_token: str = ""
    # Services Jarvis may never call on its own (e.g. unlocking doors, disarming the alarm)
    ha_blocked_services: set[str] = field(default_factory=set)
    telegram_token_jarvis: str = ""
    telegram_token_mail: str = ""
    telegram_chat_id: str = ""  # the team group (negative id)
    telegram_user_id: str = ""  # the only person the bots obey
    telegram_voice_replies: bool = True
    mail: MailSettings = field(default_factory=MailSettings)
    # Voice from Home Assistant's own text-to-speech (Piper, HA Cloud, Google…) instead of ElevenLabs
    voice_tts_entity: str = ""  # e.g. tts.piper
    elevenlabs_key: str = ""
    elevenlabs_voice: str = ""
    elevenlabs_model: str = "eleven_flash_v2_5"
    timezone: str = "Europe/Rome"
    db_path: str = "data/hubnex.db"
    agents_file: str = "config/agents.yaml"
    casa_file: str = ""  # floor plan of the house view; default: casa.yaml next to agents.yaml
    # Client IP whose requests skip the token check (HA ingress); None outside the add-on
    trusted_proxy: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        addon = _load_addon_options()
        _load_dotenv()
        e = os.environ.get
        return cls(
            model=e("HUBNEX_MODEL") or DEFAULT_MODEL,
            model_mail=e("HUBNEX_MODEL_MAIL") or DEFAULT_MAIL_MODEL,
            anthropic_credit_usd=float(e("ANTHROPIC_CREDIT_USD") or 0),
            hq_token=e("HQ_TOKEN", ""),
            internal_token=e("HUBNEX_INTERNAL_TOKEN", ""),
            install_assist_integration=addon and _bool(e("HUBNEX_INSTALL_ASSIST"), True),
            port=int(e("HQ_PORT") or 8765),
            ha_url=(e("HA_URL") or "").rstrip("/"),
            ha_token=e("HA_TOKEN", ""),
            ha_blocked_services={
                x.strip()
                for x in (
                    e("HA_BLOCKED_SERVICES") or "lock.unlock,lock.open,alarm_control_panel.alarm_disarm"
                ).split(",")
                if x.strip()
            },
            telegram_token_jarvis=e("TELEGRAM_TOKEN_JARVIS", ""),
            telegram_token_mail=e("TELEGRAM_TOKEN_MAIL", ""),
            telegram_chat_id=(e("TELEGRAM_ALLOWED_CHAT_ID") or "").strip(),
            telegram_user_id=(e("TELEGRAM_ALLOWED_USER_ID") or "").strip(),
            telegram_voice_replies=_bool(e("TELEGRAM_VOICE_REPLIES"), True),
            mail=MailSettings(
                user=e("MAIL_USER", ""),
                password=e("MAIL_PASSWORD", ""),
                imap_host=e("MAIL_IMAP_HOST") or "",
                imap_port=int(e("MAIL_IMAP_PORT") or 993),
                smtp_host=e("MAIL_SMTP_HOST") or "",
                smtp_port=int(e("MAIL_SMTP_PORT") or 465),
                from_name=e("MAIL_FROM_NAME", ""),
                signature=e("MAIL_SIGNATURE", ""),
                check_interval_minutes=int(e("MAIL_CHECK_INTERVAL_MINUTES") or 5),
                notify_min_priority=(e("MAIL_NOTIFY_MIN_PRIORITY") or "media").lower(),
            ),
            elevenlabs_key=e("ELEVENLABS_API_KEY", ""),
            elevenlabs_voice=e("ELEVENLABS_VOICE_ID", ""),
            elevenlabs_model=e("ELEVENLABS_MODEL") or "eleven_flash_v2_5",
            voice_tts_entity=(e("VOICE_TTS_ENTITY") or "").strip(),
            timezone=e("TZ") or "Europe/Rome",
            db_path=e("HUBNEX_DB") or "data/hubnex.db",
            agents_file=e("HUBNEX_AGENTS_FILE") or "config/agents.yaml",
            casa_file=e("HUBNEX_CASA_FILE", ""),
            trusted_proxy=INGRESS_PROXY_IP if addon else None,
        )


@dataclass
class Routine:
    """A recurring job for an agent: either `every` (e.g. "30m", "6h") or `at` ("09:00")."""

    task: str
    every: str | None = None
    at: str | None = None
    days: list[str] | None = None  # ["mon", "tue", ...]; None = every day
    enabled: bool = False  # off until the owner switches it on in agents.yaml


@dataclass
class AgentSpec:
    id: str
    name: str
    role: str
    company: str
    department: str
    instructions: str = ""
    tools: list[str] = field(default_factory=list)
    model: str | None = None
    effort: str = "medium"
    color: str | None = None
    routines: list[Routine] = field(default_factory=list)


@dataclass
class Department:
    id: str
    name: str
    color: str


@dataclass
class Company:
    id: str
    name: str
    logo: str
    description: str
    departments: list[Department]


@dataclass
class ConnectorSpec:
    """A program of your work reached through MCP (see connectors.py)."""

    name: str
    url: str
    token: str = ""
    extra_headers: dict[str, str] = field(default_factory=dict)
    agents: list[str] | None = None  # None: the boss and every agent
    confirm: str = "writes"  # writes | always | never
    free: list[str] = field(default_factory=list)  # tools that never need confirmation
    always_confirm: list[str] = field(default_factory=list)  # tools that always do

    def headers(self) -> dict[str, str]:
        h = dict(self.extra_headers)
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def allows(self, agent_id: str) -> bool:
        if self.agents is None:
            return True
        return agent_id in self.agents or (agent_id == "jarvis" and "boss" in self.agents)


def _connectors(raw) -> list[ConnectorSpec]:
    out = []
    for i, c in enumerate(raw or [], 1):
        if not isinstance(c, dict) or not c.get("name") or not c.get("url"):
            raise ValueError(f"connettore {i}: servono name e url")
        confirm = str(c.get("confirm", "writes"))
        if confirm not in ("writes", "always", "never"):
            raise ValueError(f"connettore {c['name']}: confirm deve essere writes, always o never")
        agents = c.get("agents")
        out.append(ConnectorSpec(
            name=str(c["name"]),
            url=str(c["url"]),
            token=str(c.get("token") or ""),
            extra_headers={str(k): str(v) for k, v in (c.get("headers") or {}).items()},
            agents=None if agents in (None, "all", ["all"]) else [str(a) for a in agents],
            confirm=confirm,
            free=[str(t) for t in c.get("free") or []],
            always_confirm=[str(t) for t in c.get("always_confirm") or []],
        ))
    return out


@dataclass
class OrgChart:
    boss_name: str
    boss_instructions: str
    boss_tools: list[str]
    boss_effort: str
    companies: list[Company]
    agents: list[AgentSpec]
    connectors: list["ConnectorSpec"] = field(default_factory=list)

    def agent(self, agent_id: str) -> AgentSpec | None:
        return next((a for a in self.agents if a.id == agent_id), None)


def load_org(path: str) -> OrgChart:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    boss = data.get("boss") or data.get("jarvis") or {}  # "jarvis:" is the old name
    companies: list[Company] = []
    agents: list[AgentSpec] = []
    seen: set[str] = set()
    for c in data.get("companies", []):
        departments = [
            Department(id=d["id"], name=d.get("name", d["id"]), color=d.get("color", "#4fd1ff"))
            for d in c.get("departments", [])
        ]
        companies.append(
            Company(
                id=c["id"],
                name=c.get("name", c["id"]),
                logo=c.get("logo", c.get("name", c["id"])[:2].upper()),
                description=c.get("description", ""),
                departments=departments,
            )
        )
        dept_ids = {d.id for d in departments}
        for a in c.get("agents", []):
            if a["id"] in seen:
                raise ValueError(f"agent id duplicato: {a['id']}")
            if a["department"] not in dept_ids:
                raise ValueError(f"agente {a['id']}: reparto '{a['department']}' non esiste in {c['id']}")
            seen.add(a["id"])
            agents.append(
                AgentSpec(
                    id=a["id"],
                    name=a.get("name", a["id"]),
                    role=a.get("role", ""),
                    company=c["id"],
                    department=a["department"],
                    instructions=a.get("instructions", ""),
                    tools=list(a.get("tools", [])),
                    model=a.get("model"),
                    effort=a.get("effort", "medium"),
                    color=a.get("color"),
                    routines=[Routine(**r) for r in a.get("routines", [])],
                )
            )
    return OrgChart(
        connectors=_connectors(data.get("connectors")),
        boss_name=boss.get("name", "Jarvis"),
        boss_instructions=boss.get("instructions", ""),
        boss_tools=list(boss.get("tools", [])),
        boss_effort=boss.get("effort", "medium"),
        companies=companies,
        agents=agents,
    )
