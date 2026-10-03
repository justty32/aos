"""agent 的手腳：讀信箱、搬信、goal、outbox、三個工具（send／write／none）——spec.md 第 10 節。"""
import os
import time

import aos7_mount
from aos7_fs import append_jsonl, now, read_json, read_jsonl, write_json


def inbox_dir(node):
    return os.path.join(node, "inbox")


def list_inbox(node):
    """信箱頂層的 *.json 檔名（排序；不含 done/ 與寫到一半的暫存檔）。"""
    try:
        names = os.listdir(inbox_dir(node))
    except OSError:
        return []
    return sorted(n for n in names if n.endswith(".json") and os.path.isfile(os.path.join(inbox_dir(node), n)))


def read_letters(node, names):
    """讀信；讀不到或壞掉的當成空信（body 為 None），讓它照樣被搬走、不會卡住信箱。"""
    out = []
    for n in names:
        l = read_json(os.path.join(inbox_dir(node), n))
        out.append(l if isinstance(l, dict) else {"from": None, "body": None, "bad": n})
    return out


def move_done(node, names):
    """處理過的信搬到 inbox/done/；已經不在的略過（重做 act 時會碰到）。"""
    done = os.path.join(inbox_dir(node), "done")
    os.makedirs(done, exist_ok=True)
    for n in names:
        try:
            os.replace(os.path.join(inbox_dir(node), n), os.path.join(done, n))
        except OSError:
            pass


def pending_goal(node):
    """goal.json 若要它先開口（say_first）就回 goal 內容，否則 None。"""
    g = read_json(os.path.join(node, "goal.json"))
    return g if isinstance(g, dict) and g.get("say_first") else None


def consume_goal(node):
    """goal 用掉了：goal.json 改名 goal.done.json（放在 node 裡，任務換 tid 重啟也不會再開口一次）。"""
    try:
        os.replace(os.path.join(node, "goal.json"), os.path.join(node, "goal.done.json"))
    except OSError:
        pass


def inbox_path(to):
    """收件人的 inbox 在空間裡的路徑。"""
    return to.rstrip("/") + "/inbox"


def outbox_dir(node):
    """還寄不出去的信（對方 inbox 還沒掛上）放這裡；放在 node 而不是任務資料夾，restart 換 tid 也不會丟。"""
    return os.path.join(node, "outbox")


def deliver(box, name, letter):
    """經過掛載點把信寫進對方 inbox；成功回 None，失敗回原因（收件夾被刪、被搬走、連結斷掉…；astra-2 二-5）。"""
    try:
        if not os.path.isdir(box):
            return "收件夾 %s 不在了（被刪或搬走？）" % box
        write_json(os.path.join(box, name), letter)
        return None
    except OSError as e:
        return "寫不進收件夾：%s" % e


def to_failed(node, name, letter, why):
    """寄不出去的信放 outbox/failed/，信裡記原因（`failed`）。"""
    l = dict(letter) if isinstance(letter, dict) else {"raw": letter}
    l["failed"] = {"why": why, "at": now()}
    write_json(os.path.join(outbox_dir(node), "failed", name), l)


def flush_outbox(ctx):
    """把 outbox 的信寄出：對方 inbox 已掛上就寄；加掛被拒就搬到 outbox/failed/；還在等就留著（S-23、M-6）。回結果字串清單。"""
    out, odir = [], outbox_dir(ctx["node"])
    try:
        names = sorted(n for n in os.listdir(odir) if n.endswith(".json"))
    except OSError:
        return out
    resolve = aos7_mount.resolver(ctx["task"])
    for n in names:
        src = os.path.join(odir, n)
        letter = read_json(src)
        to = letter.get("to") if isinstance(letter, dict) else None
        if not isinstance(to, str) or not to:
            st = "refused: 讀不懂的信"
        else:
            box = resolve(inbox_path(to))
            if box is not None:
                err = deliver(box, n, letter)
                if err is None:
                    os.remove(src)
                    out.append("outbox → %s：%s" % (to, letter.get("body")))
                    continue
                st = "refused: " + err
            else:
                st = aos7_mount.request(ctx["task"], inbox_path(to), why="寄信給 %s" % to)
        if st.startswith("refused"):
            to_failed(ctx["node"], n, letter, st[len("refused: "):] if st.startswith("refused: ") else st)
            try:
                os.remove(src)
            except OSError:
                pass
            out.append("outbox 的信寄不出去（%s），搬到 outbox/failed/" % st)
    return out


def inside(base, path):
    """path 是否在 base 底下（防 write 寫出自己 node）。"""
    base, path = os.path.realpath(base), os.path.realpath(path)
    return path == base or path.startswith(base + os.sep)


def do_tool(ctx, step, rnd):
    """執行一個工具動作，回一句結果（給 state.last 與 out.log）。不丟例外。"""
    tool = step.get("tool") if isinstance(step, dict) else None
    if tool == "send":
        to, body = step.get("to"), step.get("body")
        if not isinstance(to, str) or not to:
            return "send 失敗：沒有 to"
        if aos7_mount.check({"to": inbox_path(to)})[1]:
            return "send 失敗：%s 不是空間裡的路徑" % to
        me = ctx["node_id"]
        letter = {"from": me, "to": to, "round": rnd, "body": body, "at": now()}
        name = "%d-%s.json" % (time.time_ns(), me.replace("/", "_"))
        append_jsonl(os.path.join(ctx["node"], "sent.jsonl"), dict(letter, file=name))  # 寄件備份（memory 用）
        box = aos7_mount.resolver(ctx["task"])(inbox_path(to))
        if box is not None:
            err = deliver(box, name, letter)
            if err is None:
                return "send → %s：%s" % (to, body)
            to_failed(ctx["node"], name, letter, err)
            return "send 失敗：%s（信放 outbox/failed/）" % err
        st = aos7_mount.request(ctx["task"], inbox_path(to), why="寄信給 %s" % to)
        if st.startswith("refused"):
            return "send 失敗：%s 的 inbox 加掛被拒（%s）" % (to, st[len("refused: "):])
        write_json(os.path.join(outbox_dir(ctx["node"]), name), letter)
        return "send → %s 先放 outbox（inbox 沒掛，已請求加掛）：%s" % (to, body)
    if tool == "write":
        rel, text = step.get("path"), step.get("text", "")
        if not isinstance(rel, str) or not rel or os.path.isabs(rel):
            return "write 失敗：path 要是相對路徑"
        dest = os.path.join(ctx["node"], rel)
        if not inside(ctx["node"], dest):
            return "write 失敗：%s 跑出自己的 node" % rel
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(str(text))
        return "write %s（%d 字）" % (rel, len(str(text)))
    if tool == "none":
        return "none"
    return "看不懂的工具：%r" % (tool,)


def memory(node, n, skip=(), file_chars=4000):
    """給真模型的記憶（agent.json 的 "memory": n）：最近 n 封往來的信（收的在 inbox/done/、寄的在 sent.jsonl，
    依 at 排；視窗外的往來對象各再補它最近一封）＋自己 work/ 底下的檔（每檔截 file_chars 字）。skip＝這輪正要處理的信檔名（已經在 letters 裡）。"""
    hist = []
    done = os.path.join(inbox_dir(node), "done")
    try:
        names = [x for x in os.listdir(done) if x.endswith(".json") and x not in skip]
    except OSError:
        names = []
    for x in names:
        l = read_json(os.path.join(done, x))
        if isinstance(l, dict):
            hist.append({"dir": "收", "from": l.get("from"), "at": l.get("at", ""), "body": l.get("body")})
    for l in read_jsonl(os.path.join(node, "sent.jsonl")):
        hist.append({"dir": "寄", "to": l.get("to"), "at": l.get("at", ""), "body": l.get("body")})
    hist.sort(key=lambda h: str(h.get("at")))
    keep = hist[-n:] if n > 0 else []
    # 每個往來對象至少留最近一封：不讓頻繁的往來（例如跟 ci 互丟）把別人擠出視窗（R-13）
    seen = {h.get("from") or h.get("to") for h in keep}
    for h in reversed(hist[:-n] if n > 0 else hist):
        peer = h.get("from") or h.get("to")
        if peer not in seen:
            seen.add(peer)
            keep.append(h)
    keep.sort(key=lambda h: str(h.get("at")))
    files = {}
    wdir = os.path.join(node, "work")
    for dp, _, fns in os.walk(wdir):
        for fn in sorted(fns):
            fp = os.path.join(dp, fn)
            try:
                with open(fp, encoding="utf-8", errors="replace") as f:
                    files[os.path.relpath(fp, node)] = f.read(file_chars)
            except OSError:
                pass
    return {"recent_letters": keep, "my_files": files}
