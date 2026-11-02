# 2026-11-02 試驗場：bob 串 aos-mcp／aos-tools、cathy（資料夾工具，第二段改成 agent）；aos-mcp 改給登記檔

← [thinking README](README.md)｜月份表 [2026-11](months/2026-11.md)｜前情：[11-01 試驗場 bob](2026-11-01-playground-bob.md)、[10-28 aos-tools](2026-10-28-aos-tools.md)｜場地 `~/code/playground/`（WSL，不在 git）

本檔只記使用者原文（逐字）、決定、跟 AI 討論後的結論（[user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

## 使用者原文（11-02，逐字）

> 我有個想法，就是說你知道CPU吧，拿我們這個來類比，AOS_CF/CD/CO就像是現在執行到哪個指令，而STACK/WS就是最重要的兩個暫存器。ENTRY則與這些無關了。linux原生cwd也與我們這個無關。好，下一個playground，就是在bob的基礎上串接aos-mcp和aos-tools，並弄一個資料夾工具：cathy

## 使用者原文（11-02 第二段，逐字）

> 我這邊有些想法：bob-cathy下的mcp.json，他說要aos-mcp .，然後他會去找./tools.json...這代表說tools.json是固定的，你資料夾內一定要有這個檔案，我希望能改成aos-mcp tools.json，也就是改成指定檔案，這樣我們可以改名為aos-mcp aos-tools.json，這樣能解放一些名稱。tools.json這個挺常用的。然後cathy幫我改成另一個agent，也就是跟bob類似。除此之外，感覺.stack/<名稱>...這其實不太好，應該要改成.stack/tools/<名稱>，不然會跟其他衝突...嗎？其實也不太會，只是說.stack底下可能一大堆東西...讓fable幫我去研究一下

## 做了什麼（頂層代做，可翻案）

建的檔（都在 `~/code/playground/`；11-02 第二段照使用者改過，repo 只動了 aos-mcp，見下「結論（11-02 第二段）」）：

- `agents/cathy/`：跟 bob 同一種的 agent——`_entry.json`（`claude -p --model haiku --tools "" --strict-mcp-config --max-budget-usd 0.1 --append-system-prompt-file system.txt`）＋`system.txt`（題目是一句話或 `{"text": …}`，沒有工具、直接用自己的話答，開頭寫「cathy：」）。單獨叫：`aos-exec ../agents/cathy -- "題"`。
- `agents/bob-cathy/`：bob 的複本＋串 MCP。
  - `_entry.json`＝bob 那串 argv 多兩組：`--mcp-config mcp.json`、`--allowedTools mcp__aos__cathy`。
  - `mcp.json`＝`{"mcpServers": {"aos": {"command": "aos-mcp", "args": ["aos-tools.json"]}}}`——相對路徑從 claude 的 cwd＝這隻 agent 的資料夾算（aos-exec 會 cd 進來）；工作區與 stack 從 aos-exec 給的 `AOS_WS`／`AOS_STACK` 繼承，不另寫。**11-02 改 `"args": ["--enable-logs"]`**（不帶登記檔＝預設 `./aos-tools.json`；加 `--enable-logs` 才記 `ws/.stack/aos-mcp-logs.jsonl`，[stack-tools](2026-11-02-stack-tools.md)）。
  - `system.txt`＝bob 的那份，cwd 改成 `agents/bob-cathy`，加一段「cathy 是另一隻 agent，會自己想、回以『cathy：』開頭的回答，可能要等十幾秒；照實用、不要自己編」。
  - `aos-tools.json`＝在 `agents/bob-cathy/` 裡跑 `aos-tools --file aos-tools.json add tools/cathy` 產生（寫絕對路徑）；原本的 `tools.json` 刪了。
  - `tools/cathy/`＝工具小資料夾：`_entry.json`＝`["/home/guanyu/code/playground/agents/cathy"]`（argv[0] 是資料夾＝前面插 aos-exec，N-61；arguments 的 JSON 從 stdin 一路接到 `claude -p`，claude 沒給題目參數時讀 stdin）、`_tooldef.json`（`{"text"}`）、`_metainfo`（`time_ms` `{"val": 15000, "max": 120000}`、`resource` `llm`）。原本的 `cathy.py` 刪了。
- `env.sh`：PATH 多放 `proto8/extras/ai_tools/bin`（aos-mcp 在那裡）。

用法：

```
cd ~/code/playground && source env.sh && cd ws
aos-exec ../agents/bob-cathy -- "請問 cathy：「為什麼天空是藍色的？用一句話回答。」把她的回答原封不動寫進 env:AOS_WS 的 cathy.txt。"
```

原本的 `aos-exec ../agents/bob -- "題"` 照舊（bob 沒動）。`env.sh` 用的是 WSL 的 `~/repo/simple_tools/aos`，那份要 pull 到含 11-02 aos-mcp 改動的版本，新的 `mcp.json` 才跑得動（舊 aos-mcp 會把 `aos-tools.json` 當資料夾、報 `ToolMissing`）。

結論（實跑，haiku，11-02 第一段）：python 版 cathy 約 6 秒、結束碼 0，`calls.jsonl` 記了一行（35 ms），可證不是 bob 自己編的。

結論（實跑，haiku，11-02 第二段，cathy 改成 agent 之後）：上面那句 16 秒、結束碼 0；`ws/cathy.txt`＝「cathy：天空呈藍色，是因為陽光穿過大氣時，波長較短的藍光比紅光更容易被空氣分子散射（瑞利散射）……」（cathy 真的用腦答的）；`ws/.stack/calls.jsonl` 一行 cathy 的呼叫（arguments、code 0、4357 ms）。單獨叫 cathy、在 `CLAUDECODE=1` 下叫 cathy 的工具小資料夾都正常回答（claude 包 claude 不必清環境變數）。原本的 bob 重跑一次照舊。驗完 `ws/` 清回空的。

結論（11-02 第二段，aos-mcp 改給登記檔）：`aos-mcp [--ws WS] [--stack DIR] [--timeout-s N] REGISTRY...`，位置參數是登記檔路徑（檔名不限、相對路徑從啟動時的 cwd 算），不再給 agent 資料夾、不再預設去找 `tools.json`；給資料夾或不存在的檔＝`ToolMissing`；好幾份照舊合併、撞名＝`ToolsBad`。aos-tools 自己沒改：不給 `--file` 時照舊用 `./tools.json`，所以試驗場一律寫 `aos-tools --file aos-tools.json …`。說明在 [ai_tools README § aos-mcp](../extras/ai_tools/README.md)。

結論（跟 C-51「固定名字判準」的關係）：C-51 的 10-31 加註說固定名字可以、但範圍要限縮——理想是只有一個檔固定、其餘由它指定，要更靈活就用環境變數或 argv 指定。aos-mcp 這次是「改成 argv 指定」那一條：aos-mcp 自己不再固定任何檔名，叫它的那份 `mcp.json`（Claude Code 那邊固定的入口）指定登記檔。還留著的固定名字：aos-tools 沒給 `--file` 時的 `./tools.json`、照 round 拆成格的 agent（`lib/agent/act`、`lib/agent/round/roundlib.py`、demo 的 agent-dan 等）在 agent 資料夾找的 `tools.json`——這些沒動（任務明說不改 aos-tools 預設；agent 範本那條是 P-41 的 10-28 加註、註冊檔與固定名字共存〔11-01〕）。C-51 加註寫明使用者對判準還有後續想法（SESSION-LOG 那條 open），所以本次只當一個例子，不去改 C-51 的條文。

代定清單：

1. ~~**cathy 做什麼**：回一行「cathy 收到：…」的 python 小工具~~——11-02 第二段使用者改成 agent，見 9。
2. **另開 `agents/bob-cathy`**，不改 `agents/bob`。
3. **cathy 的工具小資料夾放在 `agents/bob-cathy/tools/cathy/`**：C-61「工具放在叫它的那一格自己的資料夾裡」。
4. **登記用 `aos-tools add`**，所以登記檔裡是絕對路徑，整個試驗場搬家要重新 add；手寫相對路徑 `tools/cathy` 也行（10-28 結論 6）。11-02 第二段起給 `--file aos-tools.json`。
5. ~~cathy 的入口用 JSON argv `["python3", "cathy.py"]`~~——改成 agent 後見 10。
6. **`mcp.json` 寫 `"command": "aos-mcp"`、靠 PATH 找**，所以 `env.sh` 加了 ai_tools/bin；不寫死 aos-mcp 的絕對路徑。
7. **aos-mcp 的 stack 跟 bob 共用 `ws/.stack/`**（aos-mcp 預設：`$AOS_STACK`），cathy 每次叫的小格在 `ws/.stack/cathy/`。**11-02 改 `ws/.stack/tools/cathy/`**（[stack-tools](2026-11-02-stack-tools.md) 選 B）。
8. **`--allowedTools mcp__aos__cathy`**：`-p` 加 `acceptEdits` 不會自動放行 MCP 工具，要明列。
9. **cathy agent 放 `agents/cathy/`，跟 bob 並排**（使用者「跟bob類似」）；bob-cathy 裡只放工具小資料夾（照 `lib/aos/ask_round` 那種「`_entry` 是 JSON argv、`_tooldef.json`／`_metainfo` 在小資料夾」的接法），所以 cathy 本身也能單獨叫。不把 agent 整份搬進 `tools/cathy/`。
10. **工具小資料夾的 `_entry.json` 只寫 `["<agents/cathy 的絕對路徑>"]`**：argv[0] 是資料夾＝前面插 aos-exec（N-61）；寫絕對路徑是為了不出現 `..`（C-61／P-25）。不給 `--ws`：cathy 吃 stdin 吐 stdout、不需要工作區，照 P-32「不需要工作區的工具不給 `--ws`（沿用），只給 stack」——stack 由 aos-mcp 給 `ws/.stack/cathy/`。
11. **題目怎麼進 cathy**：arguments 的 JSON（`{"text": …}`）原樣從 stdin 進 `claude -p`，`system.txt` 告訴她只看 `text`；不另寫轉換程式（少用 sh、KISS）。
12. **cathy 沒有工具**（`--tools ""`）、`--max-budget-usd 0.1`、不加 `--add-dir`：她只用腦答，結果由 bob 寫進工作區。
13. **逾時**：cathy 的 `_metainfo` `time_ms.max` 120000（aos-mcp 拿它當這個工具的逾時，取代預設 60 秒）；實測一次約 4 秒。
14. **不清 CLAUDECODE 那幾個環境變數**：在 `CLAUDECODE=1`、`CLAUDE_CODE_ENTRYPOINT=cli` 下實測 cathy 照樣能跑，bob（claude）→ aos-mcp → cathy（claude）不必另外 `env -u`；`env.sh` 原本那行 unset 照留。
