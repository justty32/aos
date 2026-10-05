proto7-2 已推翻 C++ 現行「同步批次 loop 同時承載 agent 語意」作為通用核心的設計；移植應先重建錯誤判定、程序身分與可恢復的執行交接，再接回 agent／LLM，而現有 C++ 已有數個可由程式碼確認的漏工作、誤報成功、併發覆寫與程序殘留缺口。

## 1. 審查範圍與驗證程度

- **基準版本**：`6daebe2ef8227021745def649f4e3d86a3a8038c`。
- **範圍**：`core/exec`、`wire`、`loop`、`llm`、`agent`、`tick`，對照 `proto7-2` 現行實作、spec、模組契約、`notes/problems.md` 與六輪 play 報告。
- 六條平行審查線均已回報；主要發現另做交叉查核。
- **全程唯讀**：沒有修改檔案、執行產品程式、建置、測試、故障注入、commit 或 push。最後檢查 `core`、`proto7-2` 沒有工作樹差異。
- 下文「已確認」指**靜態控制流程與資料流足以建立反例**，不是本次已實際重現。所有重現條件與測試建議均未執行。

判定時以現行實作、spec、各包契約為準，歷史報告用來追溯教訓。不能直接把舊調查當最新決定：[proto7-2/notes/layer-interfaces.md](../../layer-interfaces.md):5 明載它是舊 commit 的調查紀錄。

另有一項範圍差異：實際 CMake 已包含第七個核心 `core/tool`，見 [core/CMakeLists.txt](../../../../core/CMakeLists.txt):8。本次僅追查其與 agent 的依賴及測試位置，沒有將它擴大為完整第七模組審查。

## 2. 哪些 C++ 設計已被原型取代

### 2.1 核心差異

| 主題 | 現有 C++ | proto7-2 最新契約 | 移植判斷 |
|---|---|---|---|
| 回合執行 | `run_turn` 一次啟動整批，`wait_all` 等全部結束後才推進 turn。 | tick 啟動後立即返回；runner 持續監督任務；tock 收集事實。 | **同步批次 loop 不能直接充當新 tick／tock。** 證據：`core/loop/src/turn.cpp:132`、`:144`、`:160`；`proto7-2/spec.md:154`、`:161`、`:218`。 |
| daemon | 將單一 loop fork 到背景，建立 session、重導 log。 | 管理明確登記的 nodes，每個 node 有獨立時間線、owner pause、rounds、wake 與世代。 | 背景化工具可保留，但需要新的 daemon 狀態機。證據：`core/loop/src/daemon.cpp:23`、`:38`；`proto7-2/spec.md:25`、`:37`、`:76`。 |
| 任務入口 | `inbox/` 搬檔，加上 `every/` 每回合產生指令。 | 唯一 `tasks.json`，所有寫者同鎖；`once`／`each`／`keep`、`max_live`、准入回合。 | 不只是改檔名；登記、啟動、重播、刪項的語意都不同。證據：`core/loop/src/aggregate.cpp:82`、`:89`、`:113`；`proto7-2/spec.md:131`、`:137`、`:157`。 |
| 執行身分 | 指令 id、預猜回合、裸 PID。 | node＋slot＋run；程序另核對 PID＋starttime；動作有 generation。 | 身分必須貫穿結果、kill、重播與清理。證據：`core/agent/src/step.cpp:258`、`:350`；`core/loop/src/stop_cli.cpp:67`；`proto7-2/spec.md:199`、`:209`、`:245`。 |
| 中斷恢復 | 主要依賴記憶體、整數 turn、事後 state／out。 | `round.open`、launch、birth、runner、pid、exit 各自留下可查證的交接事實。 | 需要重建持久交接，不能只補「啟動時重掃 batch」。證據：`core/loop/src/turn.cpp:132`、`:138`、`:148`；`proto7-2/spec.md:170`、`:214`、`:224`。 |
| 歷史與結果 | 按 turn 永久增加 `batch/<turn>/insts`、`out`。 | 核心只留最新總結、最新 run；槽可重用，交付物須在槽外。 | 舊 batch 不再是新核心的主資料模型。證據：`core/loop/src/layout.cpp:55`；`proto7-2/spec.md:21`、`:195`、`:205`。 |
| agent 耦合 | loop 鏡射 agent 狀態、掃 `say/` 喚醒，特殊處理 exit 75；tick 直接呼叫 agent。 | 核心不知道 agent／LLM；模組透過普通任務、argv 包裝程式、工具及檔案協定接入。 | 應把語意移到上層 adapter；不必因此取消單一 `aos` 執行檔。證據：`core/loop/src/wake.cpp:70`、`core/loop/src/turn.cpp:83`、`core/tick/CMakeLists.txt:5`；`proto7-2/spec.md:269`。 |
| inst 協定 | `argv`、`env`、字串 stdin、timeout 的簡單 DTO。 | `envs`、串流重導與選項、`$env`／`$fmt`／`$ref`／`$opt`，另有 argv／inst 任務入口。 | **不是欄位改名就相容。** 證據：`core/wire/src/inst.cpp:21`；`proto7-2/lib/aos_inst.py:3`、`:7`、`:19`；`proto7-2/spec.md:136`。 |

### 2.2 三個容易移植錯的名稱

1. **C++ `core/tick` 是行事曆／心跳判定，不是 Python 的回合啟動器。**  
   它應接到上層排程任務，而不是同名逐函式翻譯。證據：[core/tick/CMakeLists.txt](../../../../core/tick/CMakeLists.txt):11、[proto7-2/spec.md](../../../spec.md):150。

2. **C++ `aos run` 是外層 loop；Python `aos7-run` 是單次任務的持續監督程序。**  
   證據：`core/loop/src/run.cpp:410`、[proto7-2/spec.md](../../../spec.md):218。

3. **`core/tool` 與 `proto7-2/modules/tools` 不是同一層。**  
   前者服務 agent 工具登記；後者提供 ctl、wait-tock、taskside 等協定工具。證據：`core/agent/CMakeLists.txt:18`、[proto7-2/modules/README.md](../../../modules/README.md):11。

**重要限制：proto7-2 沒有實作新版 kernel／agent。** 因此不能說現有 persona、Completion、模型設定或工具語意已全部被否定；被明確改掉的是基礎設施邊界與生命週期。證據：[proto7-2/README.md](../../../README.md):5。

## 3. 已確認的主要缺口

以下優先級中，P1 表示可能漏工作、破壞狀態、誤殺、雙開或留下持續工作的程序；P2 表示特定併發下失敗或結果語意錯誤。

### F01｜P1：exec 啟動失敗會被 loop 寫成成功

`exec::Result` 的 `exit`、`signal` 預設都是 0，且明載 `error` 非空時兩者不可信。`wait_all` 保留啟動錯誤，但 loop 的 `to_outcome` 完全不看 `error`；`collect_failures` 也把預設 exit 0 當成功。

因此，`mkstemp` 或 `fork` 失敗、根本沒有啟動子程序時，仍可能產生 `exit: 0` 的 out，CLI 也沒有指令失敗可報。

**證據**：

- [core/exec/include/aos/exec.hpp](../../../../core/exec/include/aos/exec.hpp):36
- [core/exec/src/start.cpp](../../../../core/exec/src/start.cpp):137、同檔 `:167`
- [core/exec/src/wait_all.cpp](../../../../core/exec/src/wait_all.cpp):67
- [core/loop/src/turn.cpp](../../../../core/loop/src/turn.cpp):30、同檔 `:83`

**最小反例**：先準備合法待執行指令，再讓執行階段的 `TMPDIR` 指向不存在的目錄，使暫存檔建立失敗。此反例不需要 SIGKILL。

**原型教訓**：失敗不能偽裝成成功。新 runner 對啟動前失敗留下明確 exit／error，見 `proto7-2/spec.md:218`。現有 `core/loop/tests/test_run_cli.cpp:89` 主要檢查子程序非零退出，沒有覆蓋這種父程序內部錯誤。

### F02｜P1：把「讀不到」當「不存在」，會重置 turn 或消耗未送達行程

這個錯誤有兩條獨立路徑。

**loop 路徑**：`ensure_layout` 只要讀 turn 失敗，就寫回 1；`read_turn` 讀取或解析失敗也回 1。`deliver` 本身會呼叫 `ensure_layout`，所以單純投遞也可能重置回合。

若 turn 已大於 1，對 turn 注入 EACCES／I/O 故障，而 `.aos` 目錄仍可發布檔案，就可能退回第一回合、覆寫舊 batch。

**tick 路徑**：`single_agent` 把目錄讀取失敗與「沒有唯一 agent」都回成 `nullopt`，轉成 `"none"`。`say_message` 遇到 `"none"` 不送訊息卻回成功，接著 schedule 被刪、routine 的 `last_run` 被更新。

**證據**：

- [core/loop/src/layout.cpp](../../../../core/loop/src/layout.cpp):74、同檔 `:82`
- [core/loop/src/deliver.cpp](../../../../core/loop/src/deliver.cpp):15
- [core/tick/src/paths.cpp](../../../../core/tick/src/paths.cpp):20
- [core/tick/src/tick.cpp](../../../../core/tick/src/tick.cpp):54、同檔 `:113`、`:181`、`:191`

另有同型問題：`core/loop/src/fs.cpp:86` 在檢查 `error_code` 前，已因 `exists == false` 返回空清單。

**定性限制**：舊 loop API 原本就把「讀不到＝1」寫成行為，這是需要撤換的危險舊契約；tick 在確知沒有唯一 agent 時採 `"none"` 則是既定行為，問題是把未知混進去。

**原型教訓**：A2-01、A2-02、G1、A4-01 都是同一類問題。來源：`proto7-2/notes/problems.md:93`、`:94`、`:152`；正確共用入口為 `proto7-2/lib/aos7_fs.py:84`、`:205`、`:223`。

### F03｜P1：aggregate 中途 I/O 失敗，前面已接受的工作不會再執行

aggregate 逐檔把 inbox 搬進 batch，並累積記憶體向量。若後面的 rename／讀檔失敗，它回傳部分向量及 error；`run_turn` 看到 error 立即退出，整批都沒有啟動。

下次 aggregate 只掃 inbox／every，不會重新接手已搬到 batch 的合法工作。

**證據**：[core/loop/src/aggregate.cpp](../../../../core/loop/src/aggregate.cpp):89、同檔 `:93`、`:99`、`:115`；[core/loop/src/turn.cpp](../../../../core/loop/src/turn.cpp):109。

**最小反例**：兩筆合法工作 a、b；a 已搬入 batch，b 在搬移後讀取失敗。解除故障再跑，a 仍只留在 insts，沒有執行與終局結果。

這不等同於 README 已接受的「壞 JSON 跳過」，也不需要程序崩潰。新 once 的 launch／birth 交接是應搬回來的設計，見 `proto7-2/spec.md:168`。回歸起點：`proto7-2/tests/core/test_once_threestate.py:86`。

### F04｜P1：`aos stop` 只憑裸 PID，可能停止 PID 重用後的無關程序

`run.pid` 只記 PID；stop 用 `kill(pid, 0)` 判活，再送 TERM／KILL，沒有 starttime、generation 或持鎖者身分核對。

自然反例是 daemon 被 SIGKILL，留下 pid 檔；同 UID 的其他程序後來取得該 PID，stop 就可能停止它。這不需要人工偽造 pid 檔。

此外，五秒後的 SIGKILL 不檢查回傳、不確認死亡，就刪 pid 檔並回成功。

**證據**：

- [core/loop/src/run.cpp](../../../../core/loop/src/run.cpp):35
- [core/loop/src/stop_cli.cpp](../../../../core/loop/src/stop_cli.cpp):36、同檔 `:67`、`:78`、`:93`

**原型教訓**：PID＋starttime，以及 kill 回成功前確認目標已死。來源：`proto7-2/spec.md:228`、`:247`；A3-09：`proto7-2/notes/problems.md:140`。

**驗證起點**：`proto7-2/tests/core/test_once_threestate.py:182`、`proto7-2/tests/core/test_daemon.py:430`。本次沒有實際製造 PID 重用。

### F05｜P1：正常 pi agent 路徑會留下另一個程序群組，並提前釋放 LLM 槽

實際組合是：

```text
loop → aos agent step → pi
        外層群組         另一個群組
```

每次 `exec::start_all` 都建立新 process group。loop 停止時，只能從自己的登記表向 agent 群組送 TERM；agent 內啟動的 pi 屬於另一個群組。agent 被終止後，監督 pi 的 `wait_all` 與十分鐘 timeout 也一起消失。

若啟用 LLM 槽限制，持槽 FD 使用 `O_CLOEXEC`，pi 不會繼承該鎖。結果可能是 **pi 還在做事，槽卻已釋放**。尚未消耗的 say 也可能在重啟後再次交給 pi。

**證據**：

- [core/agent/src/engine_pi.cpp](../../../../core/agent/src/engine_pi.cpp):84、同檔 `:110`、`:112`、`:220`、`:242`
- [core/exec/src/start.cpp](../../../../core/exec/src/start.cpp):98、同檔 `:175`
- [core/exec/src/interrupt.cpp](../../../../core/exec/src/interrupt.cpp):19、同檔 `:49`
- [core/loop/src/run.cpp](../../../../core/loop/src/run.cpp):105
- [core/llm/src/slot.cpp](../../../../core/llm/src/slot.cpp):354

**原型教訓**：G3／A5-01 的「前代未收，新代已開」。原型明確測試保留身分的 setsid 孫程序與另一 session，不能把正常 pi 組合歸為惡意逃逸。

**驗證起點**：延伸 `core/llm/tests/smoke_slots.sh:167` 的 fake pi；加入停止父程序，核對 pi 的 PID＋starttime、槽持有量與再次啟動次數。原型對照：`proto7-2/tests/core/test_ctl.py:79`、`:102`、`:116`。

### F06｜P1：exec 的中止機制有容量、啟動窗口與升級中止缺口

三個獨立問題：

1. **最多登記 256 個群組，滿了靜默略過。** `start_all` 沒有相應上限，第 257 個成功啟動的長任務不受 `interrupt_running` 管理。
2. **fork 到 register 之間有窗口。** 訊號只掃當時的登記表；`start_all` 沒有檢查取消旗標，訊號後仍可能繼續啟動本批後續工作。
3. **TERM 沒有統一升級為 KILL。** timeout 為 0 的任務若忽略 TERM，`wait_all` 可以一直等；外部 stop 最後強殺 loop，也不等於收掉任務。

**證據**：[core/exec/src/interrupt.cpp](../../../../core/exec/src/interrupt.cpp):16、同檔 `:25`；`core/exec/src/start.cpp:131`、`:163`、`:187`；[core/exec/src/wait_all.cpp](../../../../core/exec/src/wait_all.cpp):108。

**測試缺口**：`core/exec/tests/test_interrupt.cpp:10` 只測單一群組；`test_timeout.cpp:8` 雖啟動背景 sleep，但主要斷言主程序 signal 與耗時，沒有逐一核實後代已消失。

移植應搬的是受管理程序身分、TERM→grace→KILL→驗證的完整流程，不只是把 256 改大。原型實作入口：`proto7-2/lib/aos7_proc.py:176`、`:210`。

### F07｜P1：`aos chat` 繞過 run.lock，可與另一個回合執行者同時進入

`RunLock` 位於 run CLI，`run_turn` 函式本身沒有取得它。chat 只用 `run.pid` 判斷有沒有 loop，沒有時直接呼叫 `run_turn`。

然而有限步數的 `aos run --step N` 不寫 `run.pid`。所以：

- 有限步數 run 與 chat 可以並行。
- 兩個 chat 也可能一起進入。
- 它們會同時搬 inbox、產生 every 指令、改 turn／state，甚至並行消耗相同 agent 訊息。

**證據**：[core/loop/src/run.cpp](../../../../core/loop/src/run.cpp):150、同檔 `:381`、`:388`；[core/agent/src/chat_cli.cpp](../../../../core/agent/src/chat_cli.cpp):121、同檔 `:232`；`core/loop/src/turn.cpp:100`。

**驗證起點**：擴充 `core/loop/tests/test_run_cli.cpp:119`，加入 chat／有限步數 run 的交錯；現有案例只驗 run CLI 之間的锁。

原型可借鏡 action lock 與鎖內 generation 核對；但原型仍明載手動 tick／tock 與 daemon 的協調前提，不能宣稱任意混用入口都受保證。來源：`proto7-2/notes/component-contracts.md:63`。

### F08｜P1：固定 `.tmp` 破壞併發原子發布；整檔讀改寫也會丟更新

loop、agent、tick 都用固定 `目標.tmp` 寫入後 rename。

若 A、B 同時開同一暫存檔：

1. 兩者可能持有同一 inode。
2. A 寫完、rename 到正式目標。
3. B 繼續透過原 FD 寫入，等於修改**已發布的正式檔案**。

因此不只是「後寫者贏」；讀者可能看到發布後仍在變動的內容，另一個 writer 也可能 rename 失敗。

**證據**：

- [core/loop/src/fs.cpp](../../../../core/loop/src/fs.cpp):42
- [core/agent/src/store.cpp](../../../../core/agent/src/store.cpp):128
- [core/tick/src/table.cpp](../../../../core/tick/src/table.cpp):160

tick 另有整個 read→plan→deliver→write 過程沒有共同鎖的問題，見 `core/tick/src/tick.cpp:140`、`:209`。它會覆蓋同時進行的 routine／schedule 修改；這部分是舊 README 已接受的限制（`core/tick/README.md:178`）。

**原型教訓**：不同寫者使用私有暫存檔；共用表在穩定鎖檔下讀改寫，拿鎖後重讀事實。來源：`proto7-2/lib/aos7_fs.py:119`、`:184`、`:205`；A4-02：`notes/problems.md:153`。

C++ 若支援同程序多執行緒寫入，不能只照抄 PID 後綴，仍需每次寫入唯一性。

### F09｜P1：agent 多檔提交沒有可恢復的業務交接

| 中断位置 | 留下的狀態與影響 | 證據 |
|---|---|---|
| 刪 say 後、history 寫入前 | 訊息可能只留在 log，後續 step 不會從 log 重建對話。 | `core/agent/src/step.cpp:323`、`:327`、`:330` |
| history 已寫工具要求、deliver 前 | 沒有 say、沒有 pending；工具意圖可能不再執行。 | 同檔 `:330`、`:347` |
| deliver 後、pending 前 | 工具可能已執行，但 agent 沒有追蹤這次效果的 pending。 | 同檔 `:347`、`:350` |
| 工具結果寫 history 後、清 pending 前 | 下次可能再次採用相同工具結果、重複寫入歷史。 | 同檔 `:268`、`:275`、`:276` |

pi 成功路徑也先刪 say、後寫 history，見 [core/agent/src/engine_pi.cpp](../../../../core/agent/src/engine_pi.cpp):244。現有 log journal 的恢復只重建顯示用 log，不重建 history／pending，見 [core/agent/src/store.cpp](../../../../core/agent/src/store.cpp):279。

**定性**：這是 C++ agent 的交接缺口；不能寫成「proto7-2 已修好同一個 agent」，因為新版 agent 尚未實作。

可移植的教訓是持久 intent、穩定 request／attempt、結果身分核對，以及未知時停住。參考 `proto7-2/packs/step/spec.md:56`、`:59`、`:79`。A6-01 也證明只交換兩次寫檔順序不夠，必須有可重建的完成證據，見 `proto7-2/notes/play/2026-10-04-astra-5-infra.md:48`。

### F10｜P1：手動 `agent step` 會預猜錯誤的工具結果回合，之後一直等待

這是正常公開入口可建立的確定性反例：

1. 初始 `.aos/turn` 是 1，沒有 `AOS_TURN`。
2. 手動 step 讀到 turn 1，Completion 回傳工具要求。
3. 工具進 inbox，pending 記 turn 1。
4. 隨後 loop 跑的仍是第 1 回合，工具結果落在 `batch/1/out`。
5. agent 固定等待 `pending.turn + 1`，也就是 `batch/2/out`。
6. 該工具已經消耗，不會再於第 2 回合產生結果，agent 因而卡住。

**證據**：

- [core/agent/src/step.cpp](../../../../core/agent/src/step.cpp):32、同檔 `:257`、`:350`
- `core/agent/src/init.cpp:98`
- `core/loop/src/turn.cpp:107`、`:145`、`:160`
- 手動 CLI 入口：[core/agent/src/run.cpp](../../../../core/agent/src/run.cpp):444

**測試盲點**：`core/agent/tests/test_agent_step.cpp:258` 人工給 `AOS_TURN=10`，再直接建立 `batch/11/out`，没有實際走這個手動 step→loop 的交接。

**原型教訓**：不要預猜 run。`proto7-2/packs/step/spec.md:56` 明確要求包裝程式從執行環境取得實際 `slot#run`，並把業務結果留在槽外。

### F11｜P2：LLM 等待票先公開、後 flock，可被別人當死票刪掉

A 用 `open(O_CREAT)` 建票，尚未 flock；B 掃票時能取得該票的 flock，就把它當死票 unlink。A 隨後可能鎖住已無名稱的 inode，接著報「等待票遺失」；另一種交錯會報名稱衝突。

**證據**：[core/llm/src/slot.cpp](../../../../core/llm/src/slot.cpp):329、同檔 `:337`、`:159`、`:177`、`:345`。

這是正常併發的發布競態。**不能只據此宣稱超過 max_inflight**，因為容量仍有獨立 slot locks。

**驗證起點**：在建票與 flock 之間設 barrier，擴充 `core/llm/tests/test_slot.cpp:184`、`:253`。原型提供的是原子發布與清理證據的教訓，沒有可直接替換的新版 LLM 排隊器。

### F12｜P1：不同工作來源的 id 可以碰撞，工作與結果失去一對一關係

**inbox／every 碰撞**：一次性指令 id 是 `tick-1`，同時有 `every/tick.json`，第 1 回合兩者都進記憶體執行清單，但 every 覆寫相同 insts 路徑，結果也都寫 `out/tick-1.json`。兩個工作可能都执行，最後只剩一份結果。

**證據**：`core/loop/src/aggregate.cpp:90`、`:109`、`:123`、`:144`；[core/loop/src/turn.cpp](../../../../core/loop/src/turn.cpp):147。

**routines／schedule 碰撞**：兩張表各自允許同名，卻都產生 `hb-<id>-<turn>`；同回合投遞互蓋，兩邊仍可標記已處理。證據：`core/tick/src/tick.cpp:26`、`:66`、`:93`、`:187`；這也是 `core/tick/README.md:188` 已記錄的限制。

這與「使用者刻意重送相同 inbox id 就覆寫」不同：問題是不同來源共用沒有隔離的命名空間。

**原型教訓**：名稱、slot、run 與業務 request 分層，明訂作用域；參考 `proto7-2/spec.md:135`、`:209`，以及 `notes/problems.md:136`、`:137`。

### F13｜P1：id 未做路徑驗證，可讓投遞寫到 inbox 外

wire 只驗 id 是字串；deliver 直接拼 `id + ".json"`，再做路徑正規化。id 為 `../state` 時，會寫向 `.aos/state.json`。

**證據**：

- [core/wire/src/inst.cpp](../../../../core/wire/src/inst.cpp):21
- [core/loop/src/deliver.cpp](../../../../core/loop/src/deliver.cpp):16
- [core/loop/src/fs.cpp](../../../../core/loop/src/fs.cpp):112
- JSON CLI 確實走此入口：`core/loop/src/deliver_cli.cpp:110`、`:121`

tick 文件要求 id 符合固定正規式，但 JSON reader 只驗字串及表內重複，沒有套用該名稱限制。證據：`core/tick/README.md:34`、`core/tick/src/table.cpp:77`、`:128`。

**最小輸入**：含 `{"id":"../state","argv":["true"]}` 的指令 JSON。這是合作式協定的輸入驗證問題，不把它擴大成跨帳號安全隔離問題。

原型在挑槽前驗名稱，對照 `proto7-2/spec.md:135`、`:148`；回歸案例為 `proto7-2/tests/core/test_tick_tock.py:81`。

## 4. 其他已確認問題與應保留的界線

### 4.1 次要問題

| 問題 | 確認的行為與證據 |
|---|---|
| 合法 agent 名稱 `"none"` 被當成無收件人 | 名稱驗證允許 `"none"`，tick 卻以同字串當 sentinel，導致 ask 被跳過仍算成功。`core/agent/src/paths.cpp:48`；`core/tick/src/tick.cpp:54`、`:113`。 |
| JSON 字串內的 NUL 到 exec 才被截斷 | wire 接受字串內容，exec 用 `c_str()` 交給 POSIX API；例如 argv 中 `/bin/true\u0000suffix` 可能執行截斷後的程式。`core/wire/src/json_io.hpp:78`；`core/exec/src/start.cpp:145`。Python 對應路徑會處理 `ValueError`：`proto7-2/lib/aos_exec_run.py:132`。 |
| 明確路徑不可執行，被誤報為找不到 | 含 `/` 的 argv0 跳過 PATH 權限判定；`execve` 失敗一律回 127。`core/exec/src/spawn_prep.cpp:158`；`start.cpp:110`。Python 分辨 PermissionError→126：`proto7-2/lib/aos_exec_run.py:134`。 |
| 所有 SIGKILL 都被 agent 說成 timeout、可重試 | 手動 kill、其他來源的 SIGKILL 並不能推出逾時。`core/agent/src/step.cpp:127`。原型 executor 另存 `timed_out` 事實：`proto7-2/lib/aos_exec.py:64`。 |
| heartbeat 仍依賴裸 `aos` 的 PATH | 安裝的 every 指令是 `["aos","tick"]`，可能找不到或找到另一版本。`core/tick/src/init.cpp:23`。agent 初始化已使用解析後的程式路徑：`core/agent/src/init.cpp:111`。 |
| exec 被強殺後暫存檔沒有可恢復的清理歸屬 | `aos-exec-*-XXXXXX` 在正常 wait 時刪除，監督程序被殺則無此收尾。`core/exec/src/tempfile.cpp:41`；`wait_all.cpp:49`。原型 A2-07 要求確認寫者已死才清：`proto7-2/notes/problems.md:99`。 |
| heartbeat log 半行會與下一行黏在一起 | 單次 write 若短寫，回錯但留下半行，下一次直接 append。`core/tick/src/log.cpp:51`。原型 append 先檢查尾端換行：`proto7-2/lib/aos7_fs.py:163`。 |

### 4.2 不應誤報成新 bug 或過度承諾

- **C++ loop 沒有 SIGKILL 恢復，是明載舊限制。** 它已不符合新移植目標，但不能全部說成違反舊版承諾。來源：[core/loop/README.md](../../../../core/loop/README.md):162。
- **新舊兩邊都沒有承諾斷電持久化順序。** SIGKILL 恢復測試不能當成 fsync／斷電驗證。來源：`core/loop/README.md:163`、`proto7-2/notes/component-contracts.md:51`。
- **once 是 at-most-once，不是 exactly-once。** birth 寫好、runner 尚未接手時中斷，允許零執行並報 lost／never_started。來源：[proto7-2/spec.md](../../../spec.md):176。
- **通知不跨回合補送是最新設計。** F47 刻意刪除跨回合重試，只保留失敗紀錄與同回合恢復補寫。來源：`proto7-2/spec.md:258`、`:262`；`notes/problems.md:160`。
- **restart／reload 已移至 control 包。** 不應把歷史版本的核心 `ctl-seen`、永久去重或核心 restart 再搬回來。來源：`proto7-2/spec.md:248`、`notes/problems.md:157`。
- **原型只保證合作式受管理程序。** 換 uid、關 dumpable、清身分等在範圍外；保留身分的正常子程序則不能一概排除。來源：`proto7-2/spec.md:284`、`:290`。
- **核心檔案數固定，不等於儲存量固定。** `out.log` 大小上限仍未做；history 是可能漏回合的取樣，不能取代完整 agent 對話或帳本。來源：`proto7-2/spec.md:294`、`modules/README.md:30`。
- **C++ `every_ms` 已有實作。** tick README 的「沒人讀」已過時；實際程式在 `core/loop/src/aggregate.cpp:117`、`:140`，已有 `core/loop/tests/test_every.cpp:94` 等測試。
- **wire 已處理非法 UTF-8 的 JSON 序列化替換。** 不應再報成 dump 必然拋錯，見 `core/wire/src/json_io.hpp:159`。

## 5. 原型教訓如何落回 C++

| 原型教訓 | C++ 對應／移植要求 |
|---|---|
| A2-01／A2-02、G1：未知不能當不存在 | F02；共用嚴格 fact reader，將判定一路傳到控制流程。`proto7-2/notes/problems.md:93`、`:94`、`:221`。 |
| A2-07：中斷後暫存檔須有安全清理依據 | F08 及 exec 暫存檔；私有暫存檔、確認寫者死亡、穩定鎖 inode。`notes/problems.md:99`。 |
| A3-05／A3-06：識別作用域與無損命名 | F12、F13；分開 request、attempt、slot、run，名稱不能直接當任意路徑。`notes/problems.md:136`、`:137`。 |
| A3-09：不知道是否殺乾淨，不可報成功 | F04、F05、F06；kill 結果需要可核實的終局事實。`notes/problems.md:140`。 |
| A4-02：拿鎖前的快照仍會過時 | F07、F08、F11；鎖內重新讀取決策依據。`notes/problems.md:153`。 |
| A5-01／G3：前代尚活，新代已開始 | F05；先收前代，再釋放資源或開始新代。歷史實測為 10/10，見 `notes/play/2026-10-04-astra-4-infra.md:54`。 |
| A6-01：調整寫入順序仍可能錯收程序 | F09；需要可恢復的完成證據，不能只有兩個檔案的先後順序。`notes/play/2026-10-04-astra-5-infra.md:48`。 |
| A6-02：unknown 不能壓成 generic failure | F01，以及未來 LLM／budget adapter 的錯誤契約。`notes/problems.md:181`。 |
| A7-01：跨語言 rounding 不可照函式名翻譯 | 現有 C++ 無對等 adapt 實作；屬未來移植測試要求，不是本次 C++ bug。`packs/adapt/tests/test_adapt_unit.py:110`。 |

最需要保留的是**業務效果與基礎設施結果分開判定**。step 失敗、逾時或沒有結果檔，都不能推出「API 沒有收費」「工具沒有產生效果」。budget 的精確去重成立於可查回、可按 K 去重的假後端，不能直接外推到任意 LLM API。來源：[proto7-2/packs/budget/README.md](../../../packs/budget/README.md):33、同檔 `:39`、`:40`、`:55`。

## 6. 移植路線圖

這是依目前證據整理的技術路線，尚未進行實作。

### 6.1 模組對應

| 現有模組 | 建議處理 |
|---|---|
| `core/exec` | 保留 POSIX 啟動準備、環境處理、單調時計時等底層能力；新增持續 runner 與程序身分／回收層。現有 `wait_all` 留作批次相容 API，不作新 tick 的核心。 |
| `core/wire` | 保留 codec 與公開型別隔離；新增新協定的 DTO、嚴格型別與錯誤分類。舊 Inst／Outcome 不冒充新 birth／exit／tasks。 |
| `core/loop` | 主要重建區：拆成 daemon、timeline、tick、tock、task lifecycle；舊 inbox／batch 行為由相容入口保留或明確退役。 |
| `core/llm` | 保留 HTTP transport、模型設定、slot RAII；修等待票競態，另訂 request／attempt／unknown 契約。資源政策不灌進通用 tick。 |
| `core/agent` | 保留 persona、工具驗證、Completion 注入等上層能力；重做訊息與工具的持久交接，停止依賴 `pending.turn + 1`。 |
| `core/tick` | 保留 clock／due／時區判定，成為上層排程 adapter；到期後登記 once 或送上層訊息，不與新回合 tick 混為一談。 |

### 6.2 先後順序與驗收門檻

| 階段 | 工作 | 完成門檻 |
|---|---|---|
| 0．凍結相容邊界 | 定義新檔案、退出碼、欄位擁有者與命令映射；維持一支 `aos`，用子命令承載。舊 `.aos/batch` 與新槽資料隔離。 | 不能自動把舊 batch 猜成已執行／未執行的新任務；測試可選 Python 或 C++ backend。 |
| 1．共用事實與程序層 | N／U／B／K、嚴格讀取、私有原子暫存檔、鎖內 RMW、PID＋starttime、run 身分、kill 驗證。 | 未知不破壞、不重起；併發寫入不發布半份資料；過期身分不誤殺。 |
| 2．持續 runner | birth→runner→pid→exit 交接；明確啟動失敗、signal、timeout、lost；輸出持续留在任務位置。 | 父動作退出不使監督失效；合作式後代收得到；啟動各中斷點可恢復。 |
| 3．單 node tick／tock | once／each／keep、max_live、槽重用、reaped、總結先提交再通知。 | 不雙開；once 最多一次；不丟終局事實；同回合重播正確；長跑核心檔案數固定。 |
| 4．daemon | 登記 nodes、每 node 時間線、generation、action lock、owner pause／rounds／wake、接管恢復。 | 未關回合先恢復；tick 失敗不扣 rounds；未知持鎖者不殺；停止不被卡住的動作阻塞。 |
| 5．混合語言模組 | 先用 C++ 核心接既有 Python tools／control／subd，再接 step／budget／adapt／history。 | 每包以既有檔案契約通過相同驗收；不需要先把所有 Python 都翻成 C++。 |
| 6．agent／LLM／行事曆 | 業務 request、attempt、實際 run、槽外結果、訊息提交、外部效果 unknown；接回 clock／due。 | F05、F09、F10 的端到端反例消失；API 結果未知不被當成可安全無限重試。 |

有兩個容易漏掉的移植阻點：

- **不能只把測試最外層 executable 換掉。** Python daemon、task 啟動程式仍硬寫 `[sys.executable, BIN/...]`，見 `proto7-2/lib/aos7_daemon_timeline.py:37`、`lib/aos7_task.py:316`。
- **runner 判定硬編碼命令列中的 `aos7-run`。** 改成單一 `aos` 的子命令後，需同步改身分辨認；否則混合語言清理會判錯 runner。見 [proto7-2/lib/aos7_proc.py](../../../lib/aos7_proc.py):110。

平台也須明定：現有 CMake 放行 POSIX／macOS，而原型程序判定直接依賴 Linux `/proc`。證據：`CMakeLists.txt:24`、`:55`；`proto7-2/lib/aos7_proc.py:16`。目前尚未決定新核心只支援 Linux，或另做平台 backend。

## 7. 測試怎麼搬

### 7.1 保留黑箱測試語言，移植判定依據

Python 測試驅動可以保留，但要抽出完整 argv factory，且保證被測 daemon 啟動的 tick／tock／runner 也使用選定的 backend。

不能全靠替換 executable：`proto7-2/tests/base.py:169`、`:173` 直接呼叫 Python 函式並使用 mock；這些要改成 C++ 單元測試或等價的 syscall／fact 故障注入。

測試至少要檢查：

- 退出碼、stdout JSON、檔案內容及應保持不變的原始 bytes。
- 實際存活的 PID＋starttime／run，而不只看 status 自述。
- 放在槽外的效果次數，避免清槽後把重複執行證據一起清掉。
- 解除故障後是否恢復，且沒有重複效果或回合跳號。

`tasks_rev` 是 **tasks.json 原始 bytes 的 SHA-1 前 12 碼**，不能先正規化 JSON 再算，見 `proto7-2/lib/aos7_tick.py:26`、`:34`。

### 7.2 優先移植的測試群

| 驗收主題 | 現成來源 |
|---|---|
| N／U／壞內部事實、壞表拒絕 RMW | `proto7-2/tests/core/test_once_threestate.py:93`、`:112`、`:187`；`test_errors.py:57`、`:103` |
| 程序與檔案讀取故障矩陣 | `proto7-2/tests/core/test_matrix_faults.py`；故障命中斷言在 `proto7-2/tests/_matrix.py:93` |
| once／keep 的真 SIGKILL 交接 | `proto7-2/tests/core/test_matrix_once.py:25`、`:42`、`:66`，涵蓋 tick 七個點、runner 兩個點 |
| 模式、槽重用與終局保留 | `proto7-2/tests/core/test_tick_tock.py:119`、`:136`、`:213`、`:278`、`:300` |
| 後代清理、過期 run／PID 不誤殺 | `proto7-2/tests/core/test_ctl.py:54`、`:79`、`:88`、`:102`、`:116`、`:134` |
| 總結提交與同回合重播 | `proto7-2/tests/core/test_matrix_docs.py:121`；`test_daemon.py:370` |
| daemon 接管與未知持鎖者 | `proto7-2/tests/core/test_daemon.py:396`、`:415`、`:430` |
| control 並行同 request | `proto7-2/modules/control/tests/test_control.py:180` |
| subd 前代回收與 stop 中斷 | `proto7-2/modules/subd/tests/test_subd_recover.py:128`、`:177`、`:210`、`:295`、`:307` |
| step 持久交接、槽消失後結果仍有效 | `proto7-2/packs/step/tests/test_step.py:372`、`:389`、`:405`、`:421`、`:447`、`:482` |
| budget 獨立核帳、重送與 unknown | `proto7-2/packs/budget/tests/test_budget_ledger.py:119`、`:128`、`:174`、`:209`、`:385`；`tests/budgetcase.py:115` |
| adapt 跨語言數值語意 | `proto7-2/packs/adapt/tests/test_adapt_unit.py:110`、`:134`、`:177`、`:183` |

inst 執行器在 proto7-2 是沿用前代；不能只搬本地兩個整合案例就認為協定完整。來源說明為 `proto7-2/README.md:117`，更完整測試在：

- `proto6/src/py/tests/test_inst_fields.py:24`
- `proto6/src/py/tests/test_inst_ref.py`
- `proto6/src/py/tests/test_inst_fmt.py`
- `proto6/src/py/tests/test_inst_reject.py`
- `proto6/src/py/tests/test_exec_opts.py:18`
- `proto6/src/py/tests/test_exec_status.py:54`

### 7.3 必須避免的假綠燈

1. **故障注入必須證明命中。**  
   astra-2 曾發現 healthy `/proc` 的 12 案中有 9 案零命中卻全綠，見 `proto7-2/notes/play/README.md:10`。C++ 需保留逐操作命中計數，不能只搬最後 assert。

2. **用真 SIGKILL 驗證交接。**  
   例外通常會執行解構與 finally，不能替代程序被殺。現行 oracle 在 `proto7-2/tests/_matrix.py:189`。

3. **先收程序，再刪暫存根。**  
   否則會先刪掉找孤兒所需的身分證據。來源：`proto7-2/README.md:48`、`tests/_proc.py`。

4. **fake loop 測試不是 C++ agent 端到端測試。**  
   `core/agent/tests/test_fake_loop.py:31` 啟動的是 Python fake loop；而 `core/agent/tests/fake_loop.cmake:1` 找不到 Python 時不登記該測試。

5. **現有 smoke 不等於預設 CTest 覆蓋。**  
   `core/llm/CMakeLists.txt:24` 登記 C++ 單元測試；`core/llm/tests/smoke_slots.sh` 的 fake HTTP／pi 情境仍需另行納入驗收。

6. **舊行為測試要與新契約分開。**  
   例如 `pending.turn + 1`、batch 永久累积、every agent 指令等測試，不能不經判斷就當新核心的正確性標準。

本次靜態統計六個指定核心共有 **153 處 `TEST_CASE` 宣告**；加上 `core/tool` 是 173。這不是執行數或通過數。proto7-2 README 記載目前 364 項；astra-6 歷史報告是 363 項×3。**本次沒有重跑其中任何一項。**

## 8. 做到一半尚未驗完，以及尚未進行的工作

### 8.1 已建立靜態反例，尚未動態驗證

以下工作因本次唯讀限制沒有執行，不應視為已實測：

- F01 的 `mkstemp`／fork 失敗與 CLI 成功回報。
- F02、F03 的 EACCES／EIO 注入及解除故障後恢復。
- F04 的自然 PID 重用、stop 接管交錯。
- F05 的 fake pi 殘留、槽提前釋放與再次啟動。
- F06 的 257 任務、fork→register 中斷、忽略 TERM。
- F07、F08、F11 的確定性交錯 barrier。
- F09 的逐提交點 SIGKILL 與重啟採用結果。
- F10 的手動 step→真 loop 整合測試。
- F12、F13 的完整 fixture 與檔案差異驗證。

### 8.2 尚未收斂為「已確認 bug」的議題

- **LLM 外部效果未知時的重試政策**：已看到失敗後訊息可能保留並重送的路徑，但尚未用 fake endpoint 驗證「後端已完成、回應中斷」的計費／副作用情境；也尚未確認產品希望採用的 retry 契約。
- **錯誤型別的 LLM 容量設定退回不限流**：已檢視設定解析路徑，但「缺設定」與「設定壞掉」應否採不同政策尚未完成契約判定，不列為確定違約。
- **pi 串流沒有完整終局事件卻 exit 0 的處理**：需要先界定空回覆、只有工具事件、截斷輸出的合法性，尚未完成反例驗證。
- **Linux／其他 POSIX 平台的程序管理策略**：確認存在差異，尚未選定支援範圍與替代實作。

### 8.3 使用者要求立即收尾時，尚未進行

- 沒有撰寫修補、patch、測試程式或新的重現腳本。
- 沒有執行 build、CTest、proto7-2 測試、長跑、壓力或效能測試。
- 沒有完成 `core/tool` 的獨立完整審查。
- 沒有實作 Python／C++ 共用測試 backend，也沒有實際驗證混合語言部署。
- 沒有產出工期估算、API 定稿或舊世界資料遷移工具；本文路線圖是實作順序與驗收要求。

**若 C++ 正式碼仍持續使用，建議先處理 F01、F02、F04、F05、F07、F08、F10；新核心移植則以「未知不破壞、同槽不雙開、交接可恢復、結果不預猜」四項作為第一批驗收門檻。**