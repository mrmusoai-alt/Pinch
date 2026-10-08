import asyncio
import csv
import io
import logging
import re
from datetime import datetime, timedelta, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BotCommand, BufferedInputFile, Message

from . import config, db, rates, stats
from .bot import allowed, bot, money

router = Router()
router.message.filter(allowed)
log = logging.getLogger("pinch")

COMMANDS = [
    BotCommand(command="remind", description="Вечернее напоминание: /remind 21:00"),
    BotCommand(command="report", description="Недельный отчёт: /report on или off"),
    BotCommand(command="export", description="Выгрузить все записи в таблицу (CSV)"),
    BotCommand(command="tz", description="Часовой пояс: /tz 5"),
    BotCommand(command="currency", description="Основная валюта: /currency USD"),
    BotCommand(command="limit", description="Лимит на месяц: /limit 50000"),
    BotCommand(command="help", description="Что умеет бот"),
]


def _arg(m: Message) -> str:
    return (m.text.split(maxsplit=1) + [""])[1].strip().lower()


@router.message(Command("help"))
async def help_(m: Message):
    await m.answer(
        "<b>Что я умею</b>\n"
        "• Траты текстом или голосом: <code>кофе 350 такси 500</code>\n"
        "• /remind 21:00 — напоминать записать траты (/remind off — выключить)\n"
        "• /report on|off — итоги недели по воскресеньям в 20:00\n"
        "• /export — таблица CSV со всеми записями\n"
        "• /tz 5 — часовой пояс (сдвиг от UTC, например 3 для Москвы)\n"
        "• /currency USD, /limit 50000"
    )


@router.message(Command("remind"))
async def remind(m: Message):
    a, user = _arg(m), await db.get_user(m.from_user.id)
    if a in ("off", "выкл", "0"):
        await db.update_user(user["id"], remind_time=None)
        return await m.answer("Напоминание выключено")
    mt = re.fullmatch(r"(\d{1,2})[:.](\d{2})", a)
    if not mt or int(mt[1]) > 23 or int(mt[2]) > 59:
        return await m.answer("Напиши время так: <code>/remind 21:00</code> или <code>/remind off</code>")
    t = f"{int(mt[1]):02d}:{mt[2]}"
    await db.update_user(user["id"], remind_time=t)
    await m.answer(f"🔔 Напомню каждый день в {t} (UTC{user['tz_offset']:+d}). Другой пояс: /tz 3")


@router.message(Command("tz"))
async def tz(m: Message):
    try:
        v = int(_arg(m).replace("utc", "").replace("+", ""))
        assert -12 <= v <= 14
    except (ValueError, AssertionError):
        return await m.answer("Укажи сдвиг от UTC в часах: <code>/tz 3</code> (Москва), <code>/tz 5</code>")
    user = await db.get_user(m.from_user.id)
    await db.update_user(user["id"], tz_offset=v)
    await m.answer(f"Часовой пояс: UTC{v:+d}")


@router.message(Command("report"))
async def report(m: Message):
    a = _arg(m)
    if a not in ("on", "off", "вкл", "выкл"):
        return await m.answer("<code>/report on</code> или <code>/report off</code>")
    user = await db.get_user(m.from_user.id)
    on = a in ("on", "вкл")
    await db.update_user(user["id"], weekly_report=on)
    await m.answer("📊 Отчёт по воскресеньям в 20:00 включён" if on else "Отчёт выключен")


@router.message(Command("export"))
async def export(m: Message):
    user = await db.get_user(m.from_user.id)
    rows = await db.all_tx(user["id"])
    if not rows:
        return await m.answer("Пока нет записей")
    rt, base = await rates.get(), user["base_currency"]
    off = timedelta(hours=user["tz_offset"])
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Дата", "Тип", "Сумма", "Валюта", f"Сумма в {base}", "Категория", "Комментарий"])
    for r in reversed(rows):
        conv = rates.convert(rt, r["amount"], r["currency"], base)
        w.writerow([
            (r["created_at"] + off).strftime("%Y-%m-%d %H:%M"),
            "Доход" if r["kind"] == "income" else "Расход",
            str(r["amount"]).replace(".", ","), r["currency"],
            f"{conv:.2f}".replace(".", ","), r["title"] or "", r["note"] or "",
        ])
    name = f"pinch_{datetime.now(timezone.utc):%Y-%m-%d}.csv"
    await m.answer_document(
        BufferedInputFile(buf.getvalue().encode("utf-8-sig"), filename=name),
        caption="Таблица со всеми записями. Открой в Excel или импортируй в Google Таблицы (Файл → Импорт).",
    )


def _arrow(c):
    return "" if c is None else f" ({'▲' if c > 0 else '▼'} {abs(c):.0f}%)"


async def _send_report(u):
    s = await stats.summarize(u, u["base_currency"], "week")
    cur = s["currency"]
    if not s["spent"] and not s["income"]:
        text = "📊 <b>Итоги недели</b>\nЗа неделю записей нет. Записывать траты — это пара секунд, попробуй на этой неделе."
    else:
        d = (s["spent"] - s["prev_spent"]) / s["prev_spent"] * 100 if s["prev_spent"] > 0 else None
        lines = [
            "📊 <b>Итоги недели</b>",
            f"➖ Расходы: <b>{money(s['spent'], cur)}</b>{_arrow(d)}",
            f"➕ Доходы: <b>{money(s['income'], cur)}</b>",
            f"Баланс: {money(s['balance'], cur)}",
        ]
        if s["categories"]:
            lines.append("\n<b>Топ категорий</b>")
            for c in s["categories"][:3]:
                lines.append(f"{c['icon']} {c['title']} — {money(c['amount'], cur)}{_arrow(c['change'])}")
        if s["remaining"] is not None:
            lines.append(f"\nОсталось по лимиту на месяц: {money(s['remaining'], cur)}")
        lines.append("\n" + s["insight"])
        text = "\n".join(lines)
    await bot.send_message(u["telegram_id"], text)


async def _tick():
    now = datetime.now(timezone.utc)
    for u in await db.pool.fetch("SELECT * FROM users"):
        if config.ALLOWED and u["telegram_id"] not in config.ALLOWED:
            continue
        try:
            local = now + timedelta(hours=u["tz_offset"])
            today, mins = local.date(), local.hour * 60 + local.minute
            if u["remind_time"] and u["last_remind"] != today:
                h, mi = map(int, u["remind_time"].split(":"))
                if 0 <= mins - (h * 60 + mi) < 180:
                    await db.update_user(u["id"], last_remind=today)
                    start = datetime(local.year, local.month, local.day, tzinfo=timezone.utc) - timedelta(hours=u["tz_offset"])
                    n = await db.pool.fetchval(
                        "SELECT count(*) FROM transactions WHERE user_id=$1 AND created_at>=$2", u["id"], start
                    )
                    if not n:
                        await bot.send_message(
                            u["telegram_id"],
                            "🔔 Записал сегодняшние траты? Просто напиши или наговори, например: кофе 350",
                        )
            if u["weekly_report"] and local.weekday() == 6 and u["last_report"] != today and 0 <= mins - 20 * 60 < 180:
                await db.update_user(u["id"], last_report=today)
                await _send_report(u)
        except Exception:
            log.exception("scheduler user %s", u["id"])


async def scheduler():
    while True:
        try:
            await _tick()
        except Exception:
            log.exception("scheduler")
        await asyncio.sleep(60)
