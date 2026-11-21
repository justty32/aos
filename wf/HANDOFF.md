# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-21 15:20（家機，使用者 15:00 出門、約 18:00 回來，晚上要自己玩 aos）——活樹已裝到 `2060ee9d5`；四條線在跑（知識庫、md 映照、教學、前端）；今天的 commit 都沒 push

**使用者今天開場的指示（逐字）**：「事情盡量交給agent做，你就負責跟我交流。普通工作交給opus，簡單工作與雜活交給sonnet。agent做事前也要讀過wf/規矩，簡單工作與雜活除外。agent可以再派agent，模型隨意。用繁體中文跟我說話。」**現在沒有 goal**（他下午 `/goal clear`）。15:00 他說：「好了，我要出門走走。現在時間下午三點，大概六點回來。」「幫我把該準備的準備好」「你說OK，我就出門」——頂層答 OK。**他回來前要備好：教學走到第一個 eca_main、知識庫更新、知識庫中文映照版 md、前端能用。**

**授權（11-21 當場；只限這個 session）**：
- push：沒給 → **不推**。本地領先 origin 88 筆。
- `~/aos-home`：「可以開始改…」「好，install.py你跑就行」＋「幫我把該準備的準備好」。已更新四次（最後 `370962554`，裝的是 `2060ee9d5`；樹停著、乾淨；ann 的 history 多一問一答「4+5→9」）。**再裝之前先跟他說；他在玩的時候不要裝。**
- 刪檔：同意過的四批都做完，不延伸。
- 他會擋看不懂的長指令 → 指令一次一件事、說明寫清楚。子 agent 的 `commit-request submit` 被權限擋時不要繞，回報頂層代交。
- LiteLLM（localhost:4000）是他起的，不停不改。
- 活樹的 `AOS_HOME` 就是 repo 的 `proto8/`：`knowledge/`、`frontend/`、範本格程式存檔即生效；動 `py/`、`cpp/` 要 `install.py`。

**還在跑的線（Claude 子 agent；顯示 completed 可能只是在等自己的測試）**：
| 線名 | agent id | 做什麼 |
|---|---|---|
| `top-1121-kbsync` | `ae39dbd875d8b8e1a` | 知識庫 `proto8/knowledge/aos/` 對齊今天的程式（他：「aos知識庫也麻煩你去更新一下吧」）；改名可、刪整頁只列不做。**它交完要通知 mdjson 線** |
| `top-1121-mdjson` | `a40b7d9ae0e561288` | md↔json 尋址與互轉調查；交完接第二階段：知識庫**中文**映照版 md（他三句：「…中英雙語各一套的，.json硬照版的.md，我要來審…」「"硬照"->"映照"」「等等，中文一套就好。英文的以後再說」）。要等 kbsync 交完才轉。位置頂層代定：優先 `proto8/knowledge/aos-zh-md/`，會被 agent 查法撈到就改放 thinking 夾 |
| `top-1121-tutorial` | `af455381b56d784f6` | 教學 `proto8/docs/tutorial/` 更新到第一個 eca_main（他：「教學稍微更新一下就好，只要弄到第一個eca_main出來就好，剩下的我直接問agent。」）；會回報今晚在活樹加 eca_main 還是另起新樹、他要先自己做什麼 |
| `top-1121-frontend` | `a2ad3ef4b9822c487` | aos-frontend 備妥（他：「aos frontend也幫我準備好，能先動工的就先動工。」）。**頂層代定的讀法**：今晚能用＋今天改動弄壞的現在修；大修大重構是方向題不動工、只列清單；11-18 說先留著的三個小毛病不趁機修 |

**他回來要聽的（代定清單與待答）**：
- 代定兩件：前端的讀法、映照版放哪（見上表）。
- 各線回報裡「替使用者做的選擇」逐條念。
- 教學線回來後，整理「今晚從哪一行指令開始」給他。
- gdb 線（`2060ee9d5`）12 條代選只念了 7 條要緊的。
- 驗寄件人還有五題「可晚點再答」沒念（`驗寄件人-規劃-1121/08`）。
- kernel 攔截頁第 10 節三題、七種可能的樣子：他說「這需要我思考好一段時間」，不催。
- `wf/tools/index_gen_desc.json:246` 一句說明還寫 `hooks.json`（該是 `hookeds.json`），fsmguard 線只列沒動，已告訴他、他沒接話。
- 程式旁文件對不上五處（permdoc 線列的：`share/README`、`asuser/README` 等），沒改，已告訴他。
- fsmguard 線曾把整份環境變數印到自己的工具輸出（它說沒進檔），已告訴他。

**今天下午聊出來的（他的原話都逐字記在對應 thinking 檔）**：
- shell 比喻（`shell-指令的比喻-1121/04-使用者回應.md`、`05-切點.md`）：不執著單一比喻；放信也算塞指令、只是非侵入式；aos 樹沒有唯一起頭點、有一些切點（八個）；侵入式不實測。
- kernel 攔截 daemon 存取（`kernel-攔截daemon存取-1121/`，`42a50a5f9`；桌面 `aos-kernel攔截daemon存取-1121.html`）：原則「只防走規矩的存取，不守規矩的就是要自己承擔風險。真的要硬防，那就要多依賴linux的權限體系」；想探索「寄一封信給kernel，kernel返回他想要存取的daemon的東西的位置」（取一份／暫時開權限／兩者皆有）；「不是說要讓kernel完全替代daemon的用途」。今天 kernel 只攔到起停信與「表在哪」查詢信。
- 權限零件說明頁（桌面 `aos-權限零件-1121/`，留底 `46d9226e5`）：他擔心「目前aos在這方面不夠全面」。**更正舊說法：daemon 11-19 起已認 `sub:N`**；家機卡在家目錄 700。
- 驗寄件人規劃（`驗寄件人-規劃-1121/`，`8fc27cfb2`；答案 `09`，`dcaef7f4d`）：他按直覺答 1D、2C、3C、4A，「晚一點我開沙箱，裏面開一個新session去嘗試」→ **頂層沒派施工**；4A 的 `setfacl` 動他的家目錄，頂層不代下。
- gdb 停法：「停法按照gdb自己的，之後可以開一個口子，實時修改…但不急」（`85694d214`）。

**hook 的定案（11-21）**：逐字在 `hook-points-格式-使用者審-1121.md`（8 則）、`aos-hook-簡化-1121/07-使用者已答.md`、`kernel-宣告進interfaces-1121/09-使用者已答.md`。摘要：`hooks.json`＝有哪些鉤子、`hookeds.json`＝有哪些被勾著；宣告檔＝物件、鍵是 id、硬性只要 input schema；`interfaces.json` 最外層 `"hooks"`／`"hookeds"`／`"kernel"`；宣告只是參考；引擎極簡；kernel 甲案。施工 `97d4abc16`。

**今天已交的**：早上那批；`aos-agent` 省略 `-t`／`-d`；`history -n K`；kernel 入口 `aos.py.kernel.defs`；起手範本動態連結；compact 第 1、4 刀；eca 思考程度與壓縮點；小事八題；`Attached` 改名；hook 整套換新＋總文件；fsm-guard 跟上新格式（`dae2e460f`）；aos-gdb 參考宣告（`2060ee9d5`，`--hooks FILE`／`--def-hooks`）；下午四份調查與規劃（見上）。桌面頁：`aos-AOS_DAEMON調查-1121.html`、`aos-shell指令的比喻-1121.html`、`aos-hook點宣告-1121.html`（已過時）、`aos-kernel的宣告-1121.html`、`aos-home更新過程-1121.html`（四次）、`aos-kernel攔截daemon存取-1121.html`、`aos-權限零件-1121/`。

**等他的（不催）**：gpt 包預設走 `/v1/responses`；`history set` 收不收 `-n`；N-63 加註；stack 要不要記定義夾與工作區；eca 三包要不要瘦；條文整體大修；kernel 編譯「我之後再來玩」。沒排的：compact 第 3 刀、pi 的壓縮 hook 點、llm 模型清單、對外另一份 json、改名大工程、教學 eca_main 之後的章節、前端大修。

**記給公司機的**：刪 `~/code/rv`（刪前再確認）；GitHub 的 `rv` 他自己刪；公司 WSL 要重裝並照 `hook-新格式施工-1121/03` 搬。

**暫存夾留著的**：`~/.aos/scratch/top-1121-*`；其中 `top-1121-ownerplan/exp/owner/` 有歸子帳號的信夾，一般刪不掉，要 `aos-asuser --fix`。

**派線的做法（家機）**：Agent 工具派 Claude 子 agent（普通 opus、雜活 sonnet、發想他點名才 fable）；任務書寫明：先讀知識庫入口與規矩卡、線名 `top-1121-<名>`、乾淨複本＝`git archive HEAD` 解到 `~/.aos/scratch/<線名>/` 只疊自己的檔、這台沒有 pytest 用 unittest 逐夾跑、不在 repo 跑 `install.py`、不碰 `~/aos-home`、清 `AOS_*`、收行程只准兩種、不刪檔不 push、交件走 `commit-request`（zsh 路徑用陣列；日索引與進度條用 `--op`，寫法在 `wf/tools/commit_queue.py` 檔頭）、別線 claim 的檔等它交、背景等待腳本用完自己收。續派用 SendMessage 給 agent id。回報先 `git log`／`git show --stat` 核對再轉述；它替使用者做的選擇逐條念給他聽。頂層記他的原話時直接追加進對應的 thinking 檔、用線名 `top-1121-home` 交。

**坑**：
- 問句不是指示；一句話兩種讀法先確認；他補一句就可能翻掉讀法，轉給線時原話逐字附上（今天 `-N`、第 7／8 則都發生過）。
- 選項框不標推薦；最多四題、每題最多四個選項。
- 家機沒有使用者專區與全景頁，問他只能當面或選項框。
- 說話：kernel、daemon、llm kernel 直接叫；handle 說「遙控器」；「編譯／重新編譯」「靜態連結／動態連結」。
- 乾淨複本本來就紅或看負載的：`apps/feedback`、`apps/eca` 幾支、`apps/gdb` ctrl-c、`cpp/aos-loop` 訊號、`subagent` 一支撞名。
- 自動記憶夾還有 11-14～11-18 舊條目，規矩是不寫自動記憶，沒動。
