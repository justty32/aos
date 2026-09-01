# 拷問總表：已裁決、仍開著、欠帳

← [ideas](README.md)｜[WORKFLOWS](../../WORKFLOWS.md)

**要重新拷問 aos 的人先讀這份。** 到目前為止已經打過十輪，涵蓋格式／原語／CPU 類比／
交接協定／前作對照／機器形狀。這份把散在各檔的**裁決**收成一張表，目的只有一個：
**不要重問已經拍板的東西，把火力放在仍開著的地方。**

## 十輪打了哪些面向

| 輪 | 面向 | 記在哪 |
|---|---|---|
| 1 | 格式與序列化的九個缺口 | [call-format/format-gaps](call-format/format-gaps.md) |
| 2 | fork/exec 這個原語夠不夠通用 | [call-format/universality](call-format/universality.md) |
| 3 | CPU 類比撐得住多少 | [call-format/cpu-analogy](call-format/cpu-analogy.md) |
| 4 | 交接協定的實作缺陷、世界／歷史／控制流 | [call-format/handoff-and-world](call-format/handoff-and-world.md) |
| 5 | 回饋路徑、失敗語意、協定完整性 | [call-format/feedback-and-failure](call-format/feedback-and-failure.md) |
| 6 | 跨 repo 前作對照（`simple_tools/docs`，早 aos 兩天） | [prior-work](prior-work.md) |
| 7 | 指令的地位、loop 的職權、資料夾與規範 | [machine-shape/](machine-shape/README.md) |
| 8 | 裁決的欠帳 ＋ `run_loop.cpp` 實測 | [machine-shape/debts](machine-shape/debts.md)、[loop](machine-shape/loop.md) |
| 9 | 沒有回合內資料流、四階段管線、彙整崩潰窗口 | 同上 ＋ [feedback-and-failure](call-format/feedback-and-failure.md) |
| 10 | （Fable）「地位」的承載物：類比可證偽性、loop 身份判準、ownership、名冊封閉、normative | [machine-shape/](machine-shape/README.md) 三檔的第十輪（§22–30） |

不該被改掉的優點收在 [call-format/keep](call-format/keep.md)——**打之前先讀那份**，免得
把對的東西打掉。

## A. 已裁決（不必再問）

| 主題 | 裁決 |
|---|---|
| **格式的定位** | fork/exec 只是呼叫**機制**、不是呼叫**約定**；它不能成為通用契約，只作為「fork/exec as CPU instruction」的**基石** |
| **`timeout_ms`** | 移出最內圈，改由 loop 層管 |
| **exit status** | 分不開傳輸失敗與應用失敗，**之後會改** |
| **daemon** | 這東西天生會變 daemon，就這樣；LLM CPU 之後是另一個 daemon |
| **抽象 CPU 的回合** | **投遞式**，不在本回合同步跑完——工作投遞到外部資料夾，好了寫回來，「類似 CPU 與 GPU 的交流」。結果落在**未來某個回合** |
| **呼叫粒度** | 本來就這樣設計：細粒度在程式內，這裡是更高層次的 CPU 指令 |
| **權限／安全** | 交給上層呼叫 `aos exec` 的那一方，核心不管 |
| **高階形式** | 確實缺，解法在**外層另做更通用的呼叫契約**（怎麼做**還沒想好**） |
| **跨機器** | 沒差，之後用 plan 9 |
| **CPU 類比的三樣無解** | 原子性、封閉 ISA、確定性——認了，這終究不是能完全類比 CPU 的 |
| **控制流** | 就是 loop；所以 `aos core` ＝ 整套 CPU 類比，loop 在 core 裡不是外掛 |
| **世界沒有圍牆** | 沒關係，快照／回滾／複製都用 **git** |
| **回合歷史** | 是實作上要加的新東西，**加在 loop** |
| **PC 不自己前進** | **這就是要的**——控制流在投遞者手上 |
| **嚴解析、鬆執行** | **刻意的**：序列化要嚴格，`inst_t` 的實際執行故意弄鬆 |
| **delta time 從 loop 走回來** | 之後在 loop 處理 |
| **停機** | 之後在 loop 內再說 |
| **第 4～6 輪的實作缺陷** | 實作時自然會遇到，要嘛放外圈、要嘛交給使用者自行 handle 風險 |
| **前作那批（`simple_tools/docs`）** | 有些可以參考，但**很多機制可以在 loop 或更外層處理** |
| **`core/inst` 改名** | 改成 **`core/exec`**（2026-08-30）——小專案照**動詞**命名。**已實作**（2026-09-01 複核）：`core/exec/` 在、`core/inst/` 沒了，序列化另拆成 `core/wire`。`aos/inst.hpp` 那個懸念**被實作繞過**——標頭裂成 `aos/exec.hpp`（執行，`exec::Spawn`）與 `aos/wire.hpp`（格式，`wire::Inst`／`Outcome`／`State`），而當初說要留的名詞側 `inst_t`／`.aos/inst.json`／`aos_instruction_*` C ABI **三樣都不存在了**。`README.md`／`docs/build.md` 還寫 `aos/inst.hpp`，是文件殘留 → [core-layering](core-layering.md) |
| **2000ms 那個常數** | 不是使用者設計的，是 AI 自己加的，別管 |

## B. 仍開著（值得打）

1. **「批」沒有名字、沒有 header** — 真正的指令是批，但被命名的是 `inst_t`。ISA 版本、
   指令來源、批次彙總狀態、去重 id 全都沒地方放。**第 1／2／6 條是同一個決定。**
   → [machine-shape/instruction](machine-shape/instruction.md)
2. **loop 沒有可分支的狀態** — 「loop 是控制流」目前是志向；`result` 只有 `== 3` 被用過。
3. ~~**一個回合內沒有資料流**~~（實測）— 整批先 resolve 完才執行，`$ref` 引不到同批前一筆的
   產物。乾淨的語意，原本**沒寫在任何地方**。
   > **2026-09-01 複核**：新的 `core/loop`／`core/wire` 裡**連 `$ref` 都不存在了**
   > （`wire::Inst` 只剩 `id`／`argv`／`env`／`cwd`／`stdin`／`timeout_ms`），所以這條約束
   > 是無條件的。**已寫進規範**（2026-09-01）：
   > [dispatch/proto/PROTOCOL.md §5](../dispatch/proto/PROTOCOL.md#5-一回合)。
4. **四階段管線沒被命名** — fetch(claim)／decode(resolve)／execute／writeback(exit)。
   照這條線 **decode 目前卡在錯的一層**，而 **writeback 只有單筆、沒有整批**。
5. **外層契約會反噬基石** — 一旦外層有型別與回傳值，inst 可能退化成啟動器。使用者**還沒
   想好**。
6. **跨資料夾排程屬於 `exec_loop` 還是更外層** — 決定 `exec_loop` 的介面是「跑這個資料
   夾」還是「跑這一組」。
7. **`.aos` 版面需要第二個軸** — events／status 不是 `inst.json` 的「狀況」，塞不進
   `<名字>.<副檔名>.<狀況>`。
8. ~~**沒有 `deliver`**~~ — **已閉合（2026-09-01 驗證）**：`core/loop/src/deliver.cpp` ＋
   `deliver_cli.cpp`，`aos deliver` 註冊在子命令表（`core/loop/CMakeLists.txt:30`）、
   `aos --help` 印得出來。兩種用法：`aos deliver [folder] <inst.json>`（id 取檔名 stem）
   與 `aos deliver [folder] -- <argv...>`（id 由 `make_delivery_id()` 產）。
   > 原條目那句「都沒進 C ABI」也一併過期——**C ABI 整個不存在了**，`aggregate` 現在是
   > `core/loop` 的 C++ 函式。
   > **仍缺**：[T5 那份規格](../experiments/t5-agent-loop/subcommand-specs.md)五支裡的
   > `aos recover` 與 `aos status --json`（`aos agent step`／`emit-context` 由
   > `core/agent` 另解）。`deliver` 撞名直接覆蓋這個新缺陷見 D 區。
9. **沒有控制介面** — **部分閉合（2026-09-01 驗證）**。
   **有了**：`.aos/run.pid`（只有 `--step 0` 的無限 loop 寫，退出即刪）、`aos stop`
   （讀 pid → SIGTERM → 最多等 5 秒 → SIGKILL → 刪 pid 檔）、`.aos/run.lock` 的
   `flock(LOCK_EX|LOCK_NB)`（同一個世界只准一條 loop）、`--daemon` ＋ `.aos/run.log`、
   機器可讀的 `.aos/state.json`（`turn`／`phase`／`running[]`／`agents`）。
   **還缺**：**沒有 `aos status`**（`aos state` 印的是 agent 的 `status.json`，不是 loop 的
   `state.json`）、沒有 `aos recover`、**不能暫停**（只能停掉再開）。這兩支的規格仍在
   T5 那份裡沒做。
10. **格式沒有版本，版面也沒有** — 兩件不同的事，兩個都缺。
11. **規範有三份真相且在漂**（規格／實作文件／手寫 parser），第四份是 LLM 的理解。
12. **第十輪整組（§22–30，未裁；使用者：邊實作邊想）** — 五條是**待裁判準**而非缺陷：
    類比的可證偽版本（凍結的矽——與 `$ref` 取指令相撞）；**loop 只收無法成為 inst 的
    東西**（其餘是 OS-as-inst，一次回答 B6 與中斷欠帳）；控制面走投遞協定 or ad-hoc；
    程式名冊封閉判準（exec/loop/deliver/status/recover/check）；規範要一份 normative
    SPEC。
    > **其中第二條已試跑（2026-08-30；使用者當日裁定「先不裁，邊實作邊想」，故結果不具約束力）**：拿「loop 只收無法成為 inst 的東西」
    > 去過 [top-down-cli](top-down-cli.md) 的八條指令，結果在
    > [core-layering](core-layering.md) 末節——判準只對**回合內**適用
    > （**core 名冊 ≠ 指令名冊**），過完之後 core 的新增需求**只剩上面第 2 條的
    > 「分支」**，且「匯聚」被判進 core。

    另四條是缺口：opcode 懸空（header 加 manifest 欄可補）、核心方程要宣告
    footprint（**git 第三筆帳：拍的 ≠ 改的**）、**PC 不存在**（回合編號無表示，是歷史／
    記憶體模型／status／去重的共同前提）、版面要 ownership table。
    > **2026-09-01 使用者口述的兩個模型各壓上其中兩條**（[game-process-model](game-process-model.md)）：
    > **GOAP 把 footprint 從「值得做」升成「必要條件」**（規劃依賴每個 action 聲明
    > precondition／effect，`inst` 什麼都不聲明）；**L1/L2 cache 類比給 ownership table
    > 一條分類判準**（刪掉它世界語意變不變＝架構狀態 vs 微架構狀態），並指出**邊界會隨
    > 設計落地移動**（`turn` 在 PC 落地那天會從 cache 升格），ownership table 得記這件事。
    > 另：[theses-review §二](theses-review.md) 認為**給批名字與 header 的槓桿比本表原記的
    > 更高**——它同時是 CPU 讀法（去重要回合編號）與 REPL 讀法（replay 要輸入歷程）的共同
    > 地基（觀察，非裁決）。
13. **`path` 是 symbol、handle 才是 capability** — 這條**推不到上層**：namespace 必須在
    `fork` 之後、`execve` 之前建，只有 exec 層碰得到。與「安全交給別人」的裁決有出入。

## C. 欠帳（已下裁決相乘產生的，不是待辦）

| 欠帳 | 來自哪個裁決 |
|---|---|
| **兩顆 CPU 共寫一份記憶體，沒有記憶體模型**（沒有 barrier／happens-before／去重） | GPU 模型 |
| **沒有中斷線** — 非同步結果只能靠每回合塞一筆輪詢指令 | GPU 模型 |
| **git 撞上 `.aos/` 的暫態** — `.runi` 沒了，但暫態變多了：`run.pid`／`run.lock`／`run.log`／`state.json`／`turn`／`batch/<turn>/` 全在 `.aos/` 裡，回滾含它們的 commit 一樣會讓世界對不上；`.gitignore` 政策是規範的一部分，還沒寫。**判準 2026-09-01 有了**（[game-process-model §十](game-process-model.md)）：cache 永不入 commit——「回滾含 `run.pid` 的 commit 死鎖」＝把微架構狀態當架構狀態存了檔 | 用 git 做快照 |

→ [machine-shape/debts](machine-shape/debts.md)

## D. 已驗證的實作缺陷（跟設計問題分開）

可查版本在 [common/gotchas](../common/gotchas.md)。**2026-09-01 逐條用程式碼複核過**：
下面這批原本都指向 `core/inst/src/`，那個目錄已經不存在，所以分成兩段——舊條目怎麼結，
新現場（`core/loop/src/`）實際上長什麼樣。**缺陷不一定是消失，很多只是搬家。**

### D1. 舊現場（`core/inst/src/`）——條目作廢

| 舊條目 | 結案 |
|---|---|
| `.runi` 不是鎖 → 同回合跑兩次 | **作廢**：沒有 `.runi` 了。取件改成 `aggregate()` 把 `inbox/<id>.json` **先 `rename` 進** `batch/<turn>/insts/` 再讀（`aggregate.cpp:93`），互斥由 `.aos/run.lock` 的 `flock` 保證（`run.cpp:150`）——**那才是真的鎖** |
| 投遞檔名用 pid 不唯一 | **已修**：`make_delivery_id()` 產 `d-<epoch_ms>-<pid>-<seq>`（`deliver.cpp:27`）。但**只有 `aos deliver -- <argv>` 走它**，給檔案那條用檔名 stem，見 D2 |
| 彙整崩潰窗口 → 同一批跑兩次 | **翻面**：claim 移到執行之前，重複執行沒了，換成**漏跑**（`insts/` 已搬走而 `out/` 沒寫、`turn` 沒加就崩，下次不補）。由「至多兩次」變「至多一次」 |
| `--loop 0` ＝忙碌輪詢 | **旗標沒了**：現在是 `--step N`（0＝持續）＋ `--interval MS`（前景 100、`--daemon` 1000）。`--interval 0` 仍會忙碌輪詢，但不再是文件示範的用法 |
| 失敗算「有做事」、`did_work` 設在執行之前 | **作廢**：`did_work` 不存在了。改成每回合固定睡 `interval`，只有「這回合沒有 inbox 投遞」才換 `wait_for_delivery()`、一有新投遞就提早醒（`run.cpp:447`）。**失敗不再影響節奏** |
| `.bad` 是第三種狀況、沒人清 | **作廢**：`.bad` 不存在了。解析失敗的檔留在 `batch/<turn>/insts/` 原名、跳過、`out/` 無對應結果，只在 stderr 留一行。殘留物換了位置，見 D2 末條 |

### D2. 新現場（`core/loop/src/`）——實況

- **還是沒有 `fsync`——這條是搬家不是消失**：唯一的寫檔入口 `fs::write_atomic()`
  （`fs.cpp:42`）是 `ofstream` → `close` → `std::rename`，**檔案沒 `fsync`、目錄也沒**。
  `state.json`、`turn`、`out/<id>.json`、投遞、`every/.last/` 全走這條，`run.pid` 自己抄
  了一份一樣的（`run.cpp:40`）。斷電後可能留下已改名、內容零長度的 `state.json` 或
  `turn`。正確順序仍是 寫 → `fsync(fd)` → `rename` → `fsync(dir_fd)`。`core/tick` 同病。
- **`aos deliver <file.json>` 撞名直接覆蓋、不查重**（2026-09-01 實測）：id 取檔名 stem
  （`deliver_cli.cpp:49`），`deliver()` 只是 `write_atomic` 到 `inbox/<id>.json`
  （`deliver.cpp:16`）。連投兩份同名的，第一份**還沒被跑掉就消失**，exit 0、無警告。
  → [gotchas](../common/gotchas.md)
- **loop 開始看回傳值了，但仍不分支**：`collect_failures()` 把 exit 0 與 exit 75
  （`waiting-llm` 回壓）當成功、其餘記成 `InstFailure` 印到 stderr，`aos run` 有失敗就回
  1（`turn.cpp:83`）。**觀測有了，控制流沒有**——不重試、不停、不改節奏，所以 B2 原封
  不動還開著。原本「只用 `== 3`」那條隨 `aos exec` 一起作廢（**現在沒有 `aos exec` 子
  命令**，`core/exec` 只是函式庫）。
- **`.aos/batch/` 只長不清**：每回合一個 `batch/<turn>/`，程式碼裡沒有任何清理路徑。

## 最高槓桿的三件事

1. **給「批」名字與 header** — 一次解決 B1／B2／B4 與 C 的去重問題。
2. ~~**補 `deliver`**（B8）~~ — **已完工**（2026-09-01 驗證；`aos deliver`／`aos stop` 都
   上了）。**接手的是 B9 剩的那半**：`aos status --json`／`aos recover`／暫停。
3. ~~**把「一個回合內沒有資料流」寫進規範**（B3）~~ — **已完工**（2026-09-01）：寫進
   [PROTOCOL §5](../dispatch/proto/PROTOCOL.md#5-一回合)。

## 拷問之外還開著的東西

這份只收拷問產生的裁決。**其他 open 狀態不在這裡**：手上的 in-flight 看
[SESSION-LOG](../../SESSION-LOG.md)（含 T5 實測沒全過的驗收、規格與實作三處對不上），
等使用者親自做的看 [WAIT_USER](../../WAIT_USER.md)，研討會累積的問題看
[workshop/OPEN-QUESTIONS](../workshop/OPEN-QUESTIONS.md)。

**拷問已停打（十輪）。** 停打時剩的四項存貨（序列化、外層契約 B5、LLM CPU 形狀、
匯聚 lib-vs-inst）與實作排程都在 **[roadmap](../roadmap.md)**——邊實作邊裁，裁了記回這裡。
