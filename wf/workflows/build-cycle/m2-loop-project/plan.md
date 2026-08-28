# M2 exec_loop 落地分層 — 實作 plan

← [spec](spec.md)｜[build-cycle](../README.md)｜[SPEC](../../../../docs/SPEC.md)｜[code map](../../common/code-map.md)

**閘門 ①／② 由使用者概括授權**（2026-08-28 `/goal`，見 spec 開頭）。
本 plan 只講「怎麼」；「什麼」以 [spec.md](spec.md) 為準。spec 的「明確不做」一律出範圍。

**驗證一律**：從 repo 根目錄跑
`cmake --build --preset default && ctest --preset default`。
搬遷期間**每一步都要另外驗合併版**：`cmake --preset merged && cmake --build --preset merged
&& ctest --test-dir build/merged`（`merged` **沒有** testPreset，只能用 `--test-dir`）。
手動煙霧用 `./build/bin/aos`。

> 本 plan 的所有檔名、函式名、行數都對照過現況程式碼；CMake 與合併版的部分是在
> repo 副本上**實際建置並跑過 ctest** 驗證的，不是紙上推演。

---

## 零、總覽與相依圖

```text
S0 裁決清點（主線；第一節 15 項）
  └─→ S1 SPEC 條款起草（主線；新開 G 區，帶 (planned, M2)）
        │
        ├─→ S2 exec 拆非阻塞入口（core/inst 內純重構，語意零變化）
        │     └────────────────────────────┐
        ├─→ S3 core/loop 骨架（CMake＋空 lib＋空測試 target，build/merged 都綠）
        │     └─→ S4 純搬遷（git mv 回合編排＋exec 子命令＋測試，內容零改動）
        │           ├─→ S5 四階段管線重構（decode 歸位＋RoundOutcome）
        │           │     ├─→ S6 loop 接管計時（吃 S2 的入口）←────────┘
        │           │     │     └─→ S7 writeback：算 BatchResult＋寫 header result
        │           │     │           └─→ S8 節流與退避＋庫層失敗計數停機
        │           │     └─→ S9 control inbox（stop）  ←可與 S6–S8 平行
        │           └───────────────────────────────────┐
        └─→ S10 文件＋code map＋gotchas／verdicts 同步 ←┘
              └─→ S11 收尾：摘 planned 標記、驗收總跑、roadmap／SESSION-LOG、封存
```

- **立法先行**：S1 先入法（未實作的條款帶 `(planned, M2)`），程式照條款寫；S11 兌現後摘標。
  任何一步中斷，SPEC 與現實的落差都有標記可查（SPEC「三向標記」規則）。
- **搬遷的關鍵手法是「先純搬、後重構」**：S4 是 `git mv` ＋ CMake 改線，**檔案內容零改動**
  （只改 include 路徑與 namespace）。這樣 S4 的 diff 可以一眼看出「沒有行為變化」，
  真正的重構（S5–S8）各自是獨立的、小的、可 revert 的 commit。
  （**這與調度者原提示的「先重構再搬」相反，理由見裁-4，需主線拍板。**）
- **可平行**：S2 與 S3／S4 互不相干（一個動 `core/inst/src/exec.cpp`，一個動 CLI 層與
  CMake）；S9 與 S6–S8 互不相干（不同檔）。
- **每步一個檢查點**：每步結束 ctest 全綠（default ＋ merged）＋該步驗證項通過才進下一步；
  每步照 [feature-dev](../../feature-dev/README.md) 各自 commit（含 code map 同步）。

### 本 plan 不碰的（硬性）

- spec 的「明確不做」全部：回合歷史／注入機制、`status`／`recover`／`check`、doorbell
  實作、跨資料夾排程、`timeout_ms` 欄位移除、`step`／`hold`、`deliver --control`、
  新子命令、§29；以及 **`.runi` 不是鎖**（verdicts D 表唯一未修的實作缺陷）、
  **退出碼不反映子行程成敗**（§D-9）、**並行度上限**（§C-7 已裁「沒有任何上限」）、
  **`core/inst` 改名**、**`<aos/loop.h>` C ABI**、**`.aos` 版面第二個軸**、
  **`aos init`／`aos deliver` 搬家**。
- [keep.md](../../ideas/call-format/keep.md) 保護項：argv 陣列、未知 key 拒絕、無上限、
  三 stream 檔案化——**格式層（`core/inst/src/format*.cpp`、`resolve.cpp`、`inst.cpp`）
  本階段零改動**（唯一例外是 S10 改 `core/inst/docs/format.md` 那段自打嘴巴的文字，
  改的是**說明文件**、不是 schema）。
- `core/inst/src/handoff*.cpp` 的交接邏輯：**只新增 header `result` 的寫入路徑**
  （S7），彙整／取件／釋放／去重／發布順序（§D-4／§D-5／§D-6）一行不改。
- `handoff.cpp` 已 **333 行**、超過 conventions 的 300 行門檻——那是 M1 留下的既有欠帳，
  **M2 不順手動它**（動了就把「搬遷沒有行為變化」這個保證弄髒）。

---

## 一、需主線裁決的清單（S0 一次裁完，動工前）

plan 依 spec 的硬性約束不自行決定新欄位／新命名／新輸出面。以下各附建議案；
「進哪條」指它最後要落在 SPEC 的哪一條（條號提案見第二節）。

| # | 問題 | 建議案 | 替代案 | 為什麼建議 | 進哪條 |
|---|---|---|---|---|---|
| 裁-1 | **超時砍行程的機制**（spec 遺留第一題） | **A：`core/inst` 的 exec 層提供分離入口** `spawn`／`poll_child`／`reap_child`／`signal_child_group`，`execute()` 保留簽名但**改為阻塞至子行程自行結束、不再讀 `timeout_ms`**；計時迴圈與 SIGTERM→寬限→SIGKILL 的升級鏈整組搬到 `core/loop/src/deadline.cpp` | **B**：exec 只回 pid，loop 自己 `waitpid`／`kill`。**C**：`execute_bounded(inst, limit_ms, result)`，上限由呼叫端給，砍行程仍在 exec 內 | B 保不住已釋出的 `aos_instruction_execute`——要它繼續能用，`core/inst` 就得留一份完整的 wait＋狀態對應＋`exit` 檔 fsync，`core/loop` 再打第二份，**同一套邏輯兩份實作**；而且 `inst.hpp:195` 與 code map 白紙黑字寫「exec 是唯一碰 fork／exec／waitpid 的層」，B 讓那句話作廢。C 的公開面最小、diff 最小，但「計時與砍行程由回合層執行」（裁決 5）就只兌現了一半，驗收條件 4 的 grep 也擋不住回歸。**A 是唯一同時滿足裁決 5 與分層鐵律的** | §G-6 |
| 裁-2 | 裁-1 的四個新入口**要不要同步開 C ABI**（`aos_exec_spawn` 等進 `<aos/inst.h>`） | **M2 不開**：只出 C++ 公開 API。C ABI 列舉與函式一經釋出就凍結（conventions），而現在**一個 C 消費者都沒有** | 同步開，`test_capi.c` 補案 | 拿永久凍結換一個沒有使用者的介面，不划算。要 in-process 用 C++ 就夠；要跨語言就 `fork`/`exec` 一次 `aos exec`，退出碼就是它的介面 | —（記 ideas） |
| 裁-3 | `execute()`／`aos_instruction_execute` **不再套用 `timeout_ms`** ＝ 已釋出 API 的**靜默語意變更**，接受嗎 | **接受**，並且 **MUST** 同時做三件事：`test_capi.c` 補一案釘住新語意（現有案子抓不到——它設了 `timeout_ms=1000` 但指令是 `exit 7`，本來就不逾時）、`inst.h` 與 `core/inst/docs/capi.md`／`cxxapi.md`／`exec.md` 白紙黑字寫、`aos_exec_result.timed_out` 欄位**保留不刪**（ABI 凍結）改由 loop 填 | 讓 `execute()` 繼續讀 `timeout_ms`（＝退回裁-1 的 C） | 裁決 5 已定「exec 最內圈不再自帶計時」。簽名相容掩蓋語意不相容是這次搬遷最危險的一點，**只能靠測試＋文件擋**，不能靠不做 | §G-6、§C-3 |
| 裁-4 | **搬遷順序**：先在 inst 內重構四階段再搬目錄，還是先純搬再重構 | **先純搬（S4＝`git mv`＋CMake，內容零改動）、後重構（S5–S8）** | 照調度者原提示：先重構、後搬 | 要重構的檔（`run_exec.cpp` 293／`run_batch.cpp` 215／`run_loop.cpp` 84）**整批都要搬**，先重構等於在舊位址做一次、審一次，搬完再審一次。先純搬的話 S4 的 diff 是「路徑變了、內容沒變」，**一眼可驗沒有行為變化**，而重構的 diff 不再混著搬家雜訊 | — |
| 裁-5 | header `result` **四個值的確切字串** | **`"ok"`（全成功）／`"partial"`（部分失敗）／`"failed"`（全失敗）／`"machine_failed"`（庫層失敗）**。加上彙整層寫的 `null`（尚未 writeback），值域共五態 | `"ok"/"partial"/"failed"/"aborted"`（四個都是單字、無底線）；或 `"all_ok"/"partial"/"all_failed"/"library_failed"` | 全小寫、與 `origin` 的 `"aggregated"`／`"direct"` 同風格；`"ok"` 是最常見值、越短越好。`machine_failed` 直接回收 loop.md 第 15 條的原話（「是**這台機器本身**出問題」），可追溯到裁決來源——這個專案很吃這個。**主線二選一即可，別讓實作隊自己挑** | §G-2 |
| 裁-6 | **逾時的 slot 算成功還是失敗** | **算成功**（＝一次已完成的執行）。`ExecState::Ok` 且 `timed_out=true`，不影響 `result`；**不新增第五個值** | 逾時單獨一格 | `docs/exec.md` 與 §D-9 既有語意就是「逾時＝已完成的執行、CLI 仍算成功」，改它＝翻既裁。代價（一批全逾時＝有進展＝不退避）可接受：每輪本來就耗掉 `timeout_ms`，不是忙碌輪詢 | §G-2 |
| 裁-7 | **空批次**（0 筆，§C-2 合法）的 `result` | `"ok"` ＝ 有進展 | `"failed"`／不寫 | 空批次被消化掉了、`.runi` 釋放了、turn 前進了——那就是進展。判準是「批次有沒有被推進」，不是「有沒有 fork 出東西」 | §G-2 |
| 裁-8 | **退避參數**：基數／倍率／上限／重置／空回合 | **基數 ＝ `--loop <ms>` 的那個間隔本身**（`--loop 0` 走既有的下限化 1 ms）；**倍率 2**；**上限 `max(interval, 60000)` ms**；**有進展**（`result` ∈ {`ok`,`partial`}）→ **重置**；**無進展**（`failed`／`machine_failed`／回合層失敗）→ 遞增；**空回合（沒取到批）→ 計數不變、睡基數**。退避**乘在既有 loop 間隔上**，不是另一條獨立的睡眠時間 | 固定基數（如 100 ms）；上限固定 60 s；空回合也算無進展 | 乘在既有間隔上＝`--loop` 的語意不變（使用者調的還是同一個旋鈕）；上限取 `max(...)` 才不會讓 `--loop 300000` 的人被 60 s **縮短**間隔。**空回合那條是關鍵**：空閒不是故障，若把它算無進展，一個閒置世界會退到 60 s，新投遞要等一分鐘才被看到——直接打壞可用性 | §G-3 |
| 裁-8b | 要不要另設一個**最小退避基準** `kFloor`（如 50 ms），讓 `--loop 0` 在故障時真的不輪詢 | **不設**。裁決 3 寫的是「照實立法」，現行 `--loop 0` ＝ warn ＋ 1 ms；加 `kFloor` 是**改行為**不是立法 | 設 50 ms | 1 ms 每秒 1000 次 `readdir` 只保證「不佔滿一顆核心」、不保證「不輪詢」——**但那正是裁決 3 選的那條法**。而且 verdicts A 表對「2000 ms 那個常數」已表態：憑空生出的常數別再長。**若主線覺得裁決 3 的「照實立法」四個字沒打算選這麼弱的版本，就改設 `kFloor`——這句話需要主線確認是不是有意的** | §G-4 |
| 裁-9 | **庫層失敗連續 N 次停機**的 N ＋ **退出碼** | **N ＝ 10**；退出碼 **4**（SPEC §D-9 表加一行「loop 因連續庫層失敗停機」，**只在 `--loop` 模式出現**，單次 `aos exec` 一次庫層失敗仍是 1）。只數 `machine_failed`／回合層失敗，**不數 `failed`**（一批指令永遠跑不成是使用者的問題，停機會打壞正當用法）。停機前 MUST 在 stderr 印一行（連續幾次＋最後一次的 errno） | **N ＝ 5**（≈31×interval 就停，對瞬時資源壓力較不寬容）；沿用退出碼 1 | N=10 搭配倍增退避 ≈ 累計數分鐘（`--loop 1000` 下約 4 分鐘）才停機，足夠讓 fd 耗盡／磁碟滿之類的瞬時壓力自行恢復；碼 4 是 0/1/2/3 之後第一個沒被佔用的。**代價要認**：`--loop 0` 下 10 次只花約 1 秒——但那是使用者自己要求的最高侵略性，且 stderr 會說清楚為什麼 | §G-5、§D-9 |
| 裁-9b | **`run_exec_once` 的回傳值分層**（裁決 4 的隱形前置，spec 調度者須知第 7 點） | **必做，且是 S5 的一部分**：把今天混在 `int 1` 裡的七種來路分成兩類——**回合層失敗**（進不了 folder／`.aos` 壞／版本不認得／aggregate 失敗／release 失敗／turn 遞增失敗／fork 失敗／`ExitWriteFailed` 等 `ExecState` 非 Ok）＝`machine_failed`，**批次內容失敗**（整批 JSON 解析失敗、指示詞求值失敗、子行程跑壞）＝`failed`／`partial` | 不分層，全算庫層失敗 | 不分層的話「一批壞 JSON」會被算成庫層失敗，連續 N 圈就把世界停機報錯——那是誤判，而且壞批已經被消化掉了、下一圈根本不會再出現。`docs/usage.md` 現行退出碼表把「指令檔語法或 schema 有問題」歸 1，正是同一個混淆的來源 | §G-2 |
| 裁-10 | **control inbox 的目錄名** | **`.aos/control.tempd/`** | `.aos/control/`、`.aos/ctl.d/`、`.aos/events/` | §B-1 的副檔名表已有 `.tempd`＝「投遞匣資料夾」，控制記錄**就是**投遞。用它 ⇒ **零新副檔名、零新狀況、零新軸**（避開 verdicts B7），且與 `inst.tempd/` 對稱、一眼看得出協定同構 | §B-2、§G-7 |
| 裁-11 | **control 記錄的格式與消化方式** | 內容 `{"op":"stop"}`（**恰好一個 key**，未知 key 拒絕）；檔名沿用投遞規則 `<pid>-<seq>.json`，先 `.temp` 後 rename；loop 在**每一圈的最前面**（claim 之前、也就是睡醒之後）掃一次；**處理完 `unlink`**（與彙整「發布成功後才刪投遞」同構）；格式壞掉或 `op` 不認得 → 就地改名加 **`.bad`** ＋ warning ＋繼續（§D-4／§D-8 同款，**不新增狀況字**） | rename 成 `.done`；就地留著加旗標 | `.done` 是 §B-1 封閉狀況清單外的第四個狀況字＝修憲；而「消化完就刪」已經有先例（投遞）。`.bad` 由人或 `aos recover` 清（§D-8）也已經有法源 | §G-7 |
| 裁-12 | control 記錄要不要 `version`／`id`／`ts` 欄位 | **v1 都不要**：擴充點是 `op` 本身（不認得的 `op` → `.bad`，舊 aos 遇到新動詞硬失敗而不是猜） | 加 `version` 比照 header | 與 §C-5「未知 key 拒絕、舊執行檔遇新格式硬失敗是刻意的」同一條哲學；少一個欄位就少一份要維護的版本 | §G-7 |
| 裁-13 | **子命令掛載**：`aos exec` 的進入點從哪個 lib 出 | **(a) `exec` 整包搬 `core/loop`**：`aos_add_subcommand(NAME exec ENTRY aos_exec_cli_main LIBRARY aos_loop_cli …)` 移到 `core/loop/CMakeLists.txt`；`init`／`deliver` 留 `core/inst` | (b) 留 inst、`--loop` 時呼叫 loop；(c) 解析留 `app/` 依旗標分派 | (b) **CMake 直接 configure 失敗**（SHARED 之間不允許相依環，實測錯誤訊息在風險 2），而且切錯線——不只 `--loop`，連單回合的 claim／release／turn 都屬 loop。(c) 要在 `app/src/main.cpp` 這個零業務邏輯的純分派器裡開例外通道，還得繞過 `aos_add_subcommand` 的登記機制 | §A-7 |
| 裁-14 | `core/loop` 對 `core/inst` 用 **`PUBLIC_DEPS` 還是 `PRIVATE_DEPS`** | **`PUBLIC_DEPS aos::inst`**（**必須**） | `PRIVATE_DEPS` | 實測：根 `CMakeLists.txt` 的合併版**只濾 `aos_public_deps` 裡的 `aos::<小專案>`，不濾 private**，寫成 PRIVATE 會讓 `libaos.so` 長出 `NEEDED libaos_inst.so.0`——單檔部署破功、同一份符號兩顆 DSO。這條路徑在今天的 repo 從沒被走過（`core/loop` 是第一個跨小專案相依） | —（進 code-map/build.md） |
| 裁-15 | loop 的測試怎麼建一個世界（`run_init_world` 是 CLI-internal，loop 不能 include inst 的 `src/`） | **loop 測試自己鋪 `.aos/`**（`core/loop/tests/test_loop_support.hpp` 裡 mkdir ＋ 寫 `version`／`turn` ＋ 建 `inst.tempd/`，四行） | 把 `init_world` 升成 `aos::init_world()` 公開 API | 為了測試而擴永久公開 API 不划算；版面已由 §B-2 凍結，測試 helper 照抄四行的維護成本近零。**代價要記**：版面若變，兩處要改——寫進 code map 的 loop 分冊 | —（記 ideas） |

**擋關係**：裁-1／裁-2／裁-3 擋 S2 與 S6；裁-4 擋整個步驟切分；裁-5／裁-6／裁-7 擋 S7；
裁-8／裁-9 擋 S8；裁-10／裁-11／裁-12 擋 S9；裁-13／裁-14／裁-15 擋 S3 與 S4。
（依 build-cycle 常備規則 3：沒裁完也可動工，碰到那行就停下來裁。）

---

## 二、SPEC 條款起草清單（**保留給主線**，S1）

plan 不起草條文，只列「需要哪些條款、規定什麼、來源在哪」。位階（MUST／SHOULD）與措辭
由主線定，每條附來源；未實作前帶 `(planned, M2)`，S11 摘標。

### 裁-0（結構性，主線先拍）：M2 的條款放哪一區

現行六區沒有一區是 loop 的家。**建議切成兩處**：

- **A 區（機器模型）＋2 條**：loop 的**職權判準**與**控制窗口是週期的一個相位**——
  這兩件事說的是「這台機器由什麼構成」，與 §A-6「凍結的矽」同性質，A 區是它們的家。
- **新開 G 區「回合層（loop）」**：四階段、writeback 值域、退避、睡眠、停機、計時
  所有權、control inbox 協定、訊號收尾——**執行語意**，塞進 A（模型）或 D（交接協定）
  都會讓那兩區失焦（「指數退避」寫在「交接協定」底下是分類錯誤）。
  條款編號永不重用、新字母是免費的（SPEC 開頭已寫）。
- **B／C／D 只做點狀修補**（下表最後四列）。

**替代案**：全部塞進 A 與 D（`§A-7~9` ＋ `§D-10~13`），不開新區。優點是區數不變；
缺點如上。**主線一句話裁。** 下表按建議案編號。

### A 區 機器模型（接在 §A-6 之後）

| 條款 | 這條要規定什麼（措辭留給主線） | 來源 |
|---|---|---|
| **§A-7 loop 的職權判準** | 一件事歸 loop 的判準＝**它必須在沒有任何 inst 可跑的時刻運作**；**窮舉表**＝claim/fetch、decode 調度、execute 調度、writeback、睡眠／退避、控制窗口、崩潰偵測；其餘一律做成系統 inst，MUST NOT 寫成 loop 的 C++。**建議寫成「判準＋窮舉表，衝突時表優先」**（spec 調度者須知第 6 點：判準推不出它自己的列舉，別讓判準單獨承重）。三條推論：跨資料夾排程屬 OS 層、`exec_loop` 的介面 MUST 是「跑**這個**資料夾」（B6 裁掉）／doorbell 歸 loop（只裁歸屬，實作留 M4）／回合歷史歸系統 inst。代價認列：需要彙整層注入策略，M3 之後 | instruction §25（第十輪）；spec 裁決 1；[loop.md](../../ideas/machine-shape/loop.md) 第 8／25 條；[core-layering](../../ideas/core-layering.md) |
| **§A-8 控制窗口是週期的一個相位** | 回合週期 MUST 有一個明確的**控制窗口**相位（writeback 之後、下一次 claim 之前），使外部介入不必靠手快；「使用者在回合間介入」因此是 ISA 級規範、不是外掛。窗口的檔案協定在 §G-7。**條文別把理由寫成「控制面本質上做不成 inst」**——掃 control inbox 其實可以是一筆 inst，它做不成的真正原因是「inst 沒有回報通道」，而裁決 4 正在造那個通道；寫成「控制面 MUST 不依賴任何 inst 能跑」比較站得住 | loop.md 第 26 條；spec 裁決 2 |

### G 區 回合層（loop）——**新開**

| 條款 | 這條要規定什麼 | 來源 |
|---|---|---|
| **§G-1 四階段管線** | 一回合 MUST 是 **fetch（彙整＋取件）→ decode（解析＋指示詞求值）→ execute → writeback（彙總狀態＋釋放＋遞增 turn）**；**指示詞求值屬 decode、不屬 execute**（B4 歸位）；階段名是規範用語 | verdicts B4；[cpu-analogy](../../ideas/call-format/cpu-analogy.md)「exec 是指令、exec_loop 是取指與控制流」 |
| **§G-2 writeback 與批次彙總狀態** | 回合層 MUST 算出批次彙總狀態並寫進 header 的 `result`（§C-8 的欄位在此定義值域）：**`ok`／`partial`／`failed`／`machine_failed`**（＋彙整寫的 `null`＝尚未 writeback）。判準 MUST 建立在**回傳值分層**上（裁-9b）：回合層自身的失敗＝`machine_failed`；**批次內容的失敗**（整批 JSON 解析失敗、指示詞求值失敗、子行程跑壞）＝`failed`／`partial`，MUST NOT 算成 `machine_failed`。**逾時 ＝ 已完成的執行 ＝ 成功 slot**；空批次＝`ok`。寫回時點：execute 完成之後、`release_instruction` **之前**（`.runi` 還在＝現場還在）；寫回失敗 MUST NOT 讓回合失敗，記 warning（比照 `HeaderWriteFailed` 的既有取捨）。並明說：**退避的判準來自回合層自己算出的結果，MUST NOT 要求先讀回 header**（寫 header 是為了可觀察性） | spec 裁決 4；§C-8「值域於 M2 定義」；loop.md 第 6／15 條；裁-5／6／7／9b |
| **§G-3 節流與退避** | 節流判準 MUST 是「**有沒有進展**」而不是「有沒有做事」：`result` ∈ {`ok`,`partial`} ＝有進展→重置；`failed`／`machine_failed`／回合層失敗＝無進展→MUST 退避且計數遞增；**空回合（沒取到批）MUST 既不遞增也不重置**，睡基數。退避 MUST 是指數的、MUST 有上限：基數＝`--loop` 間隔、倍率 2、上限 `max(interval, 60000)` ms。「取到批次」（舊 `did_work`）MUST NOT 單獨決定睡不睡 | spec 裁決 4；loop.md 第 14／21 條；裁-8 |
| **§G-4 睡眠語意與 `--loop 0`** | `--loop <ms>` 的間隔**只用於無進展／空閒的圈**，有進展就零延遲進下一圈；**`0` MUST NOT 忙碌輪詢**——無工作時 MUST 至少睡一個最小間隔（現行＝warn ＋視為 1 ms）；事件驅動（inotify 之類）MAY 在未來取代睡眠，**語意不變** | spec 裁決 3；loop.md 第 13 條；`run.cpp` 現行行為（已 warn＋下限化）；裁-8b |
| **§G-5 庫層失敗的計數與停機** | 回合層 MUST 對庫層失敗**計數**、MUST NOT 無聲丟棄；連續 N 次（N＝10）MUST 停機、在 stderr 印出次數與最後一次的 errno、並以**退出碼 4** 返回。只數 `machine_failed`，不數 `failed`。只在 `--loop` 模式出現 | loop.md 第 15／20 條（fork bomb 無聲自我惡化）；裁-9 |
| **§G-6 計時與砍行程的所有權** | `timeout_ms` 的**值**仍住 inst schema（§C-3 不動、§F-1 MUST NOT bump），**計時與砍行程由回合層執行**；exec 層 MUST NOT 自帶計時——**`execute()` MUST NOT 施行 `timeout_ms`**（阻塞至子行程自行結束），這句要明寫，它是一次已釋出 API 的行為變更。砍法照現行行為立法：對**行程群組**送 SIGTERM → 寬限期 → 補一發 SIGKILL → 收屍；`ExecResult::timed_out` 由回合層填 | verdicts A 表「timeout_ms 移出最內圈」；spec 裁決 5；`exec.cpp` 現行行為；裁-1／裁-3 |
| **§G-7 控制面：control inbox** | 控制面 MUST 走投遞協定、MUST NOT 另開 signal／pid 檔的 ad-hoc 通道；收件匣 `.aos/control.tempd/`（**明確宣告不存在 `control.json`**——控制記錄不彙整成批，這個與 `inst.tempd` 的不對稱要寫出來，否則下一個人會去改 `derive_paths`）；記錄＝恰好一個 key 的 `{"op":"<動詞>"}`，未知 key MUST 拒絕，**MUST NOT 走格式層**（`op` 過不了 inst schema，而讓格式層長第二套 schema 違反 §A-6）；檔名與發布比照 §D-2；**v1 動詞集合封閉為 `stop`**（跑完當前回合後停、退出碼 0）；回合層 MUST 在控制窗口掃描（§A-8；建議每圈掃兩次，見 3.3）；處理完 MUST 刪除記錄（**刪除先於退出**）；格式壞掉或動詞不認得 MUST 隔離為 `.bad`＋warning＋繼續（§D-4／§D-8）；**消費語意是 at-least-once**（崩在「讀到 stop」與 unlink 之間會再停一次；`stop` 冪等所以不會壞事）——**照實寫，不要假裝 exactly-once**；**不新增子命令** | instruction §26；spec 裁決 2；裁-10／11／12 |
| **§G-8 訊號收尾**（照實立法，控制面的另一半） | 第一次 SIGINT／SIGTERM MUST 喚醒等待、讓當前回合跑完並釋放 `.runi` 後以 0 返回；第二次同訊號採預設處置立即終止。既有行為，M2 只是從 `docs/usage.md` 升成條款，**不擴充** | `run_loop.cpp` 的 `LoopSignals`（`SA_RESETHAND`）；usage.md 現行說明 |

### B／C／D 的點狀修補

| 條款 | 這條要規定什麼 | 來源 |
|---|---|---|
| **§B-2 版面樹（修改）** | 樹裡加一行 `control.tempd/ ← 控制記錄收件匣（§G-7）`；比照 §B-3 的舊世界規則：`aos init` MUST 建立、讀不到（舊世界）MUST 視為空、MUST NOT 拒絕、MUST NOT bump 版面版本（§B-4「純新增不 bump」再加一項）。**順手（低成本、主線可否決）**：承認 `.aos/` 現有的三個命名例外——`version`／`turn` 無副檔名、`insts/` 該是 `insts.d/` 卻不是；現在不寫，M3 的版面 ownership table 一定會撞上 | 裁-10；§B-3／§B-4 的既有先例 |
| **§C-3 欄位表（修改）** | `timeout_ms` 那格摘掉 `(planned, M2)`，意義欄改寫成「執行時間上限（毫秒）；為零＝無期限。**施行者是回合層（§G-6），`execute()` 不施行它**」。欄位留在表內、型別與預設不動、§F-1 不 bump | spec 裁決 5 |
| **§C-8 header（修改）** | `result` 列的「值域於 M2 定義」換成四值定義（指向 §G-2）；補一句「彙整層寫出時為 `null`，由 loop 於 writeback 寫回」 | §C-8 現行文字；spec 裁決 4 |
| **§D-9 退出碼（修改）** | 表加一行：**4 ＝ loop 因連續庫層失敗停機**（只在 `--loop` 模式；單次 `aos exec` 的一次庫層失敗仍是 1）。0／1／2／3 的既有語意一字不改；`--loop` 因 `stop` 或訊號收尾仍是 0。**前置**：§D-9 現在仍帶 `(planned, M1)`、已知未決 #2 仍在——M2 動這條之前，M1 的碼表必須先收編完 | 裁-9；§G-5／§G-7 |

**同一步（S1）順手處理**：`docs/SPEC.md` 的「已知未決 **#4**（timeout_ms）」在 §G-6 與
§C-3 落地後**消掉**（S11 執行）。**#1（SIGINT 斷點續跑）原樣保留**——§G-8 只把現行的
「跑完當前回合才退」立法，**不碰**「被 SIGINT 中止的單次 `aos exec` 留下 `.runi`」那個
矛盾。（**可選提案給主線**：`stop` 與第一次 SIGINT 行為完全相同，M2 是把 #1 一起裁掉的
最佳時機；spec 的「明確不做」沒提它，可能是漏的而不是有意排除。裁不裁由主線，plan 預設
不裁。）

**M2 開工前的現況**：`grep -n "planned, M2" docs/SPEC.md` 目前**只有兩筆**——§C-3 的
`timeout_ms` 那格，與已知未決 #4。M2 完成後兩筆都要清零。

## 三、設計提案（給實作隊的骨架，措辭與細節仍以 S1 的條款為準）

### 3.1 四階段管線在搬遷後的呼叫鏈（decode 歸位）

| 階段 | 誰承擔 | 在哪個檔 | 用到 `core/inst` 的哪些公開 API |
|---|---|---|---|
| **fetch** | `aos::loop::fetch_batch()` | `core/loop/src/round.cpp` | `aggregate_instructions()` → `claim_instruction()`（皆已 `AOS_API`） |
| **decode** | `aos::loop::decode_batch()` | **`core/loop/src/decode.cpp`（新檔）** | `read_all()` → `capture_environment()` → 逐筆 `resolve()`。**這就是 B4 的歸位**：這三步今天埋在 `run_batch.cpp:67 execute_batch()` 的前半段，搬出來成為有名字的階段 |
| **execute** | `aos::loop::execute_batch()`（沿用名字）＋ per-slot 的 `execute_slot()` | **`core/loop/src/execute.cpp`**（原 `run_batch.cpp` 的後半段）＋ **`core/loop/src/deadline.cpp`（新檔）** | `spawn()`／`poll_child()`／`signal_child_group()`／`reap_child()`（裁-1 的新入口） |
| **writeback** | `aos::loop::writeback()` | **`core/loop/src/writeback.cpp`（新檔）** | 算 `BatchResult` → 寫 header `result`（S7 在 `core/inst` 新增的 `AOS_API`）→ `release_instruction()` → 遞增 `turn` |

編排者是 `aos::loop::run_once()`（`core/loop/src/round.cpp`，原 `run_exec.cpp:198
run_exec_once`），它回傳結構化的 `RoundOutcome` 而不是今天的 `int` ＋ `bool &did_work`：

```cpp
// core/loop/include/aos/loop.hpp（提案，簽名由 S5 定案、主線過目）
namespace aos::loop {

enum class BatchResult { None, Ok, Partial, Failed, MachineFailed };  // None＝這圈沒批次
enum class RoundState  { Idle, Ran, MachineFailure, Busy };          // Busy＝.runi 已存在

struct RoundOutcome {
    RoundState  state  = RoundState::Idle;
    BatchResult result = BatchResult::None;
    int exit_code = 0;                 // 0／1／3，對應 §D-9
    bool progressed() const;           // state==Ran && (result==Ok || result==Partial)
    bool machine_failed() const;       // state==MachineFailure || result==MachineFailed
};

AOS_API RoundOutcome run_once(const char *folder);
AOS_API int run(const char *folder, std::uint64_t interval_ms);  // 迴圈本體，回退出碼
AOS_API const char *to_string(BatchResult result) noexcept;      // 四個值的唯一字面來源

}  // namespace aos::loop
```

- **`did_work` 就此消失**：它今天的位置（`run_exec.cpp:274`，設在 `execute_batch` **之前**）
  恰好就是「取到批次」的語意——換成 `RoundState::Ran` 之後語意自明，loop.md 第 21 條的
  抱怨隨之作廢。**睡不睡改看 `progressed()`。**
- **`to_string(BatchResult)` 是四個字串的唯一來源**：header 寫入與測試斷言都走它，
  避免字面值散落（驗收條件 5 的 grep 靠這個成立）。
- **命名避雷**：header 欄位叫 `result`、回合返回值叫 `RoundOutcome`，兩者不再同名
  （spec 的「調度者須知」第 2 點）。

### 3.2 exec 層的非阻塞入口（裁-1 的 A 案）

```cpp
// core/inst/include/aos/inst.hpp，接在既有 exec 區塊（inst.hpp:195-213）之後
struct ExecHandle {
    std::int64_t pid = -1;    // 公開標頭不吃 <sys/types.h>，內部轉 pid_t
    std::string exit_path;    // spawn 時抄走，reap 成功後才寫
    bool running = false;
    bool reaped  = false;     // 已收屍；pid 仍留著，供最後一發群組 kill
};

AOS_API ExecState spawn(inst_t &inst, ExecHandle &handle, ExecResult &result);
AOS_API ExecState poll_child(ExecHandle &handle, bool &finished, ExecResult &result);
AOS_API ExecState reap_child(ExecHandle &handle, ExecResult &result);
AOS_API ExecState signal_child_group(const ExecHandle &handle, int signal_number);
AOS_API ExecState execute(inst_t &inst, ExecResult &result);  // 簽名不變＝spawn＋reap_child
```

責任切法（**行為逐字保留**，對照 `exec.cpp` 現況）：
- `spawn` ＝ 驗 argv → `prepare_spawn` → `fork` → 子側 `setpgid(0,0)`＋`run_child` →
  **父側 `setpgid(pid,pid)` 與它的失敗收尾（kill＋reap＋`SpawnFailed`）也在 spawn 內**。
  這段**不可以**拆到 poll／reap：它是子側 setpgid 的雙保險，拆了會交出「fork 成功但
  群組沒建起來」的 handle，loop 的 `kill(-pid, …)` 就會打到別的群組。
- `poll_child` ＝ `waitpid(pid, …, WNOHANG)`；收到屍體才做狀態對應（`WIFSIGNALED` →
  `128+WTERMSIG`）與 `exit` 檔寫入（含 fsync）。
- `reap_child` ＝ 阻塞 `waitpid` ＋同一段狀態對應與寫檔。
- `signal_child_group` ＝ `kill(-pid, sig)`，**回傳值刻意忽略**（`ESRCH` 就是我們要的
  「無事發生」），且 `reaped == true` 時**仍允許呼叫**（現行「收掉領頭者後補一發
  SIGKILL」靠的就是這個）。
- **命名避開 `poll`／`kill`／`wait`**（POSIX 同名符號，`using namespace aos` 會撞）。
- **`ExecHandle` MUST NOT 寫自動 reap 的解構子**：`wait_until` 出錯時**刻意不 kill
  不 reap 直接 return**，code map 的 library 分冊明列這是刻意設計；加了自動 reap 就把它
  偷偷改掉了（而外部審查工具會反覆建議加）。

### 3.3 control inbox 的檔案協定（裁-10～12 的完整提案）

**版面**（`.aos/` 底下現有名字：`version`／`turn`／`inst.json`＋`.temp`／`.runi`／
`inst-head.json`／`inst.tempd/`／`insts/`）：

```text
.aos/
    control.tempd/               ← 控制記錄收件匣（§B-1 的 .tempd＝投遞匣資料夾）
        <pid>-<seq>.json.temp    ← 生成中（§B-1 的 .temp）
        <pid>-<seq>.json         ← 可被 loop 讀走
        <pid>-<seq>.json.bad     ← 格式壞掉／動詞不認得，已隔離（§B-1 的 .bad）
```

**零新副檔名、零新狀況字**——`.tempd`／`.temp`／`.bad` 全在 §B-1 的封閉清單裡，
所以**不需要修憲加狀況**，也不需要開 verdicts B7 的「第二個軸」。

| 面向 | 提案 | 與投遞協定（§D-1～§D-6）的同構程度 |
|---|---|---|
| 目錄 | `.aos/control.tempd/` | **同構**：一樣是 `.tempd` 收件匣 |
| 檔名 | `<pid>-<seq>.json`（§D-2 同一規則） | **同構** |
| 發布 | 先 `.json.temp`、寫完 rename | **同構**（排他發布是 SHOULD，v1 的寫入者是人，撞名機率可忽略） |
| 內容 | `{"op":"stop"}`，**恰好一個 key**、值為字串 | **不同構**：控制記錄**不是** inst，**MUST NOT** 走 `read_all`（§C-5 會直接 `UnknownKey` 拒絕 `op`）。用一個 20 行的定點解析器，與 `handoff_header.cpp` 的 `decode_header_id` 同款手法（受控版面、不進 JSON 函式庫） |
| 誰讀 | loop，每圈開頭（claim 之前）掃一次 | **不同構**：**沒有彙整步驟**、**沒有 `.runi`**（記錄逐筆消化，不合併成一份檔、不需要取件鎖） |
| 順序 | 字典序（同 §D-4，投遞者不得假設） | **同構** |
| 消化 | 處理完 `unlink` ＋ `fsync_dir` | **同構**（§D-4「發布成功後才刪投遞」的對應動作） |
| 無效 | 就地改名加 `.bad` ＋ warning ＋繼續；清理歸人或 `aos recover` | **同構**（§D-4／§D-8） |

**掃描點的精確位置**（`run()` 迴圈體）——**每圈掃兩次，同一個函式呼叫兩處**：

```text
for (;;) {
    scan_control();                  // 窗口①：睡醒之後、fetch 之前
    if (stop_requested) return 0;    // stop 已 unlink，重啟不會再停一次
    outcome = run_once(folder);      // fetch → decode → execute → writeback
    if (outcome.state == Busy) return 3;
    scan_control();                  // 窗口②：writeback 之後、決定睡不睡之前
    if (stop_requested) return 0;
    if (signal_stop) return 0;
    if (machine_failures >= 10) return 4;
    sleep(next_sleep(outcome));      // 有進展→0；空回合→基數；無進展→退避
}
```

**為什麼兩處都掃**：只掃②（睡前），睡眠期間投進來的 `stop` 要等睡完整個 interval——
`--loop 60000` 的世界要等一分鐘；只掃①（睡醒後），一批剛跑完就投的 `stop` 會被拖去睡
一輪。兩處都掃，`stop` 的最壞延遲 ＝ 當前回合的剩餘時間（那本來就要跑完，正是裁決 2
要的），不再額外加一個 interval。成本是每圈多一次通常為空的 `readdir`——與已經在做的
inbox `readdir` 同數量級。**回合中途不掃**，這就是「跑完當前回合才停」的機械保證。

**邊緣狀況（逐條寫進條款或 handoff 文件）**：
1. **`stop` 在批次跑到一半進來**：v1 不打斷回合——下一圈開頭掃到、當圈不再開始新回合。
   這正是「跑完當前回合停」的定義。
2. **同時多個 `stop`**：一次掃描把**全部**認得的記錄消化掉（都 unlink），停一次。
3. **格式壞掉**：`.bad` ＋ warning ＋**繼續跑**（不停機、不當成 stop）。
4. **不認得的 `op`**：同上（舊 aos 遇到新動詞硬失敗而不是猜——§C-5 的同一條哲學）。
5. **`unlink` 失敗**：warning ＋**仍然停機**（stop 的語意優先），並在 stderr 明說
   「控制記錄未能刪除，重啟前請手動清掉」——否則會變成停不掉的世界。
6. **舊世界沒有 `control.tempd/`**：視為空，**不報錯、不自動建**（比照 §B-3 對 `turn`
   的處理）；`aos init` 之後的新世界一律有。
7. **`.aos` 或版面版本不合法**：control 掃描發生在 `run_once` 之前，此時還沒驗版面——
   提案：**掃描失敗一律當成「沒有控制記錄」**，讓 `run_once` 去報版面錯（更少的結構
   改動，且錯誤訊息只會出現一次）。`readdir` 非 `ENOENT` 的失敗：記 warning、當這圈
   沒有控制記錄、**繼續跑**——控制面故障不該讓世界停擺。
8. **消費語意是 at-least-once**：loop 若崩在「讀到 stop」與「unlink」之間，下次啟動會
   再停一次。`stop` 冪等所以不會壞事，但會讓人以為 loop 起不來。**條款照實寫**，
   不要假裝 exactly-once。
9. **`unlink` 失敗**：warning ＋**仍然停機**（`stop` 的語意優先），並在 stderr 明說
   「控制記錄未能刪除，重啟前請手動清掉」——否則會變成停不掉的世界。
10. **誤投面**（新增第二個投遞匣必然產生的）：控制記錄長得像 instruction（JSON、投在
    `.tempd`、同一套檔名），但兩邊 schema 互斥——控制記錄投進 `inst.tempd/` 會被彙整
    判 `UnknownKey` 隔離成 `.bad`，反之亦然。**診斷訊息 MUST 帶匣名**
    （`.aos/inst.tempd/x.json: UnknownKey`），否則人看到的只有「UnknownKey」，
    看不出是投錯匣。成本接近零。

### 3.4 退避的實作骨架

```cpp
// core/loop/src/loop.cpp（提案）
class Backoff {
public:
    explicit Backoff(std::uint64_t base_ms) : base_(base_ms), current_(base_ms) {}
    std::uint64_t next() {                       // 無進展時呼叫，回本次該睡多久
        const std::uint64_t value = current_;
        const std::uint64_t cap = base_ > 60000 ? base_ : 60000;
        current_ = current_ > cap / 2 ? cap : current_ * 2;
        return value;
    }
    void reset() { current_ = base_; }            // 有進展時呼叫
private:
    std::uint64_t base_, current_;
};
```

三種圈的分流（**裁-8 的核心，實作最容易搞錯的一點**）：

| 這圈的結果 | 睡多久 | `Backoff` 狀態 | 庫層失敗計數 |
|---|---|---|---|
| **有進展**（`progressed()`） | **0**（不睡，立刻下一圈——現行行為） | `reset()` | 歸零 |
| **空回合**（`RoundState::Idle`，沒取到批） | `base_` | **不動**（不遞增也不重置） | **不動** |
| **無進展**（`failed`／`machine_failed`／回合層失敗） | `next()` | 遞增 | 只有 `machine_failed()` 才 `++` |

- **空回合那一列是關鍵**：空閒不是故障。若把它算無進展，一個閒置世界會退到 60 秒，
  新投遞要等一分鐘才被看到——直接打壞可用性。反過來，故障中偶然來一個空回合也不該把
  退避清掉。
- `base_` ＝ `run.cpp` 解析出來的 `interval`（`--loop 0` 已在那裡被下限化成 1，
  **這條既有行為不動**，裁-8b）。
- 溢位：`current_ > cap/2` 的寫法讓倍增在觸頂前就夾住，`std::uint64_t` 不會 wrap。
- 庫層失敗計數器（裁-9）與 `Backoff` **分開**：`Backoff` 看 `progressed()`，
  計數器只看 `machine_failed()`，連續 10 次就 `return 4`。
- **測試接縫**：睡眠走一個裝在 `core/loop/src/loop_internal.hpp` 的 hook
  （`using SleepFn = void(*)(std::uint64_t); void set_sleep_hook(SleepFn);`），
  **只給同專案測試用**（測試 target 連 `aos_loop_cli` OBJECT library，看得到 `src/`
  的內部標頭——`test_run_support.hpp` include `../src/run.hpp` 就是這個先例）。
  這樣退避測試可以斷言「第 n 次請求睡多久」而不靠牆鐘，不會 flaky。

### 3.5 「匯聚（injection lib）＝彙整（aggregate）？」——記回 ideas 的文字草稿

M2 **只搬不答**（spec 已列為明確不做）。以下這段請在 S10 原樣（或由主線潤飾後）補進
**`wf/workflows/ideas/core-layering.md`** 的「我挖到的邊緣狀況」清單，取代現有那一條
bullet；同時在 **`wf/workflows/ideas/verdicts.md` 的 B 表**加一句指過去
（roadmap M4 存貨第 4 項「匯聚 lib-vs-inst」也指這裡）：

> **「匯聚」與「彙整」是不是同一件事——M2 的實作證據（2026-08-28，未裁）。**
> core-layering 構想裡的「匯聚」是**再外圈的 core 專案、用注入式 lib 跟 loop 配合**；
> layout-handoff 裡的「彙整」是**交接協定第二步**（把多份投遞攤平成下一個
> `inst.json`）。M2 把回合搬進 `core/loop` 之後，實作上的答案偏向**兩者不是同一件事**：
> 彙整（`aggregate_instructions`）已經是 `core/inst` handoff 層的一個**公開函式**，由
> 回合層在 fetch 階段直接呼叫——它沒有注入、沒有 hook、沒有策略選擇，就是一步機制。
> 而構想裡的「匯聚」要解決的是**誰決定這一輪收哪些投遞、要不要插隊、要不要注入系統
> inst**——那是**策略**，而且正是 §25 認列的那筆代價（「系統 inst 需要彙整層注入
> 策略」）。**所以更可能的結論是：彙整＝機制（住 inst），匯聚＝策略（住 loop 或它的
> 注入點），M2 只落地了前者。** 但這只是實作觀察，**不是裁決**——真正要拍板的仍是
> keep.md 結尾那句「原語若真能承載任何東西，匯聚為什麼是注入式 lib 而不是一筆 inst？」，
> 那是 M4 閘門的存貨，M2 不碰。

---

## 四、逐步實作

### S0 裁決清點（主線，半小時級）

- 過一遍第一節 15 項，記入 `wf/workflows/ideas/verdicts.md`（A 表）＋對應 ideas 檔
  （`machine-shape/loop.md`、`core-layering.md`）。
- **驗**：verdicts diff 可讀；15 項各有結論。

### S1 SPEC 條款起草（**主線**，AI 不得自行修憲）

- 動：`docs/SPEC.md` — 新開 **G 區**（§G-1～§G-9，帶 `(planned, M2)`）＋ 修 §B-2／
  §C-3／§D-9（見第二節）。
- **驗**：`grep -n "planned, M2" docs/SPEC.md` 列出的每一條都對應 S2–S9 的某一步
  （拿第七節驗收對照表核）；G 區每條有編號、位階、來源。

### S2 exec 拆非阻塞入口（**判斷型，Opus**；`core/inst` 內純重構，語意零變化）

- 動：
  - `core/inst/include/aos/inst.hpp`：加 `ExecHandle` ＋四個 `AOS_API` 宣告（3.2 節）。
  - `core/inst/src/exec.cpp`：把 `execute()` 拆成 `spawn`／`poll_child`／`reap_child`／
    `signal_child_group`，**`execute()` 用它們組出目前完整行為（含逾時）**。
    現況 252 行，扣掉逾時分支、加回 handle 樣板約 240–260 行，仍在 300 門檻內；
    真的頂到就把子側（`ChildPlan`／`child_redirect`／`run_child`）切成
    `core/inst/src/exec_child.cpp`（切線天然：fork 兩側）。
  - **不動** `wait.cpp`／`wait.hpp`（`wait_until` 這一步還留著，S6 才搬）。
- **驗**：`core/inst/tests/test_timeout.cpp` **一字不改仍全綠**——這就是 S2 的驗收；
  ctest（default＋merged）全綠。

### S3 `core/loop` 骨架（**機械，可轉派 sonnet**）

- 動：
  - 新目錄 `core/loop/`，`CMakeLists.txt` 照 `core/inst/CMakeLists.txt` 抄
    （該檔開頭註解就寫著它是範本）：
    ```cmake
    aos_add_subproject(loop
        SOURCES src/round.cpp
        HEADERS include/aos/loop.hpp
        PUBLIC_DEPS aos::inst          # 必須 PUBLIC，見裁-14
    )
    add_library(aos_loop_cli OBJECT src/run.cpp)
    target_link_libraries(aos_loop_cli PUBLIC aos::loop)
    aos_add_test(aos_loop_tests SOURCES tests/test_smoke.cpp LINK aos_loop_cli)
    ```
  - `core/CMakeLists.txt`：加一行 `add_subdirectory(loop)`（在 `inst` 之後）。
    **根 `CMakeLists.txt` 與 `app/` 一行都不用動**（合併版 foreach 會自動撿
    `aos_loop_objects`；子命令表由 CMake 產生）。
  - 先只放一個 `to_string` 之類的最小內容，確認 build／install／export／merged 都通。
- **驗**：ctest 從 4 支變 5 支、全綠；`cmake --preset merged` 建置成功且
  `ctest --test-dir build/merged` 全綠；`readelf -d build/merged/lib/libaos.so | grep NEEDED`
  **不得**出現 `libaos_inst.so`（裁-14 的回歸守門）。

### S4 純搬遷（**機械偏判斷，Opus 帶 sonnet**；內容零改動）

- 動（`git mv` 為主）：
  | 從 | 到 |
  |---|---|
  | `core/inst/src/run_exec.cpp` | `core/loop/src/round.cpp` |
  | `core/inst/src/run_loop.cpp` | `core/loop/src/loop.cpp` |
  | `core/inst/src/run_batch.cpp`／`.hpp` | `core/loop/src/execute.cpp`／`.hpp` |
  | `core/inst/src/run.cpp` 的 `parse_interval`＋`run_exec()`＋`aos_exec_cli_main`（約 48 行） | `core/loop/src/run.cpp` |
  | `core/inst/src/run_internal.hpp` 的 `run_exec_once`／`run_exec_loop` 兩行 | `core/loop/src/loop_internal.hpp` |
  | `core/inst/tests/test_run_loop.cpp` | `core/loop/tests/test_loop.cpp` |
  | `core/inst/tests/test_run_handoff.cpp` | `core/loop/tests/test_round.cpp` |
  | `core/inst/tests/test_run_batch.cpp` | `core/loop/tests/test_execute.cpp` |
  - `core/inst/src/run.hpp`／`run_internal.hpp`：刪 exec 相關的宣告（各兩行）。
  - `core/inst/CMakeLists.txt`：`aos_inst_cli` 的 SOURCES 刪四個檔；**`aos_add_subcommand(
    NAME exec …)` 整段刪掉**；測試 SOURCES 刪三支。
  - `core/loop/CMakeLists.txt`：SOURCES／CLI／`aos_add_subcommand(NAME exec ENTRY
    aos_exec_cli_main LIBRARY aos_loop_cli SUMMARY "推進一個 aos 資料夾的一回合")`／
    測試 SOURCES 全部補上。
  - `core/inst/tests/test_run_support.hpp`（93 行）**拆**：`init_world()`＋`TempDir`／
    `ScopedCwd`／`read_file`／`write_file` 留 inst；`exec_world()`／`loop_world()` 去
    `core/loop/tests/test_loop_support.hpp`，後者**自己鋪 `.aos/`**（裁-15），不 include
    inst 的 `src/`。
  - **兩支跨界的既有測試要拆**（否則 inst 的測試會反向依賴 loop）：
    `core/inst/tests/test_run_init.cpp` 的
    `TEST_CASE("init and exec default their folder to the current directory")` 與
    `TEST_CASE("init rejects a nonexistent folder and commands reject extra arguments")`
    裡的 `run_exec` 斷言 → 搬去 `core/loop/tests/`；
    `core/inst/tests/test_run_deliver.cpp` 裡「投遞後 exec 真的執行」那個整合案
    → 搬去 `core/loop/tests/test_round.cpp`。
  - namespace：搬過去的 `aos::detail` 內容改成 `aos::loop::detail`（避免兩個小專案共用
    `aos::detail` 造成 ODR 混淆）；`aos::run_exec` 改 `aos::loop::run_exec`。
- **內容除了 include 路徑、namespace、`git mv` 之外，一行邏輯都不改。**
- **驗**：ctest（default＋merged）全綠；`aos --help` 五條子命令都在（順序會變成
  init／deliver／exec／tooljson／llms——**這是預期的**，S10 要更新 usage.md 的實跑輸出）；
  `grep -rn "loop\|run_exec" core/inst/src/ core/inst/include/` 只剩無關的字眼；
  `git log --stat` 顯示 S4 是 rename 為主的 commit。

### S5 四階段管線重構（**判斷型，Opus**）

- 動（全在 `core/loop/`）：
  - `include/aos/loop.hpp`：`BatchResult`／`RoundState`／`RoundOutcome`／`run_once`／
    `run`／`to_string(BatchResult)`（3.1 節簽名，主線過目）。
  - `src/decode.cpp`（**新**）：`decode_batch()` — 把 `execute.cpp` 前半段的
    `read_all` ＋ `capture_environment` ＋逐筆 `resolve` ＋全部診斷輸出搬過來。
    **這是 B4「resolve 屬 decode」的歸位動作。**
  - `src/execute.cpp`：只剩 execute 階段（thread fan-out ＋ join ＋ 逐 slot 診斷），
    並改成**回傳每個 slot 的 `ExecState`**（而不是今天的 `bool failed`），供 S7 算
    `BatchResult`。原 215 行拆完約 110／110，兩檔都遠低於門檻。
  - `src/round.cpp`：`run_exec_once` → `run_once()`，回傳 `RoundOutcome`；
    `did_work` 刪除（改由 `RoundState::Ran` 表達）。
    **順手拆**：現況 293 行裡有一整組本地 fs helper（`open_retry`／`read_input`／
    `write_fully`／`fsync_retry`／`fsync_dir`／`close_checked`／`parse_turn`／
    `advance_turn`，約 130 行）→ 抽成 `src/loop_fs.cpp`／`.hpp`；`round.cpp` 落在
    ~160 行。（`core/loop` 不能 include `core/inst/src/handoff_fs.hpp`——那是內部標頭，
    跨小專案只能走公開標頭。這份重複要記進 code map 的 loop 分冊。）
  - `src/loop.cpp`：改用 `RoundOutcome`；睡不睡改看 `progressed()`（退避留 S8）。
  - **回傳值分層（裁-9b，本步的核心，不是附帶）**：今天 `run_exec_once` 回 `1` 的來路
    至少七種（進不了 folder／`.aos` 壞／版本不認得／aggregate 失敗／release 失敗／
    turn 遞增失敗／`execute_batch` 回 1），而 `execute_batch` 自己又混了三種（整批
    JSON 解析失敗、指示詞求值失敗、單筆 `ExecState` 失敗）。本步 **MUST** 把它們分成
    `RoundState::MachineFailure`（回合層自己壞了，會重演）與 `BatchResult::Failed`
    （批次內容壞了，批已被消化、不會重演）兩類——**不分層，S8 的停機條件就會把
    「一批壞 JSON」誤判成機器故障**。`ExecState` 非 `Ok`（`SpawnFailed`／`WaitFailed`／
    `ExitWriteFailed`）算前者的 slot 級證據，計入 `machine_failed` 的判準。
- **驗**：ctest 全綠（既有 loop／round／execute 測試**行為不變**）；
  新增測試：`decode_batch` 對「解析失敗」「指示詞求值失敗」各回什麼；
  `run_once` 對六種情境（無批次／全成功／部分失敗／全失敗／**壞批 JSON**／
  `.runi` 已存在）各回什麼 `RoundOutcome`——**壞批那一案必須回 `Failed` 而不是
  `MachineFailed`**（裁-9b 的守門）。

### S6 loop 接管計時（**判斷型，Opus**；吃 S2 的入口）

- 動：
  - `core/loop/src/deadline.cpp`／`.hpp`（**新**）：把 `core/inst/src/wait.cpp` 的
    `wait_until`／`monotonic_now`／`elapsed_ms`／`sleep_ms` **逐字搬過來**（1 ms 起、
    倍增、上限 50 ms 的輪詢退避一個數字都不改），改成用 `poll_child()` 而不是
    `waitpid(WNOHANG)`。
  - `core/loop/src/execute.cpp`：`execute_slot()` 改成
    `spawn` → poll 迴圈到 deadline → `signal_child_group(SIGTERM)` → 寬限期
    **2000 ms**（原 `kTimeoutGraceMs`，數字照搬）→ 補一發 `signal_child_group(SIGKILL)`
    → `reap_child`；寬限也逾時就 `SIGKILL` ＋阻塞 `reap_child`。
    **`timeout_ms` 的值由這裡從 `inst_t` 讀出來**（回合層讀欄位，exec 層不讀）。
  - **關鍵手法（讓每一步都綠）**：本步先在 loop 抄走 `inst.timeout_ms` 之後、呼叫
    `spawn()` 之前**把它歸零**，這樣 S6 與 S7 之間任何時刻都只有**一個**計時者，
    兩份計時不會疊加。
  - `core/inst/src/exec.cpp`：刪 `kTimeoutGraceMs` 與逾時分支，`execute()` 變成
    `spawn`＋`reap_child`；`core/inst/src/wait.cpp`／`.hpp` 只剩 `wait_retry`。
    移除上一段的歸零 hack。
  - 測試搬家：`core/inst/tests/test_timeout.cpp` 的
    `"timeout terminates a command process group"`／
    `"fast command does not pay a polling interval"`／
    `"timeout kills grandchildren"`／
    `"timeout kills a grandchild that ignores SIGTERM"` **四案搬**
    `core/loop/tests/test_timeout.cpp`（改成打 loop 的批次入口，**不要**繞整個
    `aos exec`——會變慢且不確定）；
    `"zero timeout uses normal blocking execution"` **留 inst**、改名為
    「`execute` 阻塞至子行程結束」並刪掉 `timeout_ms` 引用；
    `"timeout format reads writes and rejects invalid values"` **留 inst**（那是格式層
    的案子，欄位沒搬），建議併進 `test_format_write.cpp`。
  - `core/inst/tests/test_capi.c`：**新增一案**釘住「設了 `timeout_ms` 之後
    `aos_instruction_execute` 仍阻塞到子行程自行結束」（裁-3；**現有測試抓不到這個變更**）。
  - `core/inst/tests/test_exec_handle.cpp`（**新**）：`poll_child` 未結束回
    `finished=false`；`reap_child` 之後 `exit` 檔內容正確；`signal_child_group` 打得到
    整個群組；`reaped` 之後仍可再發一次群組 kill。
- **驗**：ctest 全綠；`grep -n "timeout_ms" core/inst/src/exec.cpp core/inst/src/wait.cpp`
  **零筆**；`grep -n "timeout_ms" core/inst/src/format_encode.cpp core/inst/src/format_decode.cpp
  core/inst/src/capi_instruction.cpp core/inst/include/aos/inst.hpp` **仍有**（欄位沒被誤搬）。

### S7 writeback：算 `BatchResult` ＋寫 header `result`（**判斷型，Opus**）

- 動：
  - `core/inst/src/handoff_header.cpp`／`.hpp`：新增「**只改寫 `result` 欄**」的編碼
    （其餘三欄原樣保留），與既有 `encode_header`／`decode_header_id` 同款的定點手法。
  - `core/inst/include/aos/inst.hpp`：新增 `AOS_API HandoffState
    write_batch_result(const std::string &instruction_path, const char *result,
    HandoffResult &result_out);`——**只提供機制，值域由回合層決定**（inst 不認識那四個
    字串；它只負責「把這個字串寫進 header 的 `result` 欄，走 temp＋rename＋fsync」）。
    `HandoffIssueKind`／`HandoffState` 如需新值**只在尾端加**。
  - `core/inst/src/handoff.cpp`：**不動彙整邏輯**，只在需要時共用既有的耐久性 helper。
  - `core/loop/src/writeback.cpp`（**新**）：從 slot 的 `ExecState` 陣列算 `BatchResult`
    （裁-5／6/7 的判準）→ `to_string()` → `write_batch_result()` → `release_instruction()`
    → 遞增 `turn`。**順序**：寫 header → release → advance turn（提案；理由：`result`
    要在鎖還握著的時候寫，release 之後 header 可能被下一輪彙整覆蓋）。
  - `core/loop/tests/test_writeback.cpp`（**新**）：四種批次各驗 header 的 `result`
    字面值；驗彙整剛發布時 `result` 仍是 `null`。
- **驗**：ctest 全綠；驗收條件 5 的 grep 成立
  （`grep -rn '"ok"\|"partial"\|"machine_failed"' core/inst/src/` 零筆——四個值的字面
  字串只在 `core/loop` 出現，`core/inst` 只認得「把這個字串寫進 `result` 欄」這個機制）。

### S8 節流與退避＋庫層失敗停機（**判斷型，Opus**）

- 動：
  - `core/loop/src/loop_internal.hpp`：加睡眠 hook（`set_sleep_hook`，只給同專案測試用）。
  - `core/loop/src/loop.cpp`：`Backoff`（3.4 節）＋**三種圈的分流表**（有進展／空回合／
    無進展）＋庫層失敗計數器＋`return 4`（裁-9）。
  - `core/loop/tests/test_backoff.cpp`（**新**）：透過 hook 斷言
    ① 第 n 次無進展的睡眠 ≥ `2^(n-1) × 基數` 且 ≤ 上限；
    ② 有進展→計數歸零；③ **空回合→計數不變、睡基數**；
    ④ 連續 10 次庫層失敗 → 退出碼 4 ＋ stderr 有那一行；
    ⑤ **一批壞 JSON 不算庫層失敗**（裁-9b 的回歸守門：連續 N 圈壞批 **MUST NOT**
    讓 loop 退出 4）。
  - 另留一案走既有的 fork＋`usleep`＋數 stderr 行數手法當**煙霧**（不做微秒級斷言）。
- **驗**：ctest 全綠；spec 驗收 2 與 7 通過。

### S9 control inbox（**判斷型，Opus**；可與 S6–S8 平行）

- 動：
  - `core/loop/src/control.cpp`／`.hpp`（**新**）：掃 `.aos/control.tempd/`（字典序、
    只收無狀況後綴——可複用 `is_delivery_name` 的判準，但那是 inst 的內部標頭，
    **在 loop 自己實作一份**）、定點解析 `{"op":"..."}`、`stop` → 設旗標、
    未知／壞掉 → rename `.bad` ＋ warning、認得的一律 `unlink` ＋ `fsync_dir`。
  - `core/loop/src/loop.cpp`：在迴圈開頭呼叫（3.3 節的位置），**unlink 先於 return**。
  - `core/inst/src/run_init.cpp`：`aos init` 多建一個 `control.tempd/`；
    失敗清理路徑（`unlinkat` 串）同步加。
  - `core/inst/tests/test_run_init.cpp`：斷言新目錄存在。
  - `core/loop/tests/test_control.cpp`（**新**）：spec 驗收 3（stop → 跑完當前回合 →
    退出碼 0 → 記錄已消失 → 重啟不會立刻再停）；壞格式／未知 op → `.bad` ＋繼續跑；
    多個 stop 一次消化；舊世界沒有 `control.tempd/` 不報錯。
- **驗**：ctest 全綠；煙霧（實跑並留輸出給 S10）：
  ```bash
  cd "$(mktemp -d)" && "$OLDPWD/build/bin/aos" init .
  "$OLDPWD/build/bin/aos" exec --loop 200 . &
  printf '{"op":"stop"}' > .aos/control.tempd/manual.json.temp
  mv .aos/control.tempd/manual.json.temp .aos/control.tempd/manual.json
  wait $!; echo "exit=$?"   # 0，且 .aos/control.tempd/ 已空
  ```

### S10 文件＋導航同步（**機械為主，可轉派 sonnet**；usage.md 的命令要實跑）

- 動：
  - `docs/usage.md`：`aos --help` 的輸出**重貼實跑結果**（子命令順序變了）；`--loop`
    一節改寫——刪掉「`--loop 0` 合法，但會 busy poll」（**與實作矛盾，M1 沒改到**）、
    補退避說明與 control inbox 的投遞範例（貼 S9 煙霧的實跑輸出）；退出碼表加
    「4 ＝ loop 因連續庫層失敗停機」；`timeout_ms` 那句補「由回合層套用」；
    **第二節「一個完整的例子」裡的 `job.timeout_ms = 1000;` MUST 改**——那個範例
    示範的正是「設了逾時然後直接呼叫 `aos::execute()`」，搬遷後會無聲失去逾時
    （裁-3 的代價，spec 調度者須知第 5 點）。
  - `core/inst/docs/format.md`：改寫那段用 `timeout_ms` 當例子論證「未知 key 必須拒絕」
    的文字——**搬遷後 `aos::execute` 就是那段描述的行為**，不改就自打嘴巴，而它是 §C-5
    的理據來源。換一個例子（`"stdou"` 拼錯那個例子本來就在同一段，留著即可）。
  - `core/inst/docs/exec.md`／`architecture.md`／`capi.md`／`cxxapi.md`：逾時語意改寫、
    新的四個入口、`execute()` 不再套用 `timeout_ms` 的白紙黑字（裁-3）。
  - `core/loop/docs/`（新，最小）：`loop.md` — 四階段管線、退避、control inbox 協定。
  - `docs/subprojects.md`／`docs/build.md`：多一個核心小專案、`aos::loop` target 一列。
  - code map：
    - **新增 `wf/workflows/common/code-map/loop.md`**（第五冊）＋ `code-map.md` 的分冊表
      加一列 ＋ 頂端那張相依圖加 `aos::loop`（含「第一個跨小專案相依」一句）。
    - `code-map/build.md`：`core/CMakeLists.txt` 那列反映 `add_subdirectory(loop)`；
      **加一句 `PUBLIC_DEPS` vs `PRIVATE_DEPS` 的坑**（裁-14）。
    - `code-map/inst/cli.md`：刪 `run_loop.cpp`／`run_exec.cpp`／`run_batch.cpp` 三列，
      `run.cpp` 職責改成「只剩 init」。
    - `code-map/inst/library.md`：exec 那格補四個新入口與「刻意設計」清單；
      handoff 那格補 `write_batch_result`。
    - `code-map/inst/tests.md`：搬走／新增的測試檔過帳。
    （依 conventions：**code map 同步跟該步程式碼同一個 commit**——S3–S9 各自帶自己的
    code map 列，S10 只做總檢查與文檔。）
  - `wf/workflows/common/gotchas.md`：`--loop 0` 忙碌輪詢／失敗算有做事／loop 忽略
    除 3 以外的回傳值 **三條在本檔根本沒有列**（只在 verdicts D 表）——S10 補進
    「使用 aos」節並直接標「已修（M2，指 §G-5／§G-7）」，讓兩邊對得上。
    `.runi` 不是鎖那條**保留**（未修）。
    **另外要更正一條過期記載**：verdicts D 表寫「`did_work` 甚至設在執行之前」，
    引的是 loop.md 第 21 條的 `run_exec.cpp:170`——**現行程式碼是設在
    `claim_instruction` 成功之後**，語意早就是「取到批次」了。那條要改成「已在 M1
    順手修正一半；M2 補上『不再單獨決定睡不睡』」，否則實作隊會去改一個已經對的東西。
  - `wf/workflows/ideas/`：`machine-shape/loop.md`（第 6／7／8／13／14／15／20／21／25／
    26 條標已裁已做）、`core-layering.md`（3.5 節的段落＋「超時誰砍」「相依方向」
    「獨立命令否」三條邊緣狀況標已裁）、`verdicts.md` A 表加「M2 階段裁決」一列、
    B 表第 2／4／6／9／12 項過帳、D 表三條標已修。
- **驗**：文件裡每條命令照貼實跑輸出；`grep -rn "busy poll" docs/` 零筆；
  code map 五冊 diff 與新增／刪除檔一一對應。

### S11 收尾（主線）

- 動：
  - `docs/SPEC.md`：S1 埋的 `(planned, M2)` 全數摘掉；已知未決 **#4 刪除**、
    **#1 原樣保留**。
  - 驗收清單總跑（第七節逐條打勾）；`ctest --preset default` 與
    `ctest --test-dir build/merged` 最終全綠。
  - `wf/workflows/roadmap.md` M2 記完成 ＋ **留一行**：「回合歷史／注入機制未做，
    loop 崩潰後仍只有 `.runi`（§25 的代價，M3 之後）」（spec 調度者須知第 3 點）。
  - `wf/SESSION-LOG.md` 一行；本項目資料夾移 `archive/`。
- **驗**：`grep -n "planned, M2" docs/SPEC.md` 零筆；spec 驗收 11 條全過。

---

## 五、動哪些檔（總表，對照 code map 現況；行數為實測現值）

| 檔（repo 相對路徑） | 動作 | 步 | code map 落點 |
|---|---|---|---|
| `core/inst/include/aos/inst.hpp` (215) | 改：`ExecHandle`＋四入口；`write_batch_result` | S2/S7 | inst/library.md |
| `core/inst/src/exec.cpp` (252) | 改：拆四入口；S6 刪逾時分支 | S2/S6 | inst/library.md |
| `core/inst/src/exec_child.cpp` | **新**（只在 S2 頂到 300 行門檻時才拆） | S2 | inst/library.md（新列） |
| `core/inst/src/wait.cpp` (90)／`.hpp` (12) | 改：`wait_until` 等搬走，只剩 `wait_retry` | S6 | inst/library.md |
| `core/inst/src/handoff_header.cpp` (99)／`.hpp` (44) | 改：只改寫 `result` 欄的編碼 | S7 | inst/library.md |
| `core/inst/src/run.cpp` (84) | 改：exec 那 48 行搬走，只剩 init | S4 | inst/cli.md |
| `core/inst/src/run.hpp` (10)／`run_internal.hpp` (13) | 改：刪 exec 宣告 | S4 | inst/cli.md |
| `core/inst/src/run_init.cpp` (141) | 改：建 `control.tempd/`＋清理路徑 | S9 | inst/cli.md |
| `core/inst/src/run_exec.cpp` (293) | **搬** → `core/loop/src/round.cpp` | S4 | inst/cli.md 刪列 |
| `core/inst/src/run_loop.cpp` (84) | **搬** → `core/loop/src/loop.cpp` | S4 | inst/cli.md 刪列 |
| `core/inst/src/run_batch.cpp` (215)／`.hpp` (9) | **搬** → `core/loop/src/execute.cpp`／`.hpp` | S4 | inst/cli.md 刪列 |
| `core/inst/CMakeLists.txt` | 改：CLI SOURCES／`exec` 子命令刪除／測試 SOURCES | S4/S6/S9 | build.md |
| `core/inst/tests/test_timeout.cpp` (155) | 改：四案搬走、一案改寫、一案併走 | S6 | inst/tests.md |
| `core/inst/tests/test_run_init.cpp` (50) | 改：exec 斷言搬走＋`control.tempd/` 斷言 | S4/S9 | inst/tests.md |
| `core/inst/tests/test_run_deliver.cpp` (270) | 改：整合案搬走 | S4 | inst/tests.md |
| `core/inst/tests/test_run_support.hpp` (93) | 改：拆一半去 loop | S4 | inst/tests.md |
| `core/inst/tests/test_run_loop.cpp` (188)／`test_run_handoff.cpp` (162)／`test_run_batch.cpp` (82) | **搬** → `core/loop/tests/` | S4 | inst/tests.md 刪列 |
| `core/inst/tests/test_exec_handle.cpp` | **新** | S6 | inst/tests.md（新列） |
| `core/inst/tests/test_capi.c` (246) | 改：釘住 `execute` 新語意 | S6 | inst/tests.md |
| `core/loop/CMakeLists.txt` | **新** | S3–S9 | build.md（新列） |
| `core/loop/include/aos/loop.hpp` | **新**：`RoundOutcome`／`BatchResult`／`run_once`／`run` | S3/S5 | loop.md（新冊） |
| `core/loop/src/round.cpp` | **搬入＋改**：回合編排（fs helper 抽走後 ~160 行） | S4/S5 | loop.md |
| `core/loop/src/loop_fs.cpp`／`.hpp` | **新**：turn／小檔讀寫（inst 的 `handoff_fs` 是內部標頭，跨不過來） | S5 | loop.md |
| `core/loop/src/decode.cpp` | **新**：decode 階段（B4 歸位） | S5 | loop.md |
| `core/loop/src/execute.cpp`／`.hpp` | **搬入＋改**：execute 階段＋逐 slot 計時 | S4/S5/S6 | loop.md |
| `core/loop/src/deadline.cpp`／`.hpp` | **新**：計時（原 `wait.cpp` 的 `wait_until` 等） | S6 | loop.md |
| `core/loop/src/writeback.cpp` | **新**：算 `BatchResult`＋寫 header＋release＋turn | S7 | loop.md |
| `core/loop/src/control.cpp`／`.hpp` | **新**：control inbox | S9 | loop.md |
| `core/loop/src/loop.cpp` | **搬入＋改**：迴圈＋睡眠＋退避＋停機 | S4/S5/S8 | loop.md |
| `core/loop/src/run.cpp`／`run.hpp`／`loop_internal.hpp` | **新／搬入**：argv＋`aos_exec_cli_main` | S4 | loop.md |
| `core/loop/tests/test_loop_support.hpp`／`test_loop.cpp`／`test_round.cpp`／`test_execute.cpp`／`test_timeout.cpp`／`test_writeback.cpp`／`test_backoff.cpp`／`test_control.cpp` | **新／搬入** | S4–S9 | loop.md |
| `core/loop/docs/loop.md` | **新** | S10 | —（同 inst/docs，不進 code map） |
| `core/CMakeLists.txt` | 改：`add_subdirectory(loop)` 一行 | S3 | build.md |
| 根 `CMakeLists.txt`、`app/`、`cmake/AosSubproject.cmake` | **不動** | — | — |
| `docs/SPEC.md` | 改：新 G 區＋§B-2／§C-3／§D-9＋摘標＋已知未決（主線） | S1/S11 | — |
| `docs/usage.md`／`docs/subprojects.md`／`docs/build.md` | 改 | S10 | — |
| `core/inst/docs/format.md`／`exec.md`／`architecture.md`／`capi.md`／`cxxapi.md` | 改 | S10 | — |
| `wf/workflows/common/code-map/loop.md` | **新**（第五冊） | S10 | — |
| `wf/workflows/common/code-map.md`／`code-map/build.md`／`code-map/inst/{library,cli,tests}.md` | 改 | S3–S10 | — |
| `wf/workflows/common/gotchas.md`／`conventions.md` | 改：三條過帳＋單向分層的 grep checklist | S10 | — |
| `wf/workflows/ideas/verdicts.md`／`machine-shape/loop.md`／`core-layering.md` | 改 | S0/S10 | — |
| `wf/workflows/roadmap.md`／`wf/SESSION-LOG.md` | 改：收尾 | S11 | — |

**明確不動**：`core/inst/src/` 的 `format*.cpp`／`resolve.cpp`／`inst.cpp`／
`spawn_prep.*`／`handoff.cpp`／`handoff_fs.*`／`handoff_deliver.cpp`／`capi*.cpp`
（S7 只在 `handoff_header` 加一個寫入函式）、`run_deliver.cpp`；
`app/src/main.cpp`；`cmake/`；根 `.gitignore`；`core/tooljson/`、`core/llms/`。

---

## 六、風險與退路

1. **搬遷中途 ctest 紅怎麼回退**。
   對策：**S3／S4 是「加骨架」與「純 rename」兩個獨立 commit**，S4 的 diff 幾乎全是
   rename ＋ CMake 改線，`git revert` 乾淨；S5–S9 各自是獨立 commit，任何一個炸掉都可以
   單獨 revert 而不影響已搬好的目錄結構。
   最壞退路：revert 到 S4 之後的狀態——**目錄已分家、行為與 M1 完全相同**，那本身就是
   一個有價值的中間態（roadmap M2 完成定義的第一條已達成）。

2. **`merged` preset 壞掉**（最容易被漏掉的一條）。
   兩個實測過的地雷：
   (a) **`PRIVATE_DEPS aos::inst` 會讓 `libaos.so` 長出 `NEEDED libaos_inst.so.0`**
   ——根 `CMakeLists.txt` 只把 `aos::<小專案>` 從 **public** 相依清單濾掉，private 那份
   原樣灌進 `target_link_libraries(... PRIVATE ...)`。**必須用 `PUBLIC_DEPS`**（裁-14）。
   (b) `merged` **沒有 testPreset**，`ctest --preset merged` 會直接失敗——要用
   `ctest --test-dir build/merged`。
   守門：S3 起每一步都跑 `readelf -d build/merged/lib/libaos.so | grep NEEDED`，
   不得出現 `libaos_inst.so`。
   退路：真的濾不掉就在根 `CMakeLists.txt` 補一段把 `aos::` 也從 private 清單濾掉
   （但那是動骨架，要另外過閘門）。

3. **C ABI 破壞**。
   簽名層面：S2 是純新增，不動任何既有列舉值與 struct 佈局，`capi.cpp` 的 `static_assert`
   不用改（裁-2 決定 M2 不開新 C ABI，連新增都免了）。
   **行為層面有一個真的破壞**：`aos_instruction_execute` 設了 `timeout_ms` 之後不再逾時
   （裁-3）。**現有測試抓不到**（那筆設 1000 ms 但指令是 `exit 7`，本來就不逾時）。
   對策：S6 必須補測試 ＋ 改 `inst.h`／`capi.md`／`cxxapi.md`／`exec.md` 的文字。
   退路：若主線改判裁-3，退回裁-1 的 C 案（`execute_bounded`），S6 只改一個函式簽名。

4. **反向相依（`core/inst` 知道 loop）**。
   三道機械防線（實測過）：① CMake 直接 configure 失敗——SHARED 之間不允許相依環，
   錯誤訊息是 `The inter-target dependency graph contains the following strongly
   connected component (cycle)`；② 沒宣告就 `#include <aos/loop.hpp>` 會
   `fatal error: No such file or directory`（include dir 只透過 `aos::loop` 的 usage
   requirement 傳播）；③ 只剩相對路徑硬穿這條漏洞，用
   `grep -rn 'aos/loop\|\.\./\.\./loop' core/inst/` ＋
   `grep -n 'loop' core/inst/CMakeLists.txt` 蓋掉。
   **不建議**為此新增 CI 腳本（repo 目前沒有 `.github/`、沒有 `scripts/`）——把那兩行
   grep 寫進 conventions 的「單向分層是鐵律」底下當 checklist 就夠。

5. **雙重計時窗口**（S6 內部）。
   若 loop 已開始計時、`exec.cpp` 也還在計時，短的先觸發、長的對著**已收屍**的 pid 發
   `kill(-pid)` ——pid 可能已被系統重用，打到別人的行程群組。
   對策：S6 的「抄走 `timeout_ms` 之後歸零」手法，保證任何時刻只有一個計時者。
   驗證：S6 結束時 `grep -n "timeout_ms" core/inst/src/exec.cpp` 必須零筆。

6. **`kill(-pid)` 與 pid 回收的時序**。
   現行「收掉領頭者之後補一發 SIGKILL 掃群組」是**刻意**的（註解在 `exec.cpp`），
   所以 `ExecHandle` 保留 `reaped` 旗標而**不是**把 pid 清成 -1，`signal_child_group`
   在 `reaped == true` 時仍可呼叫。**MUST NOT** 給 `ExecHandle` 寫自動 reap 的解構子
   （會偷偷改掉「`wait_until` 出錯時不 kill 不 reap」這條刻意設計）。

7. **兩種睡眠的 EINTR 語意相反，別共用 helper**。
   `wait.cpp` 的 `sleep_ms` 用 `remaining` **續睡**（逾時要準）；`run_loop.cpp` 的
   `sleep_milliseconds` **不處理 EINTR**（刻意讓訊號叫醒空轉睡眠，
   `"exec loop does not run another round after a signal wakes idle sleep"` 就是釘這個）。
   兩個都要進 `core/loop`，很容易被順手合併——合併就會讓逾時提早觸發，或讓 Ctrl-C
   叫不醒空轉。**兩個檔分開放**（`deadline.cpp` vs `loop.cpp`），各自留註解。

8. **不要碰 SIGCHLD**。現行完全靠輪詢。改用 SIGCHLD／`signalfd` 會撞上：`LoopSignals`
   已用 `SA_RESETHAND` 佔了 SIGINT／SIGTERM；而且函式庫不能假設宿主行程的 SIGCHLD
   disposition（宿主設 `SIG_IGN` 時子行程自動收屍，`waitpid` 回 `ECHILD`）。M2 照抄輪詢。
   同理 **`waitpid(-1)` 永遠不准出現**——會偷走 `aos_instruction_execute` 呼叫者自己的
   子行程。現行只用 `waitpid(specific_pid)`，這條不能破。

9. **`parallel` × 逾時 ＝ N 個並行 deadline**。現行是 thread-per-parallel，
   **照抄這個模型**：每條 thread 自己 spawn／poll／kill／reap 自己的 pid，
   不需要多路 reaper。這條決定了 3.2 節的 API 是 per-handle 而不是 per-set。

10. **測試搬家造成的覆蓋漏洞**。`test_run_support.hpp` 被五支測試共用，拆一半之後
    很容易漏掉某個 helper。對策：S4 結束時比對「搬遷前後 `--list-tests` 的案名總集合」
    ——**只准多、不准少**（改名的逐一對照）。

11. **`.aos` 版面常數跨小專案重複**。`kAosDir`／`kVersionPath`／`kInstPath`／`kTurnPath`
    今天已在 `run_exec.cpp`／`run_init.cpp`／`run_deliver.cpp` 各抄一份，切開後變成兩個
    小專案各抄。**M2 接受這份重複**（裁-15 同一取捨：不為此擴公開 API），但要在
    code map 的 loop 分冊記一句「版面若變，`core/inst` 與 `core/loop` 兩處都要改」。

12. **`--help` 的子命令順序會變**（`exec` 從第一排到 `init`／`deliver` 之後，因為
    `add_subdirectory(loop)` 在 `inst` 之後）。純觀感，但 `docs/usage.md` 貼的是實跑輸出
    ——S10 要重貼。想保住原順序就把 `add_subdirectory(loop)` 提到 `inst` 之前（實測
    configure／generate 都過，ALIAS 是延後解析的），但那會讓 `core/CMakeLists.txt` 的
    順序與相依方向相反，**不建議**。

13. **停機條件誤判「一批壞 JSON」**（裁-9b 沒做好的後果）。若 S5 沒把回傳值分層，
    連續丟進 N 批語法錯誤的投遞就會讓 loop 以退出碼 4 停機——那是完全正常的使用方式。
    守門：S8 的測試 ⑤ 就是專門釘這個。

14. **控制記錄的誤投面**（新增第二個投遞匣必然產生）：診斷訊息不帶匣名的話，
    投錯匣的人只看得到「UnknownKey」。S9 要求所有交接診斷帶匣名，成本接近零。

15. **`stop` 是 at-least-once**：崩在「讀到 stop」與 unlink 之間，重啟會再停一次。
    `stop` 冪等所以不會壞事，但要在 stderr 說清楚（`stopping: control record <名字>`），
    否則使用者會以為 loop 起不來。條款照實寫，不要假裝 exactly-once。

---

## 七、外包切分（誰做哪步、驗收怎麼收）

判斷型給 Opus 實作 agent，機械型由 Opus 轉派 sonnet；**SPEC 條款起草與一切
`docs/SPEC.md` 修改保留給主線**（AI 不得自行修憲，條款清單見第二節）。

| 步 | 給誰 | 性質 | 驗收怎麼收 |
|---|---|---|---|
| S0、S1、S11 | **主線** | 裁決／修憲 | 概括授權下，verdicts＋SPEC diff 自查 |
| S2 | **Opus** | 判斷型（拆 API、保住三處刻意設計） | `test_timeout.cpp` 一字不改仍全綠＋主線抽查 setpgid 那段沒被拆散 |
| S3 | Opus→**sonnet** | 機械（CMake 抄範本） | ctest 5 支全綠＋merged 的 `readelf -d` 守門 |
| S4 | **Opus**（rename 與 CMake 可轉 sonnet，測試拆分 Opus 把關） | 機械＋判斷（測試拆分） | `--list-tests` 案名集合只准多不准少；diff 幾乎全是 rename |
| S5 | **Opus** | 判斷型（四階段切分、`RoundOutcome` 設計） | ctest 綠＋`RoundOutcome` 五情境測試＋簽名主線過目 |
| S6 | **Opus** | 判斷型（計時搬遷，最危險的一步） | 四案逐案對照通過＋兩個 grep（`exec.cpp` 零筆／格式層仍有）＋`test_capi.c` 新案必在 |
| S7 | **Opus** | 判斷型（值域判準、寫入順序） | 四值 grep 只在 `core/loop`＋`null` 初值案 |
| S8 | **Opus** | 判斷型（退避參數、停機條件） | spec 驗收 2／7 |
| S9 | **Opus**（`run_init.cpp` 那一改可轉 sonnet） | 判斷型（協定細節、邊緣狀況） | spec 驗收 3＋煙霧輸出留存（供 S10）＋四個邊緣狀況案必在 |
| S10 | Opus→**sonnet**（usage.md 實跑部分 Opus 把關） | 機械＋鐵律驗證 | 文件內命令逐條實跑核對；code map 五冊 diff 對表；`grep -rn "busy poll" docs/` 零筆 |

任務書共通條款（發包時附上）：本 plan 對應步驟全文 ＋ spec「明確不做」 ＋ keep.md 保護項
＋ conventions 的分層鐵律與 300 行門檻與 C ABI 規則 ＋ 「每步 ctest（default **與**
merged）綠才交件、code map 同 commit」 ＋ 風險節的第 5～9 條（那五條是會真的炸的）。
背景等待期間不輪詢。

---

## 八、驗收對照（spec 12 條 ↔ plan 步驟）

| spec 驗收 | 對應步驟 | 機械檢查 |
|---|---|---|
| 1. `core/inst` 不再知道 loop | S3／S4 | 四個 grep（`core/inst/src` 與 `include` 無 loop 字眼／CMakeLists 無 `run_loop.cpp` 與 `exec` 子命令／無 `aos/loop`／loop 端有 `PUBLIC_DEPS aos::inst`）＋ CMake cycle 檢查 |
| 2. 一批全失敗會退避 | S8 | `test_backoff.cpp` 兩案（圈數上界／重置） |
| 3. control inbox `stop` 停在回合邊界、退出碼 0 | S9 | `test_control.cpp` ＋ S9 煙霧 |
| 4. timeout_ms 由回合層砍 | S2／S6 | 兩個 grep ＋ `test_timeout.cpp` 四案逐案對照 ＋ 一案留 inst 改寫 ＋ 一案留格式層 |
| 5. header `result` 四種值 | S7 | `test_writeback.cpp` 四案 ＋ `null` 初值案 ＋ 四字串只在 `core/loop` 的 grep |
| 6. `--loop 0` 不忙碌輪詢 | S4／S10 | 既有兩案搬家後仍綠 ＋ `grep -rn "busy poll" docs/` 零筆 |
| 7. 新退出碼 | S1／S8 | §D-9 有那一行 ＋ 測試真的拿到 4 |
| 8. ctest 全綠（含 `aos_loop_tests`）、merged 可建 | 每步 | `ctest --preset default` ＋ `ctest --test-dir build/merged` ＋ `readelf -d` 守門 |
| 9. code map 同步 | S3–S10 | 五冊 diff 與新增／刪除檔一一對應 |
| 10. usage.md 更新且命令實跑 | S9／S10 | 逐條重跑核對；`--help` 輸出重貼 |
| 11. SPEC `(planned, M2)` 零筆 | S1／S11 | `grep -n "planned, M2" docs/SPEC.md` 零筆 ＋ 已知未決 #4 消失（現況只有兩筆待清） |
| 12. 格式版本沒被動到 | S6／S11 | `grep -n '"version":1' core/inst/src/handoff_header.cpp` 仍在；§F-1 未變；`format_encode.cpp`／`format_decode.cpp` 的 `timeout_ms` 零改動 |
