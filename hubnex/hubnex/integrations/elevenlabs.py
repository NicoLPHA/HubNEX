"""ElevenLabs: text-to-speech for Jarvis' voice, speech-to-text for incoming voice notes."""

from __future__ import annotations

import httpx

API = "https://api.elevenlabs.io/v1"


class VoiceError(Exception):
    pass


def _reason(r: httpx.Response) -> str:
    """ElevenLabs' own explanation (quota, free plan blocked, unknown voice…) in one line."""
    try:
        detail = r.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, dict):
        msg = detail.get("message") or detail.get("status") or str(detail)
    else:
        msg = str(detail or r.text[:200] or r.reason_phrase)
    hints = {401: "chiave API non valida", 402: "credito/piano ElevenLabs insufficiente", 404: "voce non trovata (controlla elevenlabs_voice_id)", 429: "troppe richieste o credito esaurito"}
    return f"ElevenLabs {r.status_code}: {hints.get(r.status_code, '')}{' — ' if r.status_code in hints else ''}{msg}"


class ElevenLabs:
    def __init__(self, api_key: str, voice_id: str, model: str = "eleven_flash_v2_5"):
        self.voice_id = voice_id
        self.model = model
        self._client = httpx.AsyncClient(base_url=API, headers={"xi-api-key": api_key}, timeout=60)
        self._has_key = bool(api_key)

    @property
    def tts_enabled(self) -> bool:
        return self._has_key and bool(self.voice_id)

    @property
    def stt_enabled(self) -> bool:
        return self._has_key

    async def close(self) -> None:
        await self._client.aclose()

    async def speak(self, text: str) -> bytes:
        """Return MP3 audio for `text`."""
        try:
            r = await self._client.post(
                f"/text-to-speech/{self.voice_id}",
                params={"output_format": "mp3_44100_128"},
                json={"text": text, "model_id": self.model},
            )
        except httpx.HTTPError as exc:
            raise VoiceError(f"ElevenLabs non raggiungibile: {exc}") from exc
        if r.status_code >= 400:
            raise VoiceError(_reason(r))
        return r.content

    async def transcribe(self, audio: bytes, filename: str = "voice.ogg") -> str:
        r = await self._client.post(
            "/speech-to-text",
            data={"model_id": "scribe_v1"},
            files={"file": (filename, audio)},
        )
        r.raise_for_status()
        return r.json().get("text", "").strip()
