"""proto8/tests 跑的是哪幾支程式、PATH 怎麼放（10-23 起）。

使用者 10-23：「python版本可以刪掉了。aos-exec/loop/daemon都用C++」；頂層問 fsm 和 tick 怎麼辦，選「fsm 也改用 C++、tick 先留 Python」。
所以 aos-exec、aos-loop、aos-fsm、aos-daemon＝proto8/impls 各專案的 bin/（C++，要先建，指令見 wf/workflows/testing.md）；
aos-tick＝proto8/bin（Python，唯一還留著的 Python 版）。

aos 的程式都不動 PATH（ideas § 24）：入口裡叫 aos-exec／aos-loop／aos-fsm／aos-tick，由呼叫者（這裡）把這幾個 bin/ 放進 PATH。"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # proto8/
IMPLS = ROOT / "impls"
CXX = ("aos-exec", "aos-loop", "aos-fsm", "aos-daemon", "aos-llm-kernel", "aos-llm-send",   # 10-24 加 llm-kernel、llm-send（LLM kernel）
       "aos-json",                                     # 10-24 遷移：lib/base/json_edit 經 aos-json 寫檔
       "aos-post")                                     # 10-30 lib/agent/queue 經 aos-post 投遞（agent-lifecycle 第 1 步）
SPY = Path(__file__).resolve().parent / "spy_bin"   # 11-03：測試用的 aos-fsm 旁觀者（fsm 不寫 trace.jsonl 了，跑了哪幾格由它記；見 spy_bin/aos-fsm）
BINS = [SPY] + [IMPLS / n / "bin" for n in CXX] + [ROOT / "bin"]   # 最後一個是 proto8/bin（只剩 aos-tick）
BIN_DIRS = [str(b) for b in BINS]

for _n in CXX:
    if not (IMPLS / _n / "bin" / _n).exists():
        raise SystemExit("proto8/tests：%s 還沒建（%s）；先照 wf/workflows/testing.md 建 proto8/impls"
                         % (_n, IMPLS / _n / "bin" / _n))


def tool(name):
    """程式的完整路徑：四支 C++ 在 impls/<名>/bin/，aos-tick 在 proto8/bin/；aos-fsm 給旁觀者 spy_bin/aos-fsm（它再叫 impls 的）。"""
    for b in BINS:
        if (b / name).exists():
            return str(b / name)
    raise FileNotFoundError(name)


def path_with(rest=None):
    """這幾個 bin/ 放最前面、後面接 rest（沒給＝目前的 PATH；裡面已有的這幾個 bin/ 先拿掉）。"""
    rest = os.environ.get("PATH", "") if rest is None else rest
    return os.pathsep.join(BIN_DIRS + [p for p in rest.split(os.pathsep) if p and p not in BIN_DIRS])


EXEC = tool("aos-exec")

# 11-03：旁觀者記在哪（整個測試行程一份，子行程從 os.environ 繼承；每行帶 stack 的實際路徑，各案照自己的 stack 篩）
if not os.environ.get("FSM_SPY_LOG"):
    import tempfile as _tempfile
    _fd, _log = _tempfile.mkstemp(prefix="aos-test-fsm-", suffix=".jsonl")
    os.close(_fd)
    os.environ["FSM_SPY_LOG"] = _log
    import atexit as _atexit
    _atexit.register(lambda: os.path.exists(_log) and os.unlink(_log))


def fsm_steps(stack):
    """這個 stack 上 aos-fsm 跑過的每一次（照順序）：[{"state", "code"〔aos-fsm 的結束碼〕, "next"〔寫進 state 的、沒寫＝None〕}]。
    11-03 前測試讀 stack 的 trace.jsonl（code 是格的碼）；現在由 spy_bin/aos-fsm 從外面看，code 是 fsm 自己的結束碼（分岔接住＝0）。"""
    import json
    want = os.path.realpath(str(stack))
    out = []
    try:
        with open(os.environ["FSM_SPY_LOG"], encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("stack") == want:
                    out.append({k: d[k] for k in ("state", "code", "next")})
    except OSError:
        pass
    return out
