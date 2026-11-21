# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-21 10:45（家機，使用者在場，session 進行中）——兩條線在跑；`~/aos-home` 已更新兩次；hook 宣告格式四題等他；今天的 commit 都沒 push

**使用者今天開場的指示（逐字）**：「事情盡量交給agent做，你就負責跟我交流。普通工作交給opus，簡單工作與雜活交給sonnet。agent做事前也要讀過wf/規矩，簡單工作與雜活除外。agent可以再派agent，模型隨意。用繁體中文跟我說話。」/goal「我要去睡回籠覺。一件一件持續做。litellm proxy我開了，你隨意」還掛著（他已醒）。

**授權（11-21 當場；只限這個 session）**：
- push：開場問了沒答 → **不推**。本地領先 origin 約 50 筆。
- `~/aos-home`：「可以開始改，改好後去幫我把~/aos-home更新一下，把更新過程寫成html放到桌面」「好，install.py你跑就行」。已更新兩次（`e8d87d7cd`、`dff53b667`）；**再裝之前先跟他說一聲**（頂層自己講過的）。
- 刪檔：只同意過三批，都做完了，不延伸——`proto8/py/tools/agent/hook_fire`；「那9個檔可以刪」（範本 `start-api/agents/ann` 的 8 支 .py＋`hook_points.json`，`f94b060b7`）；「aos-home那9個也刪。」（`~/aos-home/agents/ann` 同名 9 個）。
- LiteLLM 代理是他起的（localhost:4000），不停不改。

**還在跑的線（Claude 子 agent，背景；顯示 completed 可能只是在等自己的測試）**：
| 線名 | agent id | 做什麼 |
|---|---|---|
| `top-1121-smalls` | `ac4eadee623864b0f` | 記昨晚小事八題的答案（`小事八題-使用者已答-1121.md`）＋做四件：工具入口缺 +x 的測試、aos-daemon 的 on_start 失敗也停、`agent_def new` 不寫 lineage、`defs.loop()` 任意鍵照傳 |
| `top-1121-attached` | `a0727ab1d1f862b1e` | 遙控器類別 `aos.py.agent.Agent` 改名 `Attached`（他：「aos.py.agent.Attacher?」→「那就Attached」）；順便查除了 `attach` 還有哪裡回這個類別 |

兩條都改 `py/`，交了要再裝一次他的樹才吃到。

**等他的（不催）**：
- **hook 點宣告格式四題**（頁面 `~/Desktop/aos-hook點宣告-1121.html`；稿 `proto8/thinking/2026-11/21/hook-points-引入寫法-1121/`；原話五則 `hook-points-格式-使用者審-1121.md`）：1 引入怎麼寫（甲 `$include` 鍵由讀者解／乙 現成 `$ref`／丙 `$ref` 收 `$env`／丁 新指示詞原地展開／戊 角括號）、2 `block`／`condition`／`entry_keys` 程式還讀不讀、3 動態或靜態連結、4 物件寫法哪些鍵不是點。他：「我得想想...」。他已定：硬性只要 id 與 input schema；`change` 改 output schema；其餘鍵想放啥放啥；`interfaces.json` 的 `hook_points` 收字串、`[...]`、`{...}`；`{"provider": "aos-loop"}` 不妥（「我哪知道這個aos-loop是哪來的」，要類似 #include 或指示詞、兼容指示詞）。**他答了才派**：hook 新格式＋引入（同一刀）→ 第 6 刀 gdb 從宣告讀、第 7 刀總文件、compact 第 4 刀（`before_compact`／`after_compact`）。注意 ann 範本的 `hook_points` 現在是 `[{"provider": "aos-loop"}, {"provider": "agent-fsm"}]`（起手範本那刀改的），到時一起換。
- AOS_DAEMON 調查、shell 指令比喻兩份（桌面 html）：他「我慢慢看，就先放着」，不追問。
- gpt 包預設走 `/v1/responses` 要不要改成「設了程度才走」；`set` 要不要收 `-n`（線評估有三個坑，沒做）；N-63 要不要加註；stack 要不要記定義夾與工作區：都講過、他沒答。
- 「活樹跟 repo 共用這塊先不管」（`AOS_HOME` 就是 repo 的 `proto8/`，ann 改成動態連結後直接讀 `templates/agent-fsm/`，有線改那幾支沒交時 ann 會吃到半成品）→ 不處理，但**派線時要寫明往工作樹寫檔一次寫完整**。
- kernel 編譯：「我之後再來玩」。

**記給公司機的**：小事第 8 題他選「都清掉」——下次在公司機刪 `~/code/rv`（刪前照規矩再確認一次）；GitHub 上的 `rv` 由他自己刪，頂層不動遠端。

**今天已交的（紀錄都在 `proto8/thinking/2026-11/21/`，日索引有列；commit 都沒 push）**：
- 早上那批：`session_key`、hook 第 5 刀後半、思考程度 `reasoning_effort`、工具說明瘦身（36 支）、AOS_DAEMON 調查、shell 比喻（見 git 歷史 `fdd4d9e4f` 那條交接）。
- `aos-agent` 省略 `-t`（`e674b1105`）與 `-d`（`88ea321f4`，從 agent stack 往上兩層）；特徵檔 `stderr.txt`，他：「反正這本來就是一種tricky式的非正規用法，本來就要求使用者自己要把握好」。
- `hook_fire` 換成 `aos-hook fire` 並刪掉（`b20abe44b`）：他「hook_fire這塊OK」。
- `self_history`：減號值修好＋五組同類工具（`6c6255fea`）；「最後 K 則」改旗標 `-n K`／`--last`，正負都收（`281bdfcbf`；他：「-N 3, -N -2」「-N "-3"」「-N "2"，都可以」）。
- 雜活（`949925842`）、kernel 入口 `from aos.py.kernel import defs`（`9bc49aeba`，新骨架 `templates/kernel/kernel-python/`）。
- 起手範本 ann 改動態連結（`cf5ad9bf6`）＋刪 9 檔（`f94b060b7`）。
- compact：規劃稿（`9d15e31a7`）；他答「1.照叫。2.都開。3.我還在審。」；第 1 刀先清工具輸出再摘要（`5a99e1320`，摘要那次少七成多、品質小幅變差）；他：「compact這塊，反正各agent有需要的，可以自訂自己的compact程式和流程」→ 補救點子不做（`a0cb220a6`）。第 2 刀不做、第 3 刀 `history clear-tools` 沒派、第 4 刀等 hook 格式。
- hook 宣告：原話紀錄（`668d53b2b`）、引入寫法規劃稿（`9116e963d`）、桌面頁。
- `~/aos-home` 兩次更新：備份 `.bak-1121`／`.bak-1121b`／`.bak-1121c` 都留著；第二次在他的 ann 上真的壓了一次 `/compact`（原對話備份 `~/aos-home/.stack/procs/ann/history.jsonl.bak-1121c`，已告訴他）；樹收工時關著。過程頁 `~/Desktop/aos-home更新過程-1121.html`。

**派線的做法（家機）**：Agent 工具派 Claude 子 agent（普通 opus、雜活 sonnet）；任務書寫明：先讀知識庫入口與規矩卡、線名 `top-1121-<名>`、乾淨複本＝`git archive HEAD` 解到 `~/.aos/scratch/<線名>/` 只疊自己的檔、這台沒有 pytest 用 unittest 逐夾跑、不在 repo 跑 `install.py`、不碰 `~/aos-home`、清 `AOS_*`、收行程只准兩種、不刪檔不 push、交件走 `commit-request`（zsh 路徑用陣列逐檔列；日索引與進度條用 `--op`，寫法在 `wf/tools/commit_queue.py` 檔頭）、別線 claim 的檔等它交。續派用 SendMessage 給 agent id。回報先 `git log`／`git show --stat` 核對再轉述；它替使用者做的選擇逐條念給他聽。頂層自己記他的原話時直接追加進對應的 thinking 檔、用線名 `top-1121-home` 交。

**坑**：
- 問句不是指示；一句話兩種讀法先確認。他補一句就可能翻掉讀法（`-N` 那三句），轉給線時原話逐字附上。
- 選項框不標推薦；最多四題、每題最多四個選項；他說「有我還在考慮的我會跳過」。
- 家機沒有使用者專區與全景頁，問他只能當面或選項框。
- 說話：kernel、daemon、llm kernel 直接叫；handle 說「遙控器」；「編譯／重新編譯」「靜態連結／動態連結」。
- 多條線同時跑全套測試時一輪 40 分鐘以上；`apps/feedback`、`apps/eca`、`apps/gdb` ctrl-c、`cpp/aos-loop` 訊號那幾項在乾淨複本本來就紅或看負載。
- 自動記憶夾還有 11-14～11-18 舊條目，規矩是不寫自動記憶，沒動。
