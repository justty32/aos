"""`aos-team score` 的讀檔：時間字串、Reader（壞行略過並記數）、讀成員的 events／usage、任務單、郵差投遞紀錄、真跑紀錄。"""
import json
from pathlib import Path

import aos_agent_events as events
import aos_team_format as fmt
from aos_team_format import TeamError


# ------------------------------------------------------------------ 讀檔 ----

def when(text):
    """ISO 時間 → 帶時區的 datetime（沒時區的當本機）；讀不懂＝None。"""
    t = fmt.parse_iso(text) if isinstance(text, str) else None
    if t is None:
        return None
    return t.astimezone() if t.tzinfo is None else t


class Reader:
    """讀檔、數跳過的行與檔。"""

    def __init__(self):
        self.bad_lines = 0
        self.bad_files = 0

    def jsonl(self, path):
        out = []
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        value = json.loads(line)
                    except ValueError:
                        self.bad_lines += 1
                        continue
                    if isinstance(value, dict) and when(value.get('at')) is not None:
                        out.append(value)
                    else:
                        self.bad_lines += 1
        except FileNotFoundError:
            pass
        except OSError:
            self.bad_files += 1
        return out

    def jsonl_all(self, path):
        """連輪換舊檔（<名>.1.jsonl …）一起讀，舊的在前。"""
        olds = [events.rotated(path, i) for i in range(1, 21) if events.rotated(path, i).exists()]   # 缺號也往下看
        return [row for p in reversed(olds) for row in self.jsonl(p)] + self.jsonl(path)

    def json_dir(self, folder):
        out = []
        try:
            paths = fmt.json_files(folder)
        except OSError:                                   # 資料夾讀不到（權限）：算一個跳過的檔
            self.bad_files += 1
            return out
        for path in paths:
            try:
                value = fmt.read_json(path)
            except TeamError:
                self.bad_files += 1
                continue
            if isinstance(value, dict):
                out.append(value)
            else:
                self.bad_files += 1
        return out


def load_member_logs(lay, names, rd):
    """回 ({名: [事件（去重後）]}, {名: [用量行]})。"""
    evs, use = {}, {}
    for name in names:
        home = lay.member(name)
        rows = rd.jsonl_all(home / events.EVENTS)
        good = [r for r in rows if isinstance(r.get('ev'), str) and (r.get('id') is None or isinstance(r.get('id'), str))]
        rd.bad_lines += len(rows) - len(good)             # ev 不是字串、id 不是字串或 null：壞行（去重要拿 id 當鍵）
        evs[name] = events.dedupe(good)
        use[name] = rd.jsonl_all(home / events.USAGE)
    return evs, use


def load_tasks(lay, rd):
    out = {}
    for t in rd.json_dir(lay.tasks):
        tid = t.get('id')
        if isinstance(tid, str) and fmt.TASK_ID.match(tid) and isinstance(t.get('history'), list):
            out[tid] = t
        else:
            rd.bad_files += 1
    return out


def load_sent(lay, rd):
    return [r for r in rd.json_dir(lay.post_sent) if isinstance(r.get('id'), str)]


def load_runs(path, rd):
    """--runs：JSON 陣列，或一行一個 JSON（jsonl）。每筆 {"ok": true/false, …} 或直接 true/false。回 (過, 總)。"""
    try:
        raw = Path(path).read_text(encoding='utf-8')
    except FileNotFoundError:
        raise TeamError('NotFound', '--runs 的檔 %s 不存在' % path)
    except (OSError, UnicodeError) as e:
        raise TeamError('ReadFailed', '讀不到 --runs 的檔 %s：%s' % (path, e))
    try:
        items = json.loads(raw)
        if not isinstance(items, list):
            items = [items]
    except ValueError:
        items = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except ValueError:
                rd.bad_lines += 1
    ok = total = 0
    for it in items:
        v = it.get('ok') if isinstance(it, dict) else it
        if isinstance(v, bool):
            total += 1
            ok += v
        else:
            rd.bad_lines += 1
    return ok, total
