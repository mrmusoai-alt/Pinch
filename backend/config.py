import hashlib
import os
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _clean(url: str) -> str:
    # Берём только сам postgresql://... (на случай, если вставили команду psql или кавычки)
    m = re.search(r"postgres(?:ql)?://[^\s'\"]+", url)
    url = m.group(0) if m else url.strip().strip("'\"")
    p = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(p.query) if k != "channel_binding"]
    return urlunsplit(p._replace(query=urlencode(q)))


BOT_TOKEN = os.environ["BOT_TOKEN"].strip()
DATABASE_URL = _clean(os.environ["DATABASE_URL"])
BASE_URL = (os.getenv("BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip().strip(".")
ALLOWED = {int(x) for x in re.findall(r"\d+", os.getenv("ALLOWED_USER_IDS", ""))}
WEBHOOK_SECRET = hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:32]
CURRENCIES = ["RUB", "USD", "EUR", "KZT", "UAH", "GBP", "TRY"]
