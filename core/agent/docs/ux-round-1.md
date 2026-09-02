# UX 第一輪：少打指令、狀態可見、通訊錄進 prompt、不燒 LLM 的信箱

← [core/agent/README](../README.md)｜交接書 [proto-Y-improve](../../../wf/workflows/dispatch/proto/done/proto-Y-improve.md)｜協定 [PROTOCOL](../../../wf/workflows/dispatch/proto/PROTOCOL.md) §1 §4 §6｜發現 [trial](../../../wf/workflows/dispatch/trial/README.md)

四項改進的指令面與檔案層規格（2026-08-30）。方向性取捨已直接選最簡單的，理由一行寫在旁邊；跟修 bug 隊 X 共用的檔案在 §F 標出。

## A. 指令面

| 用法 | 行為 | stdout 範例 | exit | 小專案 | 登記 |
|---|---|---|---|---|---|
| `aos chat [--engine lmstudio\|pi] <text...>` | 解析世界（往上找 `.aos/`，找不到＝cwd）；沒有 agent 就 `initialize(folder, 資料夾名, 預設 persona, engine)`；`say`；若 `.aos/run.pid` 活著就只等，否則**前景**在本行程反覆 `loop::run_turn`（間隔 100 ms）直到 log 出現本次 say 之後的 assistant 紀錄且 status 回到 `idle`，印出所有新 assistant 內容；status 出現 `last_error` 則印到 stderr。**選前景**：不留行程、Ctrl-C 就停、不用處理孤兒 | `我是 bob。`（只印回覆正文；init 時先印一行 `已建立 agent bob（/home/u/bob，lmstudio）`） | 0 回覆；1 LLM 失敗；2 用法 | core/agent | 新 `chat` → `aos_chat_cli_main`（`aos_agent_cli` 需加 link `aos::loop`） |
| `aos run [folder] --daemon [--interval MS]` | `fork`＋`setsid`，子行程 stdout/stderr 導到 `.aos/run.log`、寫 `.aos/run.pid`、以 `--step 0` 跑；父行程印一行就回。`--daemon` 預設 interval 1000（有喚醒，不必忙轉）。收 SIGTERM：跑完當前回合（`wait_all` 收乾淨，不留孤兒）→ 刪 pid 檔 → exit 0。pid 檔已存在且該 pid 活著 → 拒絕 | `aos run: daemon pid 4242（.aos/run.pid，log 在 .aos/run.log）` | 0；1 已有 daemon 在跑 | core/loop | 不用（`run` 既有）；新檔 `daemon.cpp` |
| `aos stop [folder]` | 讀 `.aos/run.pid`；`kill(pid, SIGTERM)`，每 100 ms `kill(pid,0)` 探活，5 s 後 `kill(-pid, SIGKILL)`（整個 session）；刪 pid 檔。pid 檔不在或 pid 已死 → 刪陳舊檔、印「沒有在跑」 | `已停止 daemon pid 4242` | 0；1 SIGKILL 才停；0 沒有在跑 | core/loop | 新 `stop` → `aos_stop_cli_main` |
| `aos state [--json]` | 印人看的四行；`--json` 印 `status.json` 原文（＝舊行為）。`unread` **現場數** `say/*.md`，不信檔內數字；`loop:` 行讀 `.aos/run.pid` 探活 | `agent:  bob（/home/u/bob，lmstudio）`<br>`status: idle — 等待訊息  turn 12  2026-08-30T10:00:00Z`<br>`unread: 3 封在 say/`<br>`last:   失敗 — LLM 連線失敗: Failed to connect to localhost port 19999`<br>`loop:   沒有在跑（aos run --daemon 或 aos chat）` | 0 | core/agent | 不用（`state` 既有；改 `run_top.cpp::state_dispatch`） |
| `aos inbox ls` | 列目前世界的未讀：agent 世界＝`agents/<name>/say/*.md`，`~` 世界＝`~/.aos/say/*.md`。每列 id（檔名去 `.md`）、`from:` 標頭、正文第一行前 60 字。不叫 LLM | `ID                          FROM                       TEXT`<br>`1725000000123-4242-0        /home/u/alice              請 B 報時`<br>`（未讀 1 封）` | 0；空時印 `（沒有未讀）` 仍 0 | core/agent | 新 `inbox` → `aos_inbox_cli_main` |
| `aos inbox read [id]` | 印該封（省略 id＝全部，依檔名序）的完整內容，然後**搬到 `read/`**（見 §C）；`~` 世界另把內容 append 進 `~/.aos/log.md`。不叫 LLM。已讀的信 `step` 不會再看到 | `--- 1725000000123-4242-0`<br>`from: /home/u/alice`<br><br>`請 B 報時`<br>`（已標已讀 1 封）` | 0；1 id 不存在 | core/agent | 同上 |
| `aos listen [--once]`（空時） | 印出內容為空、或 `--once` 且 log 為空時，改印一行提示，未讀數現場數 `say/`；跟讀模式印完提示照常 tail | `無新訊息（未讀 3 封在 say/；aos inbox ls 可看）` | 0 | core/agent | 不用（改 `run_top.cpp::listen_dispatch`，與 X 共檔） |
| `aos contact status [--folder-root F]` | 自己世界一列＋通訊錄每格一列（`~` 排第一）。每格讀 `<folder>/.aos/agents/*/status.json` 取 `status`／`turn`／`unread`；`unread` 缺欄位就現場數 `say/*.md`；`~` 只數 `~/.aos/say/`。世界不存在印 `（找不到 .aos）` | `NAME   AGENT  STATUS      TURN  UNREAD  LAST_ERROR`<br>`~      -      -           -     0`<br>`.      alice  idle        12    0`<br>`bob    bob    thinking    9     1`<br>`w2     -      （找不到 .aos）` | 0 | core/tool | 不用（`contact` 既有；新檔 `contact_status.cpp`） |

`aos say --to <名字\|絕對路徑> <text>`：`--to` 除聯絡人名字外，接受以 `/` 開頭且含 `.aos/` 的路徑（信件 `from:` 標頭就是這種路徑）——這是 agent「回信地址＝自己的世界」的落點，不用先雙向登記。

## B. `status.json` 新欄位（`state.json.agents.<name>` 自動跟上）

`core/loop/src/state.cpp::mirror_agents` 讀的是 `status.json` **原文**（`wire::State::agents` 是 `map<string,string>`），loop 不解析內容；所以欄位只加在 `status.json`，`state.json.agents.<name>` 下一次寫 state 時原樣出現，loop 零改動。舊 `read_status()` 只取四個既有欄位、未知鍵忽略；`aos agent state` 與 `--json` 印原文。

| 欄位 | 型別 | 誰寫 | 預設 | 缺欄位時舊讀者 |
|---|---|---|---|---|
| `unread` | uint | `step` 每次寫 status 時現場數 `say/*.md`；`say()` 投遞後也只改這一欄重寫一次（`refresh_unread`） | 0 | `read_status` 不看；`contact status`／`aos state` 缺就現場數 |
| `last_error` | string | `step` LLM 呼叫丟例外時＝`one_line(what)`；LLM 呼叫成功時＝`""`；其他寫 status 的點**原樣帶過**（先讀舊檔再寫） | `""` | 視同成功 |
| `last_ok_at` | string ISO8601 | LLM 呼叫成功時＝現在；其餘帶過 | `""` | 不看 |

`status` 值集合不變（`idle`／`thinking`／`tool`／`waiting-llm`）：失敗回合 `status=idle`、`detail=one_line(what)`、`last_error` 同文，`aos state` 靠 `last_error` 分辨。實作放新檔 `status.cpp`（`detail::write_status_ex`／`refresh_unread`／`count_unread`），既有 `write_status(paths,status,detail,turn)` 改成薄包裝（帶過 `last_error`、現場數 `unread`），簽名不動。

## C. 檔案層新增物

| 路徑 | 內容 | 說明 |
|---|---|---|
| `.aos/run.pid` | `4242\n` | daemon 寫、退出時刪；`stop`／`state`／`chat` 用 `kill(pid,0)` 探活，ESRCH＝陳舊 |
| `.aos/run.log` | daemon 的 stdout＋stderr（append） | 每回合一行 `turn N: …`，同前景 |
| `.aos/agents/<name>/read/<同檔名>.md`、`~/.aos/read/<同檔名>.md` | `inbox read` 從 `say/` `rename` 過來 | **選搬目錄不選 `.read` 後綴**：`step` 只掃 `say/` 目錄的 `*.md`，搬走即不重讀，`unread`＝`say/` 檔數一個 `count` 就是；後綴法要改 `step` 的過濾且數字要多一個判斷 |
| `.aos/tools/say.json` | 見下 | `initialize` 在 `install_defaults` 之後另呼叫 `install_say_tool(folder)`（檔不存在才寫；舊世界 `aos tool add` 自己補）。`argv[0]` 用跟 X 隊修 L1-01 相同的解析（X 若改成絕對路徑，這裡跟著用同一個 helper） |

```json
{"name":"say","argv":["aos","say","--to"],"args":"list","stdin":"none","timeout_ms":10000,
 "description":"把一則訊息寄給通訊錄裡的聯絡人。args 是 [收件人, 訊息]，收件人可以是通訊錄名字、~（使用者）或信件 from: 那行的路徑。對方回信會進你的信箱。",
 "source":"manual","guarantee":"at-least-once","predictability":"high"}
```

loop 執行時 `cwd`＝世界、環境有 `AOS_FOLDER`，所以 `aos say --to` 查的是**自己世界**的通訊錄，`from:` 標頭＝自己世界的絕對路徑。

**system prompt 加一段**（`tools.cpp::system_prompt`，接在工具清單前）：

```text
通訊錄（可用 say 工具寄信）：
- ~ — 使用者（頂層信箱）（/home/u）
- bob — /home/u/bob（部署與實機測試）
收到的訊息開頭 from: <路徑> 是寄件世界；回信時 say 的收件人直接填那個路徑。
```

contacts 由 `aos::tool::read_contacts(folder)` 取，`~` 用 `user_contact()` 補在第一列（同 `contact ls`）。pi 引擎的 `pi_system_prompt` 也加同一段（`engine_pi.cpp`，只加字串），但 pi 沒有 say 工具，只能用它自帶的 bash 跑 `aos say --to`——本輪不做更多。

## D. LLM 失敗不吃訊息：`step` 的新時序

現況：`say/*.md` 逐封 → 寫 `history.json` → `append_log` → **`remove`** → 才呼叫 LLM；LLM 丟例外時訊息已經沒了（L1-20）。新時序（lmstudio 路；pi 路 `step_pi` 本輪不動）：

| # | 動作 | 失敗在這步時 |
|---|---|---|
| 1 | 讀 history／pending；pending 全到齊就把 tool 結果 push 進 history、`write_history`、清 pending（同現況） | 同現況（throw → status idle＋detail） |
| 2 | `unread = collect_unread(paths)`：列 `say/*.md` 排序後**讀進記憶體**，檔案不動 | — |
| 3 | `will_call = received_tools \|\| !unread.empty()`；不呼叫就 `write_status_ex(idle, unread=N, last_error 帶過)` 回 0 | — |
| 4 | 取槽；`WaitingLlm` → `write_status_ex(waiting-llm, unread=N)` 回 75。**say 檔仍在** | 同現況，只是多了 unread |
| 5 | `write_status_ex(thinking, unread=N)`；組 request＝system＋history＋`unread` 各封當 `{"user", content}`（只在記憶體） | — |
| 6 | 呼叫 LLM | 例外 → `write_status_ex(idle, detail=one_line, unread=N, last_error=one_line)`；**不寫 history、不寫 log、不 remove**；回 1。`history.json` 沒有這些 user 訊息，下回合第 2 步重新收到同一批，不重複 |
| 7 | `commit_exchange`：history 追加 N 則 user＋1 則 assistant → **一次** `write_history` → `append_log` user×N、assistant → 逐封 `remove` say 檔 | `write_history` 之後、`remove` 之前當機：下回合會把同一批再送一次（history 出現重複 user）。視窗是幾個 `unlink`，原型接受 |
| 8 | 工具呼叫解析／投遞／pending（同現況） | 同現況；訊息已在 history，不會丟 |
| 9 | `write_status_ex(next_status, unread=現場數（呼叫期間新到的）, last_error="", last_ok_at=now)` | — |

副作用：user 訊息在 log.md 出現的時間從「呼叫前」變成「呼叫成功後」；未讀期間用 `inbox ls`／`aos state` 看。第 2、7 步抽成新檔 `consume.cpp`（`detail::collect_unread`、`detail::commit_exchange`），`step()` 中段只剩三個呼叫，把 X 隊在 `step.cpp` 的改動衝突面壓到最小；順便讓 `step.cpp`（現 367 行）回到 300 以下。

## E. 投遞即喚醒（`core/loop/src/run.cpp`）

- **空回合**定義：`summary.count == summary.every_count`（只有 every 的常駐 step，inbox 沒東西）。有 every 的世界永遠不會 `count==0`，所以不能用 idle 判。
- 空回合之後不再固定 `nanosleep(interval)`，改 `wait_for_delivery(layout, interval, 50)`：每 50 ms 算一次**簽章**＝`inbox/` 與每個 `agents/*/say/` 的（檔數、最大 mtime ns）串接；簽章跟回合開始時不同就立刻回（開下一回合），否則睡滿 `interval` 才回。純 `directory_iterator`＋`last_write_time`，沒有 inotify、沒有執行緒。
- 非空回合照舊睡 `interval`。`--interval` 語意變成「沒有新投遞時的最長等待」；預設值不變（100），`--daemon` 預設 1000。
- `--step N`（有限）：喚醒只縮短回合間的等待，N 到了照停；「say 落地前 loop 已跑完 N 回合」（L2-26）不靠 run 解，靠 `chat` 自己驅動到回覆為止。
- `wait_for_delivery` 與 `delivery_signature` 公開在 `loop.hpp`（新增，不改既有簽名），放新檔 `wake.cpp`；`chat` 也用它等回覆之間的空檔。

## F. 四條實作線的切分

| 線 | 項目 | 碰的檔（★＝新檔） | 共用檔 |
|---|---|---|---|
| Y1 少打指令 | `chat`、`run --daemon`、`stop`、喚醒 | core/loop：`run.cpp`（`--daemon` 解析＋改 sleep）、★`daemon.cpp`、★`stop_cli.cpp`、★`wake.cpp`、`loop.hpp`（加宣告）、`CMakeLists.txt`（加 stop）；core/agent：★`chat_cli.cpp`、`CMakeLists.txt`（加 chat、link aos::loop） | 與 Y2：`chat` 讀 `last_error`（先做 Y2 的 `status.cpp`） |
| Y2 狀態可見 | `status.json` 新欄位、不吃訊息、`aos state` | core/agent：★`status.cpp`、★`consume.cpp`、`internal.hpp`（加宣告）、`step.cpp`（中段換成三個呼叫）、`init.cpp`（`say()` 後 `refresh_unread`）、`run_top.cpp::state_dispatch` | `step.cpp`、`init.cpp`、`run_top.cpp` 與 X 隊共檔；`run_top.cpp` 與 Y3／Y4 共檔 |
| Y3 通訊錄與投遞 | prompt 加通訊錄、預設 `say` 工具、`--to` 收路徑、`contact status` | core/agent：`tools.cpp::system_prompt`、`engine_pi.cpp::pi_system_prompt`、`init.cpp`（呼叫 `install_say_tool`）、`run_top.cpp::say_dispatch`；core/tool：`registry.cpp`（`install_say_tool`＋`default_specs` 不動）、`tool.hpp`（加宣告）、★`contact_status.cpp`、`contact_cli.cpp`（dispatch 加一行）、`CMakeLists.txt` | `init.cpp`、`run_top.cpp` 與 Y2 共檔 |
| Y4 信箱 | `inbox ls`／`read`、`listen` 空時提示 | core/agent：★`mailbox.cpp`（列／讀／標已讀，agent 與 `~` 兩種版面）、★`inbox_cli.cpp`、`agent.hpp`（加 `list_unread`／`mark_read`）、`run_top.cpp::listen_dispatch`、`CMakeLists.txt`（加 inbox） | `run_top.cpp` 與 Y2／Y3 共檔（各改不同函式，衝突可手解） |

建議循序：**Y2 → Y4 → Y3 → Y1**（Y2 先定 `status.cpp`／`count_unread`，後三條都用；Y1 最後才有 `last_error` 可等）。行數：`run_top.cpp` 152 行加三處後約 230，可不拆；`step.cpp` 靠 `consume.cpp` 抽出後回到 300 以下；`registry.cpp` 145 加一個函式不拆。

## 隊長裁決（核過本文件時追加，與上文衝突時以本節為準）

1. **pid 檔維持 `.aos/run.pid`、log 是 `.aos/run.log`，但寫 pid 的責任放進 `aos run` 的迴圈本身**：
   **任何** `aos run --step 0`（不論前景或 `--daemon`）都要寫 `.aos/run.pid`、退出時刪掉，
   都能被 `aos stop` 停掉；`--daemon` 只多做兩件事——脫離終端（`fork`＋`setsid`）與把 stdout/stderr 導向
   `.aos/run.log`。有限回合的 `--step N`（N > 0）不寫 pid 檔。
   使用者之後要在 `~` 用一個 home daemon 一次管多個目標世界（spec 在 main 的
   `wf/workflows/ideas/home-daemon-spec.md`），所以 pid 檔**每個世界一份**、內容只有 pid，
   `aos run --daemon`／`aos stop` 的語意固定是「這個世界的 loop」。
   **本輪不做**：`~/.aos/daemon.json` 目標清單、`aos daemon start` 子命令、CLI 合併。

2. **失敗回合的 `status` 值改成 `"error"`**（不是維持 `idle`）。`idle` 在失敗時是騙人的，正是 L1-19 的痛點。
   值集合變成 `idle`／`thinking`／`tool`／`waiting-llm`／`error`／（`aos state` 呈現層另有 `pending`）。
   `core/agent/tests/test_agent_step.cpp` 有一條既有斷言預期失敗後是 `idle`，一併改掉。
3. **不抽 `consume.cpp`、不抽 `status.cpp`**。X 隊同時在 `step.cpp` 修 bug，把 60 行搬出去會讓 rebase 衝突更難解，
   不是更好解。新 helper 直接放進既有的 `store.cpp`，`step.cpp` 就地小改。`step.cpp` 維持超過 300 行，本輪不處理。
4. **砍掉 `last_ok_at`**（沒有驗收條目用到）與 **`aos say --to <絕對路徑>`**（那是 L2-11，屬 `cannot`，不在這四項裡）。
5. **砍掉 `refresh_unread`**（`say()` 不去重寫 `status.json`）。`aos state`／`aos contact status`／`aos inbox`
   一律**現場數** `say/*.md`；`status.json` 裡的 `unread` 只是最後一次 step 的快照。少一個競態、少一處寫入。
6. `aos state` 採本文件的人看四行輸出，`--json` 印原文加新欄位。未讀那行固定寫成 `unread: N 封在 say/`，
   讓驗收第 3 條（「`aos state` 顯示 `unread: 3`」）字面上就對得起來。
