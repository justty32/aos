"""團隊格式的時間、id 與寫檔：現在時間、解析與短格式、新 id、原子寫 JSON、只准新建的寫、讀 JSON、列資料夾裡的 JSON 檔。"""
import datetime
import json
import os
from pathlib import Path
import tempfile
import time

from aos_team_format_base import TeamError


# ------------------------------------------------------------ 時間、id、寫檔 ----

def now_iso(tz=None):
    """ISO 8601 含時區，到秒。tz：IANA 名字（例 Asia/Taipei）或 None＝本機。"""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.astimezone(_zone(tz)).isoformat(timespec='seconds')


def _zone(tz):
    if not tz:
        return None
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz)
    except Exception:  # 沒有 tzdata 或名字不對：退回本機，不讓整件事失敗
        return None


def parse_iso(text):
    try:
        return datetime.datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def short_time(iso, tz=None):
    """'09-25 10:03'（信頭用）；讀不懂就原樣。"""
    t = parse_iso(iso)
    if t is None:
        return str(iso)
    if t.tzinfo is not None:
        t = t.astimezone(_zone(tz))
    return t.strftime('%m-%d %H:%M')


def new_id(sender):
    """outbox 檔的 id：<epoch ns>-<pid>-<寄件人>（同一行程同一奈秒不會叫兩次）。"""
    return '%d-%d-%s' % (time.time_ns(), os.getpid(), sender)


def write_json(path, obj, indent=None):
    """暫存檔（. 開頭）＋rename，整份原子換；給會被重寫的檔（任務單、問題、名冊）。"""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.%s.' % path.name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(obj, out, ensure_ascii=False, indent=indent, allow_nan=False)
            out.write('\n')
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp is not None:
            Path(tmp).unlink(missing_ok=True)


def write_new(path, obj, indent=None):
    """只在不存在時建（暫存檔＋link）；建了回 True，已在回 False（不覆蓋）。給 outbox 檔與紀錄檔。"""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.%s.' % path.name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(obj, out, ensure_ascii=False, indent=indent, allow_nan=False)
            out.write('\n')
        try:
            os.link(tmp, path)
        except FileExistsError:
            return False
        return True
    finally:
        Path(tmp).unlink(missing_ok=True)


def read_json(path, where=None):
    path = Path(path)
    try:
        raw = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        raise TeamError('NotFound', '%s 不存在' % path)
    except (OSError, UnicodeError) as e:
        raise TeamError('ReadFailed', '讀不到 %s：%s' % (path, e))
    try:
        return json.loads(raw)
    except ValueError as e:
        raise TeamError('JsonSyntax', '%s 不是合法 JSON：%s' % (where or path, e))


def json_files(folder):
    """資料夾裡要處理的 *.json（不含 . 開頭的暫存檔），照名字排。"""
    try:
        return sorted(p for p in Path(folder).iterdir()
                      if p.name.endswith('.json') and not p.name.startswith('.') and p.is_file())
    except FileNotFoundError:
        return []
