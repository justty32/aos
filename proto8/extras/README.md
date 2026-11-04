# proto8/extras — 周邊工具

← [proto8](../README.md)

aos 主體（[impls/](../impls/README.md) 的四支 C++、[bin/](../bin/README.md) 的 aos-tick、[lib/](../lib/README.md) 工具庫）以外，**拿來用 aos、寫 aos、關住 aos 的周邊命令列與外掛**。都是嘗試性質（使用者 10-24「我隨便說，你隨便做，反正只是嘗試」）。

| 資料夾 | 是什麼 | 測試 |
|---|---|---|
| [agent/](agent/README.md) | aos-agent：統一的 agent 介面（eca 與 loop／fsm agent 同一套子命令）：add／rm、start／stop、pause／resume、ls、state、where、say／listen／chat、open／close／watch、tools、llm；`source using-aos-agent.sh 名字` 之後直接 say／listen（11-04，之後取代 human、eca） | `tests/test_agent_cmd.py` |
| [ai_tools/](ai_tools/README.md) | aos-mcp：把 aos-tools 登記的工具當 MCP tools（eca 接 aos 工具用的；aos-ai 與 Claude skill 11-03 刪了） | `tests/test_aos_mcp.py` |
| [grow/](grow/README.md) | aos-grow：把一個函數往上長一級／縮回一級，呼叫方跟著改 | `tests/test_grow.py` |
| [langs/](langs/README.md) | 用 Janet、Lua 寫 aos 程式，編成資料夾＋JSON | `tests/test_janet.py`、`tests/test_lua_aos.py` |
| [sandbox/](sandbox/README.md) | aos-sandbox：照一份設定把程式關進沙箱（s6＋bwrap）再跑 | `tests/test_sandbox.py` |

逐檔說明在 code map 的 [proto8/06-周邊工具](../../wf/workflows/common/code-map/proto8/06-周邊工具.md)。
