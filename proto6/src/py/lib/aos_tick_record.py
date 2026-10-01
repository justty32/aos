"""aos-tick 的每項結束碼紀錄與格數：`.aos/tick/current.json`／`last.json`（B-633、P-213）。

只有核心寫；每次整份重寫（暫存檔 → rename）。

- `open()`：開格換檔（算 `seq` → 寫暫存檔 → current 換成 last（沒有 current 就刪 last）
  → 暫存檔換成 current）。
- `add_task()`／`finish()`：每項之後、收尾時整份重寫。
- `start_hooks()`／`add_hook()`：hooks（B-635）在收尾之後記 `hooks.after_all`，一樣整份重寫。
- 〔使用者 2026-10-01 第八批〕「tasks如果結果是0，那就不用紀錄了。hooks也是。」：`tasks`、`hooks.after_all`
  只記結束碼不是 0 的項，每筆 `{"id","index","exit"}`（被訊號殺的是 `{"id","index","signal"}`）；
  另有 `ran`＝本格到目前跑了幾項 tasks（含失敗的，被停格擋掉的不算），每跑完一項就加 1。hooks 不另記 ran。
- 〔使用者方向 2026-10-01〕POC 默認紀錄寫得進、讀得懂、不斷電：不處理寫不進（待問 7）、
  舊紀錄讀不懂（`record_unreadable`）、不做 `--firstdo-fsync`。出事就讓 OSError／ValueError 往外丟。
"""
import json
import os
import time

__all__ = ["Record"]


def _read_seq(path):
    """回這份紀錄的 `seq`；檔不在回 None。"""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)["seq"]


def _add_failed(items, item_id, index, kind, value):
    """第八批：exit 0 不記；其他記 {"id","index",kind}。"""
    if not (kind == "exit" and value == 0):
        items.append({"id": item_id, "index": index, kind: value})


class Record:
    """一格的結束碼紀錄。任務從 `$AOS_TICK_CWD/<狀態資料夾>/tick/current.json`（即 `current`）找（使用者 2026-10-01 拿掉 `AOS_TICK_RECORD`）。"""

    def __init__(self, cwd, dirname=".aos"):
        self.dir = os.path.join(cwd, dirname, "tick")      # cwd：工作資料夾；dirname：狀態資料夾名（AOS_DIRNAME）
        self.current = os.path.join(self.dir, "current.json")
        self.last = os.path.join(self.dir, "last.json")
        self.tmp = os.path.join(self.dir, ".current.json.tmp")
        self.data = None

    def open(self):
        """開格換檔（B-633「開格：換檔」）。"""
        cur_seq, last_seq = _read_seq(self.current), _read_seq(self.last)    # 第 1 步
        seq = (cur_seq if cur_seq is not None else last_seq if last_seq is not None else 0) + 1
        self.data = {"version": 1, "seq": seq, "started_at_ms": int(time.time() * 1000),
                     "ran": 0, "tasks": [], "ended": False}
        os.makedirs(self.dir, exist_ok=True)
        self._write_tmp()                                       # 第 2 步
        if cur_seq is not None:                                 # 第 3 步
            os.rename(self.current, self.last)
        elif last_seq is not None:
            os.unlink(self.last)                                # 上一格沒留下紀錄＝不知道
        os.rename(self.tmp, self.current)                       # 第 4 步

    def add_task(self, task_id, index, kind, value):
        """跑完一項：`ran` 加 1；kind 是 "exit" 或 "signal"，不是 exit 0 才記進 `tasks`（第八批）。"""
        self.data["ran"] += 1
        _add_failed(self.data["tasks"], task_id, index, kind, value)
        self._rewrite()

    def finish(self, code, stopped_after=None):
        """收尾：ended:true、exit＝整格結束碼（照表跑完就是 0，任務成敗不影響），被停格檔停下時加 stopped_after。"""
        self.data["ended"] = True
        self.data["exit"] = code
        if stopped_after is not None:
            self.data["stopped_after"] = stopped_after
        self._rewrite()

    def start_hooks(self, point):
        """hooks（B-635）：收尾之後、跑第一個 hook 前寫 `hooks.<掛點>: []`（目前只有 after_all）。"""
        self.data.setdefault("hooks", {})[point] = []
        self._rewrite()

    def add_hook(self, point, hook_id, index, kind, value):
        """跑完一個 hook 項：跟 add_task 一樣只記不是 exit 0 的（index 是它在 after_all 的位置）；不記 ran。"""
        _add_failed(self.data["hooks"][point], hook_id, index, kind, value)
        self._rewrite()

    def _write_tmp(self):
        with open(self.tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False)
            f.write("\n")

    def _rewrite(self):
        """每項之後、收尾時整份重寫（B-633「每項之後」）。"""
        self._write_tmp()
        os.rename(self.tmp, self.current)
