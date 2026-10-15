"""agent 當函數＋binding（使用者 10-15 定的概念：C-46）。純標準庫。說明在同資料夾 agent.md「agent 當函數／當工具」。

三個地方分開：
- 定義（bob/）：一份 agent.json（fsm 表＋brain、tools、system）＝綁好的函數；呼叫時一個字都不寫。
- frame（像 stack，history 累積處）：history.json、state.json、work/、lock/；每次呼叫／每個實例一個，可以跟 cwd 不同。
- cwd：呼叫者在哪；呼叫時才給的工具（`tools`／`tools_append`）的相對路徑從這裡算，也在這裡跑。

動工自定的機制（還不是規範）：不改 inst／loop／`$ref` 的通則（照 cwd 算），而是在這支前端把定義「攤開」——
定義裡的路徑（表上的格、brain、tools、system，含 `$ref`）一律從 bob/ 算、讀進來變成內嵌 inst；
這些 inst 沒寫 cwd 的就在 bob/ 跑（所以 argv 裡的相對路徑也照 bob/ 算），寫了相對 cwd＝從 bob/ 算；
執行期的 key（state、history、work）指進 frame，lock 由前端拿著整趟（fsm 自己不開 lock、不開 ctl）；
然後在本行程一拍一拍敲 aos_fsm，直到走到定義的 `end`（例 `["idle"]`）。

    Agent("bob/agent.json").call(frame, history=None, engine_args=None, tools=None, tools_append=None,
                                 cwd=None, max_ticks=20)

- history：給了＝frame 的 history 換成它、fsm 從頭來（刪掉 frame 的 state）；沒給＝接著 frame 裡現有的。
- engine_args：腦的引數。list＝接在腦 inst 的 argv 後面（例 `["--model", "x"]`）；dict＝蓋過腦 inst 的 key。
- tools：給了＝整份取代 bob 綁的預設；tools_append：再追加；都沒給＝用 bob 綁的。{名: TARGET 或內嵌 inst}。
- 回 {"reply", "ticks"}；出錯丟 CallError（code：Busy、MaxTicks（帶 partial）、SubAgentFailed、TooDeep、NoHistory…）。

`aos_agent_lib.py ask [--frame DIR] [--max-ticks N] bob/agent.json`（stdin {"question", "history"?}）就是包這個：
frame 沒給＝`$AOS_WORK/ask-<n>/`（AOS_WORK＝呼叫它的那個 agent 的 work，tool 格會給），再沒有＝`./ask-<n>/`。
遞迴：環境變數 AOS_ASK_DEPTH 每層 +1，超過 MAX_DEPTH＝TooDeep。

相依：aos_directives ← aos_cli ← aos_inst ← aos_methods ← aos_fsm ← aos_agent_call。
"""
import contextlib
import io
import json
import os

import aos_cli
import aos_fsm
import aos_inst
from aos_cli import CliError
from aos_ctl_state import read_state, write_json
from aos_directives import DirectiveError, resolve, split_target

__all__ = ["Agent", "CallError", "MAX_DEPTH", "MAX_TICKS", "ask"]

MAX_TICKS = 20
MAX_DEPTH = 3


class CallError(CliError):
    def __init__(self, code, msg, **extra):
        super().__init__(code, msg)
        self.extra = extra


def _load(target, base):
    """TARGET（從 base 算）→ 解好的 dict（指示詞也從 base 算）。"""
    try:
        file, pos = split_target(target)
        real = aos_inst._file(os.path.join(base, file))
        with open(real, encoding="utf-8") as f:
            doc = resolve(json.load(f), base, real, pos)
    except (DirectiveError, aos_inst.InstError) as e:
        raise CallError(e.code, "%s：%s" % (target, e.msg))
    except (OSError, ValueError) as e:
        raise CallError("ReadFailed", "%s：%s" % (target, e))
    if not isinstance(doc, dict):
        raise CallError("FieldType", "%s 要是物件" % target)
    return doc


def _inst(v, base, envs):
    """TARGET 或內嵌 inst → 內嵌 inst，cwd 定成絕對（沒寫＝base），envs 疊上去。"""
    inst = dict(_load(v, base) if isinstance(v, str) else v)
    inst["cwd"] = os.path.join(base, inst["cwd"]) if isinstance(inst.get("cwd"), str) else base
    inst["envs"] = dict(inst.get("envs") or {}, **envs)
    return inst


class Agent:
    """綁好的函數：bob/agent.json（定義）。call() 不寫定義資料夾。"""

    def __init__(self, path):
        self.path = os.path.realpath(path)
        self.dir = os.path.dirname(self.path)

    def _doc(self, frame, cwd, envs, engine_args, tools, tools_append):
        bob = self.dir
        d = _load(os.path.basename(self.path), bob)
        states = {}
        for name, v in (d.get("states") or {}).items():
            nxt = None
            if isinstance(v, dict) and "target" in v:
                v, nxt = v["target"], v.get("next")
            c = _inst(v, bob, envs)
            states[name] = {"target": c, "next": nxt} if nxt else c
        brain = _inst(d.get("brain"), bob, envs) if d.get("brain") else None
        if isinstance(engine_args, list):
            brain["argv"] = list(brain["argv"]) + [str(a) for a in engine_args]
        elif isinstance(engine_args, dict):
            brain.update(engine_args)
        tl = {k: _inst(t, bob, envs) for k, t in (d.get("tools") or {}).items()}
        if tools is not None:
            tl = {k: _inst(t, cwd, envs) for k, t in tools.items()}
        tl.update({k: _inst(t, cwd, envs) for k, t in (tools_append or {}).items()})
        doc = dict(d, states=states, brain=brain, tools=tl, ctl=None, lock=None,
                   state=os.path.join(frame, "state.json"), history=os.path.join(frame, "history.json"),
                   work=os.path.join(frame, "work"))
        if d.get("system"):
            doc["system"] = os.path.join(bob, d["system"])
        return doc

    def call(self, frame, history=None, engine_args=None, tools=None, tools_append=None, cwd=None,
             max_ticks=MAX_TICKS):
        cwd = os.path.abspath(cwd or os.getcwd())
        frame = os.path.abspath(os.path.join(cwd, frame))
        depth = _depth()
        envs = {"AOS_ASK_DEPTH": str(depth)}
        os.makedirs(frame, exist_ok=True)
        lock = os.path.join(frame, "lock")
        try:
            os.mkdir(lock)
        except FileExistsError:
            raise CallError("Busy", "frame %s 有人在用（lock 在）" % frame)
        try:
            doc = self._doc(frame, cwd, envs, engine_args, tools, tools_append)
            hist = doc["history"]
            if history is not None:
                write_json(hist, history)
                with contextlib.suppress(FileNotFoundError):
                    os.remove(doc["state"])          # 新的一段：fsm 從 start 來
            elif not os.path.exists(hist):
                raise CallError("NoHistory", "frame %s 沒有 history，也沒給" % frame)
            return self._run(doc, max_ticks)
        finally:
            os.rmdir(lock)

    def _run(self, doc, max_ticks):
        end = doc.get("end") or []
        for n in range(1, max_ticks + 1):
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    aos_fsm.run(doc, self.path)
            except CliError as e:
                raise CallError("SubAgentFailed", "%s: %s" % (e.code, e.msg))
            out = aos_cli.read_stream(buf.getvalue())
            st = read_state(doc["state"]) or {}
            if any(isinstance(o, dict) and "error" in o for o in out) or st.get("halted"):
                raise CallError("SubAgentFailed", st.get("last_error") or "停住了（halted）")
            if any(isinstance(o, dict) and o.get("next") in end for o in out):
                return {"reply": _last_text(doc["history"]), "ticks": n}
        raise CallError("MaxTicks", "敲了 %d 拍還沒走到 end" % max_ticks, partial=_last_text(doc["history"]))


def _depth():
    try:
        d = int(os.environ.get("AOS_ASK_DEPTH") or 0) + 1
    except ValueError:
        d = 1
    if d > MAX_DEPTH:
        raise CallError("TooDeep", "agent 叫 agent 已經 %d 層（最多 %d）" % (d, MAX_DEPTH))
    return d


def _last_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            msgs = json.load(f)
    except (OSError, ValueError):
        return None
    for m in reversed(msgs):
        if m.get("role") == "assistant" and m.get("content"):
            return m["content"]
    return None


def _new_frame(base):
    """base/ask-<n>/：挑第一個還沒有的號碼（mkdir 原子，兩個同時叫不會撞）。"""
    os.makedirs(base, exist_ok=True)
    n = 1
    while True:
        p = os.path.join(base, "ask-%d" % n)
        try:
            os.mkdir(p)
            return p
        except FileExistsError:
            n += 1


def ask(argv, stdin_text):
    """`aos_agent_lib.py ask` 的本體：回 (stdout 那份, 退出碼)。"""
    frame, max_ticks, rest = None, MAX_TICKS, list(argv)
    try:
        while rest and rest[0].startswith("--"):
            k = rest.pop(0)
            if k == "--frame":
                frame = rest.pop(0)
            elif k == "--max-ticks":
                max_ticks = int(rest.pop(0))
            else:
                raise CallError("Usage", "不認得 %s" % k)
        if len(rest) != 1:
            raise CallError("Usage", "aos_agent_lib.py ask [--frame DIR] [--max-ticks N] AGENT.json")
        docs = aos_cli.read_stream(stdin_text)
        arg = docs[0] if docs and isinstance(docs[0], dict) else {}
        hist = arg.get("history")
        if hist is None:
            q = arg.get("question")
            if not isinstance(q, str):
                raise CallError("FieldType", "stdin 要有 question（字串）或 history")
            hist = [{"role": "user", "content": q}]
        _depth()                                     # 太深就別建 frame
        if frame is None:
            frame = _new_frame(os.environ.get("AOS_WORK") or os.getcwd())
        return Agent(rest[0]).call(frame, history=hist, max_ticks=max_ticks), 0
    except (CallError, CliError, IndexError, ValueError) as e:
        code, msg = (e.code, e.msg) if isinstance(e, CliError) else ("Usage", str(e))
        out = {"error": code, "msg": msg}
        out.update(getattr(e, "extra", {}))
        return out, 1
