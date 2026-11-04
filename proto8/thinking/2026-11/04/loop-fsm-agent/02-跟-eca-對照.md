← [入口](README.md)｜涵蓋：跟 eca 對照（兩邊一樣的、兩邊不一樣的、條文要加的註）｜上一份 [01-設計](01-設計.md)｜下一份 [03-實作步驟](03-實作步驟.md)

## 跟 eca 對照（給之後統一 aos-agent 用）

使用者 11-04：「這個好了之後，就可以綜合eca和這個的特性，弄出統一的aos-agent介面」。這節把兩隻的對外接法擺在一起；**一樣的**＝統一介面可以直接當底、**不一樣的**＝統一介面要吸收或抹平的點。eca 那欄照現行程式（含 11-04 工作樹的 `--prompt`）。

### 兩邊一樣的（P-42 三樣＋同形資料夾）

| 事 | 兩邊都是 |
|---|---|
| 定義怎麼跑 | 資料夾程式，`_entry`＝`["aos-loop", "loop.json"]`，`aos-exec --ws WS <定義>` 直接跑、`aos-daemon-ctl add` 掛 daemon（loop 型） |
| 窗 | `loop.json` 開 `ctl.json`／`state.json`（aos-loop 的；`{"cmd": pause／resume／stop}`、phase） |
| 輸入 | `$AOS_STACK/queue/`，aos-post 有序信箱，一封＝`{"role": "user", "content": …}`；aos-say 寄 |
| 輸出 | `$AOS_STACK/history.jsonl`，回答＝最新沒 `tool_calls` 的 assistant；aos-listen 讀 |
| 收信 | 一次收全部、照 `letter_key` 順序；**接進去（history／CLI）那刻就 `aos-post done`**；壞信丟掉＋`mailbox_warning.txt` |
| 開場白 | `--prompt FILE` 旗標（相對定義資料夾；history 空且 queue 空才投一次；沒給＝沒有） |
| 工具箱 | 定義資料夾裡一份 aos-tools 登記檔，預設 `tools.json`、可改指；工具小格 `$AOS_STACK/tools/<名>/` |
| 生命週期 | 直接跑＝Linux 管；掛 daemon＝add／rm／start／stop／pause／resume／sleeping／wake、`where --stack`；自己退 1＝下表、stack 留 |
| 錯 | stderr 一行 `程式名: 代號 原因`、退 1、停下等人（P-20）；代號照 C-54 四種結尾 |
| log | 預設不印、不寫 |
| 固定名字 | 定義資料夾裡被程式固定認的只有一個入口（eca：aos-eca-turn 認 `cli.json`；這隻：aos-exec 認 `_entry`） |

### 兩邊不一樣的

| 事 | eca | loop／fsm agent | 統一 aos-agent 要想的 |
|---|---|---|---|
| 一輪的身體 | bin 程式 `aos-eca-turn`（一支、整批一輪） | fsm 表三格 idle／think／act（範本裡三支 `.py`） | 介面層只碰 stack，不碰身體——這條差異不用抹 |
| queue 空要不要收工 | `--on-empty stop\|idle` 旗標 | fsm 表 idle 的 `next`：`{"0": "think", "10": "idle"}`＝停著等、`"think"`＝收工 | 統一介面做 `add`／範本產生時，一邊改旗標、一邊改表；或兩邊都改成表（eca 的 loop.json 包一層 fsm？不划算）——留著 |
| 暫停粒度 | 一批信（CLI 是黑盒子） | 一格（idle／think／act 之間；暫停時能改 history） | 介面層一樣是寫 ctl；只是說明要寫清楚 |
| 工具怎麼接 | `tools.json` → cli_session 寫 `mcp.json` → `aos-mcp` → aos-tools；腦看到 `mcp__aos__<名>` | `tools.json` → brain／act 直接 `aos-tools ls／call`；腦看到 `<名>` | 同一份登記檔兩邊都吃——已經對齊；前綴是 CLI 的事 |
| 腦 | 外部 CLI（claude／codex），`cli.json` 的 `kind`／`flags` | OpenAI 相容端點 `AOS_BRAIN_*`（將來 kernel） | 介面層不管腦 |
| system prompt | 沒有（CLI 自己的） | `brain.py --system FILE` | — |
| 對話全貌 | `history.jsonl` 只有一問一答；全貌在小格 `<kind>/transcripts/` symlink、`live.jsonl` | `history.jsonl` 就是全貌（含 tool 訊息） | 統一的「看對話」要分：history（兩邊有）、transcripts（只有 eca） |
| 畫面 | tmux 畫面 `aos-eca open／close／watch`、`busy.txt`、`--on-busy` | 沒有畫面、沒有 busy | 統一介面 `open` 對這隻＝沒有（或以後開 tail history） |
| 名片 | `$AOS_STACK/eca.json`（kind、ws、template）；aos-eca `ls` 靠它認 eca、`aos_human.daemon_held` 靠它印 `aos-eca start` | 沒有 | 統一介面若要 `ls` 列出「哪些是 agent」，要一個共同名片（名字、形狀）——11-03 使用者說的 `.aos/agent/` 可能就是它；這輪不寫 |
| 管理命令列 | `aos-eca add／rm／start／stop／ls／state／open／close／watch` | 只有 `aos-daemon-ctl`（add／rm／start／stop／pause／resume／ls／where） | aos-eca 多的四件（open／close／watch／state 的畫面與 session）是 eca 專屬；其他可以直接是統一介面的子命令 |
| 入口檢查 | `aos-eca add` 先驗 cli.json／tools／prompt、不送信 | 沒有包一層，`aos-daemon-ctl add` 不驗；錯要等第一格跑了才看到（stderr.txt、下表） | 統一介面 `add` 可以替這隻先驗 `--prompt`／`--system`／`--tools` 指的檔在不在（照 aos-eca 讀 loop.json 的做法讀 fsm.json） |
| 交出去後掛掉 | 信已收、不重答（CLI 中途掛） | 信已收、history 停在 user、`state.txt` 停在 think；重起就接著問（會重答） | 語意不同但都是「邊緣狀況不影響原意」 |
| 中途來信 | 下一輪整批（CLI 一輪結束才回 loop） | 答完這題回 idle 才收 | 一樣是「等做完」（方向題 2 若選打斷才不同） |

### 條文要加的註（實作時一起、11-04 註；條文原字不動）

- P-11 10-30 改口「答完……才把信收掉」→ 看[衝突 1](04-衝突與方向題.md#衝突-1信什麼時候收掉p-11-的-10-30-改口說答完才收)裁定後加註。
- P-12「一次做一題、`cur/` 有沒做完的先接、`current.txt`」→ 走 queue 的 fsm agent：一次收一批、`cur/` 有的先接、不寫 `current.txt`。
- P-19／P-35「10 只有 idle 退」→ 看[衝突 2](04-衝突與方向題.md#衝突-2think-格也用結束碼-10p-35-說10-只有-idle-退)裁定後加註。
- P-41「act……有 `tool_calls` 就逐個跑工具、結果接回 history、退 0 回 idle……沒有 `tool_calls` 才把 `content` 寫成答案、題目搬 `done/`」→ 走 queue 的：act 退 0 回 think（物件 `next`）、答案就是 history 那則、沒有 `done/`；think 沒 `tool_calls` 退 10 回 idle。
- P-42「跑完要不要結束寫在定義裡：aos-round 的 `--on-empty`……」→ 補：loop／fsm agent 寫在 fsm 表 idle 的 `next`。
- P-43 反向：aos agent 的範本是 `demo/agent-fsm`；P-05／P-27「agent-bob 現在的樣子就是標準」→ 走 queue 的標準是 agent-fsm（舊協議的 bob 留 fixtures）。
- C-50／CONCEPTS 05 開頭「實作：fixtures 的 agent-bob、agent-ann」→ 加 `demo/agent-fsm`。
- N-16 10-30 加註「agent 層的輸入叫 queue」照舊；N-53 照舊。
