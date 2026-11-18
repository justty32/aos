"""times - comm/1 的時間寫法：ISO 8601 UTC 到毫秒（同信封 sent_at，例 2026-11-14T06:30:00.000+00:00）、解析、期間（30m、8h、2d）。"""
import datetime
import re

from . import Fail

UTC = datetime.timezone.utc
_ISO = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})$")
_DUR = re.compile(r"^([0-9]+)([smhd])$")
_UNIT = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def now():
    return datetime.datetime.now(UTC)


def fmt(dt):
    """aware datetime → `YYYY-MM-DDTHH:MM:SS.mmm+00:00`。"""
    dt = dt.astimezone(UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + "%03d+00:00" % (dt.microsecond // 1000)


def parse(value):
    """字串 → aware datetime；不是字串、沒時區、格式不對＝None（讀的人把它當沒寫）。"""
    if not isinstance(value, str) or not _ISO.match(value):
        return None
    try:
        dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else None


def is_time(value):
    return parse(value) is not None


def duration(text, what="duration"):
    """`30m`、`8h`、`2d`（正整數加 s／m／h／d）→ timedelta；其他＝ArgumentsBad。"""
    m = _DUR.match(text or "") if isinstance(text, str) else None
    n = int(m.group(1)) if m else 0
    if n <= 0:
        raise Fail("ArgumentsBad", "%s must be a positive whole number followed by s, m, h or d (like 30m, 8h, 2d), not %r"
                   % (what, text))
    return datetime.timedelta(seconds=n * _UNIT[m.group(2)])


def time_arg(text, what):
    """使用者給的時間（ISO 8601，要帶時區）→ 正規寫法字串；不對＝ArgumentsBad。"""
    dt = parse(text)
    if dt is None:
        raise Fail("ArgumentsBad", "%s must be an ISO 8601 time with a zone, like 2026-11-14T06:30:00.000+00:00, not %r"
                   % (what, text))
    return fmt(dt)
