"""Accesso alla casella via IMAP/SMTP (SSL). Tutte le funzioni sono sincrone:
chiamarle con asyncio.to_thread. Le email vengono lette con BODY.PEEK,
quindi Jarvis NON le segna come lette.

Portato dall'add-on Jarvis originale."""
from __future__ import annotations

import email
import html
import imaplib
import re
import smtplib
import ssl
import time
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formataddr, getaddresses, make_msgid, parseaddr, parsedate_to_datetime

from hubnex.config import MailSettings

MAX_BODY_CHARS = 6000
HTML_TAG = re.compile(r"<\s*/?\s*(br|p|div|span|table|tr|td|a|img|b|strong|i|em|font|hr)\b", re.I)


def _dec(value) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(str(value))))
    except Exception:
        return str(value)


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|head).*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"[ \t\r\f\v]+", " ", raw)
    raw = re.sub(r"\n\s*\n+", "\n\n", raw)
    return raw.strip()


def extract_text(msg: email.message.Message) -> str:
    plain, htm = None, None
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_maintype() == "multipart":
            continue
        if "attachment" in str(part.get("Content-Disposition", "")).lower():
            continue
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        try:
            text = payload.decode(charset, errors="replace")
        except LookupError:
            text = payload.decode("latin-1", errors="replace")
        if ctype == "text/plain" and plain is None:
            plain = text
        elif ctype == "text/html" and htm is None:
            htm = text
    if plain and plain.strip():
        return plain.strip()
    if htm:
        return html_to_text(htm)
    return ""


def attachment_names(msg: email.message.Message) -> list[str]:
    names = []
    for part in msg.walk():
        fn = part.get_filename()
        if fn:
            names.append(_dec(fn))
    return names


class MailClient:
    def __init__(self, cfg: MailSettings):
        self.cfg = cfg
        self._folders: dict[str, str] | None = None

    # ---------- connessione ----------
    def _imap(self) -> imaplib.IMAP4_SSL:
        conn = imaplib.IMAP4_SSL(self.cfg.imap_host, self.cfg.imap_port,
                                 ssl_context=ssl.create_default_context(), timeout=30)
        conn.login(self.cfg.user, self.cfg.password)
        return conn

    def _special_folders(self, conn) -> dict[str, str]:
        if self._folders is not None:
            return self._folders
        found = {}
        typ, data = conn.list()
        names = []
        for line in data or []:
            if not line:
                continue
            s = line.decode(errors="replace")
            m = re.match(r'\((?P<flags>[^)]*)\)\s+(?P<delim>"[^"]*"|NIL)\s+(?P<name>.+)$', s)
            if not m:
                continue
            name = m.group("name").strip()
            flags = m.group("flags").lower()
            names.append(name)
            if "\\drafts" in flags:
                found["drafts"] = name
            if "\\sent" in flags:
                found["sent"] = name
        def pick(cands):
            for c in cands:
                for n in names:
                    if n.strip('"').lower() == c.lower():
                        return n
            return None
        found.setdefault("drafts", pick(["Drafts", "INBOX.Drafts", "Bozze", "INBOX.Bozze"]) or "Drafts")
        found.setdefault("sent", pick(["Sent", "INBOX.Sent", "Posta inviata", "INBOX.Posta inviata", "Inviata"]) or "Sent")
        self._folders = found
        return found

    @staticmethod
    def _q(name: str) -> str:
        return name if name.startswith('"') else f'"{name}"'

    # ---------- lettura ----------
    def mailbox_state(self) -> tuple[int, int]:
        """(UIDVALIDITY, UID massimo attuale) della INBOX."""
        conn = self._imap()
        try:
            conn.select("INBOX", readonly=True)
            typ, data = conn.status("INBOX", "(UIDVALIDITY UIDNEXT)")
            s = data[0].decode()
            validity = int(re.search(r"UIDVALIDITY (\d+)", s).group(1))
            uidnext = int(re.search(r"UIDNEXT (\d+)", s).group(1))
            return validity, uidnext - 1
        finally:
            conn.logout()

    def _fetch_headers(self, conn, uids: list[bytes]) -> list[dict]:
        out = []
        for uid in uids:
            typ, data = conn.uid("FETCH", uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)] BODY.PEEK[TEXT]<0.600>)")
            if typ != "OK" or not data or data[0] is None:
                continue
            header_bytes, text_bytes, flags = b"", b"", ""
            for item in data:
                if isinstance(item, tuple):
                    meta = item[0].decode(errors="replace")
                    if "HEADER" in meta:
                        header_bytes = item[1]
                    elif "TEXT" in meta:
                        text_bytes = item[1]
                    if "FLAGS" in meta:
                        flags = meta
                elif isinstance(item, bytes) and b"FLAGS" in item:
                    flags += item.decode(errors="replace")
            h = email.message_from_bytes(header_bytes)
            snippet = text_bytes.decode("utf-8", errors="replace")
            if "<" in snippet and ">" in snippet:
                snippet = html_to_text(snippet)
            snippet = re.sub(r"\s+", " ", snippet)[:200]
            out.append({
                "uid": int(uid),
                "da": _dec(h.get("From")),
                "oggetto": _dec(h.get("Subject")) or "(senza oggetto)",
                "data": _fmt_date(h.get("Date")),
                "letta": "\\Seen" in flags,
                "anteprima": snippet,
            })
        return out

    def list_emails(self, only_unread: bool = False, limit: int = 10) -> list[dict]:
        conn = self._imap()
        try:
            conn.select("INBOX", readonly=True)
            typ, data = conn.uid("SEARCH", None, "UNSEEN" if only_unread else "ALL")
            uids = (data[0] or b"").split()[-max(1, min(limit, 30)):]
            return list(reversed(self._fetch_headers(conn, uids)))
        finally:
            conn.logout()

    def new_since(self, last_uid: int) -> list[dict]:
        conn = self._imap()
        try:
            conn.select("INBOX", readonly=True)
            typ, data = conn.uid("SEARCH", None, f"UID {last_uid + 1}:*")
            uids = [u for u in (data[0] or b"").split() if int(u) > last_uid]
            return self._fetch_headers(conn, uids[-20:])
        finally:
            conn.logout()

    def search(self, text: str, limit: int = 10) -> list[dict]:
        conn = self._imap()
        try:
            conn.select("INBOX", readonly=True)
            if text.isascii():
                safe = text.replace('"', "")
                typ, data = conn.uid("SEARCH", None, f'OR OR FROM "{safe}" SUBJECT "{safe}" BODY "{safe}"')
            else:
                conn.literal = text.encode("utf-8")
                typ, data = conn.uid("SEARCH", "CHARSET", "UTF-8", "TEXT")
            uids = (data[0] or b"").split()[-max(1, min(limit, 30)):]
            return list(reversed(self._fetch_headers(conn, uids)))
        finally:
            conn.logout()

    def get_email(self, uid: int) -> dict:
        conn = self._imap()
        try:
            conn.select("INBOX", readonly=True)
            typ, data = conn.uid("FETCH", str(uid), "(BODY.PEEK[])")
            raw = next((i[1] for i in data if isinstance(i, tuple)), None)
            if raw is None:
                raise ValueError(f"Email UID {uid} non trovata")
            msg = email.message_from_bytes(raw)
            body = extract_text(msg)
            if len(body) > MAX_BODY_CHARS:
                body = body[:MAX_BODY_CHARS] + "\n[...testo troncato...]"
            return {
                "uid": uid,
                "da": _dec(msg.get("From")),
                "a": _dec(msg.get("To")),
                "cc": _dec(msg.get("Cc")),
                "oggetto": _dec(msg.get("Subject")),
                "data": _fmt_date(msg.get("Date")),
                "message_id": msg.get("Message-ID", ""),
                "references": msg.get("References", ""),
                "reply_to": _dec(msg.get("Reply-To")),
                "allegati": attachment_names(msg),
                "testo": body,
            }
        finally:
            conn.logout()

    # ---------- scrittura ----------
    def build_reply(self, original: dict, body: str, reply_all: bool = False) -> EmailMessage:
        msg = EmailMessage()
        sender_name = self.cfg.from_name or ""
        msg["From"] = formataddr((sender_name, self.cfg.user)) if sender_name else self.cfg.user
        to_addr = original.get("reply_to") or original.get("da")
        msg["To"] = to_addr
        if reply_all:
            me = self.cfg.user.lower()
            others = [formataddr(a) for a in getaddresses([original.get("a", ""), original.get("cc", "")])
                      if a[1] and a[1].lower() != me and a[1].lower() != parseaddr(to_addr)[1].lower()]
            if others:
                msg["Cc"] = ", ".join(others)
        subj = original.get("oggetto", "")
        msg["Subject"] = subj if subj.lower().startswith(("re:", "r:")) else f"Re: {subj}"
        if original.get("message_id"):
            msg["In-Reply-To"] = original["message_id"]
            msg["References"] = (original.get("references", "") + " " + original["message_id"]).strip()
        msg["Message-ID"] = make_msgid(domain=self.cfg.user.split("@")[-1])
        msg["Date"] = email.utils.formatdate(localtime=True)
        sig = self.cfg.signature or ""
        sig_is_html = bool(HTML_TAG.search(sig))
        header = f"Il {original.get('data','')}, {original.get('da','')} ha scritto:"
        original_lines = (original.get("testo") or "").splitlines()[:40]

        text = body.rstrip()
        if sig:
            text += "\n\n" + (html_to_text(sig) if sig_is_html else sig.replace("\\n", "\n"))
        quoted = "\n".join("> " + l for l in original_lines)
        text += f"\n\n{header}\n{quoted}\n"
        msg.set_content(text)
        if sig_is_html:
            # HTML signature: send an HTML version too, so it shows formatted instead of as tags.
            def lines(rows: list[str]) -> str:
                return "<br>\n".join(html.escape(r) for r in rows)

            msg.add_alternative(
                "<html><body>"
                f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px">{lines(body.rstrip().splitlines())}</div>'
                f"<br>{sig}<br><br>"
                f'<div style="color:#555">{html.escape(header)}</div>'
                '<blockquote style="margin:0 0 0 .8ex;border-left:1px solid #ccc;padding-left:1ex;color:#555">'
                f"{lines(original_lines)}</blockquote>"
                "</body></html>",
                subtype="html",
            )
        return msg

    def save_draft(self, msg: EmailMessage) -> str:
        conn = self._imap()
        try:
            folder = self._special_folders(conn)["drafts"]
            typ, _ = conn.append(self._q(folder), "\\Draft", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
            if typ != "OK":
                raise RuntimeError("Salvataggio bozza fallito")
            return folder.strip('"')
        finally:
            conn.logout()

    def send(self, msg: EmailMessage) -> None:
        with smtplib.SMTP_SSL(self.cfg.smtp_host, self.cfg.smtp_port,
                              context=ssl.create_default_context(), timeout=30) as s:
            s.login(self.cfg.user, self.cfg.password)
            s.send_message(msg)
        # copia in Posta inviata (molti provider non la salvano da soli via SMTP)
        try:
            conn = self._imap()
            try:
                folder = self._special_folders(conn)["sent"]
                conn.append(self._q(folder), "\\Seen", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
            finally:
                conn.logout()
        except Exception:
            pass

    def test_login(self) -> str:
        conn = self._imap()
        try:
            f = self._special_folders(conn)
            return f"OK (bozze: {f['drafts']}, inviata: {f['sent']})"
        finally:
            conn.logout()


def _fmt_date(value) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).astimezone().strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(value)
