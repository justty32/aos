"""aos-tick 的每項結束碼紀錄與格數：`.aos/tick/current.json`／`last.json`（B-633、P-213）。

只有核心寫、只在持鎖時寫；每次整份重寫（暫存檔 → rename）。

- `open()`：開格換檔（算 `seq` → 寫暫存檔 → current 換成 last（沒有 current 就刪 last）
  → 暫存檔換成 current）。
- `add_task()`／`finish()`：每項之後、收尾時整份重寫。
- 寫不進（唯讀、滿碟）不另處理（plan 待問 7〔使用者方向 2026-09-30 晚〕：默認一定寫得進去），
  OSError 照常往外丟。
- 舊紀錄讀不懂（B-633「舊紀錄讀不懂」）：兩份都不動、印 `record_unreadable`，本格沒有紀錄；
  `path_for_task()` 回 None，呼叫者就不給任務設 `AOS_TICK_RECORD`。
- `--firstdo-fsync`：開格 fsync 暫存檔、第 4 步後 fsync `.aos/tick/` 目錄；每次重寫
  rename 前 fsync 暫存檔、不 fsync 目錄（B-633「落盤」那張表）。
"""
import json
import os
import time

__all__ = ["Record"]

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


def _fsync_dir(d):
    fd = os.open(d, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Record:
    """一格的結束碼紀錄。`say(code, msg)` 是印 stderr 診斷行的函式。"""

    def __init__(self, node_dir, say, fsync=False):
        self.dir = os.path.join(node_dir, ".aos", "tick")
        self.current = os.path.join(self.dir, "current.json")
        self.last = os.path.join(self.dir, "last.json")
        self.tmp = os.path.join(self.dir, ".current.json.tmp")
        self.say = say
        self.fsync = fsync
        self.data = None                                        # None＝本格沒有紀錄

    # ---- 對外 ----

    def open(self):
        """開格換檔（B-633「開格：換檔」）。回 True；舊紀錄讀不懂時回 False（本格沒有紀錄）。"""
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
            return False
        else:
            seq = 1
        self.data = {"version": 1, "seq": seq, "started_at_ms": int(time.time() * 1000),
                     "tasks": [], "ended": False}
        os.makedirs(self.dir, exist_ok=True)
        self._write_tmp()                                       # 第 2 步
        if os.path.lexists(self.current):                       # 第 3 步
            os.rename(self.current, self.last)
        elif os.path.lexists(self.last):
            os.unlink(self.last)                                # 上一格沒留下紀錄＝不知道
        os.rename(self.tmp, self.current)                       # 第 4 步
        if self.fsync:
            _fsync_dir(self.dir)
        return True

    def path_for_task(self):
        """給任務的 `AOS_TICK_RECORD`；本格沒有紀錄（舊紀錄讀不懂）時回 None（不設）。"""
        return self.current if self.data is not None else None

    def add_task(self, task_id, kind, value):
        """記一項：kind 是 "exit" 或 "signal"。"""
        if self.data is not None:
            self.data["tasks"].append({"id": task_id, kind: value})
            self._rewrite()

    def finish(self, code, stopped_after=None):
        """收尾：ended:true、exit＝整格結束碼（0／1／2），被停格檔停下時加 stopped_after。"""
        if self.data is not None:
            self.data["ended"] = True
            self.data["exit"] = code
            if stopped_after is not None:
                self.data["stopped_after"] = stopped_after
            self._rewrite()

    # ---- 內部 ----

    def _write_tmp(self):
        with open(self.tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False)
            f.write("\n")
            f.flush()
            if self.fsync:
                os.fsync(f.fileno())

    def _rewrite(self):
        """每項之後、收尾時整份重寫（B-633「每項之後」）。"""
        self._write_tmp()
        os.rename(self.tmp, self.current)
