← [入口](../proto8.md)｜涵蓋：agent-round 的格之二（範本 agent-nia、round 當外部接口、測試，10-28 晚）｜上一份：[12-agent-round](12-agent-round.md)（各格逐檔）｜工具庫其他部分見 [09-lib](09-lib.md)

### 範本 agent-nia（10-28 晚，第 6 步）

| 哪裡 | 負責什麼 |
|---|---|
| `demo/agent-nia/_entry` | JSON 入口 `["aos-loop", "loop.json"]` |
| `demo/agent-nia/loop.json` | 單子 `["aos-fsm", "fsm-stop.json"]`、`cwd` `../../lib/agent/round`（11-01 起；之前是 `aos-round --on-empty stop {"$env": "AOS_CD"}`，再之前 `aos-parts run round`；停著等＝改指 `fsm-idle.json`；`timeout_ms` 600000 管一格、`max` 40 數的也是格；開 `ctl.json`／`state.json` 兩扇窗，落在 `$AOS_STACK`）：fsm 走了一格退 0＝再叫、queue 空 idle 退 10＝loop 停 |
| `demo/agent-nia/parts.json` | 格的通訊錄（11-01 起 aos-exec 格式：槽值＝路徑字串或 `{".env", "_entry"}`、`hook`／`endpoint` 巢狀、頂層不包 `parts`），手寫相對路徑指 `../../lib/`：queue（11-01 起沒有 round 槽：停法改 loop.json 的 `--on-empty`）、history、act、`hook/pre_think`＝compact（路徑字串、門檻用預設 65536）、`endpoint/default`＝fake、`endpoint/litellm`＝openai（`.env` localhost:4000、模型名） |
| `demo/agent-nia/tools.json` | 腦的工具：clock、math（相對路徑指 `../../lib/base/`） |
| `demo/agent-nia/system.txt` | system 訊息 |
| `demo/run.sh`（職責變了） | 最後多一段 agent-nia（假腦一題、印工作區與 stack 樹；10-30 起題目經 queue 格 push 放進 stack 的 queue；11-01 起直接 `aos-exec <agent>/parts.json#/queue <agent> push`），共七段 |

### round 當外部接口（10-28 晚，第 11 步）

| 哪裡 | 負責什麼 |
|---|---|
| `lib/aos/ask_round/_entry` | 工具（照 lib 契約）：stdin `{"question", "agent"?, "timeout_s"?}`；queue 格（11-01 起經 `lib/agent/parts.py` 找、`aos-exec` 它；之前是 `aos-parts run queue`）`push` 放一則 user message（10-30 起，agent-lifecycle 第 5 步）→ `aos-exec <agent>/loop.json#/exec` 一格一格反覆叫（11-01 起；之前 `aos-round <agent>`、再之前 `aos-parts run round`；沒有 loop.json＝RoundFailed），每格後 `queue pop --timeout-s 0 <信號>`：信不見了（finish 格交卷了）就印 history 最新的 assistant；停手不看那格的 10（被問的 agent 的表是 `fsm-idle.json` 也不卡）（`--max-steps` 預設 200、`timeout_s` 預設 120）；工作區只建 `.stack/`；agent＝參數 ＞ `--agent`，工作區＝`--ws` ＞ `$AOS_STACK/tools/<agent 名>/`（11-02 進 `tools/`）、stack＝`<工作區>/.stack/`（11-01 起是旗標）；錯 `AgentMissing`／`AgentBad`／`StackMissing`／`ArgumentsBad`／`FlagUnknown`／`QueueFailed`／`RoundFailed`／`AnswerMissing`… |
| `lib/aos/ask_round/_tooldef.json`、`_metainfo` | 給模型的說明（question 必給、agent／timeout_s 選填）；特性（`time_ms.max` 600000，aos-mcp 拿它當逾時） |

### 測試

| 哪裡 | 涵蓋 |
|---|---|
| `tests/test_round_endpoint.py` | 10-31 自 test_round.py 拆出（行為不變）；endpoint fake、openai（假 server：答案與 usage、經 parts.json 的 `.env` key 帶 env〔11-01 起預設不蓋、`--dotenv-override` 才蓋〕、各錯誤代號、連不上；11-01 起 endpoint 名走第二個參數〔環境變數不再作用〕、fake 收下名字不用；LiteLLM 實跑連不上就 skip） |
| `tests/test_round_act.py` | 10-31 自 test_round.py 拆出（行為不變）；act（順序、平行〔11-01 起 `--max-parallel` argv、parts.json argv 陣列、壞值 ParallelBad、舊環境變數不再作用〕、工具的問題回給腦、pre_tool／post_tool、插話退 10、自己的錯；11-01 起登記了但壞的掛勾＝HookFailed、parts.json 不是物件＝PartsBad） |
| `tests/test_round_fsm.py` | 10-31 自 test_round.py 拆出（行為不變）；（舊骨架的 `Round` 類 10-30 aos-round 第 6 步隨 `round/_entry` 刪了）`RoundFsm`（10-30 aos-round 第 2 步：`aos-fsm fsm-stop.json`／`fsm-idle.json` 一次一格，驗 state.txt、history 與 spy_bin 旁觀者記的 (state, code, next)（11-03）：無工具、帶 clock、插話 act 10 → more → act、endpoint 壞停在 think 後 on_error switch、重來 3 次用完 `round/think: EndpointFailed`（11-01 起寫死、環境變數不再作用）、crash 後 state 說 act 卻沒待回的 calls、idle 表接住 10、補認領不叫 pre_round、pre_round 失敗、格自己的錯；第 6 步從 Round 搬來 system.txt 與 tools 帶進請求、第一題答完後的補認領不拿舊答案） |
| `tests/test_round_loop.py` | 11-01 取代 test_round_bin.py（bin/aos-round 刪了，它自己的錯那兩案跟著刪）；`RoundLoop`：loop.json＝`aos-fsm 表`＋`cwd` round 資料夾；`aos-exec <agent>/loop.json#/exec` 單次一格（舊的 `AOS_ROUND_AGENT` 不再作用）、相對 `AOS_STACK`；整隻跑：stop 表一題答完、idle 表＋ctl paused／stopped、單子 `timeout_ms` 殺在 think |
| `tests/round_common.py` | 10-31 自 test_round.py 拆出（行為不變）；`AgentCase`＝RoundFsm、RoundLoop 共用的 tmp agent（也放 Base、err_code、req、user、`parts_json`〔測試的扁平表 → 11-01 的 aos-exec 格式〕、`absolute`〔parts.json 相對路徑轉絕對〕 與 EXEC／FAKE／OPENAI／ACT／CLOCK 等路徑常數，四個 test_round_*.py 共用） |
| `tests/test_round_queue.py` | queue（10-30 改 `$AOS_STACK/queue/` 佈局：push 之後 `queue/new/` 一封有序號、body 原樣；claim 之後 history 多一則、信在 `cur/`；finish 之後信不見、`--keep` 進 `done/`；照 push 的順序；push 壞 message、不收名字；沒 stack 也建得出 queue；非有序與 body 壞＝壞信丟掉、`mailbox_warning.txt` 記最後一封的原因、check 不過的原因帶 aos-post 那行；withdraw、claim 各步當掉重跑（含 --more）、舊 `current.txt` 不算、不拿上一題答案、claim --more、沒 history 格信留 `new/`、沒 queue 退 10、pop 等到答案（跳過帶 tool_calls 的）／逾時／LetterUnknown／AnswerMissing、push --wait、emit、沒認領就 finish；`aos_bins.py` 的 C++ 清單 10-30 加 `aos-post`）、history（壞輸入、compact 換上與 `--expect-bytes`）、compact（大 history 壓短、report.json 的 `endpoint` 記整個目標〔11-02 修：曾只記第一個字元〕、沒超過不動、endpoint 壞 history 不動；11-01 起 compact 槽寫 parts.json 的 argv 陣列〔相對路徑〕帶 `--max-bytes`、壞值 ArgumentsBad、舊環境變數不再作用） |
| `tests/test_nia.py` | 10-30 起範本與 spawn 經 queue 格放題、看 history（spawn 不再經 `aos-ai ask`／`run`），範本另驗 loop 的 state 窗收工 `done`、loop.json 的 `aos-fsm fsm-stop.json`＋相對 cwd 與兩扇窗；ask_round（登記進 tools.json 經 aos-tools call 拿到假腦答案、工作區在工具小格、答完不常駐；工具小資料夾 `_entry`＝JSON argv `[ask_round, --agent …]`、舊環境變數不再作用（11-01）；`--max-steps 1` 只走一格 AnswerMissing、信留 cur/、state 停在 think，同 `--ws` 再叫接著答完、壞值 ArgumentsBad／FlagUnknown；被問的 agent 的 loop.json 指 `fsm-idle.json` 也答完就停〔trace 剛好 idle、think、act、think、finish〕；RoundFailed〔含沒有 loop.json〕與參數錯）；範本 agent-nia（10-30 aos-round 第 4 步起看 fsm trace：一題＝idle → think → act → think → finish → idle 退 10、state.txt 停在 idle；兩題＝finish 兩次、最後 idle 退 10；沒題＝只有一行 idle 10、loop 正常停；loop.json 叫 aos-fsm、pre_think 掛 compact、parts.json／tools.json 只用相對路徑且每格找得到）、`aos-ai spawn --from agent-nia`（註冊檔與 loop.json 的 cwd 改成絕對、跑一題答得出來）、沒有 parts.json 的範本 tools.json 不動 |
| `tests/test_lib.py`（職責變了） | 形狀檢查（三個檔、NAME 行…）跳過 agent 的格：`lib/endpoint/` 整層與 `lib/agent/` 的 act、queue、history、round、compact（不是工具，沒有 `_tooldef.json`） |
