# M2 exec_loop 落地分層 — 規劃 spec

← [build-cycle](../README.md)｜[roadmap M2](../../roadmap.md)｜[SPEC](../../../../docs/SPEC.md)

**閘門 ①／② 由使用者概括授權**（2026-08-28 `/goal`：調度者統籌、一路做到完全）。
先裁的問題由主線依下列方向拍板，落檔時記入 [verdicts A 表](../../ideas/verdicts.md)
＋ `docs/SPEC.md`。

> **調度者裁決（2026-08-28，實作層級；plan 第一節的提案未列者一律採建議案）**：
> 裁-1 超時機制採 **A 案**（inst 出 spawn／poll／reap／signal 非阻塞入口，`execute()` 簽名不動，
> 計時鏈搬 `core/loop`）；裁-4 **先純搬再重構**；裁-0 SPEC **新開 G 區**（§A-7／§A-8 進 A 區）；
> 裁-5 header `result` 四值 `"ok"/"partial"/"failed"/"machine_failed"`；裁-9 停機 **N=10、退出碼 4**；
> 裁-8b **不加** kFloor（照裁決 3 原文立法 1 ms）；裁-10/11/12 `.aos/control.tempd/`＋
> `{"op":"stop"}`（恰好一個 key）＋消化用 **unlink**；裁-14 `core/loop` 對 `core/inst` 用 **`PUBLIC_DEPS`**；
> 裁-9b 回傳值先分層（S5）。「調度者須知」八條全部採納（§25 寫成判準＋窮舉表、§26 改寫成
> 「控制面 MUST 不依賴任何 inst 能跑」、format.md／usage.md 的 timeout 範例要改、逾時算有進展、
> verdicts D 表 `did_work` 那列更正、§B-2 承認三個既有命名例外）。**已知未決 #1（SIGINT）不裁**，留給使用者。
> 另兩件由 M3 規劃隊轉來、M2 實作順手收：① writeback 前用 `decode_header_id()` 比對 header `id`，
> 不符只 warning（防第二支 exec 覆蓋批 N 的 header 後 `result` 寫錯檔）；② verdicts A 表
> 「回合歷史加在 loop」那列依裁決 1 改歸系統 inst。**M1 審查修補須先於本階段動工**（同動 `core/inst/src`）。

## 一句話

把**回合**這件事從 `core/inst` 整包搬出來，成為第二個核心小專案 **`core/loop`**：
`core/inst` 退回「機制」（inst_t／format／resolve／handoff／單筆 spawn-wait），
`core/loop` 接手「政策」（fetch→decode→execute→writeback 四階段、計時與砍行程、
睡眠與退避、控制窗口）。同時把 loop 唯一的那個 `if`（`result == 3`）換成**讀得懂
批次結果**的控制流。

---

## 本階段裁決（主線裁，五項，方向已定不翻案）

### 裁決 1 — §25 接受：loop 只收「無法成為 inst 的東西」

**判準（可直接抄進 SPEC）**：一件事歸 loop 的**充要條件**是——它**必須在沒有任何
inst 可跑的時刻運作**。照此判準歸 loop 的封閉清單：**claim（fetch）、decode 調度、
execute 調度、writeback、睡眠／退避、控制窗口、崩潰偵測**。其餘一律是**系統 inst**
（這台機器上的 OS），**MUST NOT** 寫成 loop 的 C++。

**直接推論（三條，一併立法）**：
1. **B6 裁掉**：跨資料夾排程屬 OS 層（做成 inst），`exec_loop` 的介面就是「跑**這個**
   資料夾」，不是「跑這一組」。
2. **中斷欠帳（doorbell）歸 loop**：它必須在回合**之間**醒著＝真硬體。M2 只裁歸屬，
   不實作。
3. **回合歷史歸系統 inst**，不是 loop 的 C++——因此**不在 M2**。

**代價認列（照實寫進條款的來源註，不含糊）**：系統 inst 需要「**彙整層注入策略**」
——那是**一個**新機制換掉 N 個 loop 功能，M2 **不做**。注入機制的設計排 M3 之後、
與名冊裁決（§29）一起看。回合歷史因此不在 M2（roadmap 的 M2 完成定義本來就沒有它）。

### 裁決 2 — §26 接受（投遞協定側）：控制面走 control inbox

**判準**：控制這台機器與對它下指令**同構**——都是「寫一份檔進一個收件匣」。
控制面 **MUST** 走投遞協定：loop 持有一個 **control inbox**（`.aos/` 之下，目錄名照
§B-1 命名標準），寫入 **MUST** 先 `.temp` 後 `rename`。**MUST NOT** 另開 signal／
pid 檔的 ad-hoc 通道（既有的 SIGINT／SIGTERM 收尾行為不變、不擴充）。

**v1 的動詞集合封閉為一個**：`stop` ＝ **跑完當前回合後停下，退出碼 0**。
`step`／`hold` **不在 M2**。

**不新增子命令**（守住 §29 名冊封閉的候選判準）：控制記錄用檔案協定直接寫，文件給
可複製的範例；要不要給 `deliver` 加 `--control` 旗標留 M3 跟 §29 一起裁。

### 裁決 3 — `--loop 0` 條款化：0 間隔不存在忙碌輪詢

**0 間隔 MUST NOT 忙碌輪詢**：沒有工作時 **MUST** 至少睡一個最小間隔。現行實作已是
「warn ＋視為 1 ms」，**照實立法**（條款寫行為，不寫常數的來歷）。
inotify 之類事件驅動 **MAY** 在未來取代睡眠，**語意不變**（「沒工作就不燒 CPU」是
規範，睡眠只是目前的實作手段）。

### 裁決 4 — 節流判準：「有沒有**進展**」取代「有沒有**做事**」

- loop 於 **writeback** 把批次的彙總狀態寫進 header 的 `result` 欄（§C-8 在 M1 立的
  欄位在此活起來）。**值域四選一**：全成功／部分失敗／全失敗／庫層失敗
  （確切字串由 plan 提案、主線於 SPEC 定案）。
- **無進展 ＝ 全失敗 或 庫層失敗** → **MUST 退避**（指數退避、**MUST** 有上限）。
- `did_work` 的語意**修正為「這一圈有沒有取到批次」**，並且**不再單獨決定睡不睡**
  （睡不睡由「有沒有進展」決定）。
- loop **MUST NOT** 再只認 `3`：庫層失敗要**計數**，連續 N 次 **MUST** 停機報錯
  （新退出碼），不再無聲丟棄。

### 裁決 5 — timeout_ms 搬遷的落點：v1 ＝ **語意搬遷**

- 欄位**留在 inst schema**：`§C-3` 的 `timeout_ms` 不動、encode／decode 不動、
  **不 bump §F-1 格式版本**。
- **計時與砍行程的所有權移到回合層**（`core/loop`）：`exec` 最內圈（單筆 spawn／
  wait）**不再自帶計時**——它不再認得 `timeout_ms` 這個欄位的存在。
- 欄位**徹底移出 schema 留給格式 v2**（屆時走修憲，走 §F-1 遞增）。
- **為什麼是語意搬遷而不是欄位搬遷**：欄位若現在就移出 inst schema，就得在「loop 先
  把 loop 專屬欄位剝掉再交給 exec」與「exec 改成忽略未知 key」之間二選一，後者違反
  [keep](../../ideas/call-format/keep.md)（未知 key 拒絕是這個格式做對的事之一）、
  前者等於憑空生出第二份 schema。**語意搬遷同時避開兩難**。

---

## 調度者須知（讀程式碼與 ideas 時挖到的八處，**裁決本文一律不改**）

1. **header `result` 的保存期非常短**：`inst-head.json` 是**當前批次**的 sidecar，
   下一輪彙整發布新批次時就會被覆蓋。因此 loop **不需要**「讀回 header 才能退避」
   ——它退避用的是**自己剛算出來的**那個結果；寫 `result` 是為了**可觀察性**與交棒
   給 M3 的回合歷史。**條款要把「算出結果 → 決定退避」與「把結果寫進 header」分成
   兩句寫**，否則會被讀成「loop 必須讀 header 才能節流」。
2. **「result」這個字在兩處指不同東西**：SPEC §C-8 的 header 欄位 `result`，與
   `run_exec_once` 目前那個 `int result`（＝退出碼）。loop.md 第 15 條說的「`result`
   只有 `== 3` 被用過」講的是後者。**條款與程式碼都 MUST 分開命名**（建議：header
   欄位保留 `result`，回合返回值改叫 `RoundOutcome`／不再叫 result）。
3. **裁決 1 把「回合歷史」推給系統 inst，但注入機制排在 M3 之後**——意思是 M2 結束
   時，「loop 崩潰後人手上只有一個 `.runi`、沒有它為什麼死的資訊」（loop.md 第 9 條）
   **仍然成立**。這是裁決 1 的代價、不是缺口，但要在 roadmap 上留一行，免得 M3 以為
   它已經解決了。
4. **裁決 4 的四個值沒有「逾時」這一格**，而 `docs/exec.md` 與 §D-9 既有語意是
   「逾時＝一次**已完成**的執行」。照既裁推下去，**一批全部逾時 ＝ 全成功 ＝ 有進展
   ＝ 不退避**。這在「外部服務掛掉、每筆都等滿逾時」的情境下不會燒 CPU（每輪本來就
   耗掉 `timeout_ms`），所以我判斷可以接受，但它是 loop.md 第 14 條那個老坑的近親，
   plan 會把它列成一條要主線點頭的提案（不新增第五個值＝不翻案）。
5. **裁決 5 會讓 `core/inst/docs/format.md` 自打嘴巴**：那份用來論證「未知 key 必須
   拒絕」（§C-5 的理據來源）的例子，寫的正是「較舊的執行檔可能會默默執行一筆含有
   `timeout_ms` 的記錄，卻完全沒有 timeout」——搬遷後 `aos::execute`／
   `aos_instruction_execute` **就是這個行為**。那段文字 **MUST** 在 M2 改寫，換一個
   不自打嘴巴的例子；§C-5 條款本身不動。**同一個代價還有第二處**：
   `docs/usage.md` 第二節「一個完整的例子」正好示範 `job.timeout_ms = 1000;` 後直接
   呼叫 `aos::execute()`——那個範例搬遷後會無聲失去逾時，也 MUST 改。
6. **§25 的判準推不出它自己的列舉**：判準是「必須在**沒有任何 inst 可跑的時刻**
   運作」，但列舉裡的「decode 調度、execute 調度、writeback」恰恰是**有 inst 可跑時**
   才運作的——列舉比判準寬。這不影響 M2（列舉是拍板的內容），但將來拿判準去裁新東西
   會得到跟列舉不一致的答案。**建議條文寫成「判準 ＋ 窮舉表，衝突時表優先」**，別讓
   判準單獨承重。
7. **裁決 4 有一個 spec 沒點名的隱形前置：現行程式碼分不出「庫層失敗」**。
   `run_exec_once` 回 `1` 的來路至少七種（進不了 folder／`.aos` 壞／版本不認得／
   aggregate 失敗／release 失敗／turn 遞增失敗／`execute_batch` 回 1），而
   `execute_batch` 自己又混了三種完全不同的東西（整批 JSON 解析失敗、指示詞求值失敗、
   單筆 `ExecState` 失敗）。**不先把回傳值分層，「一批壞 JSON」會被算成庫層失敗，
   連續幾圈就把世界停機報錯**——那是誤判。plan 把「回傳值分層」列為 writeback 與退避
   的前置步驟。
8. **裁決 4 的 `did_work` 修正，M1 已經順手做掉一半**：loop.md 第 21 條說
   `did_work = true` 設在 `execute_batch` **之前**；現行程式碼是設在 `claim_instruction`
   **成功之後**，語意已經正好是「取到批次」。所以裁決 4 的後半只剩「不再單獨決定睡不睡」
   要做。**verdicts D 表那條要一併更新**，否則實作隊會去改一個已經對的東西。

---

## 做完之後長什麼樣（結果狀態）

1. **`core/loop` 這個核心小專案存在**（名詞命名，與 `core/inst` 同式），
   `aos exec` 與 `aos exec --loop` 背後連的都是它。文件裡有一句
   「**小專案獨立 ≠ 命令獨立**」，防止之後被當成兩份真相。
2. **`core/inst` 不再知道 loop**：它的 `src/` 底下沒有任何回合編排、睡眠、退避、
   控制窗口的程式碼；它的公開標頭不出現 loop 的型別。相依單向 `inst ← loop`。
3. **四階段管線就位且各有名字**：**fetch**（aggregate＋claim）→ **decode**
   （read_all＋resolve，B4「resolve 屬 decode」歸位）→ **execute**（含計時與砍行程）
   → **writeback**（算出彙總狀態、寫 header `result`、release、遞增 turn）。
4. **loop 有可分支的狀態**：它讀得懂批次結果——全成功／部分失敗照常續跑；**全失敗**
   或**庫層失敗**進入指數退避；庫層失敗**連續 N 次**停機並以新退出碼報錯。
5. **control inbox 就位**：投一份 `stop` 記錄進去，loop 在**回合邊界**停下並以 **0**
   退出（Ctrl-C 之外的辦法，roadmap M2 完成定義第三條）。
6. **`--loop 0` 不燒 CPU**：條款與實作一致，`docs/usage.md` 那句「`--loop 0` 合法，
   但會 busy poll」改掉。
7. **timeout_ms 由回合層砍**：`exec` 層的計時碼消失，既有的逾時行為（SIGTERM →
   寬限 → SIGKILL 整個行程群組）**一模一樣**，只是由回合層驅動。
8. **SPEC 更新**：§25／§26 條款化（loop 職權判準、控制面）、四階段管線、writeback 的
   值域、節流與退避、`--loop 0`、timeout_ms ownership、新退出碼、版面樹加 control
   inbox（**條款放哪一區由 plan 提案、主線裁**）；`(planned, M2)` 摘標歸零；
   已知未決 #4 消掉。

---

## 驗收條件（每條都可機械檢查）

1. **`core/inst` 不再知道 loop**（四個 grep，每個都要零筆）：
   - `grep -rn "run_exec_loop\|run_exec_once\|execute_batch\|run_batch\|--loop\|control\.tempd" core/inst/src/ core/inst/include/`
   - `grep -rn "aos/loop\|aos::loop\|aos_loop\|\.\./\.\./loop" core/inst/`
   - `grep -n "loop" core/inst/CMakeLists.txt`（含「沒有 `run_loop.cpp`、沒有登記
     `exec` 子命令」）
   - 而 `core/loop/CMakeLists.txt` **必須有**指向 `aos::inst` 的相依（單向）。
   另加一道**編譯期**證明：在 `core/inst/src/` 任一檔插入 `#include <aos/loop.hpp>`
   會 `fatal error: No such file or directory`；在 `core/inst` 加 loop 相依會讓 CMake
   以 `strongly connected component (cycle)` 直接 configure 失敗。
2. **一批全失敗會退避**（roadmap 完成定義第二條）：`core/loop/tests/` 有**確定性**
   測試——loop 的內部標頭開一個**只給同專案測試用的睡眠 hook**（測試 target 連的是
   CLI 的 OBJECT library，看得到 `src/` 的內部標頭，`test_run_support.hpp` 就是這樣
   include `../src/run.hpp` 的），記錄每次「要睡多久」的請求，斷言：
   ① 佈置一批**每筆都庫層失敗**的 inst（不是子行程回非零——那不算失敗），第 n 次
   無進展請求的睡眠 ≥ `2^(n-1) × 基數` 且 ≤ 上限；② 中間插一個**有進展**的回合後
   計數歸零；③ **空回合（沒取到批）不累積退避、也不重置**，睡的是基數。
   **不靠牆鐘量測**（會 flaky）。牆鐘版本只當煙霧，沿用既有
   `exec loop throttles failures that happen before a round starts` 的手法。
3. **control inbox `stop` 讓 loop 在回合邊界停下**：測試——起 loop、投一份 `stop`
   記錄、斷言 loop **跑完當前回合後**返回、**退出碼 0**、且該控制記錄**已被消掉**
   （重啟不會立刻再停一次）。另有一條煙霧測試在 `docs/usage.md` 貼實跑輸出。
4. **timeout_ms 由回合層砍**：
   - `grep -n "timeout_ms" core/inst/src/exec.cpp core/inst/src/wait.cpp` **零筆**；
     `grep -n "timeout_ms" core/inst/include/aos/inst.hpp core/inst/src/format_encode.cpp
     core/inst/src/format_decode.cpp core/inst/src/capi_instruction.cpp` **仍有**
     （欄位沒被誤搬——那是裁決 5「語意搬遷不是欄位搬遷」的證據）。
   - 既有 `core/inst/tests/test_timeout.cpp` 的六案**逐案過帳、行為不變**：
     `timeout terminates a command process group`／`fast command does not pay a polling
     interval`／`timeout kills grandchildren`／`timeout kills a grandchild that ignores
     SIGTERM` **四案搬 `core/loop/tests/`**（改打回合層入口）仍通過；
     `zero timeout uses normal blocking execution` **留 inst**、改寫成「`execute` 阻塞
     至子行程結束」；`timeout format reads writes and rejects invalid values`
     **留 inst**（格式層的案子，欄位沒搬）。
   - **必須有一個新案**釘住「設了 `timeout_ms` 之後 `aos_instruction_execute` 仍阻塞
     到子行程自行結束」——既有 C ABI 測試抓不到這個語意變更。
5. **header `result` 由 loop 寫，四種值**：測試逐一產生四種批次，讀 `inst-head.json`
   斷言 `result` 的字面值；並斷言 `core/inst` 端寫出的初值仍是 `null`（彙整寫 header
   時不知道結果）。`grep -rn "result" core/inst/src/handoff_header.cpp` 只出現在
   「寫 `null`」與欄位名，不出現四個值之一。
6. **`--loop 0` 不忙碌輪詢**：既有兩案
   （`exec loop zero interval warns once and uses one millisecond`、
   `exec loop zero interval no longer busy polls startup failures`）搬到
   `core/loop/tests/` 後仍通過；`docs/usage.md` 不再出現「busy poll」字樣。
7. **退出碼**：新的「連續庫層失敗停機」退出碼在 SPEC §D-9 的表裡有一行，且有一個
   測試真的拿到那個碼；`0`／`1`／`2`／`3` 的既有語意一字不改。
8. **`ctest --preset default` 全綠**（含 `aos_loop_tests` 這個新 target），
   `cmake --preset merged` 仍能設定並建置成功。
9. **code map 同步**：`wf/workflows/common/code-map/` 多一冊 `loop.md`、總圖
   `code-map.md` 的表加一列、`code-map/build.md` 的 `core/CMakeLists.txt` 那列反映
   多出來的 `add_subdirectory(loop)`；`code-map/inst/cli.md` 不再列 `run_loop.cpp`
   等已搬走的檔。
10. **`docs/usage.md` 更新且命令實跑**：control inbox 的投遞範例、`--loop` 一節的
    退避說明、退出碼表加新碼——**每條命令與輸出都貼實跑結果**（feature-dev 鐵律）。
11. **SPEC `(planned, M2)` 零筆**：`grep -n "planned, M2" docs/SPEC.md` 無輸出；
    「已知未決 #4」消掉。（M2 開工前 M1 的 `(planned, M1)` 與已知未決 #2 應已清完；
    §D-9 要加碼之前先確認。）
12. **格式版本沒被動到**（證明裁決 5 是**語意**搬遷不是格式修改）：
    `grep -n '"version":1' core/inst/src/handoff_header.cpp` 仍在；§F-1 條文一字未變；
    `core/inst/src/format_encode.cpp`／`format_decode.cpp` 的 `timeout_ms` 處理零改動。

---

## 明確不做

- **回合歷史與注入（彙整層注入策略）機制**——裁決 1 的代價，M3 之後與 §29 一起。
- **`status`／`recover`／`check`**（M3）；**doorbell 實作**（M4 之後，M2 只裁歸屬）。
- **跨資料夾排程**（B6 已裁掉：OS 層）。
- **`timeout_ms` 欄位從 schema 移除**（格式 v2，走修憲）。
- **`step`／`hold` 控制動詞**、**`deliver --control` 旗標**、**新子命令**（M3／§29）。
- **§29 名冊裁決**本身。
- 以下是讀的過程中發現「順手就會膨脹」、**本階段一律不碰**的：
  - **`.runi` 不是鎖**（verdicts D 表唯一未修的實作缺陷）——`claim` 是 check-then-act。
    它住在 `core/inst` 的 handoff 層，不在搬遷面上；**M2 不修**。
  - **`aos exec` 退出碼不反映子行程成敗**（§D-9）與 exit status 的表達力
    （verdicts A 表「exit status 之後會改」）——不趁搬遷改。
  - **並行度上限**（loop.md 第 20 條的 fork bomb）——M2 只做「察覺並退避／停機」，
    **不加 thread 或行程數上限**（§C-7「沒有任何上限」是既裁的）。
  - **`core/inst` 改名 `core/exec`**（core-layering 的開放項）——`inst` 是名詞、
    `exec` 是動詞的既有訂定不動，M2 只新增 `core/loop`。
  - **`<aos/loop.h>` C ABI**——M2 不開（只出 C++ 公開標頭與 CLI 進入點），記進 ideas。
  - **`.aos` 版面的第二個軸**（verdicts B7，events／status）——control inbox 照 §B-1
    現行標準命名即可容納，**不趁機開新軸**。
  - **`aos init`／`aos deliver` 搬家**——依裁決 1 的判準它們不歸 loop，留在 `core/inst`。

---

## 動工前讀

[machine-shape/loop.md](../../ideas/machine-shape/loop.md) 全檔、
[core-layering.md](../../ideas/core-layering.md)（含邊緣狀況清單：超時誰砍、注入相依
方向、匯聚＝彙整?、專案改名與否）、
[machine-shape/debts.md](../../ideas/machine-shape/debts.md)、
[call-format/cpu-analogy.md](../../ideas/call-format/cpu-analogy.md)、
[verdicts](../../ideas/verdicts.md) A 表與 D 表、[keep](../../ideas/call-format/keep.md)；
`docs/SPEC.md` 全文（尤其 §A-6、§B-1／§B-2、§C-3／§C-8、D 區全區、§F-1）、
`docs/aos-folder.md`、`docs/usage.md`、`docs/subprojects.md`、`docs/build.md`；
[add-subproject](../../add-subproject.md)、`cmake/AosSubproject.cmake`、根
`CMakeLists.txt`、`core/CMakeLists.txt`、`core/inst/CMakeLists.txt`、`app/`；
[code map](../../common/code-map.md) 與 `code-map/inst/*.md`、`code-map/build.md`、
[conventions](../../common/conventions.md)（分層鐵律、300 行門檻、C ABI 規則）、
[gotchas](../../common/gotchas.md)；
程式碼現況 `core/inst/src/` 的 `run_loop.cpp`／`run_exec.cpp`／`run_batch.cpp`／
`run.cpp`／`run_internal.hpp`／`exec.cpp`／`wait.cpp`／`handoff*.cpp`、
`include/aos/inst.hpp`／`inst.h`、`tests/`；
M1 的 [spec](../archive/m1-loop-side/spec.md)／[plan](../archive/m1-loop-side/plan.md)
（header sidecar、turn、deliver 剛落地的樣子）。
