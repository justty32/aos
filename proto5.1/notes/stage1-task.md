# proto5.1 第 1 段任務書：llm cpu、think 丟請求、兩個逾時關卡（2026-09-22）

使用者一句話：「決策太多，不如開 proto5.1，讓 codex 去實作看看，實作時遇到的實際問題和經驗拿來做參考。」

## 你要做的

在 `proto5.1/`（proto5 的複本；**`proto5/` 一個字都不要碰**）照下面三份總結裡「我的建議」實作，規範跟著改，
問題記進 `proto5.1/notes/findings.md`。

先讀（照順序）：
1. `proto5.1/README.md`、`proto5.1/spec/*.md`（六份）、`proto5.1/lib/README.md`、`proto5.1/lib/*.py`、`proto5.1/lib/test/*.py`。
2. `proto5/notes-brief/README.md`（23 題總表）、`proto5/notes/2026-09-22-llm-cpu-summary.md`、`2026-09-22-timeout-summary.md`、
   `2026-09-22-act-summary.md`（只看跟 waits／協議有關的部分）。細節不夠再看 `proto5/notes/*-report-astra.md`。

### A. llm cpu

照 llm-cpu-summary §2（六題全採建議 A）：

- **格式規範** `proto5.1/spec/llm-cpu.md`：cpu 資料夾＝`info.json`（`_metainfo._type`＝`llm_cpu`、`_version`＝1；解指示詞，
  規則同 agent.md §2）＋`requests/<name>.json`→`running/<name>.json`→`done/<name>.json`；請求檔＝`{"engine": {...}, "body": {...},
  "result": "<絕對路徑>"}`（engine 是 agent 已解好的那包，含 api_key；cpu 不解指示詞、不讀 agent 資料夾）；結果檔＝
  `{"ok": true, "message": {...}}`／`{"ok": false, "error": "<白話>"}`，先 `.tmp` 再 rename；錯誤代號沿用 agent.md §5 的那套。
- **程式規範** `proto5.1/spec/aos-llm-cpu.md`＋程式 `proto5.1/lib/aos_llm_cpu.py`＋`proto5.1/cli/aos-llm-cpu`：`aos-llm-cpu [dir]`
  一次做一件：(1) 收屍：`running/` 裡 mtime 距今超過 `engine.timeout_ms`＋30 秒的→寫 `ok:false` 結果、搬 `done/`；(2) `requests/`
  照檔名排序拿第一個、rename 到 `running/`＝認領（rename 失敗＝別人搶走，拿下一個）；(3) `aos_llm_ask.call(engine, body)`；
  成功寫 `ok:true`＋message、`EngineFailed` 寫 `ok:false`；搬 `done/`；退 0。(4) 沒東西→101。讀驗錯 1、用法錯 2。
  不重試、不排優先序、不記 usage。同名已在三處任一＝拒收（agent 寫檔前先看；cpu 這邊 rename 撞到就跳過）。

### B. aos-agent 的 `think` 改成可以丟出去

照 llm-cpu-summary §2.3：`info.json` 的 `engine` 多一格 **`cpu`**（路徑，相對 agent 資料夾；沒寫＝現在的同步問法，
既有測試不能壞）。有 `cpu` 時 `think`：

| 進場看到 | 做什麼 | state | 退 |
|---|---|---|---|
| 記憶尾巴是帶 tool_calls 的 assistant | 自癒照舊 | `act` | 0 |
| `<agent>/ask-result.json` 存在 | 收回：`ok:true`→message 接記憶、`ok:false`→stderr `aos-agent: engine: …`、記憶不動；兩種都 rename 成 `.done` | `act`／`idle`／失敗留 `think` | 0 |
| 不存在 | 送出：先寫 `<cpu>/requests/<agent 資料夾名>-<epoch ns>.json`（result＝`<agent>/ask-result.json` 絕對路徑），再往 `waits` 加一條 `"ask-result.json"`（不開 consume） | `think` 不變 | 0 |

- `aos_agent_info.load()` 要驗 `engine.cpu`（字串、解指示詞、回絕對路徑 `engine["cpu"]`；沒寫＝None），`aos_llm_ask` 送 body 時不能把 `cpu` 送出去。
- 規範改 `aos-agent.md` §3 think 那幾列、拿掉「aos-agent 只劃不加 waits」那句（§2）、§5 llm cpu 移正文；`aos-llm-ask.md` §2.4 engine 加 `cpu`；`agent.md` 4.2 補一句「aos-agent 自己也會加條目」。

### C. 兩個逾時關卡

照 timeout-summary §4 前兩列：

1. **每個工具 60 秒**：工具元素旁加 `_timeout_ms`（正整數；`_` 開頭本來就不送模型；`_meta` 不動）；`aos_agent_info` 驗它、放進
   `tools_raw`；`act` 呼叫 `run_inst(inst, arguments, timeout_ms=…)`，沒寫＝60000；逾時的 tool 訊息＝`工具 xxx 逾時（60000 ms）：`＋
   收到的 stdout。`run_inst` 要能回報「是逾時砍的」（現在只有退出碼 143／137，不可靠）——加一個回傳值或旗標，自己選、記 findings。
   規範：`aos-llm-ask.md` §2.3 工具檔加 `_timeout_ms`；`aos-agent.md` §3 act 那列與 §5 逾時那句。
2. **引擎連敗 3 次暫停**：`state.json` 加 `errors`（整數、字面、程式寫；沒寫＝0）。`think` 引擎失敗（同步 EngineFailed 或收回 `ok:false`）
   →`errors`+1；成功→歸 0；到 3 →`errors` 歸 0、往 `waits` 加一條 `"continue.json"`、stderr 一行 `aos-agent: stuck: 引擎連敗 3 次，touch continue.json 繼續`。
   規範：`agent.md` §4 表加 `errors`；`aos-agent.md` §3。

### D. 一路記 findings

`proto5.1/notes/findings.md`：每撞到一件事就加一條——(1) 建議寫得不夠、你得自己決定的（寫你選了什麼、為什麼）；(2) 建議做下去發現
不對勁或有更簡單做法的；(3) 規範之間打架的；(4) 測試時發現的邊角（崩在中間、兩顆 cpu 搶、result 檔壞掉…）。這份是使用者最想看的東西，
**寫具體**：檔名、情境、你怎麼處理。

## 規則

1. Python 3.12 標準庫；風格跟既有檔一致（中文 docstring、白話錯誤、模組開頭說明）。
2. `proto5.1/lib/test/`：既有 571 條不能壞（同步路徑行為不變）；新加 `test_llm_cpu.py`（用 `test_llm_ask.FakeLLM`：成功、失敗、認領、兩份同名、
   收屍、101、CLI 退出碼）與 `test_agent.py` 補（think 送出／收回／失敗留 think／收回後 act 或 idle、`_timeout_ms` 逾時的 tool 訊息、
   errors 累計與 3 次→continue.json、touch 之後恢復）。
3. 真跑一次：LM Studio `http://127.0.0.1:1234/v1`（`qwen/qwen3-1.7b`）：在 `/tmp/claude-1000/-home-guanyu-projs-aos/c15290bb-f956-4ef2-8f96-46acea00faa2/scratchpad/p51-demo/`
   建一個 llm cpu 資料夾＋一個 agent（`engine.cpu` 指過去、一個 `now` 工具、`input.json`「現在幾點？用工具查」），交替叫 `cli/aos-agent A`
   與 `cli/aos-llm-cpu C` 直到 agent 回話、退 101；把每次的退出碼與 state／waits 變化貼進回報。
4. 文件：`proto5.1/lib/README.md`（加 aos_llm_cpu 一節、agent 那節補 think 兩段與逾時、測試表）、`proto5.1/README.md` 分段表第 1 段狀態改「做完」＋
   加規範表（沿用 proto5 README 的表、多 llm-cpu／aos-llm-cpu 兩列）。
5. 只動 `proto5.1/`；不 commit、不 push、不 stash、不 checkout。
6. 回報（中文、條列）：做了什麼（檔案清單）、測試數字、真跑紀錄、findings 有幾條＋最重要的 5 條、還沒做的。
