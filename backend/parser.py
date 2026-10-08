import re
from datetime import datetime, timedelta, timezone

CUR = [
    ("RUB", r"руб|₽|\bр\b|\brub\b"),
    ("USD", r"\$|доллар|бакс|\busd\b"),
    ("EUR", r"€|евро|\beur\b"),
    ("KZT", r"тенге|₸|\bkzt\b|\bтг\b"),
    ("UAH", r"грн|гривн|₴|\buah\b"),
    ("GBP", r"£|фунт|\bgbp\b"),
    ("TRY", r"лир|₺|\btry\b"),
]
INCOME = r"зарплат|\bзп\b|аванс|прем|получил|пришл|доход|заработал|подработк|кэшбэк|кешбэк|вернули|^\s*\+"
SALARY = r"зарплат|\bзп\b|аванс|прем"
CATS = {
    "food": r"еда|еду|обед|ужин|завтрак|кофе|продукт|магазин|кафе|ресторан|пицц|бургер|шаурм|доставк|перекус|вкусвилл|пятёроч|пятероч|магнит",
    "transport": r"такси|метро|автобус|бензин|заправк|проезд|маршрутк|яндекс\s*го|убер|uber|парковк|транспорт",
    "home": r"аренд|квартир|коммунал|\bсвет\b|интернет|жкх|ремонт|мебел",
    "fun": r"кино|игр|подписк|netflix|spotify|\bбар\b|клуб|концерт|развлеч|steam|стим|youtube",
    "health": r"аптек|лекарств|врач|стоматолог|анализ|здоровь|больниц|таблетк",
}
NUM = re.compile(r"(\d+(?:[ \u00a0]\d{3})*(?:[.,]\d+)?)\s*(к|k|тыс\w*)?(?![а-яёa-z])", re.I)
FILL = re.compile(
    r"\b(?:потратил\w*|купил\w*|заплатил\w*|отдал\w*|вчера|сегодня|ну|так|значит|еще|ещё|и|в|на|за|по)\b", re.I
)
SEP = re.compile(
    r"[,;]|\b(?:и|потом|еще|ещё|плюс|также|вчера|потратил\w*|купил\w*|заплатил\w*|получил\w*|заработал\w*)\b", re.I
)
CURW = re.compile(r"\s*(?:" + "|".join(p for _, p in CUR) + r")\w*", re.I)


def _to_float(s: str) -> float:
    """2.000 → 2000, 1 500,50 → 1500.5, 1.5 → 1.5"""
    s = re.sub(r"[ \u00a0]", "", s)
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", s):
        return float(re.sub(r"[.,]", "", s))
    return float(s.replace(",", "."))


def split(text: str) -> list[str]:
    """Разбивает одну строку «кофе 350 такси 500» на отдельные покупки."""
    ms = list(NUM.finditer(text))
    if len(ms) < 2:
        return [text]
    lead = FILL.sub("", text[: ms[0].start()])
    if not re.search(r"[а-яёa-z]", lead, re.I):
        cut = [0]
        for a, b in zip(ms, ms[1:]):
            gap = text[a.end() : b.start()]
            c = CURW.match(gap)
            s = SEP.search(gap, c.end() if c else 0)
            cut.append(a.end() + (s.start() if s else len(gap)))
        cut.append(len(text))
        return [text[cut[i] : cut[i + 1]] for i in range(len(ms))]
    out, start = [], 0
    for m in ms:
        end = m.end()
        c = CURW.match(text, end)
        if c:
            end = c.end()
        out.append(text[start:end])
        start = end
    if text[start:].strip():
        out[-1] += text[start:]
    return out


def parse_many(text: str, default_cur: str) -> list[dict]:
    res = []
    for chunk in split(text):
        p = parse(chunk.strip(" ,;.\n"), default_cur)
        if p:
            res.append(p)
    return res


def parse(text: str, default_cur: str):
    t = text.lower()
    best = None
    for m in NUM.finditer(t):
        v = _to_float(m.group(1))
        if m.group(2):
            v *= 1000
        if best is None or v > best:
            best = v
    if not best:
        return None
    cur = next((c for c, p in CUR if re.search(p, t)), default_cur)
    if re.search(INCOME, t):
        kind = "income"
        cat = "salary" if re.search(SALARY, t) else "other"
    else:
        kind = "expense"
        cat = next((c for c, p in CATS.items() if re.search(p, t)), "other")
    when = datetime.now(timezone.utc) - timedelta(days=1) if "вчера" in t else None
    return dict(
        kind=kind, amount=round(best, 2), currency=cur, category=cat,
        note=re.sub(r"\s+", " ", text).strip()[:200], created_at=when,
    )
