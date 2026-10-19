# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-16 收工（公司 → 回家）

使用者 17:00 關機下班，回家再繼續。

> **10-19 更新**：proto8-2 已併進 proto8（七批，見 [session log 10-19](session_logs/2026-10/2026-10-19.md#proto8-2-併進-proto810-19)）；下面 10-16 那套——食譜與廚房、門房 `aos exec`、`.aos` 捷徑、stdin 是正規入口、結束碼只是參考、SIGTERM 退 0（C-57／58／59／60／63、N-12／46～49／51／52／56 等）——**已作廢**，現行以 proto8 的 CONCEPTS／NORMS／CONVENTION 為準；舊 lib 在 git aa2fec1f。

1. **授權**：今天「可以隨意push」；回家開新 session 照 [user.md § push 授權](workflows/common/user.md#push-授權) 重問一次。事情交給子 agent、需要思考的派 fable，頂層只負責交流。使用者今天幾次說頭暈，要求 ELI5、一次一件、慢慢講。
2. **今天定的**（條號 C-57～C-67、N-46～N-56，全部草稿、程式未改）：
   - C-56 改成「KISS 是最高原則，也是最後原則」，加「寫什麼就做什麼」；`*_inherit`（N-26）帶回來。
   - 定義（食譜 `.aos/`）／stack（執行時站的資料夾）／工作區（使用者的成品區 `/ws`）／門房 `aos exec stack 定義`／`.aos` 捷徑；指標＝捷徑；工作區位置＝`AOS_WS`、讀它用 `$env`（N-45 改，選 A）；工具一律是定義資料夾；一般工具入口寫 `"cwd": {"$env": "AOS_WS"}`、agent 工具站自己的 stack；stack 放哪由呼叫方自由決定（[NORMS 定義與工作區](../proto8/NORMS/10-基礎設施-定義與工作區.md)）。
   - KISS 重審五件：N-10 刪（daemon 子項改寫在 ctl 的 `children`＝N-54）、daemon `adopt` 預設開（N-28）、N-52 收到 SIGTERM 優雅收工退 0、N-53 agent 由外面的 loop 驅動、兩種 kernel 不併（N-42）。
   - C-63 結束碼只是參考、結果看 JSON；C-64 用檔案為了借 Linux 讀寫權限。
   - 夜裡 frame 改名 **stack**（heap 保留給以後跨呼叫共用的記憶）。
3. **待辦**：
   - (a) 回家後開一個全新 fable 審整個架構：照 [user.md「審」的範圍](workflows/common/user.md#審的範圍)（不一致、冗餘、沒考慮的狀況、跟原則打架、基礎設施 → stdlib → agent／kernel 有沒有斷點）；報告最前面放「三分鐘看懂」；只攤問題、不改。
   - (b) 兩份網頁（食譜與廚房 `PgHcNRoMS2AABtGJAYCCEq`、概念頁 `QJjGNnKFhKeS7r1f5bHzu7`）的新 HTML 在公司機的 scratchpad；若沒發佈完，回家要重做（scratchpad 不跨機）。
   - (c) 待定：tasks 要不要改看 JSON、不看結束碼；agent 當工具誰包 loop；`AOS_WS` 誰設、沒設怎麼辦；每個小格還放不放 `ws` 捷徑等，見 [NORMS 待定](../proto8/NORMS/08-待定.md)。
   - (d) 程式全部還沒照今天的設計改。KISS 新順序：A 食譜與廚房落地 → B fsm／agent → C loop／daemon／窗 → D kernel → E 文件。

## 2026-10-16（公司 WSL）

1. **授權**：今天「隨意 push」；在公司 WSL；事情交給子 agent、頂層只交流；需要思考的派 fable。
2. **使用者叫停 KISS 批次**：撤回 10-15 深夜「都照推薦」、要重看（「我後悔惹QQ，等一下我想要重新看過」）。批次 1 已做可逐項翻案、批次 2～6 暫停 → [kiss/README 開頭註記](../proto8/thinking/2026-10-15-kiss/README.md)。
3. **C-56 本條改寫成「KISS 也是最後原則」**（使用者：不算子原則、合併進本條）：先滿足各類需求與其他原則，最後回頭把多餘的清掉；不拿「最乾淨、規則最少」抄近路 → [10-16 稿](../proto8/thinking/2026-10-16-kiss-last.md)。
4. **定義與工作區（食譜與廚房）已定、已寫進概念與規範，程式待改**：稿 [agent-inherit § 四](../proto8/thinking/2026-10-16-agent-inherit.md#四使用者決定10-16) 是唯一的決定清單（其餘節是 AI 提案）。新條 C-57～C-61、N-46～N-51（[分檔](../proto8/NORMS/10-基礎設施-定義與工作區.md)，草稿）；C-46、C-50 改字；N-27 後半被 N-50 取代、N-21～N-24 歸語法糖；沒點頭的 10 條在 [NORMS 待定](../proto8/NORMS/08-待定.md)。早上另定 C-56「最高也是最後原則」＋「寫什麼就做什麼」、N-26 `*_inherit` 還原。KISS 批次 2～6 要依新設計重看。
5. **KISS 重審五件拍板（10-16）已寫進概念與規範，程式待改**：[稿末尾](../proto8/thinking/2026-10-16-kiss-recheck.md#使用者拍板10-16)。新條 **N-52**（收到 SIGTERM＝優雅收工、做完該做的再結束、退 0；總則）、**N-53**（aos 的 agent 被外面 loop 一拍一拍驅動、定義不含 loop、連錯不數）、**N-54**（daemon 子項寫在 ctl 的 `children`）、**C-62**（agent 的定義＝一台狀態機，怎麼跑由誰跑不管）；**N-10 刪**；N-28 改（`adopt` 預設開、table 窗併進 state 窗）；N-43 改（翻 10-15 晚「loop 退 1」）；N-42 維持兩支。新待定 5 條在 [NORMS 待定](../proto8/NORMS/08-待定.md) 末段。
6. **frame 與工作區分開（10-16 夜）已寫進概念與規範，程式待改**：cwd 改叫 **frame**、「工作區」＝使用者的成品區（`/ws`）。新條 **C-65**（兩個東西、站在 frame、工作區乾淨）、**C-66**（影響外部＝指標＝捷徑）、**C-67**（frame 放哪由呼叫方決定）、**N-55**（工作區位置＝環境變數 `AOS_WS`）、**N-56**（一般工具入口寫 `"cwd": {"$env": "AOS_WS"}`、由範本給；agent 工具不寫＝站自己的 frame；工具格與門房一律同一動作）；**N-45 改**（選 A：`$ref` 只是拆檔便利，`$env` 讀執行當下的環境、可當正式機制）。沒點頭的（小格放 `ws` 捷徑、agent 工具怎麼碰工作區、`calls/<n>` 命名、`aos init` 引數／`AOS_WS` 誰設、`say`、入口包 loop）在 [NORMS 待定](../proto8/NORMS/08-待定.md)。
