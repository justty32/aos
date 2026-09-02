# 隊 V 回報——排程保底 D（flock 槽、兩層上限、數字優先度）

← [交接書 proto-V-sched-D](../done/proto-V-sched-D.md)｜[ideas/scheduling](../../../ideas/scheduling/README.md)｜[PROTOCOL](../PROTOCOL.md)

**分支**：`worktree-agent-aa49bca5136311628`（已 rebase 到 main `0aea5fa`，含隊 U 的 `core/tool`）
**隊形**：Opus 隊長＋codex gpt-5.6-sol ×3（隊長寫任務書、審 diff、跑建置與驗收、commit；不親自寫實作）

## 做了什麼

三個 commit，一條線：槽層 → CLI → pi 佔槽。

| commit | 內容 |
|---|---|
| `11f42bc` | `core/llm` 槽層：`slot.hpp`／`slot.cpp`／`test_slot.cpp`＋CMake |
| `df33f4c` | `aos llm` 接上槽：`--engine`／`--priority`／`--slots`、exit 75；review 修正 `O_CLOEXEC` |
| `ea8f12a` | pi 的 step 佔一個 provider 槽；`smoke_slots.sh`＋README／code-map／ideas 註記 |

**機制**：每顆 CPU 一個目錄 `<AOS_HOME>/slots/<cpu>/`，`N` 個槽檔 `<k>.lock` 用
`flock(LOCK_EX|LOCK_NB)` 輪取；取不到就寫等待票 `wait/<pkey>-<ts>-<pid>`，
`pkey = 2e9 - priority` 補零成 10 位 → **字典序＝優先度大者先、同優先度先到先得**。
掃描時只有**前 N 名**去搶槽（保住優先序，又能讓 N 個槽同一輪填滿）。
等待票自己也被 flock 住：別人鎖得住就代表原主已死，順手清掉——
否則一個被 kill 的等待者會永遠卡住整條佇列。持有者死掉核心自動放槽。

**設定兩層**：使用者層 `<AOS_HOME>/cpus.json` 權威；世界層 `<world>/.aos/llm.json`
的 `max_inflight` 只能往下限（取小者，且無權替使用者層沒設的 CPU 開上限），
`wait_ms` 可覆蓋。**沒設定＝不限＝完全不取槽**，維持現狀。

## 5 條驗收的證據

| # | 驗收 | 證據 |
|---|---|---|
| 1 | build＋ctest 全綠（rebase 後） | rebase 到 main `0aea5fa` 後 `cmake --build --preset default -j8` 無 warning；`ctest --preset default` **8/8 全過**（隊 U 的 `aos_tool_tests` 一併過） |
| 2 | 兩個 `aos llm` 搶一個槽；`wait_ms` 100 → exit 75 | `smoke_slots.sh` [1/4]：`--slots` 在第一個跑時顯示 `lmstudio 1 held 1 waiting`，假端點的呼叫時序算出**同時最大呼叫數＝1**（`start A`→`end A`→`start B`），兩個都 exit 0。[2/4]：`wait_ms=100` 時第二個 `exit=75`、stderr **剛好一行** `waiting-llm` |
| 3 | 三個等待者 priority 1／5／3 → 取槽順序 5、3、1 | `aos_llm_tests` 的 `waiting llm slots honor numeric priority`：父行程佔住唯一的槽、fork 三個子行程（priority 1／5／3）、輪詢等三張票都到齊才放槽。斷言 `{"5","3","1"} == {"5","3","1"}` PASSED |
| 4 | 世界層只能往下限 | `smoke_slots.sh` [3/4]：使用者層 `max_inflight 1`，世界層設 `0` → `aos llm` 立刻 `exit 75`＋`waiting-llm`；世界層設 `5` → `--slots` 的 `MAX` 欄**仍是 1**（取小者） |
| 5 | pi 的 step 期間 `--slots` 顯示 deepseek 佔 1 | `smoke_slots.sh` [4/4]：`aos agent init --engine pi`＋假 pi（`AOS_PI_BIN`，睡 2 秒後吐一行 `turn_end` JSON），step 背景跑時 `--slots` 顯示 `deepseek 1 held / MAX 3`；step 結束後再看已回到 `0` |

**驗收腳本**：`bash core/llm/tests/smoke_slots.sh`（可重跑、離線、全程 `AOS_HOME`
指暫存目錄，不碰真的 `~/.aos`、不打網路、不用 GUI、不碰 LM Studio）。
隊長另外獨立跑過一份等價腳本交叉驗證第 2、4 條，結論相同。

## 隊長裁決

| # | 裁決 | 理由 |
|---|---|---|
| 1 | **不做 `aos agent init --priority N`** | 交接書 §4 要它，但硬性限制寫明 `core/agent` 只可改 `engine_pi.cpp`／`init.cpp` 一欄／`README.md` 一段；`--priority` 需要動 `run.cpp`＋`agent.hpp`＋`engine.cpp`＋`step.cpp` 四個檔（隊 U 的領地，衝突面大），且**5 條驗收沒有一條需要它**。改在 `core/llm` 全做：`--priority` 旗標＋`AOS_LLM_PRIORITY` 環境變數，pi 那條也讀同一個環境變數 |
| 2 | pi 的 CPU 名＝`engine.json` 的 `provider`（空的話 `deepseek`） | 交接書 §5 的講法 |
| 3 | **取槽放在「吃掉 `say/*.md` 之前」** | 裁決 3 說逾時退回不算失敗、下回合重試；訊息一旦 `remove` 就沒了。先取槽才吃訊息，逾時時訊息原封不動留給下回合的 `every` |
| 4 | 世界層的 `wait_ms` **直接覆蓋**（不套「只能往下」） | 它是「這個世界願意等多久」，不是資源上限，沒有跨世界外部性 |
| 5 | 沒設定＝不限（不是套用裁決 9 的 1／3 當預設） | 依交接書 §3「沒設定＝不限（維持現狀）」；1／3 寫進 README 當建議值。驗收 2／4 也都靠明示設定 |
| 6 | 等待迴圈「前 N 名都可搶槽」而非「只有隊首搶」 | 一樣是嚴格優先序，但 N 個槽能同一輪填滿，不必一輪放一個 |
| 7 | `core/llm` 自己實作 `resolve_world()`（10 行），不引入 `aos::loop` 相依 | 只為了找 `.aos/` 就多一條跨小專案相依不划算 |

**審 diff 抓到的一個實質問題**（已修）：`slot.cpp` 的 `open()` 原本沒有 `O_CLOEXEC`。
flock 的鎖掛在 open file description 上、`fork` 後父子共用，所以 `exec` 出去的
無關子行程會把槽一直佔住——而 pi 那條正是「持有槽的同時 fork+exec」，會直接踩到。
四處 `open()` 全部補上。

## 沒做、留給下一棒

- **`aos agent step` 走 lmstudio 那條還沒取槽**：它直接呼叫 `aos::llm::complete()`
  （函式庫層），槽只加在 `aos llm` 的 CLI 層。所以 lmstudio 的上限目前**只對
  `aos llm` 子命令成立**，agent 內嵌呼叫那條要動 `step.cpp`（本輪禁區）。**這是這一輪真實的缺口**，已記進 [ideas/scheduling](../../../ideas/scheduling/README.md) 的實作註記。
- `state.json` 不動（裁決：B 再做）；沒有 durable 隊伍、沒有依可用性跨 CPU 改派、
  沒有 token bucket、`unknown` 仍無處記——這些都是正式方案 B 的範圍。
- 邊緣狀況照原則跳過：等待票 unlink 與他人 open 之間的競態、
  `Ticket::remove()` 拋錯時的 fd 洩漏。

## 收線狀態

已 `git rebase main`（乾淨，無衝突），**未 push、未 merge**——請調度者在主 repo 合。
