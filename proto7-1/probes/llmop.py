"""第二波探針共用：讓 LLM 當操作者，只給它兩個工具（read_file、write_file），看它能不能只靠檔案把 daemon 用對。

- `FileTools(base)`：路徑一律相對 base（多半是空間根），跑不出 base。read_file 對資料夾回列表（含 `.` 開頭的），
  對 FIFO 等非一般檔回錯誤（不會卡住），太長留開頭與結尾；write_file 原子寫（`.名字.tmp.pid` 再 rename），父資料夾自動建。
  每次呼叫記一行在 `self.log`（給探針事後找「讀錯、寫錯」）。
- `Brain`：`RealBrain(model)` 打 LiteLLM `http://127.0.0.1:4000/v1`（只准雲端模型，見 `check_model`）；
  `ScriptBrain(steps)` 是離線的照稿腦（steps＝[(tool, args) 或 callable(tools)->(tool,args) 或 None＝結束]），
  run_all 用它證明「只靠檔案做得到」，也測探針本身。
- `run_agent(...)`：迴圈「問腦 → 執行工具 → 把結果接回去」，到腦說完（不叫工具）、`max_calls`、`until()` 成立或逾時為止。
  每輪至少 `min_turn_s` 秒（讓 daemon 跑幾個回合；LLM 看不到這個等待）。回 `{"calls","tokens","turns","stop","final","tools":[...]}`。

真模型呼叫數：每個探針自己設上限（`max_calls`），`run_agent` 回的 `calls` 是實際打了幾次（含失敗重試）。
"""
import json
import os
import stat
import time
import urllib.error
import urllib.request

URL = "http://127.0.0.1:4000/v1"
CARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_card.md")
DENY = ("lm-", "ollama", "claude-fable")
MAX_READ = 6000

TOOLS_SPEC = [
    {"type": "function", "function": {
        "name": "read_file",
        "description": "讀一個檔（回內容；太長只回開頭 1000 字與結尾）或列一個資料夾（回每項名字，資料夾結尾加 /）。path 相對空間根；\".\" 是根。",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "把 content 原樣寫成檔（整份覆寫，原子寫入；父資料夾會自動建）。path 相對空間根。",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                       "required": ["path", "content"]}}},
]


def clip(text):
    """太長時留開頭 1000 字與結尾，中間標明省略幾字（第一波只回開頭，jsonl／log／長列表看不到最新的；
    probes/llmteam 誤解 6、llmops 誤解 8）。"""
    if len(text) <= MAX_READ:
        return text
    head, tail = text[:1000], text[-(MAX_READ - 1000):]
    return "%s\n…（中間省略 %d 字；共 %d 字，下面是結尾）…\n%s" % (head, len(text) - MAX_READ, len(text), tail)


def card():
    with open(CARD, encoding="utf-8") as f:
        return f.read()


def check_model(model):
    if not model or any(model.startswith(p) for p in DENY):
        raise SystemExit("不准用這個模型：%r（只准 LiteLLM 上的雲端模型，不要 lm-*、ollama*、claude-fable-*）" % (model,))
    return model


class FileTools:
    def __init__(self, base, name="op", read_only=()):
        self.base = os.path.realpath(base)
        self.name = name
        self.read_only = tuple(read_only)   # 相對 base 的前綴：寫入拒絕
        self.log = []

    def _resolve(self, path):
        if not isinstance(path, str):
            raise ValueError("path 要是字串")
        p = os.path.normpath(os.path.join(self.base, path))   # 絕對路徑 join 後就是它自己
        if p != self.base and not p.startswith(self.base + os.sep):
            raise ValueError("path 跑出空間根")
        return p

    def rel(self, p):
        return os.path.relpath(p, self.base)

    def call(self, tool, args):
        rec = {"t": time.time(), "tool": tool, "path": args.get("path") if isinstance(args, dict) else None}
        try:
            if tool == "read_file":
                out = self.read_file(args["path"])
            elif tool == "write_file":
                out = self.write_file(args["path"], args["content"])
                rec["content"] = args["content"][:2000]
            else:
                raise ValueError("沒有這個工具：%s" % tool)
            rec["ok"] = True
        except (KeyError, TypeError) as e:
            out = "錯誤：參數不對（%s）" % e
            rec["ok"], rec["err"] = False, out
        except (OSError, ValueError) as e:
            out = "錯誤：%s" % e
            rec["ok"], rec["err"] = False, out
        self.log.append(rec)
        return out

    def read_file(self, path):
        p = self._resolve(path)
        st = os.stat(p)   # 不存在丟 FileNotFoundError
        if stat.S_ISDIR(st.st_mode):
            names = []
            for n in sorted(os.listdir(p)):
                names.append(n + "/" if os.path.isdir(os.path.join(p, n)) else n)
            return clip("\n".join(names)) if names else "（空資料夾）"
        if not stat.S_ISREG(st.st_mode):
            raise OSError("不是一般檔（%s），不讀" % ("FIFO" if stat.S_ISFIFO(st.st_mode) else "特殊檔"))
        with open(p, encoding="utf-8", errors="replace") as f:
            text = f.read()
        return clip(text) if text else "（空檔）"

    def write_file(self, path, content):
        if not isinstance(content, str):
            raise TypeError("content 要是字串")
        p = self._resolve(path)
        r = self.rel(p)
        if any(r == x or r.startswith(x.rstrip("/") + "/") for x in self.read_only):
            raise OSError("這裡不准寫：%s" % r)
        d = os.path.dirname(p)
        os.makedirs(d, exist_ok=True)
        tmp = os.path.join(d, ".%s.tmp.%d" % (os.path.basename(p), os.getpid()))
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, p)
        return "寫好了：%s（%d 字）" % (r, len(content))

    def writes(self):
        return [x for x in self.log if x["tool"] == "write_file"]

    def errors(self):
        return [x for x in self.log if not x.get("ok")]


# ---------------- 腦 ----------------

class RealBrain:
    def __init__(self, model, timeout_s=120, temperature=0):
        self.model = check_model(model)
        self.timeout_s = timeout_s
        self.temperature = temperature

    def step(self, messages):
        """回 {"content", "tool_calls": [{"id","name","args"}], "tokens", "error"?, "raw_msg"}。"""
        body = {"model": self.model, "messages": messages, "tools": TOOLS_SPEC, "temperature": self.temperature,
                "max_tokens": 2000}
        req = urllib.request.Request(URL + "/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read())
        except (urllib.error.URLError, OSError, ValueError) as e:
            return {"content": None, "tool_calls": [], "tokens": 0, "error": str(e)[:300]}
        try:
            msg = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            return {"content": None, "tool_calls": [], "tokens": 0, "error": "回應壞：%s" % str(data)[:300]}
        calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {"_bad_json": fn.get("arguments")}
            calls.append({"id": tc.get("id"), "name": fn.get("name"), "args": args})
        raw = {"role": "assistant", "content": msg.get("content") or ""}
        if msg.get("tool_calls"):
            raw["tool_calls"] = [{"id": tc.get("id"), "type": "function", "function": tc.get("function")}
                                 for tc in msg["tool_calls"]]
        return {"content": msg.get("content"), "tool_calls": calls,
                "tokens": (data.get("usage") or {}).get("total_tokens", 0), "raw_msg": raw}


class ScriptBrain:
    """照稿腦：每一步是 (tool, args)、callable(tools) -> (tool, args) 或 None（結束），或字串（最後的話）。
    callable 可回 "wait" 表示這一輪什麼都不做（讓時間過去，不算工具呼叫）。"""

    def __init__(self, steps):
        self.steps = list(steps)
        self.i = 0
        self.tools = None

    def step(self, messages):
        while self.i < len(self.steps):
            s = self.steps[self.i]
            if callable(s):
                v = s(self.tools)
                if v == "wait":
                    return {"content": None, "tool_calls": [], "tokens": 0, "wait": True}
                self.i += 1
                if v is None:
                    continue
                s = v
            else:
                self.i += 1
            if isinstance(s, str):
                return {"content": s, "tool_calls": [], "tokens": 0}
            tool, args = s
            tc = {"id": "s%d" % self.i, "name": tool, "args": args}
            return {"content": None, "tool_calls": [tc], "tokens": 0,
                    "raw_msg": {"role": "assistant", "content": "",
                                "tool_calls": [{"id": tc["id"], "type": "function",
                                                "function": {"name": tool, "arguments": json.dumps(args, ensure_ascii=False)}}]}}
        return {"content": "（照稿完）", "tool_calls": [], "tokens": 0}


def run_agent(brain, tools, system, goal, max_calls=30, until=None, min_turn_s=0.0, timeout_s=600,
              transcript=None, nudge=None):
    """跑一個 LLM 操作者。nudge：腦不叫工具就結束前，若給了 nudge(final)->str|None，可以再推它一次（算一次呼叫）。"""
    if isinstance(brain, ScriptBrain):
        brain.tools = tools
    messages = [{"role": "system", "content": system}, {"role": "user", "content": goal}]
    out = {"calls": 0, "tokens": 0, "turns": 0, "stop": None, "final": None, "errors": 0}
    t_end = time.monotonic() + timeout_s
    while True:
        if until and until():
            out["stop"] = "until"
            break
        if out["calls"] >= max_calls:
            out["stop"] = "max_calls"
            break
        if time.monotonic() > t_end:
            out["stop"] = "timeout"
            break
        t0 = time.monotonic()
        r = brain.step(messages)
        if r.get("wait"):
            time.sleep(max(min_turn_s, 0.05))
            continue
        out["calls"] += 0 if isinstance(brain, ScriptBrain) else 1
        out["turns"] += 1
        out["tokens"] += r.get("tokens", 0)
        _log(transcript, {"turn": out["turns"], "content": r.get("content"), "calls": r.get("tool_calls"),
                          "error": r.get("error")})
        if r.get("error"):
            out["errors"] += 1
            if out["errors"] >= 3:
                out["stop"] = "llm_error"
                break
            time.sleep(2)
            continue
        if not r["tool_calls"]:
            out["final"] = r.get("content")
            more = nudge(out["final"]) if nudge else None
            if more and out["calls"] < max_calls:
                messages.append({"role": "assistant", "content": r.get("content") or ""})
                messages.append({"role": "user", "content": more})
                continue
            out["stop"] = "done"
            break
        messages.append(r["raw_msg"])
        for tc in r["tool_calls"]:
            res = tools.call(tc["name"], tc["args"])
            _log(transcript, {"turn": out["turns"], "tool": tc["name"], "args": tc["args"], "result": res[:600]})
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": res})
        dt = time.monotonic() - t0
        if dt < min_turn_s:
            time.sleep(min_turn_s - dt)
    return out


def _log(path, obj):
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def system_prompt(role_text):
    return "%s\n\n以下是這套系統的操作卡：\n\n%s" % (role_text, card())


def model_arg(argv):
    """`--real MODEL[,MODEL...]` → 模型清單；沒有回 []（離線照稿）。"""
    if "--real" in argv:
        i = argv.index("--real")
        return [check_model(m) for m in argv[i + 1].split(",")]
    return []
