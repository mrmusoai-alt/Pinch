import time

import httpx

_cache = {"t": 0.0, "r": {"USD": 1.0}}


async def get() -> dict:
    if time.time() - _cache["t"] > 6 * 3600:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                data = (await c.get("https://open.er-api.com/v6/latest/USD")).json()
            if data.get("result") == "success":
                _cache.update(t=time.time(), r=data["rates"])
        except Exception:
            pass
    return _cache["r"]


def convert(rates: dict, amount, a: str, b: str) -> float:
    amount = float(amount)
    if a == b or a not in rates or b not in rates:
        return amount
    return amount / rates[a] * rates[b]
