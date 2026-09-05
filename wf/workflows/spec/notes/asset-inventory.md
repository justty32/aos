# 舊程式碼盤點：拆出來重用 vs 廢棄

依 code-map.md／ideas/README.md／2026-09-05 拍板 8 條盤點。只讀不改。

判定三檔：**RU**＝可直接重用｜**改**＝拆開改一改能用｜**廢**＝廢棄。

| 組件（路徑） | 今天做什麼 | 新構想對應 | 判定 | 理由 | 測試 |
|---|---|---|---|---|---|
| `core/exec/src/start.cpp`,`spawn_prep.cpp` | 批次 fork/exec 啟動 | 06 一格=exec | RU | 純 POSIX 原語，跟舊 protocol 無關 | 有 |
| `core/exec/src/wait.cpp`,`wait_all.cpp` | 批次等完、逾時 kill、收結果 | 06 | RU | 同上，逾時語意通用 | 有 |
| `core/exec/src/interrupt.cpp` | signal handler 可呼叫的中斷登記表 | 06 | RU | 任何 runner 都要能中斷子行程群組 | 有 |
| `core/exec/src/tempfile.cpp` | mkstemp 暫存檔轉 stdio | 沒有直接對應 | RU | 避免 pipe 死結的通用技巧 | 間接 |
| `core/exec/src/clock.cpp` | 單調時鐘／deadline 換算 | 06 | RU | 純數學，通用 | 間接 |
| `core/wire/src/inst.cpp` | Inst(指令) JSON 邊界 | 04／09 | 改 | 序列化手法可重用，但欄位綁死舊固定 inbox schema | 有 |
| `core/wire/src/outcome.cpp` | Outcome(結果) JSON 邊界 | 09 | 改 | I-02/I-04 要求成敗拆兩頻道，目前混一起 | 有 |
| `core/wire/src/state.cpp`+`json_io.hpp` | state.json running[]／agents 鏡射 | 07 | 改 | 可能被 daemon 登記表(G-03)取代，共用取值 helper 可留 | 有 |
| `core/loop/src/layout.cpp` | `.aos/` 路徑推導 | 04 | 改 | 找世界／正規化 folder 的思路可留，具體目錄名(inbox/every/batch)是舊協定 | 有 |
| `core/loop/src/fs.cpp` | `write_atomic`：tmp 寫再 rename | 04／05 | RU | 這就是題目要的「原子改名投遞」核心，跟版面無關 | 間接(多處測試覆蓋) |
| `core/loop/src/deliver.cpp`,`deliver_cli.cpp` | 投遞進 inbox | 09 | 改 | 用了 write_atomic，但 Inst schema 要跟 I-01 的「結果落點由父指定」改 | 有 |
| `core/loop/src/turn.cpp`,`aggregate.cpp` | 一回合：匯聚→並行→落檔→state | 06 | 改 | 順序精神對，但 batch/<turn>/out 固定路徑被 I-01 廢除 | 有 |
| `core/loop/src/state.cpp`(loop) | running/done state 組裝 | 07 | 改 | 同上，可能被 daemon 登記表取代 | 有 |
| `core/loop/src/daemon.cpp` | `--daemon`：fork+setsid 背景化、run.log | 07 | 改 | fork/setsid 技巧可留，但 G-01 要 daemon 改管「替每塊地起 aos run」而非自己背景化單一世界 | 無專測(間接) |
| `core/loop/src/wake.cpp` | 空回合盯 inbox/say 簽章、有信立刻醒 | 06 | RU | F-03 明確保留「沒新指令就停、有信就醒」，精神完全match | 有 |
| `core/loop/src/run.cpp`,`stop_cli.cpp` | run/stop CLI，`run.lock` 單例保證 | 06／12 | 改 | flock 單例機制可留，CLI 外形要配合 12 章重排 | 有 |
| `core/tool/src/spec.cpp` | 工具 spec 驗證／序列化 | 11 | 改 | 驗證手法可重用，但欄位比新構想多(lifecycle/state/guarantee等)，K-02 要精簡 | 有 |
| `core/tool/src/registry.cpp` | 世界工具登記表原子讀寫排序 | 11 | 改 | 機制對，schema 要瘦身 | 有 |
| `core/tool/src/probe.cpp` | 用 exec 跑 `--metainfo` 探測 | 11 | RU | 獨立、通用，不受 I/E 系列裁決影響 | 有 |
| `core/tool/src/contacts.cpp`,`contact_status.cpp` | 通訊錄讀寫 | 11 | RU | K-03 定案的形狀「陣列、每列{名字,資料夾,備註?}」就是現有實作 | 有 |
| `core/tool/src/tool_cli.cpp`,`contact_cli.cpp` | tool/contact CLI | 11／12 | 改 | 命令可留，但要配合 K-04~K-06 加欄位、L-01/L-02 重排指令面 | 有 |
| `core/llm/src/llm.cpp` | OpenAI 相容 chat completion client(libcurl) | 07(LLM 世界) | RU | 打端點的動作跟並行策略無關，哪個世界都要用它 | 有 |
| `core/llm/src/slot.cpp` | flock 並行槽＋等待逾時 exit 75 | 07 | 廢 | G-04 明講「08-30 那套鎖檔槽機制作廢」，07-daemon.md 描述的`<AOS_HOME>/slots/`正是這支;改由 daemon 走時鐘時數並行 | 有 |
| `core/llm/src/run.cpp` | `aos llm` CLI | 07／11 | 改 | 讀 stdin/呼叫 client 可留，但 `--priority`/`--slots` 依附 slot.cpp 要拔掉，退出碼配合 K-04 四種 | 有(help部分) |
| `core/agent/src/paths.cpp` | 世界／agent 路徑解析(resolve_folder/name) | 08 | 改 | 「一個 agent=一個資料夾」精神留，但要配合 H-03 限制參數檔、H-05 借鐘規則 | 有 |
| `core/agent/src/store.cpp` | journal 原子寫、log.md 重畫防竄改 | 08 | 改 | 原子寫/重畫技巧可留，agent 整體版面會因 08 章重寫而動 | 有 |
| `core/agent/src/deliver.cpp` | 包裝 loop::deliver 送工具 instruction | 09 | 改 | I-01 要求呼叫記錄帶「結果落點」欄，目前是直接投 argv 進 inbox，要重寫 | 有 |
| `core/agent/src/inbox.cpp`,`inbox_cli.cpp` | agent 收件匣讀取／搬移 | 09 | 改 | 通訊機制概念留，路徑/搬遷要配合新呼叫協定 | 有 |
| `core/agent/src/tools.cpp` | 工具清單一行化、argv 展開、呼叫抽取 | 11 | 改 | 「給模型看的表述、錯誤封套」跟 11 章直接對應，K-01 要求拿掉 agent 白名單交集那段，其餘邏輯可留 | 有 |
| `core/agent/src/step.cpp` | 回合內同步呼叫 LLM、更新 history/log/status | 08 | 廢 | F-02 裁定 LLM 必須是獨立世界、同步呼叫在架構上不成立，這支正是「同回合同步等 LLM」的實作 | 有 |
| `core/agent/src/engine.cpp`,`engine_pi.cpp` | lmstudio/pi 引擎選擇，pi 同步做完思考+工具 | 08 | 廢 | 同上，且 pi 不走三回合投遞，跟 F-02＋09 章協定衝突更大 | 有 |
| `core/agent/src/user.cpp` | `~` 使用者世界 say/listen、天然通訊錄 | 沒有明確對應 | 不確定 | 概念可能保留(人跟系統對話)，但 13 章沒點名哪一章接手 | 有(smoke_user.sh) |
| `core/agent/src/init.cpp`,`run.cpp`,`run_top.cpp`,`chat_cli.cpp` | agent CLI 群、初始化版面 | 08／12 | 改 | init 建版面部分邏輯可留，CLI 外形依附 step/engine 的同步模型，要跟著大改 | 有 |
| `core/tick/src/due.cpp` | interval/slot/schedule 到期判定(純函式) | 06／07 | RU | 純日期數學，不碰 LLM 不碰同步問題，新舊架構都要「這件事到期了嗎」 | 有 |
| `core/tick/src/table.cpp` | `wf-table/1` 讀寫 | 07 | 改 | atomic 讀寫手法可留，但 routines.json/schedule.json 這兩張表本身是否被 daemon 登記表(E-01 接力棒/G-03)取代還不清楚 | 有 |
| `core/tick/src/clock.cpp`,`ids.cpp`,`log.cpp`,`paths.cpp` | 時鐘換算、id 產生、log.md 追加、路徑推導 | 07 | 改 | 小工具技巧通用，schema 要配合新登記表 | 有 |
| `core/tick/src/tick_cli.cpp`,`heartbeat_cli.cpp`,`routine_cli.cpp`,`schedule_cli.cpp`,`cli_common.cpp` | tick/heartbeat/routine/schedule 整組 CLI | 07 | 不確定 | G-01「所有時鐘由 daemon 走並登記在一處」——這整套獨立心跳系統會不會被 daemon 直接吸收掉，沒有明說 | 有 |

## 建議第一批拿出來重用的

- `core/exec` 全部五塊（start_all／wait_all／interrupt／tempfile／clock）：POSIX 執行原語，跟協定無關。
- `core/loop/src/fs.cpp` 的 `write_atomic`：題目點名的「原子改名投遞」，到哪個版面都要用。
- `core/loop/src/wake.cpp`：F-03 已經照現有做法拍板，直接搬。
- `core/tool/src/probe.cpp`、`contacts.cpp`／`contact_status.cpp`：K-03 定案的通訊錄形狀就是現有實作。
- `core/llm/src/llm.cpp`：OpenAI 相容 client，跟並行策略無關，LLM 世界照樣要用它打端點。
- `core/tick/src/due.cpp`：純函式到期判定，不涉及 LLM 同步問題。

## 一定廢的

- `core/llm/src/slot.cpp`：G-04 明講鎖檔槽機制作廢，改由 daemon 走時鐘時數並行。
- `core/agent/src/step.cpp`：F-02 裁定 LLM 是獨立世界，同回合同步等 LLM 的模式架構上不成立。
- `core/agent/src/engine.cpp`／`engine_pi.cpp`：同上，且 pi 同步做完思考+工具跟 09 章的呼叫協定衝突更大。

## 不確定、要使用者看的

- `core/tick` 的 heartbeat/routine/schedule CLI 整組：G-01 說「所有時鐘由 daemon 走並登記在一處」，不確定這是指 daemon 接手 tick 現有的兩張表機制，還是 tick 繼續當 daemon 底下的一個獨立小專案運作。這個邊界會決定 `table.cpp`／四支 CLI 是整批搬進 daemon 還是原樣保留。
  → 答：`core/tick` 那組留著當 daemon 底下的小專案，daemon 只管起停，tick 自己判到期（R-01）。
- `core/agent/src/user.cpp`（`~` 使用者世界 say/listen）：ideas 13 章的待決定總表裡沒有任何一條點名它，看不出新構想要不要保留「使用者世界」這個獨立概念，還是併進一般的呼叫協定(09章)。
  → 答：`~` 使用者世界的 say/listen 保留，使用者就是住 `~` 的一個 agent（R-02）。
