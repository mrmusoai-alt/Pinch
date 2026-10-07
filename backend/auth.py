import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException

from . import config, db


def validate(init_data: str, max_age: int = 7 * 86400) -> dict:
    data = dict(parse_qsl(init_data, keep_blank_values=True))
    got = data.pop("hash", None)
    if not got:
        raise ValueError("no hash")
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, got):
        raise ValueError("bad hash")
    if time.time() - int(data.get("auth_date", 0)) > max_age:
        raise ValueError("expired")
    return json.loads(data["user"])


async def current_user(x_init_data: str = Header(default="")):
    try:
        tg = validate(x_init_data)
    except Exception:
        raise HTTPException(401, "unauthorized")
    if config.ALLOWED and tg["id"] not in config.ALLOWED:
        raise HTTPException(403, "forbidden")
    return await db.get_user(tg["id"])
