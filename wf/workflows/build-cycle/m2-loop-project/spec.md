# M2 exec_loop 落地分層 — 規劃 spec

← [build-cycle](../README.md)｜[roadmap M2](../../roadmap.md)

> **草稿**（2026-08-28）：M1 收尾後定稿；裁決屆時記 verdicts＋SPEC。

## 本階段裁決（主線裁，落檔時記 verdicts＋SPEC）

1. **§25 接受**：loop 只收「**無法成為 inst 的東西**」——必須在沒有任何 inst 可跑的
   時刻運作的：claim（fetch）、decode 調度、execute 調度、writeback、睡眠／退避、
   控制窗口、崩潰偵測。其餘（回合歷史、輪詢外部 CPU、排程器）＝系統 inst（這台機器
   上的 OS），**不寫成 loop 的 C++**。
   - 直接推論：B6 裁掉——跨資料夾排程屬 OS 層（inst），`exec_loop` 介面就是「跑這
     個資料夾」；中斷欠帳（doorbell）歸 loop（真硬體）。
   - 代價認列：系統 inst 需要「彙整層注入策略」——那是**一個**新機制，M2 不做
     （回合歷史因此不在 M2；roadmap M2 完成定義本來就沒有它）。注入機制設計排 M3
     之後、名冊裁決（§29）一起看。
2. **§26 接受（投遞協定側）**：控制面走投遞協定——loop 持有的 control inbox
   （`.aos/` 下，命名照 B 區標準），寫入走 temp＋rename 同構。**不開 signal／pid 檔
   的 ad-hoc 通道**。v1 只做 `stop`（跑完當前回合停，退出碼 0）；`step`／`hold` 留
   之後。**不新增子命令**（守住 §29 名冊封閉的候選判準）：控制記錄用檔案協定直接寫，
   文件給範例；要不要給 deliver 加 `--control` 旗標留 M3 跟 §29 一起裁。
3. **`--loop 0` 條款化**：0 間隔不存在忙碌輪詢——無工作時至少睡最小間隔（現行實作
   已是 warn＋視為 1ms，照實立法）；inotify 之類事件驅動 MAY 在未來取代睡眠，語意
   不變。
4. **節流判準**：「有沒有進展」取代「有沒有做事」——loop 於 writeback 寫 header
   `result`（M1 立的欄位在此活起來：全成功／部分失敗／全失敗／庫層失敗），**全失敗
   或庫層失敗＝無進展 → 退避**（指數退避、有上限），`did_work` 語意修正為「取到批
   次」且不再直接決定睡不睡。
5. **timeout_ms 搬遷的落點**：v1 ＝ **語意搬遷**——欄位留在 inst schema（格式不變、
   不 bump §F-1 版本），計時與砍行程由回合層（loop 專案）執行，`exec` 最內圈（單筆
   spawn／wait）不再自帶計時。欄位徹底移出 schema 留給格式 v2（屆時走修憲）。
   避開「loop 剝欄位 vs exec 忽略未知 key」兩難（後者違反 keep）。

## 做完之後長什麼樣

1. 新 core 小專案 **`core/loop`**（名詞命名，與 core/inst 同式；`aos exec --loop`
   背後連的是它——小專案獨立 ≠ 命令獨立，這句寫進文件防兩份真相）。
   `run_loop.cpp`／`run_exec.cpp`（回合編排：claim→resolve→execute→release→turn）
   ＋ `run_internal.hpp` 相關搬入；`core/inst` 退回 inst_t／format／resolve／handoff
   ／單筆執行，**不再知道 loop**。
2. 四階段管線就位：fetch（claim）→ decode（resolve，歸位）→ execute → writeback
   （loop 寫 header `result`）。
3. loop 分支不再只認 3：讀 header 旗標；全失敗→退避；庫層失敗（1）計數＋退避＋
   連續 N 次停機報錯（不再無聲丟棄）。
4. control inbox：`stop` 使 loop 在回合邊界停下（Ctrl-C 之外的辦法，roadmap 完成
   定義第三條）。
5. SPEC 更新（主線）：§25／§26 裁決條款化（loop 職權判準、控制面）、D 區退避與
   writeback 條款、`--loop 0`、timeout_ms ownership；`(planned, M2)` 摘標。

## 明確不做

回合歷史與注入機制（§25 代價，M3 之後）；`status`／`recover`／`check`（M3）；
doorbell 實作（M4 之後，僅裁歸屬）；跨資料夾排程（OS 層）；timeout_ms 欄位移除
（格式 v2）；`step`／`hold` 控制動詞；§29 裁決。

## 動工前讀

machine-shape/loop.md 全檔、core-layering.md（含邊緣狀況清單：超時誰砍、注入相依
方向、匯聚＝彙整?、專案改名 core/exec 否）、run_loop.cpp／run_exec.cpp 現況、
cmake/aos_add_subproject 機制（add-subproject 工作流）、SPEC D 區。

## 遺留給 plan 的問題（Fable plan agent 處理）

- 超時砍行程的機制（非阻塞入口 vs loop 持有 child handles）——core-layering 邊緣
  狀況第一條，plan 提案、主線裁。
- core/loop 與 core/inst 的 CMake 相依方向與 subcommand 掛載（exec 子命令從哪個
  lib 出）。
- 「匯聚（injection lib）＝彙整（aggregate）？」——M2 只搬不答，記 ideas。
