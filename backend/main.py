import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram.types import MenuButtonWebApp, Update, WebAppInfo
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import auth, config, db, extras, rates, stats
from .bot import bot, dp

dp.include_router(extras.router)
INDEX = Path(__file__).parent.parent / "webapp" / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init()
    if config.BASE_URL:
        await bot.set_webhook(f"{config.BASE_URL}/webhook", secret_token=config.WEBHOOK_SECRET)
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Pinch", web_app=WebAppInfo(url=config.BASE_URL))
        )
    await bot.set_my_commands(extras.COMMANDS)
    task = asyncio.create_task(extras.scheduler())
    yield
    task.cancel()
    await bot.session.close()


app = FastAPI(lifespan=lifespan)


def _cur(user, cur):
    cur = (cur or user["base_currency"]).upper()
    if cur not in config.CURRENCIES:
        raise HTTPException(400, "bad currency")
    return cur


@app.get("/")
async def index():
    return FileResponse(INDEX)


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/webhook")
async def webhook(req: Request):
    if req.headers.get("X-Telegram-Bot-Api-Secret-Token") != config.WEBHOOK_SECRET:
        raise HTTPException(403)
    update = Update.model_validate(await req.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/api/summary")
async def summary(period: str = "month", cur: str = "", user=Depends(auth.current_user)):
    return await stats.summarize(user, _cur(user, cur), "week" if period == "week" else "month")


@app.get("/api/transactions")
async def transactions(cur: str = "", limit: int = 60, offset: int = 0, user=Depends(auth.current_user)):
    cur = _cur(user, cur)
    rt = await rates.get()
    rows = (await db.all_tx(user["id"]))[offset : offset + limit]
    return [
        dict(
            id=r["id"], kind=r["kind"], amount=float(r["amount"]), currency=r["currency"],
            converted=rates.convert(rt, r["amount"], r["currency"], cur),
            title=r["title"] or "Другое", icon=r["icon"] or "📦", note=r["note"] or "",
            created_at=r["created_at"].isoformat(),
        )
        for r in rows
    ]


@app.delete("/api/transactions/{tx_id}")
async def delete_tx(tx_id: int, user=Depends(auth.current_user)):
    await db.delete_tx(user["id"], tx_id)
    return {"ok": True}


class Settings(BaseModel):
    base_currency: str | None = None
    monthly_limit: float | None = None
    clear_limit: bool = False


@app.post("/api/settings")
async def settings(s: Settings, user=Depends(auth.current_user)):
    fields = {}
    if s.base_currency:
        new = _cur(user, s.base_currency)
        fields["base_currency"] = new
        if s.monthly_limit is None and not s.clear_limit and user["monthly_limit"] is not None:
            fields["monthly_limit"] = round(
                rates.convert(await rates.get(), user["monthly_limit"], user["base_currency"], new), 2
            )
    if s.clear_limit:
        fields["monthly_limit"] = None
    elif s.monthly_limit is not None:
        fields["monthly_limit"] = s.monthly_limit if s.monthly_limit > 0 else None
    if fields:
        await db.update_user(user["id"], **fields)
    return {"ok": True}
