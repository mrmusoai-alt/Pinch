import hashlib
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _clean(url: str) -> str:
    p = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(p.query) if k != "channel_binding"]
    return urlunsplit(p._replace(query=urlencode(q)))


BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = _clean(os.environ["DATABASE_URL"])
BASE_URL = (os.getenv("BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ALLOWED = {int(x) for x in os.getenv("ALLOWED_USER_IDS", "").replace(" ", "").split(",") if x}
WEBHOOK_SECRET = hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:32]
CURRENCIES = ["RUB", "USD", "EUR", "KZT", "UAH", "GBP", "TRY"]
