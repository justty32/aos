"""aos7-ctl：替你寫控制檔的小工具——LLM 直接寫同樣的 JSON 檔也做得到（spec.md 第 10 節，S-01）。

    aos7-ctl daemon <root|掛載點> <op> [node] [--kill|--no-kill] [--rounds N] [--owner X] [--all] [--by WHO]
    aos7-ctl task <槽資料夾> <kill|restart> [why] [--reload] [--run N] [--id ID] [--by WHO]
    aos7-ctl add <node 資料夾> '<項目 JSON>'... [--by WHO]

daemon 控制檔用固定名 `<by>.<op>.<node>[@<owner>].json`（回條同名蓋掉，只留每個寫的人、每個 owner、每件事的上一次；W3、A2-13）。
起點是 proto7-1 lib/aos7_ctl.py。
由人或任務呼叫；只負責寫 daemon 的 .aosd/ctl/、槽內 ctl.json，或鎖住後讀改 .aos/tasks.json。
控制的接受與執行分別留給 daemon／tick／tock（spec §2.3、§6）；印出路徑不代表已執行。
"""
import argparse
import json
import os
import re
import sys

from aos7_fs import Unknown, edit_json, write_json

DAEMON_OPS = ("register", "unregister", "pause", "resume", "wake", "stop")
TASK_OPS = ("kill", "restart")


def default_by():
    """無參數；讀任務環境，回傳預設 by 字串；沒有 tid 時回 cli，node id 缺漏用 ?（spec §10）。"""
    e = os.environ
    if e.get("AOS7_TID"):
        return "%s:%s" % (e.get("AOS7_NODE_ID", "?"), e["AOS7_TID"])
    return "cli"


def ctl_dir(where):
    """將 where（daemon 根、掛入的 .aosd 或 ctl）轉成控制目錄絕對路徑（spec §10，S-23）。

    以連結的實際目標辨識種類，回傳路徑仍經原掛載點；不要求 daemon 已啟動。
    """
    where = os.path.abspath(where)
    real = os.path.realpath(where)
    if os.path.basename(real) == ".aosd":
        return os.path.join(where, "ctl")
    if os.path.basename(real) == "ctl" and os.path.basename(os.path.dirname(real)) == ".aosd":
        return where
    return os.path.join(where, ".aosd", "ctl")   # daemon 根（daemon 還沒起也行，起來才處理；2.3）


PART_MAX = 64   # 一段編碼後超過這麼長就截短加雜湊尾碼（檔名總長要在 255 bytes 內）


def enc(s):
    """檔名的一段：**無損編碼**（A3-06）。`/` 換成 `+`（node id 好讀），其他不是英數、`_`、`-` 的位元組（含 `+`、`.`、`@`、`%`、
    非 ASCII）一律 `%XX`。不同字串一定編成不同片段（以前不安全字元都換成 `_`，「甲」「乙」都變 `_` 而互蓋）；`.` 與 `@` 也被編碼，
    所以段與段的分隔不會混淆。編碼後太長：取前 40 字＋`~`＋完整字串 sha1 前 16 碼（`~` 不會出現在一般編碼裡，不會撞到短的）。"""
    import hashlib
    out = "".join(c if re.match(r"[A-Za-z0-9_-]", c) else "+" if c == "/" else
                  "".join("%%%02X" % b for b in c.encode("utf-8")) for c in s)
    if len(out) > PART_MAX:
        out = out[:40] + "~" + hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]
    return out


def fixed_name(by, op, node, owner=None):
    """由寫入者 by、動作 op、可省略的 node 與 owner 回傳固定檔名；同名回條覆寫以免累積（spec §2.3、§10）。
    A2-13：帶 owner 時檔名多一段 `@<owner>`——不同 owner 是不同控制者，daemon 處理前的待辦請求不能互相蓋掉。
    A3-06：各段用 enc 無損編碼，不同的 by／node／owner 不會撞成同一個檔名（空字串 owner 是 `@` 後面空著，跟沒帶 owner 不同）。"""
    parts = [enc(by) or "%", op] + ([enc(node)] if node is not None else [])
    name = ".".join(parts)
    if owner is not None:
        name += "@" + enc(owner)
    return name + ".json"


def daemon_ctl(root, op, node=None, kill=None, by=None, rounds=None, owner=None, all_=False, why=None):
    """向 root 寫 op 控制檔，回傳路徑；寫入失敗向呼叫者拋例外（spec §2.3、§2.4、§10）。

    node 指目標；kill 控制收程序；by／why 記來源與原因；rounds／owner／all_ 控制 pause 倒數與歸屬。
    未提供的選項不落檔，讓 daemon 採協定預設；這裡不等待回條。
    """
    by = by or default_by()
    obj = {"op": op, "by": by}
    if node is not None:
        obj["node"] = node
    if kill is not None:
        obj["kill"] = kill
    if rounds is not None:
        obj["rounds"] = rounds
    if owner is not None:
        obj["owner"] = owner
    if all_:
        obj["all"] = True
    if why:
        obj["why"] = why
    path = os.path.join(ctl_dir(root), fixed_name(by, op, node, owner))
    write_json(path, obj)
    return path


def task_ctl(slot_dir, op, why="", by=None, reload=False, run=None, id_=None):
    """向 slot_dir 寫 op（kill／restart），回傳 ctl.json 路徑；已有請求覆寫（spec §6、§10）。

    why／by 記原因與來源；reload 要求重讀任務定義；run 可限定這次執行，省略指現在這次。
    id_：這件請求的識別；沒給就自動產生一個新的（A3-05：新請求用新 id，重送同一件才用 `--id` 沿用原 id）。
    寫入失敗拋例外；請求等 tick／tock 才執行。
    """
    import uuid
    path = os.path.join(os.path.abspath(slot_dir), "ctl.json")
    obj = {"op": op, "by": by or default_by(), "why": why, "id": id_ or uuid.uuid4().hex}
    if reload:
        obj["reload"] = True
    if run is not None:
        obj["run"] = run
    write_json(path, obj)
    return path


def add_items(node, items):
    """將 items 一批加進 node 的 tasks.json，回傳檔案路徑（spec §4.1、§10）。

    拿鎖後一次 rename，避免 tick 看見半批或互蓋。既有表讀不到、壞掉或結構不合都丟 Unknown，不覆蓋它（G1）。
    """
    path = os.path.join(os.path.abspath(node), ".aos", "tasks.json")

    def fn(t):
        """以讀到的表 t 建立追加 items 的新表並回傳；缺檔從空表起，結構不符就丟 Unknown。"""
        if t is None:
            t = {"tasks": []}
        if not isinstance(t, dict) or not isinstance(t.get("tasks", []), list):
            raise Unknown("tasks.json 不是 {\"tasks\": [...]}，沒加", kind="bad")
        t = dict(t)
        t["tasks"] = list(t.get("tasks", [])) + list(items)
        return t
    edit_json(path, fn)
    return path


def main(argv=None):
    """解析 argv（None 用命令列），寫指定控制檔並印路徑；成功／說明回 0，參數錯誤回 1。"""
    ap = argparse.ArgumentParser(prog="aos7-ctl", description="寫 aos7 控制檔")
    sub = ap.add_subparsers(dest="what", required=True)
    d = sub.add_parser("daemon")
    d.add_argument("root", help="daemon 根，或掛進來的 .aosd／.aosd/ctl")
    d.add_argument("op", choices=DAEMON_OPS)
    d.add_argument("node", nargs="?")
    d.add_argument("--kill", dest="kill", action="store_true", default=None, help="stop：先 kill 所有活任務")
    d.add_argument("--no-kill", dest="kill", action="store_false", help="unregister：不殺 node 上的任務")
    d.add_argument("--rounds", type=int, help="resume：只跑這麼多回合就以同一個 owner 再 pause")
    d.add_argument("--owner", help="pause／resume 的 owner")
    d.add_argument("--all", action="store_true", help="resume：清掉所有 owner 的 pause")
    d.add_argument("--why")
    d.add_argument("--by")
    t = sub.add_parser("task")
    t.add_argument("slot_dir")
    t.add_argument("op", choices=TASK_OPS)
    t.add_argument("why", nargs="?", default="")
    t.add_argument("--reload", action="store_true", help="restart 照 node 現在 tasks.json 的同名項目")
    t.add_argument("--run", type=int, help="只在槽現在的 run 是這個時執行")
    t.add_argument("--by")
    t.add_argument("--id", help="請求識別（預設自動產生新的；重送同一件請求時沿用原 id，最多 200 字）")
    a_ = sub.add_parser("add")
    a_.add_argument("node")
    a_.add_argument("items", nargs="+")
    a_.add_argument("--by")
    try:
        a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as e:
        return 0 if e.code == 0 else 1
    if a.what == "daemon":
        if a.op not in ("stop",) and not a.node:
            print("aos7-ctl: %s 要給 node" % a.op, file=sys.stderr)
            return 1
        path = daemon_ctl(a.root, a.op, a.node, a.kill, a.by, a.rounds, a.owner, a.all, a.why)
    elif a.what == "task":
        if a.reload and a.op != "restart":
            print("aos7-ctl: --reload 只給 restart", file=sys.stderr)
            return 1
        if a.id is not None and not (0 < len(a.id) <= 200):
            print("aos7-ctl: --id 要是 1～200 字（不截斷；A3-04）", file=sys.stderr)
            return 1
        path = task_ctl(a.slot_dir, a.op, a.why, a.by, a.reload, a.run, a.id)
    else:
        try:
            items = [json.loads(x) for x in a.items]
        except ValueError as e:
            print("aos7-ctl: 項目不是 JSON：%s" % e, file=sys.stderr)
            return 1
        if not all(isinstance(i, dict) for i in items):
            print("aos7-ctl: 每個項目要是 JSON 物件", file=sys.stderr)
            return 1
        try:
            path = add_items(a.node, items)
        except Unknown as e:
            print("aos7-ctl: %s" % e, file=sys.stderr)
            return 1
    print(json.dumps({"wrote": path}, ensure_ascii=False))
    return 0
