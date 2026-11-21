# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-21 14:30（家機，使用者在場，session 進行中）——hook 整套換新已交並裝進 `~/aos-home`；兩條線在跑；今天的 commit 都沒 push

**使用者今天開場的指示（逐字）**：「事情盡量交給agent做，你就負責跟我交流。普通工作交給opus，簡單工作與雜活交給sonnet。agent做事前也要讀過wf/規矩，簡單工作與雜活除外。agent可以再派agent，模型隨意。用繁體中文跟我說話。」/goal「我要去睡回籠覺。一件一件持續做。litellm proxy我開了，你隨意」還掛著（他醒著、在場）。

**授權（11-21 當場；只限這個 session）**：
- push：開場問了沒答 → **不推**。本地領先 origin 約 80 筆（`git log origin/main..HEAD`）。
- `~/aos-home`：「可以開始改，改好後去幫我把~/aos-home更新一下，把更新過程寫成html放到桌面」「好，install.py你跑就行」。已更新三次（`e8d87d7cd`、`dff53b667`、`62129fe49`；現在裝的是 `97d4abc16`）。備份 `.bak-1121`／`b`／`c`／`d` 都留著。**再裝之前先跟他說一聲。**
- 刪檔：同意過的三批都做完了，不延伸（`hook_fire`；範本 ann 的 9 個檔；`~/aos-home/agents/ann` 同名 9 個）。**等他點頭**：`proto8/py/aos/hook_handle.py`、`py/aos/hook_flags.py`（hook 換新後沒人用）。
- LiteLLM 代理是他起的（localhost:4000），不停不改。
- 「活樹跟repo共用這塊先不管」：他的 `AOS_HOME` 就是 repo 的 `proto8/`，ann 動態連結 `templates/agent-fsm/` 的格程式——**派線時寫明：往工作樹寫檔一次寫完整；動到 `py/` 又動格程式的改動交了之後，活樹要先 `install.py` 才能起，要馬上告訴他別起樹。**

**還在跑的線（Claude 子 agent，背景；顯示 completed 可能只是在等自己的測試；等別線放 claim 的線可能要叫一聲才醒）**：
| 線名 | agent id | 做什麼 |
|---|---|---|
| `top-1121-compact4` | `a9d485d9bc10d9bdd` | agent-fsm 的 `/compact` 加 `before_compact`／`after_compact`（他對 hook 深度答「都開」），用新格式與極簡引擎；回報最前面會寫活樹要不要重裝 |
| `top-1121-hookdoc` | `ac520839c57d96c5d` | hook 總文件＋對齊散落的說明，只動文件與知識庫 |

**hook 的定案（他 11-21 定的；逐字在 `proto8/thinking/2026-11/21/`）**：`hook-points-格式-使用者審-1121.md`（8 則）、`aos-hook-簡化-1121/07-使用者已答.md`、`kernel-宣告進interfaces-1121/09-使用者已答.md`。摘要：宣告檔＝物件、鍵是 id、硬性只要 input schema、其餘鍵自由；`hooks.json`＝有哪些鉤子、`hookeds.json`＝有哪些被勾著；`interfaces.json` 最外層 `"hooks"`／`"hookeds"`（檔名或檔名陣列、支援指示詞、不收直接寫內容）；宣告只是參考、沒宣告照樣跑；引擎簡化到第四層（`aos-hook fire` 與 Python 庫只叫 handler；逾時留著；退出碼用旗標 `--stop-on-nonzero` 選；沒有旗標檔、編譯時決定接不接 `before_run`／`after_run`）；「發事件的程式自己決定」；kernel 做甲案（`kernel_hooks.json`、`kernel_hookeds.json`、最外層 `"kernel": {}`），模型清單 `llm_kernel: {"models": "llm_models.json"}`「另外做」、對外另一份 json「之後再來串」。施工 `97d4abc16`（247 檔；紀錄 `hook-新格式施工-1121/`，34 條替他做的選擇在 02，**只念了最要緊的五條**，他沒要求念完）。

**今天已交的（紀錄都在 `proto8/thinking/2026-11/21/`，日索引有列）**：早上那批（`session_key`、hook 第 5 刀後半、`reasoning_effort`、工具說明瘦身、AOS_DAEMON 調查、shell 比喻）；`aos-agent` 省略 `-t`／`-d`；`hook_fire` 換掉並刪；`self_history` 減號值與 `history -n K`；kernel 入口 `aos.py.kernel.defs`；起手範本 ann 動態連結＋刪 9 檔；compact 規劃與第 1 刀（他：「compact這塊，反正各agent有需要的，可以自訂自己的compact程式和流程」）；eca 思考程度／工具包／壓縮兩點（`9aab22baf`、`661801492`、`1c4e39074`）；小事八題（`小事八題-使用者已答-1121.md`：補 +x 測試、daemon on_start 也停、`agent_def new` 不寫 lineage、`defs.loop` 任意鍵；後續「every_ms感覺可以拿掉，反正有interval_ms？lineage都拿掉吧。」→ `ecedfa41c`、`e781ef00e`）；遙控器類別改名 `Attached`（`ca4ac9242`）；hook 整套換新＋kernel 甲案（`97d4abc16`）；桌面頁四份：`aos-AOS_DAEMON調查-1121.html`、`aos-shell指令的比喻-1121.html`、`aos-hook點宣告-1121.html`（內容是定案前的四題，已過時）、`aos-kernel的宣告-1121.html`、`aos-home更新過程-1121.html`。

**等他的（不催）**：
- 刪 `hook_handle.py`、`hook_flags.py`。
- gpt 包預設走 `/v1/responses` 要不要改成「設了程度才走」；`history set` 要不要收 `-n`（線評估三個坑，沒做）；N-63 加註；stack 要不要記定義夾與工作區；eca 才有的三包（events、def、jsonx，佔工具清單七成）要不要瘦；條文要補的字（各刀紀錄末節都有，他說條文會整體大修）。
- AOS_DAEMON 調查、shell 比喻兩份：他「我慢慢看，就先放着」。kernel 編譯：「我之後再來玩」。
- 沒排的：gdb 從宣告讀（原第 6 刀；新做法下「宣告只是參考」，要不要做沒問）、compact 第 3 刀 `history clear-tools`、pi 的壓縮 hook 點、llm 模型清單、對外另一份 json、「問特定的東西、直接回」、改名大工程、教學重寫。

**記給公司機的**：小事第 8 題他選「都清掉」——下次在公司機刪 `~/code/rv`（刪前照規矩再確認）；GitHub 上的 `rv` 他自己刪。公司 WSL 要重裝才吃到今天的東西（hook 換新後舊定義夾與 stack 要照 `hook-新格式施工-1121/03` 搬）。

**派線的做法（家機）**：Agent 工具派 Claude 子 agent（普通 opus、雜活 sonnet、發想他點名才 fable）；任務書寫明：先讀知識庫入口與規矩卡、線名 `top-1121-<名>`、乾淨複本＝`git archive HEAD` 解到 `~/.aos/scratch/<線名>/` 只疊自己的檔、這台沒有 pytest 用 unittest 逐夾跑、不在 repo 跑 `install.py`、不碰 `~/aos-home`、清 `AOS_*`、收行程只准兩種、不刪檔不 push、交件走 `commit-request`（zsh 路徑用陣列；日索引與進度條用 `--op`，寫法在 `wf/tools/commit_queue.py` 檔頭）、別線 claim 的檔等它交、背景等待腳本用完自己收。續派用 SendMessage 給 agent id。回報先 `git log`／`git show --stat` 核對再轉述；它替使用者做的選擇逐條念給他聽。頂層記他的原話時直接追加進對應的 thinking 檔、用線名 `top-1121-home` 交。

**坑**：
- 問句不是指示；一句話兩種讀法先確認；他補一句就可能翻掉讀法，轉給線時原話逐字附上（今天 `-N`、第 7／8 則都發生過）。
- 選項框不標推薦；最多四題、每題最多四個選項。
- 家機沒有使用者專區與全景頁，問他只能當面或選項框。
- 說話：kernel、daemon、llm kernel 直接叫；handle 說「遙控器」；「編譯／重新編譯」「靜態連結／動態連結」。
- 乾淨複本本來就紅或看負載的：`apps/feedback`、`apps/eca` 幾支、`apps/gdb` ctrl-c、`cpp/aos-loop` 訊號、`subagent` 一支撞名。
- 自動記憶夾還有 11-14～11-18 舊條目，規矩是不寫自動記憶，沒動。
