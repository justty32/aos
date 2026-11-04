#!/usr/bin/env python3
"""子 agent 的腦：替主指定的那一支 Python 檔想一句 docstring，寫回主指定的落點。

只用標準庫，不 import aosp。它只寫兩個地方：自己這塊地的 `state/`，
以及主交給它的那一條落點（`$AOS_RESULT`）——那條路徑就是主開給它的寫入洞
（spec 07b：把路徑交出去這個動作本身就是授權）。

它從哪知道自己被派了什麼？三個環境變數，由 `aos run` 從登記表那筆重建：
  AOS_RESULT    主指定的落點（絕對路徑）
  AOS_CALLER    主那塊地的根
  AOS_ARG_FILE  主那塊地上的相對路徑（要加 docstring 的那支檔）
  AOS_ARG_WHO   我是誰（A 或 B）

兩個 op：
  prep   讀那支檔，組 prompt，寫 state/req.json（投給 LLM 世界）
  apply  讀回話裡的 `DOC:` 那行，寫回落點；沒有就再繞一圈，繞滿 max_rounds
         就自己替主寫一份 <落點>.status.json（不然主只會一直等到 await 逾時）
"""
import json
import os
import sys
import time

LAND = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(LAND, "state")
ROUNDS = os.path.join(STATE, "rounds")
ANSWER = os.path.join(STATE, "answer.txt")

DOC_MARK = "DOC:"
TEMPLATE_LINE = "DOC: <一句話>"


def read(path, default=""):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return default


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def cfg():
    c = json.loads(read(os.path.join(LAND, "agent.json"), "{}") or "{}")
    c.setdefault("max_rounds", 3)
    c.setdefault("tier", "fast")
    return c


def job():
    """我被派了什麼？拿不到就講清楚少了哪一個。"""
    j = {
        "result": os.environ.get("AOS_RESULT"),
        "caller": os.environ.get("AOS_CALLER"),
        "file": os.environ.get("AOS_ARG_FILE"),
        "who": os.environ.get("AOS_ARG_WHO") or "?",
    }
    missing = [k for k in ("result", "caller", "file") if not j[k]]
    if missing:
        sys.stderr.write(
            "少了環境變數：%s。\n"
            "這塊地要由主的 `call`（mode:async）派活、再由 daemon 起 "
            "`aos run <這塊地> --register` 才會有這幾個值；\n"
            "單獨跑 `aos run` 是拿不到的（登記表那筆的 result／parent／args 才是來源）。\n"
            % "、".join("AOS_" + m.upper() for m in missing))
        sys.exit(2)
    j["source"] = os.path.join(j["caller"], j["file"])
    return j


def round_no():
    try:
        return int(read(os.path.join(STATE, "round.txt"), "1").strip() or "1")
    except ValueError:
        return 1


def caller_alive(j):
    """spec 07b S-07-70：寫落點之前先確認主那塊地的 .aos/ 還在。"""
    return os.path.isdir(os.path.join(j["caller"], ".aos"))


def publish(path, text):
    """落點的發布法（07b）：暫存檔開在落點自己那個目錄 → 改名 → 刷目錄。"""
    d = os.path.dirname(path)
    tmp = os.path.join(d, os.path.basename(path) + ".tmp.%d" % os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    fd = os.open(d, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


# ---------------------------------------------------------------- prep
def op_prep():
    c = cfg()
    j = job()
    n = round_no()
    os.makedirs(STATE, exist_ok=True)
    for p in (ANSWER, ANSWER + ".status.json"):
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass

    body = read(j["source"], None)
    if body is None:
        sys.stderr.write("讀不到主派給我的檔 %s（AOS_CALLER=%s、AOS_ARG_FILE=%s）\n"
                         % (j["source"], j["caller"], j["file"]))
        sys.exit(1)
    funcs = [ln.split("(")[0][4:].strip()
             for ln in body.splitlines() if ln.startswith("def ")]

    lines = ["你是子 agent %s。主派給你一支 Python 檔，請替它想一句檔頭 docstring。" % j["who"],
             "你不用自己改檔，只要把那句話回給我；主會替你貼上去。", "",
             "== 檔 %s ==" % j["file"], body.rstrip(), "",
             "== 怎麼回話 ==", "只回一行，格式：", "    " + TEMPLATE_LINE,
             "想不到就照抄下面這行（備用答案）：",
             "    DOC: 子 %s 寫的：%s 提供 %s。"
             % (j["who"], j["file"], "、".join(funcs) or "幾個小函式"),
             "", "（現在是第 %d 圈，最多 %d 圈）" % (n, c["max_rounds"])]
    prompt = "\n".join(lines) + "\n"
    write(os.path.join(STATE, "prompt.txt"), prompt)
    write(os.path.join(ROUNDS, "%03d" % n, "prompt.txt"), prompt)
    write(os.path.join(STATE, "req.json"), json.dumps({
        "kind": "llm",
        "prompt": "state/prompt.txt",
        "result": "state/answer.txt",
        "tier": c["tier"],
    }, ensure_ascii=False, indent=2) + "\n")
    print("子 %s 第 %d 圈：讀了 %s，prompt %d 字，投給 LLM 世界"
          % (j["who"], n, j["source"], len(prompt)))
    return 0


# ---------------------------------------------------------------- apply
def pick_doc(text):
    hit = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(DOC_MARK) and line != TEMPLATE_LINE:
            hit = line[len(DOC_MARK):].strip()
    return hit


def give_up(j, n, why, message):
    """繞滿了還是沒有答案：自己替主寫 <落點>.status.json，主的 await 才看得到「壞了」。

    機器不會替脫節子地寫這個檔（見 FINDINGS-team）；不寫的話主只會一路等到
    `max_ticks` 用完，拿到的是 `await_timeout`，講不出到底是誰壞了。
    """
    if caller_alive(j):
        publish(j["result"] + ".status.json", json.dumps({
            "format_version": 1, "state": "failed", "reason": why,
            "message": message, "at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "ext": {"land": LAND, "who": j["who"], "rounds": n},
        }, ensure_ascii=False, indent=2) + "\n")
    write(os.path.join(STATE, "next.txt"), "end\n")
    write(os.path.join(STATE, "done.json"), json.dumps(
        {"why": why, "message": message, "rounds": n, "who": j["who"]},
        ensure_ascii=False, indent=2) + "\n")
    print("子 %s 收工（%s）：%s" % (j["who"], why, message))
    return 0


def op_apply():
    c = cfg()
    j = job()
    n = round_no()
    answer = read(ANSWER, "")
    write(os.path.join(ROUNDS, "%03d" % n, "answer.txt"), answer)

    doc = pick_doc(answer)
    if doc is None:
        if n >= c["max_rounds"]:
            return give_up(j, n, "no_doc",
                           "繞了 %d 圈，LLM 都沒給 `DOC:` 那行" % n)
        write(os.path.join(STATE, "round.txt"), "%d\n" % (n + 1))
        write(os.path.join(STATE, "next.txt"), "prep\n")
        print("子 %s 第 %d 圈：回話裡沒有 DOC: 那行，再繞一圈" % (j["who"], n))
        return 0

    if not caller_alive(j):
        return give_up(j, n, "caller_gone",
                       "主那塊地 %s 的 .aos/ 不在了，不往落點寫（07b S-07-70）" % j["caller"])

    publish(j["result"], json.dumps({
        "format_version": 1,
        "who": j["who"],
        "land": LAND,
        "file": j["file"],
        "docstring": doc,
        "rounds": n,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    }, ensure_ascii=False, indent=2) + "\n")
    write(os.path.join(STATE, "next.txt"), "end\n")
    write(os.path.join(STATE, "done.json"), json.dumps(
        {"why": "wrote_result", "message": doc, "rounds": n, "who": j["who"],
         "result": j["result"]}, ensure_ascii=False, indent=2) + "\n")
    print("子 %s 第 %d 圈：寫回落點 %s" % (j["who"], n, j["result"]))
    return 0


OPS = {"prep": op_prep, "apply": op_apply}

if __name__ == "__main__":
    op = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = OPS.get(op)
    if fn is None:
        sys.stderr.write("用法：python3 worker.py prep|apply\n")
        sys.exit(2)
    sys.exit(fn())
