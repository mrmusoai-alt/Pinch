from collections import defaultdict
from datetime import datetime, timedelta, timezone

from . import db, rates


def _insight(items, spent):
    if not items:
        return "Пока нет трат за этот период."
    chg = [i for i in items if i["change"] is not None]
    if chg:
        up = max(chg, key=lambda x: x["change"])
        i = up if up["change"] > 0 else min(chg, key=lambda x: x["change"])
        word = "больше" if i["change"] > 0 else "меньше"
        return f'{i["icon"]} На «{i["title"]}» ушло на {abs(i["change"]):.0f}% {word}, чем в прошлом периоде'
    top = items[0]
    return f'{top["icon"]} Больше всего ушло на «{top["title"]}»: {top["amount"] / spent * 100:.0f}% трат'


async def summarize(user, cur: str, period: str) -> dict:
    rt = await rates.get()
    now = datetime.now(timezone.utc)
    days = 7 if period == "week" else 30
    t0, t1 = now - timedelta(days=days), now - timedelta(days=2 * days)
    m0 = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    balance = income = prev_income = spent = prev_spent = month_spent = 0.0
    cats, prev, meta = defaultdict(float), defaultdict(float), {}
    spend, inc = [0.0] * days, [0.0] * days
    for r in await db.all_tx(user["id"]):
        v = rates.convert(rt, r["amount"], r["currency"], cur)
        d = r["created_at"]
        di = (now.date() - d.date()).days
        if r["kind"] == "income":
            balance += v
            if d >= t0:
                income += v
            elif d >= t1:
                prev_income += v
            if 0 <= di < days:
                inc[di] += v
            continue
        balance -= v
        slug = r["slug"] or "other"
        meta[slug] = (r["title"] or "Другое", r["icon"] or "📦")
        if 0 <= di < days:
            spend[di] += v
        if d >= m0:
            month_spent += v
        if d >= t0:
            spent += v
            cats[slug] += v
        elif d >= t1:
            prev_spent += v
            prev[slug] += v
    items = []
    for slug, a in sorted(cats.items(), key=lambda x: -x[1]):
        p = prev.get(slug, 0.0)
        items.append(dict(
            slug=slug, title=meta[slug][0], icon=meta[slug][1], amount=a, prev=p,
            change=(a - p) / p * 100 if p > 0 else None,
        ))
    limit = None
    if user["monthly_limit"] is not None:
        limit = rates.convert(rt, user["monthly_limit"], user["base_currency"], cur)
    bal_end, acc = [], balance
    for i in range(days):
        bal_end.append(acc)
        acc -= inc[i] - spend[i]
    return dict(
        currency=cur, balance=balance, income=income, prev_income=prev_income, spent=spent,
        prev_spent=prev_spent, month_spent=month_spent, limit=limit,
        remaining=None if limit is None else limit - month_spent,
        categories=items, insight=_insight(items, spent),
        series=[dict(spent=spend[i], income=inc[i]) for i in reversed(range(days))],
        spark=list(reversed(bal_end)),
    )
