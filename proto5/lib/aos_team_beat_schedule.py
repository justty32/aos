"""心跳的時間表：欄位與單位常數、崩潰測試點、時區、every／daily／once 解析、Schedule 算下一次到期、期間印法。"""
import datetime
import os
import re

import aos_team_format as fmt
from aos_team_format import TeamError


ROUTINE_COLUMNS = ('name', 'every', 'daily', 'once', 'tz', 'to', 'workflow', 'goal', 'done_when', 'timeout_minutes',
                   'retries', 'added_by', 'added_at', 'q', 'request')
FIELDS = ('op', 'name', 'every', 'daily', 'once', 'tz', 'to', 'workflow', 'goal', 'done_when', 'timeout_minutes',
          'retries')
APPROVE = ('批准', '同意', '好', '可以', 'yes', 'y', 'ok', 'approve')
UNITS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
CRASH_ENV = 'AOS_TEAM_POST_CRASH'


def crash(point):
    if point in (os.environ.get(CRASH_ENV) or '').split(','):
        import signal
        os.kill(os.getpid(), signal.SIGKILL)


def _zone(tz):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz) if tz else None
    except Exception:
        return None


# ------------------------------------------------------------ 時間表 ----

def check_tz(tz):
    """IANA 時區名字要載得起來；打錯字不要默默變成本機時間。"""
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(str(tz))
    except Exception:
        raise TeamError('BadRoutine', 'tz %r 不是認得的 IANA 時區（例 Asia/Taipei）' % (tz,))
    return tz

def parse_every(text):
    m = re.fullmatch(r'\s*([0-9]+)\s*([smhd])\s*', str(text or ''))
    if not m or int(m.group(1)) <= 0:
        raise TeamError('BadRoutine', 'every 要寫成 30s／10m／6h／1d 這種（收到 %r）' % (text,))
    return int(m.group(1)) * UNITS[m.group(2)]


def parse_daily(text):
    m = re.fullmatch(r'\s*([01]?[0-9]|2[0-3]):([0-5][0-9])\s*', str(text or ''))
    if not m:
        raise TeamError('BadRoutine', 'daily 要寫成 09:00 這種（收到 %r）' % (text,))
    return int(m.group(1)), int(m.group(2))


def parse_at(text):
    t = fmt.parse_iso(text)
    if t is None or t.tzinfo is None:
        raise TeamError('BadRoutine', 'once 要是含時區的 ISO 時刻，例 2026-09-25T10:00:00+08:00（收到 %r）' % (text,))
    return t


class Schedule:
    """一條例行的時間表：occurrences 都是有時區的 datetime。"""

    def __init__(self, row, team_tz):
        self.tz = _zone(row.get('tz') or team_tz)
        self.anchor = fmt.parse_iso(row.get('added_at')) or datetime.datetime.now(datetime.timezone.utc)
        if self.anchor.tzinfo is None:
            self.anchor = self.anchor.replace(tzinfo=datetime.timezone.utc)
        if row.get('every'):
            self.kind, self.period = 'every', parse_every(row['every'])
        elif row.get('daily'):
            self.kind, self.hm = 'daily', parse_daily(row['daily'])
        elif row.get('once'):
            self.kind, self.at = 'at', parse_at(row['once'])
        else:
            raise TeamError('BadRoutine', '%s 沒寫 every／daily／once' % row.get('name'))

    def _daily(self, day):
        """那一天的當地時刻，換成 UTC 回（同一個 ZoneInfo 的兩個時刻比大小會照牆上時間比、不管夏令，所以一律用 UTC 比）。
        夏令時間重複的那一小時取第一次（fold=0）；跳過的那一小時照 zoneinfo 換算（等於往後推一小時）。"""
        local = datetime.datetime(day.year, day.month, day.day, self.hm[0], self.hm[1])
        local = local.replace(tzinfo=self.tz) if self.tz else local.astimezone()
        return local.astimezone(datetime.timezone.utc)

    def _first_daily(self):
        day = self.anchor.astimezone(self.tz).date()
        t = self._daily(day)
        return t if t >= self.anchor else self._daily(day + datetime.timedelta(days=1))

    def latest(self, now):
        """now 以前（含）最近的一次；還沒有＝None。"""
        if self.kind == 'every':
            if now < self.anchor:
                return None
            k = int((now - self.anchor).total_seconds() // self.period)
            return self.anchor + datetime.timedelta(seconds=k * self.period)
        if self.kind == 'daily':
            day = now.astimezone(self.tz).date()
            t = self._daily(day)
            if t > now:
                t = self._daily(day - datetime.timedelta(days=1))
            return t if t >= self._first_daily() else None
        return self.at if now >= self.at else None

    def count(self, after, upto):
        """(after, upto] 之間該跑幾次；after 是 None＝從頭算。"""
        if upto is None:
            return 0
        if self.kind == 'every':
            k_up = int(round((upto - self.anchor).total_seconds() / self.period))
            k_af = -1 if after is None else int(round((after - self.anchor).total_seconds() / self.period))
            return max(0, k_up - k_af)
        if self.kind == 'daily':
            first = self._first_daily() if after is None else after
            days = (upto.astimezone(self.tz).date() - first.astimezone(self.tz).date()).days
            return max(0, days + (1 if after is None else 0))
        return 0 if after is not None else 1

    def next(self, now):
        if self.kind == 'every':
            last = self.latest(now)
            return self.anchor if last is None else last + datetime.timedelta(seconds=self.period)
        if self.kind == 'daily':
            last = self.latest(now)
            if last is None:
                return self._first_daily()
            return self._daily(last.astimezone(self.tz).date() + datetime.timedelta(days=1))
        return self.at if now < self.at else None

    def describe(self):
        if self.kind == 'every':
            return 'every %s' % fmt_period(self.period)
        if self.kind == 'daily':
            return 'daily %02d:%02d' % self.hm
        return 'once %s' % self.at.isoformat(timespec='minutes')


def fmt_period(seconds):
    for unit, size in (('d', 86400), ('h', 3600), ('m', 60)):
        if seconds % size == 0:
            return '%d%s' % (seconds // size, unit)
    return '%ds' % seconds
