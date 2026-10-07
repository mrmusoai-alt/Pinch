import httpx

from . import config


async def transcribe(audio: bytes) -> str:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
            files={"file": ("voice.ogg", audio, "audio/ogg")},
            data={"model": "whisper-large-v3-turbo", "language": "ru", "response_format": "text"},
        )
    r.raise_for_status()
    return r.text.strip()
