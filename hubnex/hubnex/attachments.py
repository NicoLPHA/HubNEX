"""Files the owner sends to the team (a photo from the building site, a PDF, a text file).

Each attachment is saved once, under a short id, and goes to Claude as content blocks: photos
as images (rotated as taken, scaled to what Claude reads anyway), PDFs as documents, text files
as text documents. The conversation history keeps only a note with the id
("[Allegati: #1a2b3c4d «foto.jpg» (foto)]"), so a photo is not paid for again at every turn:
Jarvis passes the ids to the agents he delegates to, and any agent can look at one again with
the `view_attachment` tool. Attachments older than KEEP_DAYS are deleted.
"""

from __future__ import annotations

import io
import json
import re
import secrets
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from hubnex.i18n import tr

MAX_BYTES = 20 * 1024 * 1024  # also what a Telegram bot may download
MAX_PDF_PAGES = 100
MAX_TEXT_CHARS = 200_000
MAX_PER_MESSAGE = 10
IMAGE_EDGE = 1568  # Claude scales larger images down to this anyway
KEEP_DAYS = 30
ID = re.compile(r"[0-9a-f]{8}")
TEXT_EXT = {".txt", ".csv", ".tsv", ".md", ".json", ".xml", ".log", ".yaml", ".yml", ".ini", ".html", ".htm"}
KIND_LABEL = {"image": "foto", "pdf": "PDF", "text": "testo"}


class AttachmentError(ValueError):
    pass


@dataclass
class Attachment:
    id: str
    name: str
    kind: str  # image | pdf | text
    size: int
    ts: float
    pages: int | None = None

    @property
    def ext(self) -> str:
        return {"image": ".jpg", "pdf": ".pdf", "text": ".txt"}[self.kind]


def _clean_name(name: str | None, fallback: str) -> str:
    name = Path(name or "").name.strip()
    name = re.sub(r"[\x00-\x1f«»\[\]]", "", name)[:120]
    return name or fallback


def _image(data: bytes) -> bytes | None:
    """The photo as a JPEG, turned the way it was taken and not larger than IMAGE_EDGE."""
    from PIL import Image, ImageOps

    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
    except Exception:
        return None
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.getchannel("A"))
        img = bg
    img = img.convert("RGB")
    img.thumbnail((IMAGE_EDGE, IMAGE_EDGE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)
    return out.getvalue()


def _text(data: bytes) -> str | None:
    if b"\x00" in data[:4096]:
        return None
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def note(items: list[Attachment]) -> str:
    """What the conversation keeps of the attachments: ids, names and kinds."""
    if not items:
        return ""
    parts = []
    for a in items:
        extra = f", {a.pages} pag." if a.pages else ""
        parts.append(f"#{a.id} «{a.name}» ({KIND_LABEL[a.kind]}{extra})")
    return "[Allegati: " + "; ".join(parts) + "]"


class Attachments:
    def __init__(self, folder: Path):
        self.folder = folder

    # ------------------------------------------------------------------ saving
    def save(self, data: bytes, name: str | None = None, mime: str | None = None) -> Attachment:
        """Check, convert and keep a file. AttachmentError says what is wrong with it."""
        if not data:
            raise AttachmentError(tr("file vuoto"))
        if len(data) > MAX_BYTES:
            raise AttachmentError(tr("file troppo grande (massimo 20 MB)"))
        mime = (mime or "").split(";")[0].strip().lower()
        ext = Path(name or "").suffix.lower()
        pages = None
        if data[:5] == b"%PDF-":
            import pypdfium2 as pdfium

            try:
                pages = len(pdfium.PdfDocument(data))
            except Exception as exc:
                raise AttachmentError(tr("PDF danneggiato o protetto da password")) from exc
            if pages > MAX_PDF_PAGES:
                raise AttachmentError(tr("PDF troppo lungo (massimo {n} pagine)", n=MAX_PDF_PAGES))
            kind, body, fallback = "pdf", data, "documento.pdf"
        elif mime.startswith("text/") or ext in TEXT_EXT or mime in ("application/json", "application/xml"):
            text = _text(data)
            if text is None:
                raise AttachmentError(tr("file di testo non leggibile"))
            kind, body, fallback = "text", text[:MAX_TEXT_CHARS].encode(), "testo.txt"
        else:
            body = _image(data)
            if body is None:
                raise AttachmentError(tr("formato non supportato: invia foto, PDF o file di testo"))
            kind, fallback = "image", "foto.jpg"
        att = Attachment(secrets.token_hex(4), _clean_name(name, fallback), kind, len(body), time.time(), pages)
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / f"{att.id}{att.ext}").write_bytes(body)
        (self.folder / f"{att.id}.json").write_text(json.dumps(asdict(att), ensure_ascii=False), encoding="utf-8")
        self.cleanup()
        return att

    def cleanup(self, now: float | None = None) -> int:
        """Delete the attachments older than KEEP_DAYS. Returns how many."""
        if not self.folder.exists():
            return 0
        limit = (now or time.time()) - KEEP_DAYS * 86400
        removed = 0
        for meta in self.folder.glob("*.json"):
            if meta.stat().st_mtime >= limit:
                continue
            for f in self.folder.glob(meta.stem + ".*"):
                f.unlink(missing_ok=True)
            removed += 1
        return removed

    # ------------------------------------------------------------------ reading
    def get(self, att_id: str) -> Attachment | None:
        att_id = (att_id or "").strip().lstrip("#").lower()
        if not ID.fullmatch(att_id):
            return None
        meta = self.folder / f"{att_id}.json"
        try:
            att = Attachment(**json.loads(meta.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return None
        return att if self.path(att).exists() else None

    def find(self, ids: list[str] | None) -> tuple[list[Attachment], list[str]]:
        """The attachments for these ids (each once) and the ids that are not (or no longer) there."""
        found, missing, seen = [], [], set()
        for i in ids or []:
            att = self.get(str(i))
            if att is None:
                missing.append(str(i))
            elif att.id not in seen:
                seen.add(att.id)
                found.append(att)
        return found, missing

    def path(self, att: Attachment) -> Path:
        return self.folder / f"{att.id}{att.ext}"

    def media_type(self, att: Attachment) -> str:
        return {"image": "image/jpeg", "pdf": "application/pdf", "text": "text/plain"}[att.kind]

    def blocks(self, items: list[Attachment]) -> list[dict]:
        """The content blocks Claude reads: each attachment introduced by its id and name."""
        import base64

        out: list[dict] = []
        for a in items:
            out.append({"type": "text", "text": f"Allegato #{a.id} «{a.name}»:"})
            raw = self.path(a).read_bytes()
            if a.kind == "image":
                out.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(raw).decode()}})
            elif a.kind == "pdf":
                out.append({"type": "document", "title": a.name, "source": {"type": "base64", "media_type": "application/pdf", "data": base64.b64encode(raw).decode()}})
            else:
                out.append({"type": "document", "title": a.name, "source": {"type": "text", "media_type": "text/plain", "data": raw.decode()}})
        return out


def with_blocks(text: str, blocks: list[dict]) -> str | list[dict]:
    """A user turn: the plain text, or the attachments followed by the text."""
    return [*blocks, {"type": "text", "text": text}] if blocks else text


def join(a: str | list[dict], b: str | list[dict]) -> str | list[dict]:
    """Two pieces of the same user turn, kept as text while neither has attachments."""
    if isinstance(a, str) and isinstance(b, str):
        return f"{a}\n\n{b}"
    as_list = lambda c: [{"type": "text", "text": c}] if isinstance(c, str) else list(c)  # noqa: E731
    return as_list(a) + as_list(b)
