"""aos_ai_make - aos-ai 的「生成」：產 JSON（inst、loop、fsm、daemon、metainfo、tool_json）與骨架（工具、fsm 格、函數資料夾）。

使用者 10-24「aos工具集這邊，也要包括方便生成相關json和工具的。」；設計與代定見 proto8/thinking/2026-10-24-ai-tools.md § 生成。
只「生成」：已經存在的 JSON 要改，交給 aos-json（proto8/impls/aos-json，另一套 JSON 修改工具集）；有它就用它的 set／check，沒有才自己寫。"""
import json, os, shutil, subprocess
from pathlib import Path

INST_KEYS = ("argv", "cwd", "envs", "stdin", "stdout", "stderr", "stdout_append", "stderr_append", "timeout_ms", "grace_ms")
LOOP_ENTRY = ["aos-loop", {"$env": "AOS_CF"}]
FSM_ENTRY = ["aos-fsm", {"$env": "AOS_CF"}]
DAEMON_ENTRY = ["aos-daemon", {"$env": "AOS_CF"}]
META_NUM = ("time_ms", "mem_mb", "gpu_mem_mb", "llm_calls", "llm_tokens", "cost")
META_BOOL = ("side_effect", "idempotent", "deterministic", "parallel")
JSON_TYPES = ("string", "number", "integer", "boolean", "object", "array")


class MakeBad(Exception):
    """生成的參數或結果不合（aos-ai 轉成 stderr 一行）。"""

    def __init__(self, code, reason, hint=None):
        super().__init__(code)
        self.code, self.reason, self.hint = code, reason, hint


def bad(why, hint=None):
    raise MakeBad("SpecBad", why, hint)


def loads(text, what):
    try:
        return json.loads(text)
    except ValueError as e:
        bad("%s 不是 JSON：%s" % (what, e))


def value(text):
    """命令列上的一個值：像 JSON 的（{ [ 數字 true false null "）照 JSON 讀，其他當字串。"""
    t = text.strip()
    if t[:1] in "{[\"" or t in ("true", "false", "null") or t.lstrip("-").replace(".", "", 1).isdigit():
        return loads(t, repr(text))
    return text


def opt(o, k, default=None):
    return o.get(k, [default])[-1]


def base_spec(o):
    spec = loads(opt(o, "spec"), "--spec") if opt(o, "spec") else {}
    if not isinstance(spec, dict):
        bad("--spec 要是 JSON 物件")
    for kv in o.get("set", []):                          # --set key=值（值照 value() 讀）
        if "=" not in kv:
            bad("--set 要寫 key=值：%s" % kv)
        k, v = kv.split("=", 1)
        spec[k] = value(v)
    return spec


# ---------- 形狀檢查（只看 aos 讀的那幾格；其他 key 照 C-48 忽略） ----------

def is_directive(v):
    return isinstance(v, dict) and ("$env" in v or "$ref" in v)


def check_inst(x, where):
    if not isinstance(x, dict):
        bad("%s：單子要是物件" % where)
    argv = x.get("argv")
    if not is_directive(argv) and not (isinstance(argv, list) and argv and
                                       all(isinstance(a, str) or is_directive(a) for a in argv)):
        bad("%s：argv 要是非空陣列（字串或指示詞）" % where)
    for k in ("cwd", "stdin", "stdout", "stderr"):
        if k in x and not (x[k] is None or isinstance(x[k], str) or is_directive(x[k])):
            bad("%s：%s 要是字串路徑" % (where, k))
    if "timeout_ms" in x and not (x["timeout_ms"] is None or (type(x["timeout_ms"]) is int and x["timeout_ms"] > 0)):
        bad("%s：timeout_ms 要是正整數" % where)
    if "grace_ms" in x and not (type(x["grace_ms"]) is int and x["grace_ms"] >= 0):
        bad("%s：grace_ms 要是非負整數" % where)
    if "envs" in x and not (isinstance(x["envs"], dict) and all(isinstance(v, str) or is_directive(v) for v in x["envs"].values())):
        bad("%s：envs 要是 {名: 字串}" % where)


def check_exec(x, where):
    """exec＝字串（aos-exec 的目標）、[目標, 參數...]、或單子物件（10-24 起）。"""
    if isinstance(x, str) and x:
        return
    if isinstance(x, list) and x and all(isinstance(a, str) or is_directive(a) for a in x):
        return
    if isinstance(x, dict) and not is_directive(x):
        return check_inst(x, where)
    if is_directive(x):
        return
    bad("%s：exec 要是非空字串、[目標, 參數...] 或單子物件" % where)


def nonneg(x, k, where):
    if k in x and not (type(x[k]) is int and x[k] >= 0):
        bad("%s：%s 要是非負整數" % (where, k))


def check_loop(x, where="loop.json"):
    if "exec" not in x:
        bad("%s：沒有 exec（要跑什麼）" % where)
    check_exec(x["exec"], where + "#/exec")
    for k in ("max", "interval_ms"):
        nonneg(x, k, where)


def check_fsm(x):
    states = x.get("states")
    if not isinstance(states, dict) or not states:
        bad("fsm.json：states 要是非空物件")
    if x.get("start") not in states:
        bad("fsm.json：start（%r）不在 states 裡" % x.get("start"))
    for name, cell in states.items():
        if not isinstance(cell, dict) or "exec" not in cell:
            bad("fsm.json：格 %s 沒有 exec" % name)
        check_exec(cell["exec"], "fsm.json#/states/%s/exec" % name)
        if not isinstance(cell.get("next"), str) or cell["next"] not in states:
            bad("fsm.json：格 %s 的 next（%r）不在 states 裡" % (name, cell["next"]))


def check_daemon(x):
    for k in ("max", "interval_ms"):
        nonneg(x, k, "daemon.json")
    if "exec" in x:
        check_exec(x["exec"], "daemon.json#/exec")
    loops = x.get("loops", {})
    if not isinstance(loops, dict):
        bad("daemon.json：loops 要是物件")
    for name, sub in loops.items():
        if not name or name.startswith(".") or "/" in name or "#" in name:
            bad("daemon.json：子項名字不合：%r" % name)
        if isinstance(sub, dict) and not is_directive(sub):
            check_loop(sub, "daemon.json#/loops/" + name)
        else:
            check_exec(sub, "daemon.json#/loops/" + name)


def check_metainfo(x):
    for k in META_NUM:
        v = x.get(k)
        if v is not None and not (isinstance(v, (int, float)) and not isinstance(v, bool)) and \
                not (isinstance(v, dict) and isinstance(v.get("val"), (int, float))):
            bad("_metainfo：%s 要是數字或 {\"val\": 數字, \"max\": …}" % k)
    for k in META_BOOL:
        if k in x and not isinstance(x[k], bool):
            bad("_metainfo：%s 要是 true／false" % k)
    r = x.get("resource")
    if r is not None and not (isinstance(r, str) or (isinstance(r, list) and all(isinstance(i, str) for i in r))):
        bad("_metainfo：resource 要是字串或字串陣列")
    if "interrupt" in x and x["interrupt"] not in ("safe", "unsafe", "resumable"):
        bad("_metainfo：interrupt 只認 safe／unsafe／resumable")
    if "priority" in x:
        bad("_metainfo：priority 不放這裡（跟著請求、由呼叫者填；M5）")


def check_tool_json(x):
    if not isinstance(x.get("description"), str) or not x["description"].strip():
        bad("_tooldef.json：要有 description（給模型看的一句話）")
    p = x.get("parameters")
    if not isinstance(p, dict) or p.get("type") != "object" or not isinstance(p.get("properties", {}), dict):
        bad("_tooldef.json：parameters 要是 {\"type\": \"object\", \"properties\": {...}}")
    for r in p.get("required", []):
        if r not in p.get("properties", {}):
            bad("_tooldef.json：required 的 %s 不在 properties 裡" % r)


# ---------- 各種 JSON 怎麼從參數生出來 ----------

def gen_inst(o):
    x = base_spec(o)
    if opt(o, "argv"):
        x["argv"] = value(opt(o, "argv")) if opt(o, "argv").lstrip()[:1] == "[" else opt(o, "argv").split()
    for k in ("cwd", "stdin", "stdout", "stderr"):
        if opt(o, k):
            x[k] = value(opt(o, k))
    for k in ("timeout-ms", "grace-ms"):
        if opt(o, k):
            x[k.replace("-", "_")] = int(opt(o, k))
    if opt(o, "envs"):
        x["envs"] = loads(opt(o, "envs"), "--envs")
    check_inst(x, "單子")
    return x


def gen_loop(o):
    x = base_spec(o)
    if opt(o, "exec"):
        x["exec"] = value(opt(o, "exec"))
    for k in ("max", "interval-ms"):
        if opt(o, k):
            x[k.replace("-", "_")] = int(opt(o, k))
    for k in ("ctl", "state"):
        if opt(o, k):
            x[k] = opt(o, k)
    if opt(o, "entry") != "no":
        x.setdefault("_entry", LOOP_ENTRY)
    check_loop(x)
    return x


def pair(text, flag):
    if "=" not in text:
        bad("%s 要寫 名=值：%s" % (flag, text))
    k, v = text.split("=", 1)
    return k.strip(), v


def gen_fsm(o):
    """--cell 名=exec（exec 是 JSON 單子／陣列或字串目標），可重複、照順序；--next 名=下一格，沒給＝照順序的下一格、最後一格回 start。"""
    x = base_spec(o)
    states = x.setdefault("states", {})
    for c in o.get("cell", []):
        name, rest = pair(c, "--cell")
        states[name] = {"exec": value(rest)}
    if opt(o, "start"):
        x["start"] = opt(o, "start")
    elif states:
        x.setdefault("start", next(iter(states)))
    for c in o.get("next", []):
        name, nxt = pair(c, "--next")
        if name not in states:
            bad("--next 的 %s 不是格" % name)
        states[name]["next"] = nxt.strip()
    names = list(states)
    for i, n in enumerate(names):
        if isinstance(states[n], dict) and "next" not in states[n]:
            states[n]["next"] = names[i + 1] if i + 1 < len(names) else x.get("start")
    if opt(o, "entry") != "no":
        x.setdefault("_entry", FSM_ENTRY)
    check_fsm(x)
    return {"_entry": x.pop("_entry"), **x} if "_entry" in x else x


def gen_daemon(o):
    x = base_spec(o)
    loops = x.setdefault("loops", {})
    for c in o.get("loop", []):
        if "=" not in c:
            bad("--loop 要寫 名=exec 或 名={loop.json 的內容}：%s" % c)
        name, rest = c.split("=", 1)
        loops[name.strip()] = value(rest)
    for k in ("max", "interval-ms"):
        if opt(o, k):
            x[k.replace("-", "_")] = int(opt(o, k))
    for k in ("ctl", "state", "exec"):
        if opt(o, k):
            x[k] = value(opt(o, k)) if k == "exec" else opt(o, k)
    if opt(o, "entry") != "no":
        x.setdefault("_entry", DAEMON_ENTRY)
    check_daemon(x)
    return x


def gen_metainfo(o):
    x = base_spec(o)
    if opt(o, "summary"):
        x["summary"] = opt(o, "summary")
    for k in META_NUM:
        if opt(o, k.replace("_", "-")):
            x[k] = value(opt(o, k.replace("_", "-")))
    for k in META_BOOL:
        if opt(o, k.replace("_", "-")):
            x[k] = value(opt(o, k.replace("_", "-")))
    if opt(o, "resource"):
        r = [s for s in opt(o, "resource").split(",") if s]
        x["resource"] = r[0] if len(r) == 1 else r
    if opt(o, "interrupt"):
        x["interrupt"] = opt(o, "interrupt")
    check_metainfo(x)
    return x


def parse_param(text):
    """--param 名:型別[:說明][:required]，例 expr:string:要算的式子:required。"""
    parts = text.split(":")
    if len(parts) < 2 or parts[1] not in JSON_TYPES:
        bad("--param 要寫 名:型別[:說明][:required]，型別是 %s：%s" % ("／".join(JSON_TYPES), text))
    required = parts[-1] == "required"
    if required:
        parts = parts[:-1]
    prop = {"type": parts[1]}
    if len(parts) > 2:
        prop["description"] = ":".join(parts[2:])
    return parts[0], prop, required


def gen_tool_json(o):
    x = base_spec(o)
    if opt(o, "description"):
        x["description"] = opt(o, "description")
    params = x.setdefault("parameters", {"type": "object", "properties": {}})
    for p in o.get("param", []):
        name, prop, req = parse_param(p)
        params.setdefault("properties", {})[name] = prop
        if req:
            params.setdefault("required", []).append(name)
    check_tool_json(x)
    return x


GEN = {"inst": gen_inst, "loop": gen_loop, "fsm": gen_fsm, "daemon": gen_daemon, "metainfo": gen_metainfo,
       "tool_json": gen_tool_json}


# ---------- 寫檔與 aos-json ----------

def dump(x):
    return json.dumps(x, ensure_ascii=False, indent=1) + "\n"


def write_new(path, text, force=False, mode=None):
    """原子寫入（先寫 . 開頭暫存再改名，N-05）；已存在又沒 --force＝FileExists。"""
    path = Path(path)
    if path.exists() and not force:
        raise MakeBad("FileExists", "已經有了：%s" % path, "換位置，或加 --force 蓋過；改既有的 JSON 用 aos-json")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    if mode:
        os.chmod(tmp, mode)
    os.replace(tmp, path)


def aos_json_check(which, env, path):
    """有 aos-json 就跑它的 check（$ref 指得到、指示詞寫法、exec 形狀）；回 None＝沒有 aos-json。"""
    prog = which("aos-json")
    if not prog:
        return None
    r = subprocess.run([prog, "check", str(path)], capture_output=True, text=True, env=env, cwd=Path(path).parent)
    return {"ok": r.returncode == 0, "problems": [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]}


def aos_json_set(which, env, target, val):
    """改既有 JSON 交給 aos-json set；沒有 aos-json 才自己讀－改－原子寫（只做 /a/b 這種簡單指標）。回用的是誰。"""
    prog = which("aos-json")
    if prog:
        r = subprocess.run([prog, "set", "--parents", target, json.dumps(val, ensure_ascii=False)],
                           capture_output=True, text=True, env=env)
        if r.returncode != 0:
            raise MakeBad("EditFailed", "aos-json set 失敗：%s" % (r.stderr.strip() or r.stdout.strip()))
        return "aos-json"
    f, _, ptr = target.partition("#")
    doc = json.loads(Path(f).read_text(encoding="utf-8"))
    node, keys = doc, [k.replace("~1", "/").replace("~0", "~") for k in ptr.strip("/").split("/")]
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = val
    write_new(f, dump(doc), force=True)
    return "aos-ai"


# ---------- 骨架 ----------

PY_TOOL = '''#!/usr/bin/env python3
# {name} - {desc}
# 介面（P-41）：stdin 收模型給的 arguments（JSON），stdout 整段是結果；自己的錯 stderr 一行「{name}: 代號 原因」、退 1。
import json, sys


def bad(code, reason):
    print("{name}: %s %s" % (code, reason), file=sys.stderr)
    sys.exit(1)


try:
    args = json.loads(sys.stdin.read() or "{{}}")
except ValueError as e:
    bad("ArgumentsBad", "stdin 不是 JSON：%s" % e)
{reads}
# TODO：在這裡做事，結果印到 stdout
print(json.dumps({{"ok": True, "args": args}}, ensure_ascii=False))
'''

SH_TOOL = '''#!/bin/sh
# {name} - {desc}
# 介面（P-41）：stdin 收模型給的 arguments（JSON），stdout 整段是結果；自己的錯 stderr 一行「{name}: 代號 原因」、退 1。
args=$(cat)
# TODO：在這裡做事，結果印到 stdout
printf '%s\\n' "$args"
'''

SH_CELL = '''#!/bin/sh
# {name} - fsm 的一格：退 0＝往下一格，退 10＝請 loop 停，其他非 0＝失敗、state 不動（P-19、P-20）
# 跑的時候 cwd＝這個資料夾，$AOS_WS＝工作區，$AOS_STACK＝這台 fsm 的 stack（格之間要傳的東西寫成那裡的檔，P-10）
exit 0
'''

SH_FUNC = '''#!/bin/sh
# {name} - {desc}
# 函數＝資料夾程式：aos-exec 跑這個 _entry（cwd＝這個資料夾）；特性寫在旁邊的 _metainfo（給 kernel 與人看，aos-exec 不讀）
echo "{name}: hello from $AOS_WS"
'''


def scaffold_tool(tools_dir, name, o):
    desc = opt(o, "description") or "TODO 一句話說這個工具做什麼"
    tj = gen_tool_json({**o, "description": [desc]})
    lang = opt(o, "lang", "python")
    if lang not in ("python", "sh"):
        bad("--lang 只認 python、sh")
    d = Path(tools_dir) / name
    if d.exists():
        raise MakeBad("ToolExists", "已經有工具 %s：%s" % (name, d), "換名字；改它用 aos-json 或直接編輯")
    props = tj["parameters"].get("properties", {})
    reads = "".join('%s = args.get("%s")\n' % (k if k.isidentifier() else "arg_" + k, k) for k in props)
    entry = (PY_TOOL if lang == "python" else SH_TOOL).format(name=name, desc=desc.replace("\n", " "), reads=reads)
    write_new(d / "_tooldef.json", dump(tj))
    write_new(d / "_entry", entry, mode=0o755)
    files = ["_tooldef.json", "_entry"]
    meta = gen_metainfo(o) if any(k in o for k in ("summary", "resource", "time-ms", "side-effect")) else None
    if meta:
        write_new(d / "_metainfo", dump(meta))
        files.append("_metainfo")
    return {"path": str(d), "files": files, "tool_json": tj}


def scaffold_func(d, o):
    d = Path(d)
    if (d / "_entry").exists() or (d / "_entry.json").exists():
        raise MakeBad("FileExists", "已經有入口了：%s" % d)
    name = d.name
    desc = opt(o, "summary") or "TODO 一句話說這個函數做什麼"
    if opt(o, "inst") or opt(o, "argv"):          # 入口是單子（沒 +x 的 JSON，C-73、P-40）
        inst = gen_inst({**o, "spec": [opt(o, "inst")] if opt(o, "inst") else []})
        write_new(d / "_entry", dump(inst))
    else:
        write_new(d / "_entry", SH_FUNC.format(name=name, desc=desc), mode=0o755)
    meta = gen_metainfo({**o, "summary": [desc]})
    write_new(d / "_metainfo", dump(meta))
    return {"path": str(d), "files": ["_entry", "_metainfo"], "metainfo": meta}


# ---------- 欄位說明（生成時附上，幫 AI 邊做邊懂；--no-notes 關掉） ----------

NOTES = {
    "_entry": "入口：aos-exec 這份 JSON 時跑的就是它；[\"aos-loop\"/\"aos-fsm\", {\"$env\": \"AOS_CF\"}]＝把自己（AOS_CF＝這份檔）交給那支程式（N-61、explain entry）",
    "exec": "要跑什麼：字串＝aos-exec 的目標（資料夾、檔、檔#/指標）、陣列＝[目標, 參數...]、物件＝內嵌單子，行程內跑（explain inline）",
    "max": "最多跑幾次，沒寫＝不限（P-06）",
    "interval_ms": "上一次結束到下一次開始至少隔幾毫秒（N-32）",
    "ctl": "ctl 窗的檔名，在 $AOS_STACK 底下；誰都能寫、loop 只讀（explain window）",
    "state": "state 窗的檔名，在 $AOS_STACK 底下；只有 loop 自己寫（explain window）",
    "start": "fsm 的起始格；$AOS_STACK/state.txt 沒有時從這格開始（explain fsm）",
    "states": "fsm 的整張表：每格 {exec, next}，格退 0 才換到 next（explain fsm）",
    "loops": "daemon 顧的子 loop：名字→目標或一份 loop.json；小格＝$AOS_STACK/<名字>/（explain daemon）",
    "argv": "單子要跑的程式與參數；argv[0] 沒 / 照 PATH 找（explain inst）",
    "cwd": "單子的工作資料夾，相對路徑從入口所在的資料夾算",
    "envs": "疊在現有環境上的環境變數",
    "stdin": "stdin 從哪個檔讀（沒寫＝接呼叫者的）",
    "stdout": "stdout 寫到哪個檔（覆寫；沒寫＝接呼叫者的）；常見 {\"$env\": \"AOS_STACK\", \"$path\": \"out.txt\"}",
    "stderr": "stderr 寫到哪個檔（覆寫；沒寫＝接呼叫者的）",
    "timeout_ms": "到了先 SIGTERM 整群、過 grace_ms 再 SIGKILL；被收掉的碼是 143（explain exit）",
    "grace_ms": "SIGTERM 後等多久才 SIGKILL，預設 2000",
    "summary": "一句話說這個函數做什麼（給 kernel／人看）",
    "time_ms": "宣告跑一次多久：數字＝典型值，{val, max}＝典型與上限；不是逾時（逾時是單子的 timeout_ms）",
    "resource": "佔哪幾種格：llm／gpu／cpu／disk／net／human，可自訂",
    "side_effect": "會不會動到自己 stack 以外的東西",
    "idempotent": "同樣輸入重跑一次結果一樣",
    "deterministic": "同樣輸入每次輸出一樣（問腦的通常 false）",
    "interrupt": "被殺掉會怎樣：safe／unsafe／resumable",
    "parallel": "同一個函數能不能同時跑好幾份",
    "description": "給模型看的一句話：這個工具做什麼、什麼時候用（P-41）",
    "parameters": "JSON Schema：模型給的 arguments 長怎樣；工具從 stdin 收到的就是它（P-41）",
}


def notes_for(x, kind):
    keys = list(x) if isinstance(x, dict) else []
    out = {k: NOTES[k] for k in keys if k in NOTES}
    if kind == "metainfo":
        out["(整份)"] = "_metainfo＝作者自報的特性，aos-exec／loop／fsm／daemon 都不讀（explain metainfo）"
    if kind == "tool_json":
        out["(整份)"] = "工具名＝資料夾名，這份不寫 name；資料夾要有 _tooldef.json、還要登記進 agent 的 tools.json（aos-tools add）才算工具（explain tool）"
    return out
