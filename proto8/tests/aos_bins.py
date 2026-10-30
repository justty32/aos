"""proto8/tests 跑的是哪幾支程式、PATH 怎麼放（10-23 起）。

使用者 10-23：「python版本可以刪掉了。aos-exec/loop/daemon都用C++」；頂層問 fsm 和 tick 怎麼辦，選「fsm 也改用 C++、tick 先留 Python」。
所以 aos-exec、aos-loop、aos-fsm、aos-daemon＝proto8/impls 各專案的 bin/（C++，要先建，指令見 wf/workflows/testing.md）；
aos-tick＝proto8/bin（Python，唯一還留著的 Python 版）。

aos 的程式都不動 PATH（ideas § 24）：入口裡叫 aos-exec／aos-loop／aos-fsm／aos-tick，由呼叫者（這裡）把這幾個 bin/ 放進 PATH。"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # proto8/
IMPLS = ROOT / "impls"
CXX = ("aos-exec", "aos-loop", "aos-fsm", "aos-daemon", "aos-llm-kernel", "aos-gate",   # 10-24 加 llm-kernel、gate（LLM kernel）
       "aos-json",                                     # 10-24 遷移：lib/base/json_edit 經 aos-json 寫檔
       "aos-post")                                     # 10-30 lib/agent/queue 經 aos-post 投遞（agent-lifecycle 第 1 步）
BINS = [IMPLS / n / "bin" for n in CXX] + [ROOT / "bin"]   # 最後一個是 proto8/bin（只剩 aos-tick）
BIN_DIRS = [str(b) for b in BINS]

for _n in CXX:
    if not (IMPLS / _n / "bin" / _n).exists():
        raise SystemExit("proto8/tests：%s 還沒建（%s）；先照 wf/workflows/testing.md 建 proto8/impls"
                         % (_n, IMPLS / _n / "bin" / _n))


def tool(name):
    """程式的完整路徑：四支 C++ 在 impls/<名>/bin/，aos-tick 在 proto8/bin/。"""
    for b in BINS:
        if (b / name).exists():
            return str(b / name)
    raise FileNotFoundError(name)


def path_with(rest=None):
    """這幾個 bin/ 放最前面、後面接 rest（沒給＝目前的 PATH；裡面已有的這幾個 bin/ 先拿掉）。"""
    rest = os.environ.get("PATH", "") if rest is None else rest
    return os.pathsep.join(BIN_DIRS + [p for p in rest.split(os.pathsep) if p and p not in BIN_DIRS])


EXEC = tool("aos-exec")
