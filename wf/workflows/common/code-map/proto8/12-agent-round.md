← [入口](../proto8.md)｜涵蓋：agent-round 的格（`proto8/lib/agent/` 的 round、queue、history、compact、act，`proto8/lib/endpoint/`）與它們的測試、範本 `demo/agent-nia`，10-28 晚｜工具庫其他部分見 [09-lib](09-lib.md)

### agent 自己的格（不是給腦叫的工具）

一輪（round）照順序叫的那幾格：每格一個資料夾程式，叫法 `aos-exec <格> <agent 資料夾絕對路徑> [子命令]`，stdin／stdout 是資料、錯 stderr 一行 `名: 代號 原因` 退 1；格與格之間經 `aos-parts --file <agent>/parts.json which --json 槽` 互相找。沒有 `_tooldef.json`／`_metainfo`（不是工具）。設計與代定：[thinking 2026-10-28 agent-round](../../../../../proto8/thinking/2026-10-28-agent-round.md)（§ 2～§ 5、文末「實作時代定」）；說明在 [lib/README「agent 自己的格」](../../../../../proto8/lib/README.md)。

| 哪裡 | 負責什麼 |
|---|---|
| `lib/agent/round/_entry` | 一輪的骨架：照「從哪接著做」（`cur/` 與 history 最後一則）認領 → 問腦 → 跑工具 → 交卷，叫 `hook/pre_round`、`pre_think`、`post_think`、`on_error`、`pause`、`post_round`；endpoint 照 `$AOS_STACK/endpoint.txt` 選、on_error 的 retry／switch（上限 `MAX_RETRIES`，預設 3）；act 退 10（插話）就 `queue claim --more`；每叫一格 `$AOS_STACK/trace.jsonl` 一行；`--step`＝只做下一格（給 aos-loop 一格一格跑） |
| `lib/agent/queue/_entry` | 收題格：`$AOS_WS/new cur out done` 信箱的 push／pop／claim [--more]／peek／current／done／emit／finish／withdraw；claim 先接 history、再寫 `current.txt`、最後搬 `cur/` |
| `lib/agent/history/_entry` | 對話紀錄格：`$AOS_STACK/history.jsonl` 的 append／read／compact（compact 收 stdin 的短版，舊的整份收進 `history_archive/<UTC 毫秒>.jsonl` 再換上，`--expect-bytes`） |
| `lib/agent/compact/_entry` | 掛在 `hook/pre_think`：history 超過 `MAX_BYTES` 才壓（三步土法：工具呼叫各一句 → 逐段總結＋保留行 → 修飾），壓好的交給 history compact 換上；半成品與報告在 `$AOS_STACK/compact/`；來源 demo/agent-hal/compact |
| `lib/agent/compact/ask.py` | compact 格問腦（經 endpoint 格）與讀回覆（容許 ``` 包起來的 JSON、讀不懂走退路） |
| `lib/agent/compact/prompts/` | 三步的提示詞：`note.txt`、`segment.txt`、`final.txt` |
| `lib/agent/act/_entry` | 跑工具格：吃一則 assistant，每個 tool_call 經 `hook/pre_tool`（10＝不跑）→ `aos-tools call` → `hook/post_tool`，吐一行一則 tool 訊息、照原順序；`MAX_PARALLEL` 一批一批跑；批與批之間 `new/` 有題就問 `hook/on_interrupt`，interrupt＝剩下的接「被打斷」、退 10；全有或全無 |
| `lib/endpoint/fake/_entry` | 假腦：最後一則 user＋tools 有 clock＝叫 clock，否則 `FAKE ANSWER to: …`（接過 tool 附 clock said）；不連網、不寫 usage |
| `lib/endpoint/openai/_entry` | OpenAI 相容腦：stdin 請求體 → `{AOS_BRAIN_URL}/chat/completions` → 一行 assistant（只留 role／content／tool_calls）；usage 追加 `$AOS_STACK/usage.jsonl`；錯 `BrainFailed`／`KeyBad`／`ModelUnknown`／`RequestBad`／`ReplyBad`／`UrlMissing`／`TimeoutBad` |

### 範本 agent-nia（10-28 晚，第 6 步）

| 哪裡 | 負責什麼 |
|---|---|
| `demo/agent-nia/_entry` | JSON 入口 `["aos-loop", "loop.json"]` |
| `demo/agent-nia/loop.json` | 單子 `aos-parts run round {"$env": "AOS_CD"}`（`timeout_ms` 600000、`max` 40）：round 退 0＝再叫一次、退 10＝loop 停 |
| `demo/agent-nia/parts.json` | 格的通訊錄，手寫相對路徑指 `../../lib/`：round、queue、history、act、`hook/pre_think`＝compact（`MAX_BYTES` 65536）、`endpoint/default`＝fake、`endpoint/litellm`＝openai（localhost:4000） |
| `demo/agent-nia/tools.json` | 腦的工具：clock、math（相對路徑指 `../../lib/base/`） |
| `demo/agent-nia/system.txt` | system 訊息 |
| `demo/run.sh`（職責變了） | 最後多一段 agent-nia（假腦一題、印工作區與 stack 樹），共七段 |

### 測試

| 哪裡 | 涵蓋 |
|---|---|
| `tests/test_round.py` | endpoint fake、openai（假 server：答案與 usage、經 aos-parts run 帶註冊檔 env、各錯誤代號、連不上；LiteLLM 實跑連不上就 skip）；act（順序、平行、工具的問題回給腦、pre_tool／post_tool、插話退 10、自己的錯）；round（假腦答完一題、system 與 tools 帶進請求、trace 每格一行、沒題退 10；endpoint 壞退 1 且 history 沒多接、on_error switch 換 endpoint.txt 再成功、retry 有上限；pause yield 後接著做；`--step` 一格一格、aos-loop 跑 `--step`；pre_round 失敗；插話 claim --more 再問腦、兩題一起答；PartMissing／AgentBad／SettingBad） |
| `tests/test_round_queue.py` | queue（push → claim → finish、撞名與空題、withdraw、claim 各步當掉重跑、不拿上一題答案、claim --more、沒 history 格、pop 逾時、emit、沒認領就 finish）、history（壞輸入、compact 換上與 `--expect-bytes`）、compact（大 history 壓短、沒超過不動、endpoint 壞 history 不動） |
| `tests/test_nia.py` | 範本 agent-nia（一題答完、stack 的檔與 trace 有 pre_think、兩題＝round 退 0 後 loop 再叫、沒題 loop 正常停、parts.json／tools.json 只用相對路徑且每格找得到）、`aos-ai spawn --from agent-nia`（註冊檔改成絕對、跑一題答得出來）、沒有 parts.json 的範本 tools.json 不動 |
| `tests/test_lib.py`（職責變了） | 形狀檢查（三個檔、NAME 行…）跳過 agent 的格：`lib/endpoint/` 整層與 `lib/agent/` 的 act、queue、history、round、compact（不是工具，沒有 `_tooldef.json`） |
