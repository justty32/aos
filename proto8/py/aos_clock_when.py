"""aos_clock_when 時鐘登記表的牆鐘排法：解析 at（HH:MM、YYYY-MM-DD HH:MM、+N[smhd]）與五欄 cron、算 cron 的下一次（本機時區；11-13 線鐘 wake-timer）。
只做時間運算，不讀寫檔、不寄信；壞輸入丟 ValueError（英文原因）。時刻一律帶時區的 datetime，存檔用 fmt()（ISO、到秒）。"""
import datetime
import re

REL = re.compile(r"\+(\d+)([smhd])\Z")
HHMM = re.compile(r"(\d{1,2}):(\d{2})\Z")
UNIT = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
FIELDS = (("minute", 0, 59), ("hour", 0, 23), ("day of month", 1, 31), ("month", 1, 12), ("day of week", 0, 7))
SEARCH_DAYS = 5 * 366        # 五年內排不到＝當成永遠不會到（例：2 月 30 日）


def now():
    """現在，本機時區、到秒。"""
    return datetime.datetime.now().astimezone().replace(microsecond=0)


def fmt(t):
    return t.isoformat(timespec="seconds")


def show(t):
    """給人看的短寫法：2026-11-13 22:30（秒是 0 就不印秒）。"""
    t = t.astimezone()
    return t.strftime("%Y-%m-%d %H:%M" + (":%S" if t.second else ""))


def parse_iso(text):
    """存檔的 ISO → 帶時區 datetime；沒時區＝本機。壞＝ValueError。"""
    if not isinstance(text, str):
        raise ValueError("must be an ISO date-time string")
    t = datetime.datetime.fromisoformat(text)
    return t if t.tzinfo else t.astimezone()


def parse_at(text, base=None):
    """at 的寫法 → 帶時區 datetime（> base）。HH:MM＝今天、已過＝明天；+N[smhd]＝base 往後；其餘當 ISO 日期時間（空白或 T 隔開）。"""
    base = base or now()
    text = text.strip() if isinstance(text, str) else ""
    m = REL.match(text)
    if m:
        n = int(m.group(1))
        if n <= 0:
            raise ValueError("at %r: the amount after + must be a positive integer" % text)
        return base + datetime.timedelta(**{UNIT[m.group(2)]: n})
    m = HHMM.match(text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if h > 23 or mi > 59:
            raise ValueError("at %r: not a time of day (00:00 to 23:59)" % text)
        t = base.astimezone().replace(hour=h, minute=mi, second=0)
        return t if t > base else (t.replace(tzinfo=None) + datetime.timedelta(days=1)).astimezone()
    try:
        t = parse_iso(text.replace(" ", "T", 1))
    except ValueError:
        raise ValueError("at %r: write HH:MM, YYYY-MM-DD HH:MM, or +N with s, m, h or d (like +10m)" % text) from None
    if t <= base:
        raise ValueError("at %r is in the past (now %s)" % (text, show(base)))
    return t


def _field(part, name, lo, hi):
    """一欄 → 數字集合。*、N、A-B、*/S、A-B/S、逗號清單。"""
    out = set()
    for item in part.split(","):
        m = re.fullmatch(r"(\*|\d+(?:-\d+)?)(?:/(\d+))?", item)
        if not m:
            raise ValueError("cron %s field %r: use *, N, A-B, */S, A-B/S or a comma list" % (name, part))
        rng, step = m.group(1), int(m.group(2) or 1)
        a, b = (lo, hi) if rng == "*" else (int(rng.split("-")[0]), int(rng.split("-")[-1]))
        if m.group(2) and "-" not in rng and rng != "*":
            b = hi                                              # N/S＝從 N 起到底，同 Vixie cron
        if not (lo <= a <= b <= hi) or step <= 0:
            raise ValueError("cron %s field %r: out of range %d-%d" % (name, part, lo, hi))
        out.update(range(a, b + 1, step))
    return out


def parse_cron(text):
    """五欄 cron → (分, 時, 日, 月, 週, 日是*, 週是*)；週的 7 當 0。壞＝ValueError。"""
    parts = text.split() if isinstance(text, str) else []
    if len(parts) != 5:
        raise ValueError("cron %r: needs 5 fields: minute hour day-of-month month day-of-week (like 0 9 * * 1)" % text)
    sets = [_field(p, *f) for p, f in zip(parts, FIELDS)]
    dow = {d % 7 for d in sets[4]}
    return sets[0], sets[1], sets[2], sets[3], dow, parts[2] == "*", parts[4] == "*"


def cron_next(text, after):
    """cron 在 after 之後（不含）的第一個整分時刻，本機時區。五年內沒有＝ValueError。"""
    mins, hours, doms, mons, dows, dom_any, dow_any = parse_cron(text)
    after = after.astimezone()
    day = after.date()
    for _ in range(SEARCH_DAYS):
        if day.month in mons:
            dom_ok, dow_ok = day.day in doms, (day.weekday() + 1) % 7 in dows
            if (dom_ok and dow_ok) if (dom_any or dow_any) else (dom_ok or dow_ok):
                for h in sorted(hours):
                    for mi in sorted(mins):
                        t = datetime.datetime(day.year, day.month, day.day, h, mi).astimezone()
                        if t > after:
                            return t
        day += datetime.timedelta(days=1)
    raise ValueError("cron %r never fires within 5 years" % text)


def late(due, at):
    """晚了多久的短句（不到一分鐘＝空字串）：'late by 2h 5m'。"""
    s = int((at - due).total_seconds())
    if s < 60:
        return ""
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    parts = ["%dd" % d] if d else []
    parts += ["%dh" % h] if h else []
    parts += ["%dm" % (s // 60)] if s // 60 or not parts else []
    return "late by " + " ".join(parts)
