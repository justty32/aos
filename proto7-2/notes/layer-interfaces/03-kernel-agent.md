# kernel ↔ agent，以及 proto7-1 的 kernel／agent 接到 proto7-2 會怎樣

← [入口](../layer-interfaces.md)｜上一份：[tick-tock ↔ 任務](02-ticktock-task.md)｜下一份：[跨層](04-cross-layer.md)

proto7-2 還沒有 kernel 與 agent（只有 `modules/counter.py`、`history.py` 兩個示範任務）。這一節拿 proto7-1 的實作當參考：`proto7-1/lib/aos7_kernel.py`、`aos7_kernel_rules.py`、`aos7_agent.py`、`aos7_agent_tools.py`、`aos7_llm.py`，以及 `notes/problems-kernel.md`、`problems-agent.md`、`infra-needs.md`。

**先說結論**：kernel 和 agent 之間**沒有直接的通道**，全部經過檔案，而且大多是「kernel 讀 agent 寫的檔」和「kernel 寫核心的控制檔、核心再去動 agent」。核心看不懂這些檔的內容，它們是 kernel 層自己的約定——這正好合設計原則第 5 條：只為 agent／LLM 的東西都留在這一層，沒有長進 daemon／tick。

## 1. 交接點清單（proto7-1 的做法）

| 交接點 | 誰寫 → 誰讀 | 時機 | 格式 | 通用／專用 |
|---|---|---|---|---|
| `progress.json`（槽裡） | agent → kernel（卡住規則） | agent 每處理一次 tock；問 LLM 前另寫一次 | `{round, state, steps}`；等 LLM 時加 `llm_since` | 機制通用（任何任務都能報進度）；**`llm_since` 只為 LLM** |
| `usage.json`（槽裡） | agent → kernel（預算規則） | 每次 LLM 呼叫後 | proto7-1：`{tokens, calls}`，一直累加 | 機制通用（任何可數的資源）；目前內容只有 token |
| `kernel.json`（kernel 的 node） | 人／LLM → kernel | kernel 每回合重讀 | `{members, roles, stuck_rounds, llm_stuck_rounds, budget_tokens, cap_tokens, cool_rounds, max_age}` | 混合：`stuck_rounds`、`max_age`、`members` 通用；`llm_stuck_rounds`、token 預算只為 LLM |
| `roster.json`（成員 node 的 `.aos/`） | kernel → agent（放進 LLM prompt） | 內容變了才寫 | `{by, members: [{node, inbox, role}]}` | **只為 agent**（名冊給 LLM 看） |
| 任務 `ctl.json`（restart、kill） | kernel → 核心 → agent | kernel 收到自己的 tock 後寫；成員 node 的 tick／tock 才執行 | 見 [02](02-ticktock-task.md) | 通用 |
| daemon 控制檔 `pause`／`resume` | kernel → daemon → 成員 node 的時間線 | 同上 | 見 [04](04-cross-layer.md) | 通用 |
| 結束碼（`exit.json` → `last-round.json` 的 `ended`） | agent 結束 → aos7-run → tock → kernel | 下一次 tock | `{run, code}` | 通用（proto7-1 kernel 沒用到） |
| `agent.json`（agent 的 node） | 人 → agent | 每次 think 重讀 | `{name, llm: {url, model, timeout_s}, memory, wake}` | 只為 agent |
| `inbox/`、`outbox/`、信件 JSON | agent ↔ agent，經掛載 | act 狀態寄、idle 狀態讀 | `{from, to, body, round, ...}` | 機制通用（任何 node 間傳訊）；目前只有 agent 用 |
| `decisions.jsonl`、`trace.jsonl`、`llm.jsonl` | kernel／agent 自己 | 每回合追加 | 自己的紀錄 | kernel 的通用；`llm.jsonl` 只為 LLM |

**時機上的關係**：kernel 一回合只取樣一次（收到**自己 node** 的 tock），agent 也是每收到**自己 node** 的 tock 換一次狀態。兩者常在不同時間線上，kernel 的「連續 N 回合沒變」要數成員的回合（problems-kernel K-2），而 kernel 看到的永遠是取樣，不是每一回合。

## 2. 彼此的影響

- **agent 卡在 LLM 裡**：progress.json 不動。proto7-1 用 `llm_since` 讓 kernel 不把「在等 LLM」當卡住，另設 `llm_stuck_rounds`。kernel 真的下 restart 時，正在跑的 LLM 呼叫被殺掉，那次已花的 token 白花，重起後 `recover` 會重想一次。
- **kernel 用 pause 管預算擋不住正在燒的錢**：pause 只是不開新回合，agent 程序照跑，已經送出的 LLM 呼叫照樣完成（problems-agent A-7）。要真的停只能 kill，而 kill 要等成員 node 的 tick／tock；node 被 pause 時任務控制根本不執行（K-4）。
- **kernel 不能 pause 自己的 node**：pause 了就收不到 tock，就不會再跑規則去 resume（K-5）。proto7-2 的 `resume --rounds N` 與 `until_round` 可以讓「到期自動停」不靠 kernel 活著，但「到期自動恢復」仍沒有。
- **kernel 下了指令不知道有沒有生效**（K-10）：proto7-1 寫完就當作做了。proto7-2 有可用的回饋（任務控制回條帶 `ctl_id`、round.json 帶 `tasks_rev`），但 daemon 控制檔沒有請求 id（見 [05](05-gaps.md) G4）。

## 3. 接到 proto7-2 的介面上會怎樣

| 項目 | proto7-1 怎麼做 | 接到 proto7-2 | 判定 |
|---|---|---|---|
| 怎麼起 | kernel、agent 是 tasks.json 的 keep 項；llmkernel 探針用 `spawn/` 起一次 | keep 照用；`spawn/` 沒了，改寫 `mode: "once"` | 直接可用（探針要改） |
| 讀自己是誰 | `task_env()` | proto7-2 的 `task_env()` 多回 `run` | 直接可用 |
| 等 tock | `wait_tock(task, last, timeout)` | proto7-2 版多了 `run` 過濾（預設取 `AOS7_RUN`），呼叫方式相容 | 直接可用，而且更安全 |
| 接前任的 state | 自己資料夾沒有就去 `restart_of`、同名最新的、`tasks-old/` 找；用 `task_dirs_of`、`task_read` | 槽重用：state.json、kernel-state.json 就在同一個槽。**proto7-2 的 `aos7_fs` 沒有 `task_dirs_of`、`task_read`**，`aos7_agent.py:15` 一 import 就失敗，kernel 的 `load_state` 與 `snapshot_node` 也一樣 | **要改**（改成只讀自己的槽，程式會變短） |
| kernel 看成員的任務 | 掃 `tasks/`＋`tasks-old/`，自己判活死：有 exit.json＝結束，pid 在＝活，沒權限也算活 | 只有 `tasks/`；槽裡可能留著上一個 run 的檔，判定要比 `run`；三態規則（讀不到＝不知道）kernel 自己的簡化版沒有 | **要改**：最好直接用 status 的 `live`（要經掛載）或同一套判定，不要再寫一份 |
| 看成員有沒有被 pause | 讀 status 的 `nodes[id].paused` | proto7-2 是 `paused_by`（清單）＋`pause_pending`；舊欄位不存在，`aos7_kernel_rules.py:103` 永遠得到 false | **要改** |
| 「已下過指令」的記號 | `issued` 以 `node:tid` 為鍵，任務不活了才拿掉（`aos7_kernel_rules.py:239-243`） | tid 變成固定的槽名。restart 後新 run 在下一個 tick 就起來，kernel 幾乎取樣不到「不活」的那一刻，鍵永遠留著 → **同一個槽之後再卡住也不會再 restart** | **要改**：鍵改成 run id（`槽#run`） |
| 寫任務 ctl.json | `<.aos>/tasks/<tid>/ctl.json`，已存在就不蓋 | 路徑形狀一樣，槽名固定反而好指；應該帶 `run`（只收那一次）和 `id`（重送時沿用） | 小改 |
| 寫 daemon 控制檔 | 每回合新檔名 `kernel-<tid>-r<回合>-<序>-<op>-<目標>.json`，不帶 `owner` | 每次新名字＝`ctl-done/` 回條越積越多（違反 W3）；不帶 owner＝跟人、`aos7-ctl` 不帶 `--owner` 的共用一格，會互相放掉 pause（N-81） | **要改**：用 `aos7_ctl.daemon_ctl` 的固定檔名，帶 `owner` |
| 用量 | agent 的 `usage.json`＝`{tokens, calls}` 一直累加；kernel 加總所有任務資料夾 | spec §8 說 usage.json 只記**這一次 run**（`{run, usage}`），kernel 對每個 run id 記最大值再相加。槽重用後 proto7-1 的 agent 會把前幾個 run 的累計一路帶下去；照 §8 的算法加總會重複算 | **要改**，而且要先定格式（見 [05](05-gaps.md) G16） |
| 預算 pause／resume | kernel 自己記「第幾回合 pause、過幾回合 resume」 | 可以改用 `resume --rounds N`（daemon 數回合）；但要注意 G2：失敗的 tick 也會被算成一回合 | 可用，語意要重核 |
| 名冊 roster.json | 寫進成員的 `.aos/` | 核心不認識這個檔，不會刪也不會讀；但 spec 沒說 `.aos/` 裡哪些名字是核心保留的 | 能用；命名空間沒定義（G10） |
| 寄信 | 對方 inbox 沒掛上就寫 mount-req，信先放 `outbox/`，下回合寄 | 一樣；keep 任務換 run 時執行中加掛的掛載會消失（只有 restart 帶 `mounts_dyn`），要重新請求，多等一個 tick | 直接可用，偶爾慢一回合 |
| LLM 端點設定 | `agent.json` 的 `llm.url`／`model`／`api_key`（key 寫在 node 裡的普通檔） | 照用。但 key 不管放 agent.json 還是放環境都藏不住：node 裡的檔同 node 的任務都讀得到，環境則整份從 daemon 繼承，tasks.json 也沒有 `env` 欄可以只給某一項 | 可用；「只有分配者拿得到 key」做不到（G8） |
| agent 的狀態機 | 每個 tock 換一格，做事做到完為止，中間的 tock 被併掉 | 不變（固定 interval 也不會讓 LLM 呼叫變快） | 直接可用 |

## 4. 往後的方向會接在哪裡

思考筆記（[LLM 端點是一種資源](../../../proto7/notes/2026-10-04-llm-endpoint-resource.md)、[事實的傳遞](../../../proto7/notes/2026-10-04-fact-propagation.md)、[第一輪綜合](../../../proto7/notes/thinking/2026-10-04-r1-synthesis.md)）裡的東西，都落在「任務 ↔ 任務」和「kernel ↔ 核心」這兩面，不需要新的層間通道：

- **分配者（kernel 角色）**：普通 keep 任務。請求與使用權走掛載的信箱；使用權到期可以直接寫成成員項目的 `until_round`（proto7-2 已有，分配者死了也會到期）。這些都是**通用**機制，LLM 端點只是其中一種資源。
- **請求要多快被看到**：寫信的一方順手寫 daemon `wake`，固定 interval 的 node 約 20 ms 就開下一回合（P2-01 已實作；綜合筆記第 77 行還寫「缺、待決定」，已過時）。
- **事實帶出處**：核心已經提供了出處需要的零件——node id、回合數、run id（`槽#run`）。要不要做成約定是 kernel 層的事。
- **強制點**：只能放在副作用的入口（持有 key 的 gateway）。核心目前會把 daemon 的整份環境傳給每個任務，這一點跟「只有根分配者拿得到 key」衝突（G8）。
