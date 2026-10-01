"""aos-tick 的每項結束碼紀錄與格數：`.aos/tick/current/`／`last/`（B-633、P-213）。

〔使用者 2026-10-01 第九批〕「current.json這邊，也要引入指示詞，把容易被改動的弄成$ref指向其他檔案，
不容易被改動的留在current.json」：一格的紀錄是一個資料夾，裡面四個檔（各一個檔、原位）：

    record.json      開格寫一次、收尾寫一次：version、seq、started_at_ms、ended、exit、blocked_before，
                     加上 `"ran":{"$ref":"ran.json"}`、`"tasks":{"$ref":"task-exits.json"}`，
                     有 hooks 時再加 `"hooks":{"$ref":"hook-exits.json"}`
    ran.json         一個數字＝本格到目前跑了幾項 tasks（含失敗的，被停格擋掉的不算），每跑完一項重寫
    task-exits.json  結束碼不是 0 的任務 [{"id","index","exit"|"signal"}...]；開格寫 `[]`，有失敗才重寫
    hook-exits.json  {"after_all":[...]}，結束碼不是 0 的 hook；收尾時有 hooks 要跑才建（先寫 `[]`）

$ref 是相對路徑（相對於 record.json 所在資料夾），整個資料夾改名後仍指得對。
每個檔都是整份重寫（暫存檔 → rename）。只有核心寫；讀的一方用 `read_record()` 拿展開後的完整紀錄。

- `open()`：開格換紀錄（算 `seq` → 在 `.current.tmp/` 寫好 record.json、ran.json、task-exits.json →
  刪 `last/`、`current/` 整個換成 `last/`（沒有 current 就只刪 last）→ `.current.tmp/` 換成 `current/`）。
- `add_task()`：每項之後寫 ran.json；不是 exit 0 才重寫 task-exits.json。
- `finish()`：收尾寫 record.json；這格有 hooks 要跑時先寫好 hook-exits.json（`after_all: []`）再寫 record.json，
  所以 record.json 只在開格與收尾各寫一次。
- `add_hook()`：hooks（B-635）跑完一項，不是 exit 0 才重寫 hook-exits.json。
- 〔第八批〕只記結束碼不是 0 的項，每筆 `{"id","index","exit"}`（被訊號殺的是 `{"id","index","signal"}`）。
- 〔使用者方向 2026-10-01〕POC 默認紀錄寫得進、讀得懂、不斷電：不處理寫不進、舊紀錄讀不懂、
  不做 `--firstdo-fsync`；舊的 `current.json`／`last.json` 不再使用、不遷移。出事就讓 OSError／ValueError 往外丟。
"""
import json
import os
import shutil
import time

from aos_directives import Context, is_directive, load_document, resolve

__all__ = ["Record", "read_record", "RECORD", "RAN", "TASK_EXITS", "HOOK_EXITS"]

RECORD, RAN, TASK_EXITS, HOOK_EXITS = "record.json", "ran.json", "task-exits.json", "hook-exits.json"


def read_record(record_dir):
    """讀一格紀錄資料夾（`.../tick/current` 或 `.../tick/last`），回展開 `$ref` 後的完整紀錄（dict）。
    只展開頂層各鍵的值（`ran`、`tasks`、`hooks`）；資料夾或 record.json 不在回 None。"""
    path = os.path.join(record_dir, RECORD)
    if not os.path.exists(path):
        return None
    doc = load_document(path)
    ctx = Context(doc)                      # $ref 的相對檔名從 record.json 所在資料夾算
    return {k: resolve(v, ctx, [k]) if is_directive(v) else v for k, v in doc.root.items()}


def _read_seq(record_dir):
    """回這格紀錄的 `seq`（只看 record.json，不必展開）；不在回 None。"""
    path = os.path.join(record_dir, RECORD)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)["seq"]


def _write(path, value):
    """整份重寫：同資料夾暫存檔 → rename。"""
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False)
        f.write("\n")
    os.rename(tmp, path)


def _add_failed(items, item_id, index, kind, value):
    """第八批：exit 0 不記；其他記 {"id","index",kind}。回有沒有記。"""
    if kind == "exit" and value == 0:
        return False
    items.append({"id": item_id, "index": index, kind: value})
    return True


class Record:
    """一格的結束碼紀錄。任務從 `$AOS_TICK_CWD/<狀態資料夾>/tick/current/`（即 `current`）找，
    用 `read_record()` 讀展開後的完整紀錄（使用者 2026-10-01 拿掉 `AOS_TICK_RECORD`；第九批拆檔）。"""

    def __init__(self, cwd, dirname=".aos"):
        self.dir = os.path.join(cwd, dirname, "tick")      # cwd：工作資料夾；dirname：狀態資料夾名（AOS_DIRNAME）
        self.current = os.path.join(self.dir, "current")
        self.last = os.path.join(self.dir, "last")
        self.tmp = os.path.join(self.dir, ".current.tmp")
        self.meta = None             # record.json 的內容（ran／tasks／hooks 是 $ref）
        self.ran = 0
        self.tasks = []
        self.hooks = {}

    def open(self):
        """開格換紀錄（B-633「開格：換紀錄」）。"""
        cur_seq, last_seq = _read_seq(self.current), _read_seq(self.last)     # 第 1 步
        seq = (cur_seq if cur_seq is not None else last_seq if last_seq is not None else 0) + 1
        self.meta = {"version": 1, "seq": seq, "started_at_ms": int(time.time() * 1000),
                     "ran": {"$ref": RAN}, "tasks": {"$ref": TASK_EXITS}, "ended": False}
        if os.path.exists(self.tmp):                            # 第 2 步：上次開格寫到一半留下的
            shutil.rmtree(self.tmp)
        os.makedirs(self.tmp)
        _write(os.path.join(self.tmp, RAN), 0)
        _write(os.path.join(self.tmp, TASK_EXITS), [])
        _write(os.path.join(self.tmp, RECORD), self.meta)
        if os.path.exists(self.last):                           # 第 3 步
            shutil.rmtree(self.last)                            # 沒有 current 時＝上一格沒留下紀錄＝不知道
        if cur_seq is not None:
            os.rename(self.current, self.last)
        elif os.path.exists(self.current):
            shutil.rmtree(self.current)
        os.rename(self.tmp, self.current)                       # 第 4 步

    def add_task(self, task_id, index, kind, value):
        """跑完一項：ran.json 加 1；kind 是 "exit" 或 "signal"，不是 exit 0 才重寫 task-exits.json（第八批）。"""
        self.ran += 1
        if _add_failed(self.tasks, task_id, index, kind, value):
            _write(os.path.join(self.current, TASK_EXITS), self.tasks)
        _write(os.path.join(self.current, RAN), self.ran)

    def finish(self, code, blocked_before=None, hook_points=()):
        """收尾：ended:true、exit＝整格結束碼（照表跑完就是 0，任務成敗不影響），被 tasks-blocked 擋下時加
        blocked_before＝被擋下（沒跑）的那一項 id（第十六批；原 stopped_after）。
        hook_points：這格接著要跑的 hooks 掛點（目前只有 "after_all"）；有的話先寫 hook-exits.json（每個掛點 `[]`）、
        record.json 加 `hooks` 的 $ref，hook 一開跑就讀得到（B-635）。沒寫 hooks 時紀錄沒有 `hooks`。"""
        if hook_points:
            self.hooks = {p: [] for p in hook_points}
            _write(os.path.join(self.current, HOOK_EXITS), self.hooks)
            self.meta["hooks"] = {"$ref": HOOK_EXITS}
        self.meta.pop("ended")                                  # 重新放到後面：鍵的順序 ran、tasks、hooks、ended、exit…
        self.meta["ended"] = True
        self.meta["exit"] = code
        if blocked_before is not None:
            self.meta["blocked_before"] = blocked_before
        _write(os.path.join(self.current, RECORD), self.meta)

    def add_hook(self, point, hook_id, index, kind, value):
        """跑完一個 hook 項：跟 add_task 一樣只記不是 exit 0 的（index 是它在 after_all 的位置）；不記 ran。"""
        if _add_failed(self.hooks[point], hook_id, index, kind, value):
            _write(os.path.join(self.current, HOOK_EXITS), self.hooks)
