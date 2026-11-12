"""agent_tool - claude、codex 共用的工具形入口 ask_cli。

這支不是工具（沒有 _entry），是模組；工具從自己資料夾或 lib 的 agent 套件 import。純標準庫。
找 tool_io：用它的工具已把 lib/ 放進 sys.path，或由標準 Python 路徑提供（lib/docs/01 規則 9）。"""
import os, sys

import tool_io
try:                                    # 工具夾自帶一份（cli_session.py 與全部 cli_*.py）就用它，否則用 lib/agent 的
    import cli_ask, cli_base, cli_cell, cli_cfg
except ModuleNotFoundError as error:
    if error.name not in {"cli_ask", "cli_base", "cli_cell", "cli_cfg"}:
        raise
    from agent import cli_ask, cli_base, cli_cell, cli_cfg


die = tool_io.die


def ask_cli(tool_dir, name, help_text):
    """claude、codex 工具形：tool_io 收參數與工作區，cli_ask.ask 問一輪並續存對話。"""
    tool_io.start(name, help_text)
    cli_base.PROG, cli_base.ECHO = name, True             # 各分檔的錯誤行都經 cli_base.die
    cfg = cli_cfg.load_cfg(tool_dir)
    stack = os.environ.get("AOS_STACK")
    if not stack:
        die("StackMissing", "AOS_STACK is not set")
    ws = tool_io.workspace()
    args = tool_io.arguments()
    if not isinstance(args.get("prompt"), str) or not args["prompt"].strip():
        die("ArgumentsBad", "missing prompt (a non-empty string)")
    cell = cli_cell.Cell(stack)
    text = cli_ask.ask(cfg, cell, os.path.abspath(tool_dir), ws, cell.path, args["prompt"], "yield")
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
