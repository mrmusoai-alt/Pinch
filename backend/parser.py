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


def parse(text: str, default_cur: str):
    t = text.lower()
    best = None
    for m in NUM.finditer(t):
        v = float(re.sub(r"[ \u00a0]", "", m.group(1)).replace(",", "."))
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
