# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-21 晚（家機，使用者在場、洗完澡要開始玩 aos、要 compact）——兩條線在跑（映照版搬家＋原型、fable 規劃「json 骨架＋md」知識庫）；活樹裝到 `83e6fa5e3`；今天的 commit 都沒 push

**使用者今天開場的指示（逐字）**：「事情盡量交給agent做，你就負責跟我交流。普通工作交給opus，簡單工作與雜活交給sonnet。agent做事前也要讀過wf/規矩，簡單工作與雜活除外。agent可以再派agent，模型隨意。用繁體中文跟我說話。」**現在沒有 goal。**他今晚自己玩 aos（eca_main、前端），有問題會來問。

**授權（11-21 當場；只限這個 session）**：
- push：沒給 → **不推**。本地領先 origin 約 100 筆。
- `~/aos-home`：「好，install.py你跑就行」「幫我把該準備的準備好」。已更新五次（最後 `628982cac`，裝的是 `83e6fa5e3`；樹停著時裝的）。**他今晚在玩：再裝之前一定先問他、等他說樹停了才裝。**
- 刪檔：先前四批用完。今晚另准的只有：關 9 個 tmux session（已做）、映照版搬家造成的舊路徑移除、`top-1121-kbmd` 第三段換知識庫樣子時被取代的舊檔（他：「實作好了之後趕快更新知識庫」）。其他不延伸。
- 他會擋看不懂的長指令 → 指令一次一件事、說明寫清楚。子 agent 的 `commit-request submit` 被擋不要繞，回報頂層代交。
- LiteLLM（localhost:4000）是他起的，不停不改。
- 活樹的 `AOS_HOME` 就是 repo 的 `proto8/`：`knowledge/`、`frontend/`、範本格程式**存檔即生效**；動 `py/`、`cpp/` 要 `install.py`。

**還在跑的線（Claude 子 agent；「completed」可能只是在等自己的測試）**：
| 線名 | agent id | 做什麼、頂層要接什麼 |
|---|---|---|
| `top-1121-mdjson` | `a40b7d9ae0e561288` | ①把中文映照版從 `proto8/knowledge/aos-zh-md/` 再搬到 **`proto8/knowledge-zh-md/`**（他：「…用grep找東西的時候量會變多，這就糟糕了，麻煩你幫我搬到proto8/knowledge-zh-md吧」），並回報新位置不會被 agent 撈到的五項確認；②接著做「骨架＋md」小原型（`md與json尋址-1121/原型-骨架加md/`、`10-…`）。交了核對 commit、告訴他「搬好了，可以放心起 agent」 |
| `top-1121-kbmd` | `adf161e2ec180c38c` | **fable 隊長**（他點名）。三段：規劃 → 實作工具 → 換知識庫樣子。他三句原話：「…是否可以是index中有說"xxx":"xxx.md"這樣，指向某個.md檔案？就是說，仍然以.md爲主體，然後index做導航骨架，這樣git diff也比較舒服…」「尋址這塊，感覺也可以用這套#/xxx的方式去尋markdown」「好，總之讓fable去規劃一下，然後能實作的話就儘快實作，實作好了之後趕快更新知識庫。」**順序鎖**：它交完工具會停下來回報「需要重裝活樹」→ 頂層**先問他、等樹停著**再派線跑 `install.py`（照 `aos-home-更新-1121.md` 第五次的做法）→ 用 SendMessage 回它「已裝」→ 它才把新樣子的知識庫寫進工作樹。**在「已裝」之前知識庫不能換**（他正在跑的 agent 會查壞）。它若列方向題，用選項框問他（最多四題四選項、不標推薦） |

**今晚他用的東西（都備好了）**：
- eca_main：`proto8/docs/tutorial/05b-起eca_main.md`（最短路 01、02→05b；`a0318f73f`）。先確認 `claude` 登入過；第一次 `open` 要自己選信任資料夾；範本寫檔跑指令不問就准，加在 `~/aos-home` 時 `-w` 指專案夾別用 `.`。
- 前端：起樹後另開視窗 `cd ~/aos-home`、`AOS_DAEMON=~/aos-home/.stack aos-frontend serve`，新版頁 http://127.0.0.1:8768/ （`5d9f87043`）。「要決定」欄會是空的（活樹沒有 `ws/`）；對 ann 按 `/compact` 會被擋。
- 知識庫已對齊程式（`fad6bef74`；`cli/hook_points.json` 改名 `cli/offer_hooks.json`）。
- `aos-gdb --hooks FILE`／`--def-hooks`（`2060ee9d5`）；停法他答「停法按照gdb自己的，之後可以開一個口子，實時修改…但不急」。
- 三處 `--help` 已改（實際四處，`83e6fa5e3`）。tmux 9 個被自動復原的 session 已關（下次他開 tmux 外掛可能又還原）。

**今天下午聊出來、他還在想的（原話都逐字在對應 thinking 檔，不催）**：
- shell 比喻：`shell-指令的比喻-1121/04-使用者回應.md`、`05-切點.md`。
- kernel 攔截 daemon 存取：`kernel-攔截daemon存取-1121/`；桌面 `aos-kernel攔截daemon存取-1121.html`（七種可能的樣子、三題）。原則：「只防走規矩的存取，不守規矩的就是要自己承擔風險。真的要硬防，那就要多依賴linux的權限體系」；想探索「寄一封信給kernel，kernel返回他想要存取的daemon的東西的位置」。
- 權限零件：桌面 `aos-權限零件-1121/`。daemon 11-19 起已認 `sub:N`，家機卡在家目錄 700。
- 驗寄件人：`驗寄件人-規劃-1121/`，他按直覺答 1D、2C、3C、4A，「晚一點我開沙箱，裏面開一個新session去嘗試」→ 頂層沒派施工；另五題沒念。
- md 與 json：`md與json尋址-1121/`；他「平常就是用vscode打開知識庫」；四題只答了這一題。
- 前端大修盤點 14 項（`frontend-備妥-1121.md`）沒念；程式旁文件對不上幾處（`share/README`、`asuser/README` 等）沒改；`wf/tools/index_gen_desc.json:246` 一句舊說明沒改；知識庫線拿不準沒動的一處（kernel 站「不在一輪中間跑」）。
- 更早等他的：gpt 包預設走 `/v1/responses`；`history set` 收不收 `-n`；N-63 加註；stack 要不要記定義夾與工作區；eca 三包要不要瘦；條文整體大修；kernel 編譯「我之後再來玩」。

**hook 的定案（11-21）**：逐字在 `hook-points-格式-使用者審-1121.md`、`aos-hook-簡化-1121/07-使用者已答.md`、`kernel-宣告進interfaces-1121/09-使用者已答.md`。`hooks.json`＝有哪些鉤子、`hookeds.json`＝有哪些被勾著；宣告只是參考；引擎極簡；kernel 甲案。施工 `97d4abc16`。

**記給公司機的**：刪 `~/code/rv`（刪前再確認）；GitHub 的 `rv` 他自己刪；公司 WSL 要重裝並照 `hook-新格式施工-1121/03` 搬。

**暫存夾留著的**：`~/.aos/scratch/top-1121-*`；`top-1121-ownerplan/exp/owner/` 有歸子帳號的信夾，要 `aos-asuser --fix` 才清得掉。

**派線的做法（家機）**：Agent 工具派 Claude 子 agent（普通 opus、雜活 sonnet、發想他點名才 fable）；任務書寫明：先讀知識庫入口與規矩卡、線名 `top-1121-<名>`、乾淨複本＝`git archive HEAD` 解到 `~/.aos/scratch/<線名>/` 只疊自己的檔、這台沒有 pytest 用 unittest 逐夾跑、不在 repo 跑 `install.py`、不碰 `~/aos-home`、清 `AOS_*`、收行程只准兩種、不刪檔不 push、交件走 `commit-request`（zsh 路徑用陣列；日索引與進度條用 `--op`，寫法在 `wf/tools/commit_queue.py` 檔頭）、別線 claim 的檔等它交、背景等待腳本用完自己收。續派用 SendMessage 給 agent id。回報先 `git log`／`git show --stat` 核對再轉述；它替使用者做的選擇逐條念給他聽。頂層記他的原話時直接追加進對應的 thinking 檔、用線名 `top-1121-home` 交。

**坑**：
- 問句不是指示；一句話兩種讀法先確認；他補一句就可能翻掉讀法，轉給線時原話逐字附上（今天 `-N`、第 7／8 則都發生過）。
- 選項框不標推薦；最多四題、每題最多四個選項。
- 家機沒有使用者專區與全景頁，問他只能當面或選項框。
- 說話：kernel、daemon、llm kernel 直接叫；handle 說「遙控器」；「編譯／重新編譯」「靜態連結／動態連結」。
- 乾淨複本本來就紅或看負載的：`apps/feedback`、`apps/eca` 幾支、`apps/gdb` ctrl-c、`cpp/aos-loop` 訊號、`subagent` 一支撞名。
- 自動記憶夾還有 11-14～11-18 舊條目，規矩是不寫自動記憶，沒動。
- 子 agent 不要開 tmux：11-21 教學線開 tmux 測畫面，觸發他的自動復原外掛還原了 9 個舊 session。
- 知識庫、前端、範本格程式存檔即生效：他在玩的時候，往這三處寫檔要一次寫完整，會改變查法的改動要先確認工具已裝進活樹。
