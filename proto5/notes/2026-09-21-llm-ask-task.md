# 任務書：aos-llm-ask 實作（2026-09-21）

使用者一句話：「先做 aos-llm-ask，使其能處理我們現有的、以 info.json 為開頭的體系，先不管 state.json。」

## 要做什麼

照 [spec/aos-llm-ask.md](../spec/aos-llm-ask.md)（程式規範）＋ [spec/agent.md](../spec/agent.md)（資料夾與各檔形狀、
讀驗規則、錯誤代號）寫程式。規範是老大；對不上的地方**不改規範**，寫進回報。

| 檔 | 職責 |
|---|---|
| `proto5/lib/aos_agent_info.py` | 讀驗 agent 資料夾（agent.md §2）：`load(dir) -> dict`——`info.json` 用 `aos_directives` 每格解（含 `_metainfo`；`Context(load_document(info), base_dir=dir)`，位置＝實體路徑，容器用 `resolve_located` 走進去）、驗 `_metainfo`（`llm_agent`／1）、`system`／`history`／`tools`／`engine` 型別；`system` 指到的檔（不存在＝空字串）、`history` 指到的檔（不存在＝`[]`，每則照 §2.3 驗）、`tools` 列的檔（不存在＝`ReadFailed`；每份是陣列；元素驗 `type`／`function`／`function.name`／`_meta`；`_meta` 不是物件、寫了 `stdin`／`stdout` ＝`ToolInvalid`；合併後同名＝`ToolInvalid`）——全部**原樣讀、不解指示詞**。錯誤 `AgentError(code, msg)`，`str(e)`＝「代號: 白話」，`DirectiveError` 包成同形狀。**不碰 `state.json`**（那是之後 aos-agent 的事，這個模組先不管）。回傳裡把「送模型用的工具表」（去掉所有 `_` 開頭 key）跟「原始工具表」（含 `_meta`）都給 |
| `proto5/lib/aos_llm_ask.py` | `build_request(dir) -> body`、`ask(dir) -> message`（`urllib.request`，`timeout_ms`、`Authorization: Bearer` 有值才送、`endpoint` 結尾 `/` 去掉、`params` 撞 `model`／`messages`／`tools`／`stream` 忽略、`stream` 不送）＋ `main()`（`aos-llm-ask [dir] [--dry-run]`，退出碼 0／1／2／3，stderr 一行 `aos-llm-ask: …`）。引擎失敗丟 `EngineFailed(msg)`（不是 AgentError） |
| `proto5/cli/aos-llm-ask` | 薄入口，跟 `cli/aos-exec` 一樣 |
| `proto5/lib/test/test_agent_info.py`、`test_llm_ask.py` | 測試。HTTP 用 `http.server` 在執行緒裡開一個假的 chat/completions（能回正常、回 500、回壞 JSON、回沒有 choices、故意慢讓 timeout 觸發），**不打真模型**；命令列那幾條開子進程驗退出碼 0／1／2／3 與 stdout 只有一行 |

## 規則

1. Python 3.12 標準庫；指示詞用 `proto5/lib/aos_directives.py`（不改它）；`aos_inst`／`aos_exec` 這次用不到（工具不跑）。
2. 讀驗照 agent.md 的代號：`NotAnAgent`（沒有 `info.json`／沒有 `_metainfo`／`_type` 解完不是 `llm_agent`）、`MetainfoInvalid`／`UnsupportedVersion`、`ReadFailed`／`JsonSyntax`／`NotAnObject`／`NotAnArray`、`FieldTypeMismatch`、`MessageInvalid`、`ToolInvalid`、`EngineInvalid`；指示詞的代號照 directives.md §6。
3. 路徑一律相對於 agent 資料夾；`$env` 讀執行者環境（`load(dir, env=None)` 留一個參數給測試）。
4. `history` 裡不認得的 key 原樣保留、原樣送（規範說原樣）；工具元素只拿掉 `_` 開頭的 key，其他原樣。
5. 寫完：`proto5/lib/README.md` 加兩節、`proto5/README.md` 程式表加列、`wf/workflows/common/code-map.md` proto5 那列補一句。
6. 測試 `cd proto5/lib && python3 -m unittest discover -s test` 要跟現有 329 條一起全綠。
7. 真打一次：LM Studio 在 `http://127.0.0.1:1234/v1`（模型 `qwen/qwen3-1.7b`；沒開的話用 `/mnt/c/Users/WG-Guanyu/.lmstudio/bin/lms.exe server start --port 1234`）。在 `~/.claude/jobs/c15290bb/tmp/` 建一個最小 agent 資料夾（`info.json`＋`prompts/system.json`＋`prompts/history.json` 一則 user＋一份工具檔），`cli/aos-llm-ask <dir> --dry-run` 看請求、`cli/aos-llm-ask <dir>` 看它真的回一行 message；把兩行輸出貼進回報。
8. 回報：做了什麼、測試數字、規範對不上或含糊的地方（條列）、自己拿不定的決定。不 commit。
