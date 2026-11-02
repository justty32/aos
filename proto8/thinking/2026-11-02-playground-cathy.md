# 2026-11-02 試驗場：bob 串 aos-mcp／aos-tools、資料夾工具 cathy

← [thinking README](README.md)｜月份表 [2026-11](months/2026-11.md)｜前情：[11-01 試驗場 bob](2026-11-01-playground-bob.md)、[10-28 aos-tools](2026-10-28-aos-tools.md)｜場地 `~/code/playground/`（WSL，不在 git）

本檔只記使用者原文（逐字）、決定、跟 AI 討論後的結論（[user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

## 使用者原文（11-02，逐字）

> 我有個想法，就是說你知道CPU吧，拿我們這個來類比，AOS_CF/CD/CO就像是現在執行到哪個指令，而STACK/WS就是最重要的兩個暫存器。ENTRY則與這些無關了。linux原生cwd也與我們這個無關。好，下一個playground，就是在bob的基礎上串接aos-mcp和aos-tools，並弄一個資料夾工具：cathy

## 做了什麼（頂層代做，可翻案）

建的檔（都在 `~/code/playground/`，repo 程式沒動）：

- `agents/bob-cathy/`：bob 的複本＋串 MCP。
  - `_entry.json`＝bob 那串 argv 多兩組：`--mcp-config mcp.json`、`--allowedTools mcp__aos__cathy`。
  - `mcp.json`＝`{"mcpServers": {"aos": {"command": "aos-mcp", "args": ["."]}}}`——`.`＝claude 的 cwd＝這隻 agent 的資料夾（aos-exec 會 cd 進來），aos-mcp 讀它的 `tools.json`；工作區與 stack 從 aos-exec 給的 `AOS_WS`／`AOS_STACK` 繼承，不另寫。
  - `system.txt`＝bob 的那份，cwd 改成 `agents/bob-cathy`，加一段「你有 MCP 工具 cathy，她回什麼照實用、不要自己編」。
  - `tools.json`＝在 `agents/bob-cathy/` 裡跑 `aos-tools add tools/cathy` 產生（寫絕對路徑）。
  - `tools/cathy/`＝資料夾工具：`_entry.json`（JSON argv `["python3", "cathy.py"]`）、`cathy.py`、`_tooldef.json`、`_metainfo`。
- `env.sh`：PATH 多放 `proto8/extras/ai_tools/bin`（aos-mcp 在那裡）。

用法：

```
cd ~/code/playground && source env.sh && cd ws
aos-exec ../agents/bob-cathy -- "請叫 cathy，跟她說「你好，我是 bob」，把她回的那一行原封不動寫進 env:AOS_WS 的 cathy.txt。"
```

原本的 `aos-exec ../agents/bob -- "題"` 照舊（bob 沒動）。

結論（實跑，haiku）：上面那句約 6 秒、結束碼 0；`ws/cathy.txt`＝`cathy 收到：你好，我是 bob（2026-11-02T01:02:46Z）`；`ws/.stack/calls.jsonl` 記了一行 cathy 的呼叫（arguments、code 0、35 ms），可證不是 bob 自己編的。原本的 bob 也重跑過一次、照舊。驗完 `ws/` 清回空的。

代定清單：

1. **cathy 做什麼**：收 `{"text"}`、回一行「cathy 收到：<那句話>（UTC 時間）」，不碰檔案、不用 `$AOS_WS`。照舊 demo 的 cathy（`demo/agent-bob/act/tools/cathy`，假腦回「FAKE ANSWER to: 題」）只留「回一句看得出被叫到的話」，舊版那套 fsm 小 agent 不搬。結果由 bob 寫進工作區，不是 cathy 寫。
2. **另開 `agents/bob-cathy`**，不改 `agents/bob`。
3. **cathy 放在 `agents/bob-cathy/tools/cathy/`**：C-61「工具放在叫它的那一格自己的資料夾裡」。
4. **登記用 `aos-tools add`**（照 aos-mcp 新寫法：給 agent 資料夾＋add），所以 `tools.json` 是絕對路徑，整個試驗場搬家要重新 add；手寫相對路徑 `tools/cathy` 也行（10-28 結論 6）。
5. **cathy 的入口用 JSON argv**（`["python3", "cathy.py"]`，cwd＝工具資料夾），不是 lib 契約那種帶 shebang 的 `_entry` 可執行檔。
6. **`mcp.json` 寫 `"command": "aos-mcp"`、靠 PATH 找**，所以 `env.sh` 加了 ai_tools/bin；不寫死 aos-mcp 的絕對路徑。
7. **aos-mcp 的 stack 跟 bob 共用 `ws/.stack/`**（aos-mcp 預設：`$AOS_STACK`），cathy 每次叫的小格在 `ws/.stack/cathy/`。
8. **`--allowedTools mcp__aos__cathy`**：`-p` 加 `acceptEdits` 不會自動放行 MCP 工具，要明列。
