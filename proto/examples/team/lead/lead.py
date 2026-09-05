#!/usr/bin/env python3
"""lead 的腦：派兩個子 agent、等兩個落點、合併寫總結。

只用標準庫，只碰自己這塊地（`work/`、`out/`、`state/`）與 `main.aos.json` 派活時
交出去的那兩個落點。它不 import aosp——機器內部長怎樣不關 agent 的事。

兩個 op（`main.aos.json` 裡各一步）：
  prep    讀兩個子寫回來的落點 out/a.done.json、out/b.done.json，
          組一份「請你把兩邊做的事講成一句」的 prompt，寫 state/req.json 投給 LLM 世界。
  report  讀回話，把兩個子提的 docstring 真的貼進 work/a.py、work/b.py，
          寫 report.md（誰改了什麼、誰先好、各幾圈）與 state/done.json。

派活本身不是這支做的：那是 main.aos.json 的兩個 `call`（mode:async）步，
由 exec 把子地登進登記表、daemon 去起 `aos run <子> --register`。
"""
import json
import os
import sys
import time

LAND = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(LAND, "state")
OUT = os.path.join(LAND, "out")
ANSWER = os.path.join(STATE, "answer.txt")

SUM_MARK = "SUM:"
TEMPLATE_LINE = "SUM: <一句話>"


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
    c.setdefault("tier", "fast")
    c.setdefault("team", [])
    return c


def drop(member):
    """一個隊員的落點三態（跟父的 `await` 步看的是同一組檔）。"""
    path = os.path.join(LAND, member["result"])
    st = path + ".status.json"
    if os.path.exists(st):
        return "failed", json.loads(read(st, "{}") or "{}"), path
    if os.path.exists(path):
        return "ok", json.loads(read(path, "{}") or "{}"), path
    return "pending", None, path


# ---------------------------------------------------------------- prep
def op_prep():
    c = cfg()
    os.makedirs(STATE, exist_ok=True)
    for p in (ANSWER, ANSWER + ".status.json"):
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass

    lines = ["你是一隊的主 agent。兩個子 agent 已經把結果寫回我指定的落點了。",
             "請把「這一隊做了什麼」講成一句話。", "",
             "== 兩邊交回來的東西 =="]
    for m in c["team"]:
        state, obj, path = drop(m)
        if state == "ok":
            lines.append("- 子 %s（%s）：%s → docstring 「%s」（跑了 %s 圈）"
                         % (m["who"], m["file"], os.path.basename(path),
                            (obj or {}).get("docstring", "?"), (obj or {}).get("rounds", "?")))
        elif state == "failed":
            lines.append("- 子 %s（%s）：壞了，%s：%s"
                         % (m["who"], m["file"], (obj or {}).get("reason"),
                            (obj or {}).get("message")))
        else:
            lines.append("- 子 %s（%s）：落點還是空的（不該走到這一步）" % (m["who"], m["file"]))
    lines += ["", "== 怎麼回話 ==", "只回一行，格式：", "    " + TEMPLATE_LINE,
              "想不到就照抄下面這行（備用答案）：",
              "    SUM: 兩個子 agent 各替一支 Python 檔加了一句 docstring，主把兩份改動合起來。"]
    prompt = "\n".join(lines) + "\n"
    write(os.path.join(STATE, "prompt.txt"), prompt)
    # 不帶 id：`aos deliver` 會發一個新的（同 id 再投會被擋，I-05）
    write(os.path.join(STATE, "req.json"), json.dumps({
        "kind": "llm",
        "prompt": "state/prompt.txt",
        "result": "state/answer.txt",
        "tier": c["tier"],
    }, ensure_ascii=False, indent=2) + "\n")
    print("主：兩邊都回來了，組了 %d 字的 prompt，投給 LLM 世界" % len(prompt))
    return 0


# ---------------------------------------------------------------- report
def pick_line(text, mark):
    """挑最後一行以 mark 開頭的（假後端 echo: 把 prompt 原樣回，備用答案在最後）。"""
    hit = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(mark) and line != TEMPLATE_LINE:
            hit = line[len(mark):].strip()
    return hit


def apply_docstring(path, doc):
    """把 docstring 貼到檔頭。已經有 docstring 就不動。"""
    body = read(path, None)
    if body is None:
        return False, "讀不到 %s" % path
    head = body.lstrip()
    if head.startswith('"""') or head.startswith("'''"):
        return False, "已經有 docstring 了，沒動"
    write(path, '"""%s"""\n\n' % doc + body)
    return True, "加了檔頭 docstring"


def op_report():
    c = cfg()
    answer = read(ANSWER, "")
    one_line = pick_line(answer, SUM_MARK) or "（LLM 沒給 SUM: 那行）"

    rows = []
    for m in c["team"]:
        state, obj, path = drop(m)
        row = {"who": m["who"], "file": m["file"], "state": state, "drop": path}
        if state == "ok":
            row.update({
                "docstring": (obj or {}).get("docstring", ""),
                "rounds": (obj or {}).get("rounds"),
                "at": (obj or {}).get("at"),
                "land": (obj or {}).get("land"),
                "finished_mtime": os.path.getmtime(path),
            })
            changed, note = apply_docstring(os.path.join(LAND, m["file"]), row["docstring"])
            row["applied"] = changed
            row["note"] = note
        else:
            row["note"] = json.dumps(obj, ensure_ascii=False) if obj else "落點是空的"
        rows.append(row)

    done = [r for r in rows if r["state"] == "ok"]
    first = min(done, key=lambda r: r["finished_mtime"])["who"] if done else None

    md = ["# 這一隊做了什麼", "",
          "LLM（假後端 echo:）給的一句話：%s" % one_line, "",
          "| 誰 | 檔 | 落點 | 幾圈 | 加了什麼 | 主做了什麼 |",
          "|---|---|---|---|---|---|"]
    for r in rows:
        md.append("| %s | %s | %s | %s | %s | %s |" % (
            r["who"], r["file"], r["state"], r.get("rounds", "-"),
            r.get("docstring", "-"), r.get("note", "-")))
    md += ["", "先寫回落點的是：子 %s" % (first or "（沒有人寫回來）"), ""]
    for r in rows:
        md.append("- 子 %s 的落點 `%s`（%s）" % (r["who"], os.path.relpath(r["drop"], LAND),
                                              r["state"]))
    write(os.path.join(LAND, "report.md"), "\n".join(md) + "\n")

    write(os.path.join(STATE, "done.json"), json.dumps({
        "why": "team_done",
        "rounds": 1,
        "one_line": one_line,
        "first_back": first,
        "members": rows,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, ensure_ascii=False, indent=2) + "\n")
    print("主：寫好 report.md，先回來的是子 %s" % first)
    return 0


OPS = {"prep": op_prep, "report": op_report}

if __name__ == "__main__":
    op = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = OPS.get(op)
    if fn is None:
        sys.stderr.write("用法：python3 lead.py prep|report\n")
        sys.exit(2)
    sys.exit(fn())
