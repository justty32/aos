# 08 fsm 施工結果（11-12 晚，家機）：07 的九步全做完（步 8 真腦驗收也在家機暫存樹跑過）——`aos-mcp-import` 把外部 server 的工具凍結進 server 檔，疊進 `tools.json` 後 `aos-tools call` 叫得到外部 stdio 與 http（Bearer＋自簽 CA）工具；代定 G1～G12 可翻案

← [external-mcp](README.md)｜[07 fsm 施工單](07-fsm施工單.md)｜[06 施工結果](06-施工結果.md)

## 使用者原話

- 「fsm來得及做嗎？」「派」（11-12 傍晚，公司）。
- 題一與代定：「那就a。fable代定就先這樣，感覺都OK，以後出問題再來解決」（只收 Bearer；F1～F12 照圖）。

## 做完的（各自一個 commit，照 07 的步號）

| 步 | commit | 做了什麼 | 怎麼驗的 |
|---|---|---|---|
| 4 | `15e7f8225` | `lib/mcp_freeze.py`：登記名、`$ref` 展開與拿掉 `$` 鍵、說明前綴與截斷、`_metainfo`、`diff_tools` | 單元 21 支 |
| 1 | `847f54433` | `lib/mcp_client.py` stdio 半邊；假 stdio server `lib/tests/fake_mcp_stdio.py` | 單元 30 支（握手、翻頁、六種 `FAKE_MODE`、逾時、收行程群） |
| 6 | `c45dad9bf` | `mcp_client` 加 http（Streamable HTTP、Bearer、`ca_file`、session id、SSE、DELETE） | 單元 41 支（對 `extras/fake-mcp-http` 實連）；隊長實跑見下 |
| 2 | `a7a730e2d` | `lib/base/mcp_tool/`：共用 `_entry`，文字結果與基本錯誤；手寫包檔 fixture | 單元 11 支；先驗兩件事都成立（aos-tools 沒動）；實跑見下 |
| 5 | `a55f61f3d` | 新指令 `aos-mcp-import SERVER_FILE`（`--only`／`--except`／`--timeout-s`） | 單元 15 支；實跑見下 |
| 3 | `333eb2afa` | `mcp_tool` 補完：圖片／聲音存小格、resource、structuredContent、截斷、逾時、TERM 收 server | 單元 21 支（測完沒殘留 server） |
| 7 | `39376709c` | `aos-mcp-import sync [--yes]` | 單元 22 支；實跑：少一支 → sync 印 `- peek_clock` 不寫 → `--yes` 寫回 → `ls` 剩一支 |
| 9 | `b9ca076fc` | 說明與登記：cmd README、cmd/docs/01、lib/docs/02、templates/docs/01「經 aos」一段與兩條路差別表、aos-eca README、knowledge 新節點 `cli/mcp_import`（含錯誤代號怎麼讀）、install.sh 檔頭、fake-mcp-http 產憑證補欄位 | codemap、knowledge JSON 讀得過、index_view 測試 |
| 8 | （不新增程式） | 真腦驗收，暫存樹在 scratchpad（不碰試驗場）：fsm gemma-4-e4b、eca haiku、eca codex gpt-6-luna | 見下「步 8 真腦驗收」；約 0.02 美金 |

隊長實跑（不用真腦）：

- **stdio**：第二台 aos-mcp 寫成 server 檔 → `aos-mcp-import` 印 `imported 2 of 2 tools from demo` → 再跑一次＝`PackExists` → `aos-tools ls` 看到 `demo_peek_clock`、`demo_peek_now_time` → `aos-tools call demo_peek_now_time` 印 `2026-11-12T11:09:15Z`、退 0。
- **http**：假 http server（當場產 CA 與假 token）→ `aos-mcp-import` 匯入 2 支 → `call teamsite_echo` 印 `echo: hello`、`call teamsite_list_threads` 印兩筆假資料；server log `"auth": "ok"` 12 行、錯的 0 行；假 token `grep -rlaF` 掃包檔、ws、server log＝0，所有 `/proc/*/cmdline`＝0；env 檔換成錯 token＝`mcp_tool: error: ServerRejected MCP HTTP request failed (status 401)`、退 1。

## 步 8 真腦驗收（家機，暫存樹，五項都過）

1. **fsm 叫外部 stdio**：gemma 叫 `demo_peek_now_time`（第二台 aos-mcp、`aos-mcp-import --only peek_now_time`），拿到時間、照答（`history.jsonl`；fsm 沒有 `live.jsonl`）。
2. **fsm 叫外部 http**：gemma 叫 `fakeh_echo`、`fakeh_list_threads` 拿到結果；假 server log 每筆 `"auth": "ok"`。
3. **eca 經 aos**：claude 身（haiku）`live.jsonl` 的 init 列出 `mcp__aos__demo_peek_now_time` 並叫到；codex 身（luna）`mcp_tool_call … demo_peek_now_time completed`。**codex 底下 `mcp_tool` 起得了 server，不用補 `cli_session.MCP_ENV`**（server 收到的變數名有 `PATH`、`HOME`、`AOS_HOME` 等）。
4. **hook 與關單支**：`before_tool` handler 掛在 `demo_peek_now_time`，fsm、eca 各叫一次都被攔、server 沒起；腦自己 `self_tools rm demo_peek_now_time` 只關那一支（49→48），包檔沒被改。
5. **金鑰不落地**：兩把假 token 掃暫存樹（定義、stack、`live.jsonl`、hook 紀錄）、`~/.codex`／`~/.claude/projects` 新檔、150 秒連續掃 `/proc` 的 cmdline＝0；http 那把連 environ 都沒有；stdio 那把只在 server 行程與它的子行程 environ（設計上該在的地方）。
6. `uvx mcp-server-time`（要下載）沒做。

測試（最後一個 commit，家機）：lib 132、lib/agent 63、`lib/base/mcp_tool` 21、`cmd/aos-mcp-import` 22、`cmd/aos-tools` 120、`cmd/aos-mcp` 15、`cmd/aos-eca` 89、templates 20、`cmd/aos-agent` 72 全過（家機這次 `test_daemon_down` 也過）。

## 代定（隊長與寫手定的，可翻案）

- **G1** `mcp_client` 不遮 server 自己錯誤訊息裡的環境變數值（寫手原本把 server 環境每個值都遮成 `[redacted]`，`LANG=C` 這類短值會把訊息遮爛；隊長拿掉）。http 那條只遮 bearer 本身。server 自己把金鑰印進錯誤訊息算 server 的事。
- **G2** http 用 Python 預設的嚴格憑證驗證（3.13 起 `VERIFY_X509_STRICT`）：自簽 CA 沒有 `keyUsage`、leaf 沒有 key identifier 會驗不過（codex／claude 不受影響）。沒放寬；假 server 的產憑證步驟補上這幾個欄位。真主機的公司 CA 若驗不過，要嘛換正規 CA，要嘛再議放寬。
- **G3** server 那邊工具不見了時，aos-mcp 與假 server 都回 JSON-RPC `-32602`，照步 1 規則翻成 `ArgumentsBad`（例 `ArgumentsBad no such tool: gone`），不是 07 邊緣 8 寫的 `ServerFailed …(run aos-mcp-import sync)`——兩者從協定上分不開，沒做。
- **G4** `sync` 的差異只比 description 與 parameters（照圖）：只有 annotations（`side_effect`、`idempotent`、`resource`）變了＝`no changes`、不寫；server 檔改名後 `--pack` 與 `tools.path` 還指舊名，sync 也看不出。
- **G5** `sync --yes` 整份重建 `tools`：人在包檔 `tools` 裡手加的條目會被拿掉（包檔的 `tools` 當成匯入產物）。
- **G6** `only` 裡的工具 server 已經沒有：匯入＝`ToolUnknown`（照圖）；sync＝warning、當成拿掉（不然有 `only` 的檔永遠 sync 不掉消失的那支）。`--except` 列了 server 沒有的名字＝warning。
- **G7** 已匯入的判定：檔裡有 `mcp_tools`、`mcp_import`、`tools` 任一個就算 `PackExists`（圖只寫 `mcp_tools`），免得蓋掉手寫的 `tools`。
- **G8** `--timeout-s N`＝initialize 與每頁 `tools/list` 各自的上限（不是總時限）；為此 `open_session` 加 `init_timeout_s`、`list_tools` 加 `timeout_s`。
- **G9** 媒體（image／audio）存 `$AOS_STACK`，沒有＝`StackMissing`；檔名唯一、副檔名照 MIME。
- **G10** `openWorldHint` 沒寫＝不算 `net`（MCP 規格的預設是 true，這裡照「有寫才算」）；transport 是 http 一律 `net`。
- **G11** 登記名先接成 `<server>_<tool>` 再整串轉，工具名開頭的 `_` 會併掉；server 名叫 `aos` 也算 `NameBad`。
- **G12** `mcp_tool --help` 的旗標段是 `tool_io` 生成的固定句「each sets the same key of the JSON object on stdin」，對 `--pack`／`--tool` 不準（它們只是旗標，stdin 原樣轉交）；屬性說明裡補了「flag only」，`tool_io` 沒動。

## 要使用者看的（不擋）

- **Q1（方向題）fsm 經 aos 起的外部 stdio server 拿到整棵樹的全部環境變數**：`mcp_server_file.stdio_launch` 是 `dict(os.environ)`＋`env`＋`env_file`，步 8 實測 server 環境裡有起樹那個殼留下的 `DEEPSEEK_API_KEY`、`NEXUS_API_KEY`。codex 原生掛那條只帶白名單十幾個。同一份 server 檔，經 aos 給第三方 server 的反而多得多。F3 照 `aos-mcp-launch` 寫、不算寫錯；要不要給 stdio server 改成白名單（例：`PATH`、`HOME`、`LANG`、`AOS_*` ＋ `env`／`env_file`），兩條路一起改，請使用者裁。沒改。
- **Q2** server 檔 `args` 裡的相對路徑從 server 的 cwd（`$AOS_WS`）算，`command` 含 `/` 時卻從包檔資料夾算（`stdio_launch` 現況，06 那半就這樣）；`args` 陣列裡單一元素不能寫指示詞。寫包檔的人容易踩，要不要統一，請裁。
- **Q3** 代定 G3（工具不見了＝`ArgumentsBad`）、G4（sync 不比 annotations）可翻案。

## 沒做／沒驗

- 真的別人寫的 stdio server（`uvx mcp-server-time`）：要下載，等使用者點頭。
- 07 不在範圍的照舊：常駐 proc、M7「每次重問」、給腦用的 `mcp_import` 工具、任意標頭（題一 b）、舊式 HTTP+SSE。
- 06 留下的：codex 沙盒對 stdio、`disabled_tools`、`--envs` 明文（P1）、外部 server 壞了 aos 看不到（P3）、代定 E1～E7。
- 圖紙與施工都沒經 Argon 審。

## 殘留

- scratchpad 底下 `mcpfsm-*` 暫存樹與假 server 的憑證、假 token（session 結束自動清）。
