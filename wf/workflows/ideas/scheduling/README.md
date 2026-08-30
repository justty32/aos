# scheduling — 有限的 LLM CPU 給所有 agent 共用，排程該怎麼做

← [ideas](../README.md)｜前身 [llm-cpu](../llm-cpu.md)｜[top-down-cli §三](../top-down-cli.md)｜workshop [finite-resource-queue](../../workshop/records/finite-resource-queue.md)｜實測 [experiments](experiments.md)｜交接書 [proto-S-scheduling](../../dispatch/proto/proto-S-scheduling.md)

**記錄日期**：2026-08-30，隊 S（Fable 隊長＋codex ×3）。**純規劃，沒動程式。方向留給使用者，本頁只列選項＋建議＋代價。**

## 一、題目（使用者三次具體化後的版本）

1. 「一切都是在 llm cpu 只有一個的狀況下，也就是要做排程管理。」
2. 修正：不是一顆，是 **N 顆有限的 LLM CPU**（本機 LM Studio、DeepSeek…），每顆各自有並行上限、速率、成本、可預期性；N=1 是特例。
3. 再具體：「假如我設定只允許同時有三個正在跑的 DeepSeek API 呼叫」——**每顆 CPU 有一個使用者設定的並行上限**（例：`deepseek: 3`、`lmstudio: 1`），
   排程要**保證**同時在跑的呼叫不超過那個數，超過的排隊。

所以要交的是：誰排隊、隊伍住哪、誰消化、優先序與公平、餓死／逾時／CPU 掛了、**跟「一回合一批、回合邊界不變」怎麼相容**、上限住哪、超上限排隊還是退回。

## 二、爭用點盤點：現在誰在打 LLM、怎麼打

| 路徑 | 打哪顆 | 觸發 | 每回合次數 | 阻塞方式 | timeout | 失敗時 | 出處 |
|---|---|---|---|---|---|---|---|
| `aos agent step`（lmstudio 引擎）首次思考 | LM Studio | `say/*.md` 有新訊息 | 0 或 1 | step 行程內同步 POST，**佔住該世界整回合** | 120 s | status 寫 idle＋錯誤一行，訊息已吃掉、**不重試** | `core/agent/src/step.cpp:79–85, 150–158` |
| 同上，收到工具結果後再思考 | LM Studio | `batch/N+1/out/` 齊了 | 0 或 1（與上互斥，同回合最多一次） | 同上 | 120 s | 同上 | `step.cpp:106–128` |
| `aos agent step`（pi 引擎） | DeepSeek | 有新訊息 | 0 或 1 條 step，**內含 1～k 次連續呼叫**（工具迴圈），aos 數不到 | fork `pi`，同步等整個 step | 600 s | `log.md` 留 `> pi 失敗`，**step 仍 exit 0**，不重試 | `core/agent/src/engine_pi.cpp:47–72, 175–192` |
| heartbeat `ask` 型 routine／schedule | 間接 | `aos tick` 到期 → `agent::say()` | 0（tick 自己絕不叫 LLM）；下回合變成上面那條 | — | — | 投出就算做了，不追 | `core/tick/README.md` §一次心跳 |
| `aos llm` 當登記工具（未來） | 任一 | 模型末行 JSON 叫它 | 每隻 agent 每回合 ≤ 1 條工具 inst | 工具 inst 在 loop 批內同步 | inst `timeout_ms` | `out/` 有 exit≠0，下下回合回給模型 | [call-loop](../tools/call-loop.md) |
| 子 agent 團隊（未來，第二級） | 各自 engine | 主 agent 派工 | 主 1＋子 N，**同回合**最多 N+1 次 | 各自世界各自佔回合 | 各自 | 各自 | [usability-target](../usability-target.md) |
| 多世界同機各自 `aos run` | 各自 | 各自回合 | 世界數 × 上面 | 互不知道對方存在 | — | — | `core/loop/README.md` 已知不管「沒有鎖」 |

**共同點**：每條路徑都是「自己直接打端點、同步等、佔住回合」；沒有任何一處知道別人也在打；沒有優先序；沒有跨世界的計數。
**量級**（[experiments §三](experiments.md)）：qwen3.5-9b 一次思考 2～17 秒；LM Studio 這顆預設 `n_slots = 4`（不是 1），log 裡最多只見過同時 2 條；
DeepSeek 官方帳號併發上限 2500，端點不會替我們擋「同時 3 個」。
**順手挖到的邊緣狀況**（sol）：`aos tick` 與 `agent step` 同批並行 fork，tick 寫 `say/` 與 step 掃 `say/` 之間沒有先後保證——heartbeat 的 ask 有時同回合就被讀到、有時下回合，
文件說的「下回合」不是實作保證（`turn.cpp:86–98`、`tick.cpp:180–183`、`step.cpp:132–139`）。

**最壞情況**（同步等、每次思考 T=10 s）：一顆 P=1 的 CPU，K 隻 agent 同回合都要想 → 回合長 K×T：K=1 → 10 s、K=3 → 30 s、K=10 → 100 s；
同世界的 heartbeat tick 與其他 inst 全部陪等。加一顆 DeepSeek P=3、每次 3 s，理想分配下 K=10 → lmstudio 吃 1～2 條、deepseek 吃 8～9 條 ≈ 9 s。

## 三、方案空間（四條）

| | A「LLM PU 是另一個世界」 | B「外部處理器監控資料夾」 | C「loop 內的資源閘」 | D「`aos llm` 自己排隊」 |
|---|---|---|---|---|
| 一句話 | 每顆 CPU（或一個 broker）是含 `.aos/` 的世界，有人 `aos run --step 0`；agent 把「想一次」投到它的 inbox，回合輪詢結果 | 使用者層級 spool `~/.local/state/aos/llm/<cpu>/{ready,running,done,failed,delayed,unknown}/`；一支小程式（可不引用 aos lib）逐件打端點、寫回 | inst 加可選欄 `resources:["llm:deepseek"]`，`aos run` 匯聚時每種資源每回合只放行 N 條，其餘留在 inbox／`deferred/` | `aos::llm::complete()` 打端點前先 `flock` 使用者層級 `~/.local/state/aos/llm/<cpu>/slots/<k>.lock`（N 個檔＝N 槽），拿到才 POST |
| 誰排隊／住哪／誰消化 | 請求＝llm 世界 inbox 的 inst；消化者＝那個世界的 `aos run` | 請求檔在 spool；消化者＝常駐 worker（`aos llm work` 或 100 行 Python） | 請求＝本世界 inbox 裡的 inst；消化者＝本世界 `aos run` | 請求＝正在等 flock 的 step 行程；沒有隊伍檔、沒有消化者 |
| N 顆 CPU／選 CPU | 一顆一世界（選世界＝選 CPU），或一個 broker 世界管 N 條 lane（能依可用性轉投） | 一顆一 spool＋一 worker（選目錄＝選 CPU），或總 `ready/`＋dispatcher 分派（能依可用性、成本、健康改派） | 資源名帶 CPU 名各有各的 N；**loop 不知道哪顆有空**，做不到依可用性 | CPU 表 `cpus.json`，`complete(tier)` 掃各 CPU try-lock、都滿才 block 在偏好那顆——「依可用性」的最小實作 |
| 優先序 | 請求欄位 `priority`，要 broker 依它排；純 inbox 只有檔名序 | 子目錄 `ready/0-user/ 5-agent/ 9-heartbeat/`＋aging | inst 加 `priority` 欄、loop 排序 | flock **沒有**順序保證；要加得寫 `waiting/<prio>-<ts>-<pid>` 檔由放鎖者喚醒 |
| 公平（多世界、高產 agent） | broker 持久 cursor 逐 tenant 取一件；否則高產者塞滿下一批 | worker 持久 cursor 逐 world/agent 取一件——天然 | **只管單世界**；兩個 `aos run` 各放 3 條＝6 條並行，閘失效 | 全機共用同一組 lock 檔，上限成立；但誰先搶到看核心，可能連續被同一隻拿走 |
| 餓死／逾時／CPU 掛了／unknown | 未取件者可轉投別的 CPU 世界；連線斷掉＝`unknown`，不自動重送 | `delayed/<not-before>-<id>` 退避、`unknown/` 留人裁、dispatcher 改派健康 CPU——狀態機最完整 | 只有 `timeout_ms`；CPU 沒開＝inst 失敗；unknown 無處記 | 取槽 timeout 與 HTTP timeout 分開；CPU 沒開照樣拿到槽再失敗；unknown 無處記 |
| **回合邊界** | 天然是「投遞回合／取件回合」（延遲 +2～+3 回合、idle 空轉輪詢） | 同 A（+1～+2 回合） | 天然「佔住回合同步等」；閘掉的下回合再來 | 天然「佔住回合同步等」；**回合被拖到拿到槽＋跑完** |
| 改多少 | `core/agent` step 改 submit/poll＋pending；`aos llm` 讀 stdin 請求；**loop 要加「一回合只放 P 條」否則 llm 世界自己就並行爆量**；估 8～13 檔、700～1300 行 | agent submit/poll ≈ 3～5 檔 200～400 行；worker 另 250～500 行；**loop 不動** | `aggregate.cpp`＋`turn.cpp`＋`wire` 一欄＋CLI `--slots`；估 5～9 檔 230～510 行；**改 PROTOCOL §1／§2**（loop 開始讀 metadata） | 只動 `core/llm`（＋agent 傳 tier、pi 包一層）；估 4～8 檔 175～415 行；**loop、wire、協定不動** |
| 子 agent 團隊／多世界 | 撐得住，前提是 broker 化 | **最適合**：所有世界共用一個 spool、一張 CPU 表、一個 cursor | 撐不住多世界（除非再加使用者層級鎖＝變 D） | 撐得住（鎖是全機的），但沒有公平、沒有 durable 隊伍 |
| 崩潰恢復 | agent `pending.json` 記世界＋id；llm 世界重啟掃 inbox／running | `running/` 裡的檔＝重啟後要裁的現場；有 receipt 才 done | inbox／deferred 未取走者天然 pending | flock 隨行程死亡自動釋放；等待者死了＝請求消失，**沒有 pending 可辨認** |
| pi 引擎那條 | 要 pi 支援 proxy 或維持直連（繞過） | 同左 | step 標 `llm:deepseek` 即可，整個 step 佔一槽 | `step_pi` 包一層取槽即可（+30～80 行） |

## 四、拿具體案例走一遍：`deepseek: 3`、`lmstudio: 1`，五隻 agent 同回合都要想（4 隻走 DeepSeek、1 隻走 LM Studio）

| 問題 | A | B | C | D |
|---|---|---|---|---|
| 第四個 DeepSeek 呼叫怎麼等 | 躺在 llm-deepseek 世界 inbox（或 broker 的 lane）；下一個能放行的回合才 fork | 躺在 `deepseek/ready/`；worker 一有槽就 `rename` 進 `running/` | 那條 inst 留在本世界 inbox／`deferred/`，本回合不 fork | 那個 step 行程卡在第 4 個 `flock`，直到前三個之一 POST 回來 |
| 等的那個回合怎麼算 | agent 世界的回合早就結束（投出就返回）；agent status `waiting-llm`；之後每回合來取一次，取到才算「想完」 | 同 A | 本世界回合只跑 3 條，正常結束；第四條**下回合再排**——但 agent step 是 `every/` 型，下回合又複製一條，要去重 | 本世界回合＝max(前三批之一 + 第四條)＝**兩波**才結束；同回合的 tick 與其他 inst 陪等 |
| 兩個世界各自 `aos run`、各 3 隻走 DeepSeek | 6 條都投到同一個 llm 世界，它一次放 3 → 上限成立 | 6 個檔在同一個 `ready/`，worker 只開 3 → 上限成立 | 各世界各放 3 ＝ **6 條同時跑，上限破功**（除非加全機鎖） | 6 個行程搶同 3 個 lock 檔 → 上限成立 |
| pi 引擎的 step 算不算一個呼叫 | 算：pi 內部連續打，對外是一條佔一槽的長呼叫（最長 600 s） | 同左；但 pi 不經 spool，要嘛 pi 指 proxy、要嘛承認它繞過 | 算：step inst 標 `llm:deepseek`，佔一槽整個 step | 算：`step_pi` 取槽→fork pi→放槽 |
| 上限保證的強度 | 靠 llm 世界的「每回合放 P 條」＋回合內 P 條並行 | 靠 worker 的並行數＋`running/` 檔數 | 只在單世界成立 | 靠核心 flock，**全機成立、行程死了自動放** |

## 五、回合邊界：四種相容方式與各方案的歸屬

| 方式 | 行為 | 代價 | 天然屬於 |
|---|---|---|---|
| 1 佔住回合同步等（現況） | 思考在 inst 內做完才返回 | 最慢的一條拖住整批；heartbeat 陪等 | C、D |
| 2 投遞回合／取件回合 | step 投出就返回，下回合（起）來取；status 多一個 `waiting-llm` | +1～+3 回合；`--interval` 越小空輪詢越多；要存 `pending.json` | A、B |
| 3 尾巴批 | 同回合內 out 產生新 inbox 就再跑一批 | 改 PROTOCOL §5「一回合一批」；要設尾巴上限 | 誰都不天然；只是 2 的加速 |
| 4 `timeout_ms` 保險絲 | 仍同步，超時殺掉 | 超時≠端點沒收到，留 unknown | 所有方案都該有 |

子 agent 推演（主 agent 派 3 隻子 agent 各想一次；LM Studio P=1、每次 10 s、`--interval 100`）：方式 1 → 1 回合 30 s；方式 2 → 2 回合、30 s 內約 300 次空輪詢；
換 DeepSeek P=3、每次 3 s：方式 1 → 1 回合 3 s；方式 2 → 2 回合 3 s。**並行上限決定回合長度，方式 1／2 只決定「誰陪等」。**

## 六、建議（隊長判斷；代價一併列）

1. **保底先做 D**：只動 `core/llm`，協定、loop、版面全不動，四條路徑（含 pi 包一層）立刻受「每顆 CPU 同時 ≤ N」約束，全機成立、死行程自動放槽。代價：回合被拖長、沒優先序、沒 durable 隊伍、unknown 沒地方記——它是**閘**不是**排程器**。
2. **正式方向走 B**：使用者層級 spool＋每顆 CPU 一個 worker（原型可以是不引用 aos lib 的 Python），agent 改 submit/poll（方式 2）。它同時答了公平、優先序、退避、unknown、崩潰恢復、多世界、子 agent 團隊——五位 workshop 與 terra 都落在這裡。代價：多一支要監控、啟停的 daemon；多一份 spool contract；agent 多 1～2 回合延遲。
3. **A 當 B 的「介面」而不是排程器**：「LLM 是另一台同協定機器」的心智模型值得留（`aos deliver <llm-world>` 已可跨資料夾），但 loop 一回合把 inbox 全 fork，A 要真的限流就得改 loop 加 `--max-inflight`，最後長成 B 同型。
4. **C 不建議**：`every/` 型 step 被閘掉下回合又複製一條（要去重）、閘只管單世界、還要改 PROTOCOL 讓 loop 讀 metadata——三個代價換來的只有單世界的並行上限，D 用更少改動做到更多。
5. **選 CPU**：預設**固定綁**（`engine.json` 現況）＋可選 `tier`；「依可用性」只在同 tier 內、且對話 session pin 住實際 CPU，改派要寫進結果 metadata。代價：pin 住的 CPU 掛了要問人或依 policy 降級。

## 七、要使用者拍板的清單

| # | 問題 | 選項 | 建議 | 代價 |
|---|---|---|---|---|
| 1 | 排程機制走哪條 | A 世界／B spool+worker／C loop 閘／D flock 槽 | **先 D 保底，正式走 B**；A 留作介面；C 不做 | D 回合變慢；B 多一支 daemon |
| 2 | **上限設定住哪** | ① 使用者層 `~/.config/aos/llm/cpus.json`（或 `~/.aos/cpus.json`）② 世界層 `.aos/llm.json` ③ 兩層：使用者層是總上限、世界層只能再往下限 | **① 為權威**（endpoint 是跨世界共享的，上限放世界裡第二個世界就看不到）；③ 之後要配額再加 | 多一個 aos 的使用者層設定目錄，要決定 `~/.aos/` 還是 XDG |
| 3 | **超上限時排隊還是退回** | ① 排隊（等到有槽）② 退回 exit 75（`EX_TEMPFAIL`），呼叫者下回合再來 ③ 排隊但帶等待上限，超過才退回 | **③**：D 是取槽 timeout、B 是 `deadline_at`；退回時 agent status 寫 `waiting-llm` 不算失敗 | 要定等待上限的預設值；退回後 `every/` 型 step 下回合自然重來，一次性 inst 要自己重投 |
| 4 | pi 引擎那條算不算一個呼叫 | ① 算一個佔槽的長呼叫 ② 不算、放行（繞過） | **①**，整個 step 佔一槽 | pi 一步最長 600 s，佔槽期間別人等；上限 3 時等於最多 3 隻 pi agent 同時想 |
| 5 | 回合邊界怎麼相容 | ① 佔住回合同步等 ② 投遞／取件兩回合 ③ 尾巴批 | D 用 ①、B 用 ②；③ 不做 | ② 多 1～2 回合與空輪詢；① 一個世界的回合可能拖到幾十秒 |
| 6 | 優先序要不要、怎麼表達 | ① 不做 FIFO ② `user > agent > heartbeat` 三級（B：子目錄；D：hi/lo 兩組槽） ③ 數字優先權 | 原型 ①；B 落地時 ② | ② 要 aging 防 heartbeat 餓死 |
| 7 | 選 CPU 的策略 | ① 固定綁 ② tier 映射 ③ 依可用性 ④ 依成本上限 | ①＋可選 ②；③ 只在同 tier 內且 session pin | ③ 同一對話換模型、可預期性跳動 |
| 8 | CPU 掛了能不能自動改派 | ① 永不 ② 同 tier 內 ③ 跨 tier 降級 | ②，且**只對未送出的**；送出後斷線＝unknown 不重送 | 改派要寫進結果 metadata，否則帳本說謊 |
| 9 | 每顆 CPU 的並行上限預設值 | lmstudio：1／4（實測 `n_slots=4`）；deepseek：3（使用者的例子） | lmstudio 先 1（VRAM 保守），量完 [experiments §四](experiments.md) 再放大 | 設 1 會浪費端點本來的 4 槽 |
| 10 | 速率（RPM／TPM）與日額要不要一起管 | ① 只管並行 ② 加 token bucket ③ 加成本帳本 | 原型 ①；B 落地時 ② | ②③ 都要 durable 狀態，D 做不到 |
| 11 | A 的心智模型要不要保留 | ① 保留為 B 的投遞介面 ② 放棄 | ① | 兩套說法（世界 vs spool）要在文件裡對齊 |

## 八、交接

- **待使用者**：模型載好時跑 [experiments §四](experiments.md) 的並行度腳本，把四行數字填回 §五（今天不能跑：POST 會觸發 JIT 載入）。
- 拍板 1／2／3 之後：D → 開一條 `core/llm` 的實作線；B → 先寫 spool contract（請求檔、結果檔、六個目錄）再開 worker 線；兩者都要回頭改 [pi-cpu](../../../../core/agent/docs/pi-cpu.md) 的「pi 繞過」段。
- 隊員成品原文（sol：盤點表＋log 掃描＋CPU 表欄位草案；terra：A/B＋CPU 表＋JSON 原型；luna：C/D＋回合邊界＋選 CPU）只留在隊長 scratchpad，本頁已合成；要看細節再開線重跑。
- sol 對 CPU 表的一個提醒值得留：**表的列 ≠ 配額邊界**——本機容量按「載入的 instance」、DeepSeek 容量按「帳號」（多把 key 共用）、價格按「model」；欄位要分 `cpu_id`／`capacity_scope`／`credential_scope`／`model`，別把三件事塞進一個名字。

## 使用者裁決（2026-08-30）

| # | 裁決 |
|---|---|
| 1 | **先 D（flock 槽）保底，正式走 B（spool＋worker）**；A 留作介面；C 不做 |
| 2 | 上限設定**兩層**：使用者層總上限（權威），世界層只能再往下限 |
| 3 | 超上限：**排隊但帶等待上限，超過才退回**（status `waiting-llm`，不算失敗） |
| 4 | pi 引擎的 step **算一個呼叫、佔一槽** |
| 5 | 回合邊界隨 1：D 同步等、B 投遞／取件兩回合 |
| 6 | **優先序要做：數字優先度，登記時填**（使用者主動要求；D 保底就要做進去） |
| 7 | 選 CPU：agent 固定綁 engine＋可選 tier |
| 8 | CPU 掛了：同 tier 改派、只對未送出的；送出後斷線＝unknown 不重送 |
| 9 | 並行上限預設：lmstudio 1、deepseek 3（實作層，可調） |
| 10 | 原型只管並行；B 落地時加 token bucket |
| 11 | A 的心智模型留作 B 的投遞介面 |
