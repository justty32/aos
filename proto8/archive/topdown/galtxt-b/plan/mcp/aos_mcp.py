#!/usr/bin/env python3
# aos_mcp - 把一棵 aos 資料夾樹裡有 _tooldef.json 的資料夾程式攤成 MCP tools（stdio JSON-RPC 原型，只做 initialize／tools/list／tools/call）
#
# 用法：aos_mcp.py ROOT [--ws WS] [--stack DIR] [--timeout-s N]
#   ROOT        掃這個資料夾底下的 _tooldef.json（跟著捷徑走、同一個實體只算一次、找到 _tooldef.json 就不再往下、跳過 . 開頭的）
#   --ws WS     工具的工作區（傳給 aos-exec --ws）；沒給＝$AOS_WS，再沒有＝目前資料夾
#   --stack DIR 這支 server 自己的 stack；每個工具一個小格 DIR/<工具名>/（P-17），跨呼叫延續；沒給＝$AOS_STACK，再沒有＝WS/.stack/
#   --timeout-s 一次呼叫的上限（秒，預設 600）：到了先 TERM 整群、2 秒後 KILL
# PATH 上要有 aos-exec（同 aos 的其他指令，呼叫者自己放；C-61）。
# 介面對照、為什麼這樣做：同層的 ../mcp.md。純 Python 標準庫；不用 sh（argv 直接跑 aos-exec）。
# 錯：自己的錯（參數不對、ROOT 不是資料夾）stderr 一行「aos_mcp: 代號 原因」、退 1；工具的錯不是 server 的錯，回 isError。
import json, os, re, signal, subprocess, sys

NAME = "aos_mcp"
PROTOCOL = "2025-06-18"            # 客戶端給別的版本也照它回（原型只用到三個方法，各版一樣）
GRACE_S = 2


def die(code, reason):
    print("%s: %s %s" % (NAME, code, reason), file=sys.stderr)
    sys.exit(1)


def log(text):
    print("%s: %s" % (NAME, text), file=sys.stderr, flush=True)


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def metainfo(d):
    # 找法同 thinking 10-24 metainfo 01 § 1：X/_metainfo 與 X/_metainfo.json，兩個都在＝_metainfo 贏
    for n in ("_metainfo", "_metainfo.json"):
        p = os.path.join(d, n)
        if os.path.isfile(p):
            try:
                m = read_json(p)
                return m if isinstance(m, dict) else {}
            except (OSError, ValueError) as e:
                log("_metainfo 讀不了，當沒說：%s（%s）" % (p, e))
                return {}
    return {}


def tool_name(rel):
    # MCP 的名字只收 [A-Za-z0-9_-]（客戶端多半限 64 字）；路徑的 / 換成 __
    n = re.sub(r"[^A-Za-z0-9_-]", "_", rel.replace(os.sep, "__"))
    return n[-64:]


def annotations(m):
    # 只寫 _metainfo 有說的；沒說就不寫，讓客戶端用 MCP 的保守預設（不唯讀、可能破壞、碰外界）
    a = {}
    if isinstance(m.get("summary"), str):
        a["title"] = m["summary"]
    if isinstance(m.get("side_effect"), bool):
        a["readOnlyHint"] = not m["side_effect"]
    if isinstance(m.get("idempotent"), bool):
        a["idempotentHint"] = m["idempotent"]
    r = m.get("resource")
    if isinstance(r, str):
        r = [r]
    if isinstance(r, list):
        a["openWorldHint"] = any(x in ("net", "llm", "human") for x in r)
    return a


def scan(root):
    # 先收「實體 → 路徑」：同一個實體被捷徑掛在好幾處（例 check/tools/lint、writer/tools/lint → lib/lint）只算一個，
    # 名字取實體自己那條路（路上沒有捷徑的），沒有才取先走到的
    found, seen, rroot = {}, set(), os.path.realpath(root)
    for d, dirs, files in os.walk(root, followlinks=True):
        real = os.path.realpath(d)
        rel = os.path.relpath(d, root)
        if "_tooldef.json" in files:
            dirs[:] = []                 # 工具裡面是工具自己的事（C-52），不往下找
            if real not in found or os.path.join(rroot, rel) == real:
                found[real] = rel
            continue
        if real in seen:                 # 捷徑繞回走過的資料夾：不再往下（防繞圈）
            dirs[:] = []
            continue
        seen.add(real)
        dirs[:] = sorted(x for x in dirs if not x.startswith("."))
    tools = {}
    for real, rel in sorted(found.items(), key=lambda x: x[1]):
        d = os.path.join(root, rel)
        try:
            spec = read_json(os.path.join(d, "_tooldef.json"))
        except (OSError, ValueError) as e:
            log("_tooldef.json 讀不了，跳過：%s（%s）" % (rel, e))
            continue
        name = tool_name(rel if rel != "." else os.path.basename(real))
        if name in tools:
            log("名字撞了，跳過後來的：%s（%s）" % (name, rel))
            continue
        m = metainfo(d)
        t = {"name": name,
             "description": spec.get("description", ""),
             "inputSchema": spec.get("parameters") or {"type": "object"}}
        a = annotations(m)
        if a:
            t["annotations"] = a
        if m:
            t["_meta"] = {"aos/metainfo": m}   # 原樣附上（deterministic、interrupt、time_ms…MCP 沒對應的格）
        tools[name] = (t, os.path.abspath(d))
    return tools


def run(path, name, args, ws, stack, timeout_s):
    cell = os.path.join(stack, name) + os.sep
    os.makedirs(cell, exist_ok=True)
    env = dict(os.environ, AOS_STACK=cell)
    p = subprocess.Popen(["aos-exec", "--ws", ws, path], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                         start_new_session=True)
    data = json.dumps(args, ensure_ascii=False).encode("utf-8")
    timed_out = False
    try:
        out, err = p.communicate(data, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(p.pid, signal.SIGTERM)       # aos-exec 會再轉給它的子程式群
        try:
            out, err = p.communicate(timeout=GRACE_S)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            out, err = p.communicate()
    for line in err.decode("utf-8", "replace").splitlines():
        log("[%s] %s" % (name, line))          # 下層的 stderr 不轉進結果（C-52、C-53），只進 server 自己的 stderr
    code = p.returncode if p.returncode >= 0 else 128 - p.returncode
    text = out.decode("utf-8", "replace")
    res = {"content": [{"type": "text", "text": text}]}
    if code == 0:
        return res
    note = "結束碼 %d" % code + ("（逾時，被停掉）" if timed_out else "（10＝沒事可做）" if code == 10 else "")
    res["content"].append({"type": "text", "text": note})
    if code != 10:
        res["isError"] = True
    return res


def main(argv):
    root, ws, stack, timeout_s = None, os.environ.get("AOS_WS") or ".", os.environ.get("AOS_STACK"), 600
    i = 0
    try:
        while i < len(argv):
            a = argv[i]
            if a in ("--ws", "--stack", "--timeout-s"):
                v = argv[i + 1]
                i += 2
                if a == "--ws":
                    ws = v
                elif a == "--stack":
                    stack = v
                else:
                    timeout_s = int(v)
            elif a.startswith("-"):
                die("FlagUnknown", a)
            elif root is None:
                root, i = a, i + 1
            else:
                die("ArgumentsBad", "多了一個參數：" + a)
    except (IndexError, ValueError):
        die("ArgumentsBad", "usage: aos_mcp.py ROOT [--ws WS] [--stack DIR] [--timeout-s N]")
    if root is None or not os.path.isdir(root):
        die("RootMissing", "ROOT 要是資料夾：%s" % root)
    if not os.path.isdir(ws):
        die("WsMissing", "工作區不是資料夾：%s" % ws)
    ws = os.path.abspath(ws)
    stack = os.path.abspath(stack or os.path.join(ws, ".stack"))
    tools = scan(root)
    log("%d 個工具，工作區 %s，stack %s" % (len(tools), ws, stack))

    def reply(mid, result=None, error=None):
        msg = {"jsonrpc": "2.0", "id": mid}
        msg["error" if error else "result"] = error or result
        sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    for raw in sys.stdin.buffer:
        if not raw.strip():
            continue
        try:
            req = json.loads(raw)
        except ValueError:
            reply(None, error={"code": -32700, "message": "不是 JSON"})
            continue
        method, mid, params = req.get("method"), req.get("id"), req.get("params") or {}
        if mid is None:                  # 通知（notifications/initialized 等）：不回
            continue
        if method == "initialize":
            reply(mid, {"protocolVersion": params.get("protocolVersion") or PROTOCOL,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "aos-mcp", "version": "0.1"}})
        elif method == "ping":
            reply(mid, {})
        elif method == "tools/list":
            reply(mid, {"tools": [t for t, _ in tools.values()]})
        elif method == "tools/call":
            name = params.get("name")
            if name not in tools:
                reply(mid, error={"code": -32602, "message": "沒有這個工具：%s" % name})
                continue
            args = params.get("arguments") or {}
            reply(mid, run(tools[name][1], name, args, ws, stack, timeout_s))
        else:
            reply(mid, error={"code": -32601, "message": "不支援：%s" % method})


if __name__ == "__main__":
    main(sys.argv[1:])
