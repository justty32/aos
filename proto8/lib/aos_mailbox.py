"""kernel 信箱的共用部分（閘門 aos_gate、兩種 kernel 都用）。純標準庫。說明在同資料夾 kernel.md。

信箱＝一個資料夾，四格：tmp/ → new/ → cur/（N-16 Maildir），回信與旁檔在 reply/。
信＝那張要跑的 inst 本身（inst 族，C-48）：target 的 key 攤在最上層（argv、cwd、`_metainfo`、timeout_ms…），
加三個私有 key `priority`、`reply`（回信的絕對路徑 reply/<名>.json）、`sent`（epoch 秒）；
`stdin`＝旁檔 reply/<名>.stdin（呼叫者 stdin 的內容）。kernel 把 `stdout`／`stderr` 填成 reply/<名>.stdout／.stderr，
直接 `aos_inst.run(信)`（aos_inst 不認得的 key 一律忽略）。回信＝aos_inst 的結果（N-30）或 `{"error": {"code", "msg"}}`。

- `mailbox(path)`：四格建好，回 {名: 絕對路徑}。
- `side(reply_path, kind)`：回信路徑 → 旁檔路徑（kind＝stdin／stdout／stderr）。
- `read_letter(path)`：讀一封（不是物件、讀不了＝None）。
- `claim(box, name)`：new/ → cur/；被撤走了回 None。
- `reply(letter, rep)`：寫回信（照 N-05）；寫不進去＝stderr 警告。
- `run_letter(letter)`：跑一封，回 (回信 dict, 用掉的 token)；token＝stdout 旁檔最後一份的 usage.total_tokens，沒有＝0。
- `log(path, rec)`：往 log 檔追加一行 JSON（path 是 None＝不記）。

相依：aos_cli ← aos_inst ← aos_mailbox ← aos_gate ← aos_gate_kernel ← aos_kernel_judge ← aos_kernel。
"""
import json
import os

import aos_cli
import aos_inst
from aos_ctl_state import write_json

__all__ = ["claim", "log", "mailbox", "read_letter", "reply", "run_letter", "side"]


def mailbox(path):
    """信箱的四格資料夾（tmp、new、cur、reply）建好，回 {名: 絕對路徑}。"""
    box = {k: os.path.join(os.path.abspath(path), k) for k in ("tmp", "new", "cur", "reply")}
    for d in box.values():
        os.makedirs(d, exist_ok=True)
    return box


def side(reply_path, kind):
    """reply/<名>.json → reply/<名>.<kind>。"""
    base = reply_path[:-5] if reply_path.endswith(".json") else reply_path
    return base + "." + kind


def read_letter(path):
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        return doc if isinstance(doc, dict) else None
    except (OSError, ValueError):
        return None


def claim(box, name):
    """new/ → cur/；被撤走了回 None，否則回 cur/ 裡的路徑。"""
    dst = os.path.join(box["cur"], name)
    try:
        os.rename(os.path.join(box["new"], name), dst)
        return dst
    except FileNotFoundError:
        return None


def reply(letter, rep):
    try:
        write_json(letter["reply"], rep)
    except (OSError, KeyError, TypeError):
        aos_cli.warn("ReplyFailed", "回信寫不進 %r" % (letter.get("reply") if isinstance(letter, dict) else None,))


def run_letter(letter):
    """跑一封信（信＝inst），回 (回信 dict, 用掉的 token)。stdout／stderr 落在回信旁邊的旁檔。"""
    try:
        out = side(letter["reply"], "stdout")
        doc = dict(letter, stdout=out, stderr=None if letter.get("stderr_merge") else side(letter["reply"], "stderr"),
                   stdin_inherit=False, stdout_inherit=False, stdout_append=False, stdout_mkdir=False,
                   stderr_inherit=False, stderr_append=False, stderr_mkdir=False)
        try:
            result = aos_inst.run(doc)
        except aos_inst.InstError as e:
            return {"error": {"code": e.code, "msg": e.msg}, "exit": aos_inst.exit_code(e)}, 0
    except (KeyError, TypeError, AttributeError) as e:
        return {"error": {"code": "BadLetter", "msg": "信壞了：%s" % e}}, 0
    try:
        with open(out, encoding="utf-8", errors="replace") as f:
            last = aos_cli.read_stream(f.read())
    except OSError:
        last = []
    usage = last[-1].get("usage") if last and isinstance(last[-1], dict) else None
    used = usage.get("total_tokens") if isinstance(usage, dict) else None
    return result, (used if isinstance(used, int) and not isinstance(used, bool) and used >= 0 else 0)


def log(path, rec):
    if path:
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass
