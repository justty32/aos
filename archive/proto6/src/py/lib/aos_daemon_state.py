"""aos-daemon 的記住狀態模組（plan m3m-daemon-modules.md 模組三）。

設定檔寫 `"modules": {"state": {"$ref": "aos-state.json"}}` 時掛上（使用者 2026-10-01：「"state":{"$ref":...}
會比較好，因為有時候它會頻繁被改動。」）。`$ref` 指的檔（以設定檔所在資料夾為準，跟其他 `$ref` 一樣）
就是狀態檔；展開後 `modules.state` 就是目前狀態：

    {"insts": {"a": {"paused": true}, "jobs/report.json": {"stopped": true}}}

只列不正常的項，每項只寫是 true 的那幾個。檔不在＝全部正常（不算設定錯），第一次要寫時才建。

- 開起來時（`restore()`）：還在 `insts` 裡的項照檔恢復暫停、已停，這些項開起來不先跑那一次；
  不在 `insts` 裡的鍵丟掉（下一次寫檔時就不見了）。
- 每次某一項的暫停或已停變了（pause、resume、stop_on_nonzero 停掉、重讀設定拿掉項）就當場寫整份
  （`StateFile.save()`）：先寫同資料夾的暫檔再 rename。內容跟上次寫的（或開起來時讀到的）一樣就不寫。
- 不記待補、上次結束時間、last_exit（S1：第一版不記）。

〔使用者方向 2026-10-01〕POC 默認一切正常：檔寫得進、讀得懂、沒有別的 daemon 共用。
"""
import json
import os
import threading

from aos_daemon import say

FLAGS = ("paused", "stopped")


def restore(items, data):
    """照狀態檔內容恢復各項的暫停、已停，並在 stdout 印跟平常同樣的行。items＝[Item]。"""
    saved = data.get("insts", {})
    for item in items:
        flags = saved.get(item.inst, {})
        for f in FLAGS:
            if flags.get(f) is True:
                setattr(item, f, True)
                say("inst=%s %s" % (item.inst, f))


def dump(items):
    """[Item] → 狀態檔的內容（只列不正常的項）。"""
    out = {}
    for item in items:
        flags = {f: True for f in FLAGS if getattr(item, f)}
        if flags:
            out[item.inst] = flags
    return {"insts": out}


class StateFile:
    """一個狀態檔。`last`＝上次寫出（或開起來時讀到）的內容；檔不在時當成 `{"insts": {}}`。"""

    def __init__(self, path, data):
        self.path = path
        self.last = data
        self.lock = threading.Lock()

    def save(self, items):
        """在鎖底下照目前各項的狀態算一次整份，跟上次不同才寫（暫檔 → rename）。
        拍照也在鎖底下，所以後寫的一定包含先發生的變動。"""
        with self.lock:
            data = dump(items)
            if data == self.last:
                return
            tmp = os.path.join(os.path.dirname(self.path), "." + os.path.basename(self.path) + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
            os.replace(tmp, self.path)
            self.last = data
