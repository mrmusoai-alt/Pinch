import base64

import httpx

from . import config

PROMPT = (
    "Дословно расшифруй это голосовое сообщение на русском. "
    "Суммы и числа пиши цифрами (например 350, а не «триста пятьдесят»). "
    "Верни только текст расшифровки, без комментариев."
)
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"


async def _gemini(audio: bytes) -> str:
    body = {
        "contents": [{
            "parts": [
                {"text": PROMPT},
                {"inline_data": {"mime_type": "audio/ogg", "data": base64.b64encode(audio).decode()}},
            ]
        }]
    }
    models = [config.GEMINI_MODEL, "gemini-3.5-transcribe", "gemini-3.1-flash-lite"]
    err = "no model"
    async with httpx.AsyncClient(timeout=60) as c:
        for model in dict.fromkeys(m for m in models if m):
            r = await c.post(
                GEMINI_URL.format(model), headers={"x-goog-api-key": config.GEMINI_API_KEY}, json=body
            )
            if r.status_code == 200:
                try:
                    parts = r.json()["candidates"][0]["content"]["parts"]
                    text = "".join(p.get("text", "") for p in parts).strip()
                except (KeyError, IndexError):
                    text = ""
                if text:
                    return text
            err = f"{model}: {r.status_code} {r.text[:200]}"
    raise RuntimeError(err)


async def _groq(audio: bytes) -> str:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
            files={"file": ("voice.ogg", audio, "audio/ogg")},
            data={"model": "whisper-large-v3-turbo", "language": "ru", "response_format": "text"},
        )
    r.raise_for_status()
    return r.text.strip()


async def transcribe(audio: bytes) -> str:
    if config.GEMINI_API_KEY:
        return await _gemini(audio)
    return await _groq(audio)
