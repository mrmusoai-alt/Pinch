from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from . import config, db, parser, stats, stt

bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
router = Router()
dp.include_router(router)

SYM = {"RUB": "₽", "USD": "$", "EUR": "€", "KZT": "₸", "UAH": "₴", "GBP": "£", "TRY": "₺"}


def allowed(ev) -> bool:
    return not config.ALLOWED or ev.from_user.id in config.ALLOWED


router.message.filter(allowed)
router.callback_query.filter(allowed)


def money(v: float, cur: str) -> str:
    s = f"{v:,.2f}".replace(",", " ")
    if s.endswith(".00"):
        s = s[:-3]
    return f"{s} {SYM.get(cur, cur)}"


@router.message(CommandStart())
async def start(m: Message):
    await db.get_user(m.from_user.id)
    await m.answer(
        "Привет! Я <b>Pinch</b> — считаю твои деньги.\n\n"
        "Пиши или наговаривай голосом:\n"
        "• <code>кофе 350</code>\n• <code>такси 500 рублей</code>\n"
        "• <code>получил зарплату 80000</code>\n• <code>20 долларов подписка</code>\n\n"
        "Открой приложение кнопкой меню внизу слева.\n"
        "Команды: /currency USD — основная валюта, /limit 50000 — лимит на месяц (/limit 0 — убрать)"
    )


@router.message(Command("currency"))
async def currency(m: Message):
    cur = (m.text.split(maxsplit=1) + [""])[1].strip().upper()
    if cur not in config.CURRENCIES:
        return await m.answer("Доступны: " + ", ".join(config.CURRENCIES))
    user = await db.get_user(m.from_user.id)
    fields = {"base_currency": cur}
    if user["monthly_limit"] is not None:
        from . import rates
        fields["monthly_limit"] = round(
            rates.convert(await rates.get(), user["monthly_limit"], user["base_currency"], cur), 2
        )
    await db.update_user(user["id"], **fields)
    await m.answer(f"Основная валюта: {cur}")


@router.message(Command("limit"))
async def limit(m: Message):
    arg = (m.text.split(maxsplit=1) + [""])[1].replace(" ", "").replace(",", ".")
    try:
        v = float(arg)
    except ValueError:
        return await m.answer("Напиши сумму: <code>/limit 50000</code>")
    user = await db.get_user(m.from_user.id)
    await db.update_user(user["id"], monthly_limit=v if v > 0 else None)
    await m.answer("Лимит убран" if v <= 0 else f"Лимит на месяц: {money(v, user['base_currency'])}")


async def record(m: Message, text: str):
    user = await db.get_user(m.from_user.id)
    p = parser.parse(text, user["base_currency"])
    if not p:
        return await m.answer("Не нашёл сумму. Например: <code>кофе 350</code>")
    row = await db.add_tx(user["id"], **p)
    s = await stats.summarize(user, user["base_currency"], "month")
    head = "➕ Доход" if p["kind"] == "income" else "➖ Расход"
    lines = [f"{head}: <b>{money(p['amount'], p['currency'])}</b>", f"{row['icon']} {row['title']}"]
    lines.append(f"Баланс: {money(s['balance'], s['currency'])}")
    if s["remaining"] is not None:
        lines.append(f"Осталось по лимиту: {money(s['remaining'], s['currency'])}")
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="↩️ Отменить", callback_data=f"del:{row['id']}")]]
    )
    await m.answer("\n".join(lines), reply_markup=kb)


@router.message(F.voice)
async def voice(m: Message):
    if not config.GROQ_API_KEY:
        return await m.answer("Голос не настроен: добавь GROQ_API_KEY. Пока пиши текстом.")
    f = await bot.get_file(m.voice.file_id)
    buf = await bot.download_file(f.file_path)
    try:
        text = await stt.transcribe(buf.read())
    except Exception:
        return await m.answer("Не получилось распознать голос, попробуй ещё раз или напиши текстом.")
    await m.answer(f"🎙 «{text}»")
    await record(m, text)


@router.message(F.text & ~F.text.startswith("/"))
async def text(m: Message):
    await record(m, m.text)


@router.callback_query(F.data.startswith("del:"))
async def undo(cb: CallbackQuery):
    user = await db.get_user(cb.from_user.id)
    await db.delete_tx(user["id"], int(cb.data[4:]))
    await cb.message.edit_text("↩️ Запись отменена")
    await cb.answer()
