"""aos-tick 的每項結束碼紀錄與格數：`.aos/tick/current.json`／`last.json`（B-633、P-213）。

只有核心寫、只在持鎖時寫；每次整份重寫（暫存檔 → rename）。

- `open()`：開格換檔（算 `seq` → 寫暫存檔 → current 換成 last（沒有 current 就刪 last）
  → 暫存檔換成 current）。
- `add_task()`／`finish()`：每項之後、收尾時整份重寫。
- **本格紀錄失效**是一個開關：任何一次寫失敗就打開，之後不再寫，stderr 只印一次
  `record_unwritable`；`path_for_task()` 回 None，呼叫者就不給之後的項設 `AOS_TICK_RECORD`。
- `--firstdo-fsync`：開格 fsync 暫存檔、第 4 步後 fsync `.aos/tick/` 目錄；每次重寫
  rename 前 fsync 暫存檔、不 fsync 目錄（B-633「落盤」那張表）。

測試用的寫入失敗注入：環境變數 `AOS_TICK_TEST_FAIL_WRITE`＝逗號分隔的「第幾次寫紀錄」
（1＝開格那次，2＝第一項之後…），到那一次就當成寫失敗。只給測試用。
"""
import json
import os
import time

__all__ = ["Record", "FAIL_WRITE_ENV"]

FAIL_WRITE_ENV = "AOS_TICK_TEST_FAIL_WRITE"

_MISSING, _BAD, _OK = "missing", "bad", "ok"


def _read_seq(path):
    """回 (狀態, seq)：檔不在＝missing；讀不懂（壞 JSON、不是物件、seq 不是正整數）＝bad。"""
    try:
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
    except FileNotFoundError:
        return _MISSING, None
    except (OSError, ValueError):
        return _BAD, None
    seq = obj.get("seq") if isinstance(obj, dict) else None
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
        return _BAD, None
    return _OK, seq


def _fail_points(env):
    raw = env.get(FAIL_WRITE_ENV, "")
    out = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


def _fsync_dir(d):
    fd = os.open(d, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Record:
    """一格的結束碼紀錄。`say(code, msg)` 是印 stderr 診斷行的函式。"""

    def __init__(self, node_dir, say, fsync=False, env=None):
        self.dir = os.path.join(node_dir, ".aos", "tick")
        self.current = os.path.join(self.dir, "current.json")
        self.last = os.path.join(self.dir, "last.json")
        self.tmp = os.path.join(self.dir, ".current.json.tmp")
        self.say = say
        self.fsync = fsync
        self.valid = False
        self.data = None
        self._writes = 0
        self._warned = False
        self._fail_at = _fail_points(os.environ if env is None else env)

    # ---- 對外 ----

    def open(self):
        """開格換檔（B-633「開格：換檔」）。成功回 True；失效回 False（任務照跑、不設紀錄變數）。"""
        cur, cur_seq = _read_seq(self.current)
        last, last_seq = _read_seq(self.last)
        if cur == _OK:
            seq = cur_seq + 1
        elif last == _OK:
            seq = last_seq + 1
        elif _BAD in (cur, last):
            # 在的那幾份全都讀不懂：當成開格失敗，兩份都不動、要人手修（B-633「舊紀錄讀不懂」）。
            # 〔最小合理〕spec 寫「兩份都壞」；一份壞、另一份不在也照這樣，免得 seq 從 1 重數。
            self.say("record_unreadable", "%s 讀不懂，要人手修；修好前每格都沒有紀錄" % self.dir)
            self._invalidate("開格讀不到舊紀錄")
            return False
        else:
            seq = 1
        self.data = {"version": 1, "seq": seq, "started_at_ms": int(time.time() * 1000),
                     "tasks": [], "ended": False}
        try:
            os.makedirs(self.dir, exist_ok=True)
            self._write_tmp()                                   # 第 2 步
            if os.path.lexists(self.current):                   # 第 3 步
                os.rename(self.current, self.last)
            elif os.path.lexists(self.last):
                os.unlink(self.last)                            # 上一格沒留下紀錄＝不知道
            os.rename(self.tmp, self.current)                   # 第 4 步
            if self.fsync:
                _fsync_dir(self.dir)
        except OSError as e:
            self._drop_tmp()
            if os.path.lexists(self.current):                   # 失效表「開格」那列
                try:
                    os.rename(self.current, self.last)
                except OSError:
                    pass
            self._invalidate("開格：%s" % e)
            return False
        self.valid = True
        return True

    def path_for_task(self):
        """給任務的 `AOS_TICK_RECORD`；本格紀錄失效後回 None（不設）。"""
        return self.current if self.valid else None

    def add_task(self, task_id, kind, value):
        """記一項：kind 是 "exit" 或 "signal"。"""
        if self.valid:
            self.data["tasks"].append({"id": task_id, kind: value})
            self._rewrite()

    def finish(self, code, stopped_after=None):
        """收尾：ended:true、exit＝整格結束碼（0／1／2），被停格檔停下時加 stopped_after。"""
        if self.valid:
            self.data["ended"] = True
            self.data["exit"] = code
            if stopped_after is not None:
                self.data["stopped_after"] = stopped_after
            self._rewrite()

    # ---- 內部 ----

    def _write_tmp(self):
        self._writes += 1
        if self._writes in self._fail_at:
            raise OSError("（測試注入）第 %d 次寫紀錄失敗" % self._writes)
        with open(self.tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False)
            f.write("\n")
            f.flush()
            if self.fsync:
                os.fsync(f.fileno())

    def _rewrite(self):
        """跑到中途的整份重寫；失敗就留著最後一次寫成功的 current.json，本格不再寫。"""
        try:
            self._write_tmp()
            os.rename(self.tmp, self.current)
        except OSError as e:
            self._drop_tmp()
            self._invalidate("中途：%s" % e)

    def _drop_tmp(self):
        try:
            os.unlink(self.tmp)
        except OSError:
            pass

    def _invalidate(self, why):
        self.valid = False
        if not self._warned:
            self._warned = True
            self.say("record_unwritable", "本格結束碼紀錄失效（%s），照表跑完、之後不再寫" % why)
