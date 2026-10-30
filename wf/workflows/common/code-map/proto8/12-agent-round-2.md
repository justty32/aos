← [入口](../proto8.md)｜涵蓋：agent-round 的格之二（範本 agent-nia、round 當外部接口、測試，10-28 晚）｜上一份：[12-agent-round](12-agent-round.md)（各格逐檔）｜工具庫其他部分見 [09-lib](09-lib.md)

### 範本 agent-nia（10-28 晚，第 6 步）

| 哪裡 | 負責什麼 |
|---|---|
| `demo/agent-nia/_entry` | JSON 入口 `["aos-loop", "loop.json"]` |
| `demo/agent-nia/loop.json` | 單子 `aos-round {"$env": "AOS_CD"}`（10-30 aos-round 第 4 步，原本 `aos-parts run round`；`timeout_ms` 600000 管一格、`max` 40 數的也是格；開 `ctl.json`／`state.json` 兩扇窗，落在 `$AOS_STACK`）：fsm 走了一格退 0＝再叫、queue 空 idle 退 10＝loop 停 |
| `demo/agent-nia/parts.json` | 格的通訊錄，手寫相對路徑指 `../../lib/`：round（10-30 起 env `ROUND_ON_EMPTY` `stop`，範本射後不理）、queue、history、act、`hook/pre_think`＝compact（`MAX_BYTES` 65536）、`endpoint/default`＝fake、`endpoint/litellm`＝openai（localhost:4000） |
| `demo/agent-nia/tools.json` | 腦的工具：clock、math（相對路徑指 `../../lib/base/`） |
| `demo/agent-nia/system.txt` | system 訊息 |
| `demo/run.sh`（職責變了） | 最後多一段 agent-nia（假腦一題、印工作區與 stack 樹；10-30 起題目經 `aos-parts run queue … push` 放進 stack 的 queue），共七段 |

### round 當外部接口（10-28 晚，第 11 步）

| 哪裡 | 負責什麼 |
|---|---|
| `lib/aos/ask_round/_entry` | 工具（照 lib 契約）：stdin `{"question", "agent"?, "timeout_s"?}`；`aos-parts run queue <agent> push` 放一則 user message（10-30 起，agent-lifecycle 第 5 步）→ `aos-round <agent>` 一格一格反覆叫（10-30 aos-round 第 5 步，原本 `aos-parts run round`），每格後 `queue pop --timeout-s 0 <信號>`：信不見了（finish 格交卷了）就印 history 最新的 assistant；停手不看 aos-round 的 10（被問的 agent 是 `ROUND_ON_EMPTY=idle` 也不卡）（`ASK_MAX_STEPS` 預設 200、`timeout_s` 預設 120）；工作區只建 `.stack/`；agent＝參數 ＞ `ASK_AGENT`，工作區＝`ASK_WS` ＞ `$AOS_STACK/<agent 名>/`、stack＝`<工作區>/.stack/`；錯 `AgentMissing`／`AgentBad`／`StackMissing`／`SettingBad`／`QueueFailed`／`RoundFailed`／`AnswerMissing`… |
| `lib/aos/ask_round/_tooldef.json`、`_metainfo` | 給模型的說明（question 必給、agent／timeout_s 選填）；特性（`time_ms.max` 600000，aos-mcp 拿它當逾時） |

### 測試

| 哪裡 | 涵蓋 |
|---|---|
| `tests/test_round.py` | endpoint fake、openai（假 server：答案與 usage、經 aos-parts run 帶註冊檔 env、各錯誤代號、連不上；LiteLLM 實跑連不上就 skip）；act（順序、平行、工具的問題回給腦、pre_tool／post_tool、插話退 10、自己的錯）；round（10-30 起題目經 queue push、答案看 history；假腦答完一題、system 與 tools 帶進請求、trace 每格一行、沒題退 10；`ROUND_ON_EMPTY=idle` 空退 0 不動 history／trace、壞值 SettingBad；claim 死在搬進 cur/ 之後的補認領；aos-loop 下 idle＋`interval_ms` 常駐、ctl paused 時信留 new/、放行後答出、stopped 收工；endpoint 壞退 1 且 history 沒多接、on_error switch 換 endpoint.txt 再成功、retry 有上限；pause yield 後接著做；`--step` 一格一格、aos-loop 跑 `--step`；pre_round 失敗；插話 claim --more 再問腦、兩題一起答；PartMissing／AgentBad／SettingBad）；`RoundFsm`（10-30 aos-round 第 2 步：`aos-fsm fsm-stop.json`／`fsm-idle.json` 一次一格，驗 state.txt、history 與 trace 的 (state, code, next)：無工具、帶 clock、插話 act 10 → more → act、endpoint 壞停在 think 後 on_error switch、`MAX_RETRIES` 用完 `round/think: EndpointFailed`、crash 後 state 說 act 卻沒待回的 calls、idle 表接住 10、補認領不叫 pre_round、pre_round 失敗、格自己的錯）；`AosRound`（第 3 步：`bin/aos-round` 單次叫一格、相對 `AOS_STACK`；loop.json 用 aos-round 整隻跑：stop 一題答完、idle＋ctl paused／stopped、單子 `timeout_ms` 殺在 think；ArgumentsBad／AgentBad／SettingBad／PartsBad）；`AgentCase`＝三類共用的 tmp agent |
| `tests/test_round_queue.py` | queue（10-30 改 `$AOS_STACK/queue/` 佈局：push 之後 `queue/new/` 一封有序號、body 原樣；claim 之後 history 多一則、信在 `cur/`；finish 之後信不見、`--keep` 進 `done/`；照 push 的順序；push 壞 message、不收名字；沒 stack 也建得出 queue；非有序與 body 壞＝壞信丟掉；withdraw、claim 各步當掉重跑（含 --more）、舊 `current.txt` 不算、不拿上一題答案、claim --more、沒 history 格信留 `new/`、沒 queue 退 10、pop 等到答案（跳過帶 tool_calls 的）／逾時／LetterUnknown／AnswerMissing、push --wait、emit、沒認領就 finish；`aos_bins.py` 的 C++ 清單 10-30 加 `aos-post`）、history（壞輸入、compact 換上與 `--expect-bytes`）、compact（大 history 壓短、沒超過不動、endpoint 壞 history 不動） |
| `tests/test_nia.py` | 10-30 起範本與 spawn 經 queue 格放題、看 history（spawn 不再經 `aos-ai ask`／`run`），範本另驗 loop 的 state 窗收工 `done`、parts.json 的 `ROUND_ON_EMPTY`、loop.json 的兩扇窗；ask_round（登記進 tools.json 經 aos-tools call 拿到假腦答案、工作區在工具小格、答完不常駐；工具小資料夾 `.env` 固定 `ASK_AGENT`；10-30 aos-round 第 5 步起：`ASK_MAX_STEPS=1` 只走一格 AnswerMissing、信留 cur/、state 停在 think，再叫一次接著答完、壞值 SettingBad；被問的 agent 設 `ROUND_ON_EMPTY=idle` 也答完就停〔trace 剛好 idle、think、act、think、finish〕；RoundFailed 與參數錯）；範本 agent-nia（10-30 aos-round 第 4 步起看 fsm trace：一題＝idle → think → act → think → finish → idle 退 10、state.txt 停在 idle；兩題＝finish 兩次、最後 idle 退 10；沒題＝只有一行 idle 10、loop 正常停；loop.json 叫 aos-round、pre_think 掛 compact、parts.json／tools.json 只用相對路徑且每格找得到）、`aos-ai spawn --from agent-nia`（註冊檔改成絕對、跑一題答得出來）、沒有 parts.json 的範本 tools.json 不動 |
| `tests/test_lib.py`（職責變了） | 形狀檢查（三個檔、NAME 行…）跳過 agent 的格：`lib/endpoint/` 整層與 `lib/agent/` 的 act、queue、history、round、compact（不是工具，沒有 `_tooldef.json`） |
