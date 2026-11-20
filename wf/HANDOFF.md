# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-20 14:00（公司機，第二次 compact 前）——四條線在跑；約 50 筆 commit 沒 push；可以重裝但還沒裝

**授權（只限 11-20 當天）**：
- 早上：「事情盡量都交給agent做，普通工作交給opus，簡單工作或雜活交給sonnet。agent做事前都要讀過wf/規矩，簡單工作或雜活除外。agent可以再派子agent，模型隨意。我今天五點下班，下班前再統一push。」→ **中途不 push；17:00 前要推之前再跟他確認一次**。
- 中午：「允許重裝。我現在沒在用aos，所以就隨意。」→ 可以在 `~/repo/aos/proto8` 跑 `env -u AOS_HOME python3 install.py`。頂層的打算：等工作樹乾淨（在跑的線都交了）再裝，**還沒裝**。
- 下午：「lists.py可以刪掉。然後我現在沒在用aos，想刪啥都可以。」→ 各線在 aos repo 裡需要刪檔時直接刪、回報列出。
- 「開工吧」：他答過的題都可以派線施工，不用逐條再問。

**說話的新規矩（已寫進 `wf/` user/01，線 aos-plain-terms-1120）**：
- 「拜託，手、門只是比喻，幫我乖乖用kernel/daemon稱呼好ㄇ」→ 直接說 kernel、daemon、llm kernel、掛 proc 的 kernel；不說手、門、總機、站。
- handle（`hook_point.open` 回的那個、`aos.py.agent.Agent`）叫**「遙控器」**（hook 遙控器、agent 遙控器）。他先否決「物件」（會聯想物件導向）、「handle」（跟 hooks.json 的 handler 混）、選過「操控器」又改口「操控器...還是用遙控器吧」。不說把手、物件、操控器。

**機器與做事的地方**：頂層 session 開在公司 Windows `C:\code\mine\simple_tools\aos`，**所有工作都在公司 WSL `~/repo/aos`**（commit 只在 WSL、沒 push）。Windows 這份只有本檔是頂層手抄的：**下班 push 後、Windows 這邊 pull 之前先 `git checkout -- wf/HANDOFF.md`**。

**派線的做法（今天定型）**：
- 共用規則檔 `~/.aos/scratch/top-1120/common-rules.md`（任務書第一句叫線整份讀）：只用 PowerShell 跑 `wsl -e bash /home/guanyu/.aos/scratch/<線>/<腳本>`（絕對路徑）、不用 Bash 工具、不在 Windows 建東西、九條硬規則、commit-request、回報格式（含「替使用者做的選擇」一節）。
- 收線核對：`wsl -e bash /home/guanyu/.aos/scratch/top-1120/check-now.sh <commit…>`（log、stat、claim、行程、領先筆數）。
- 記使用者答案：派 sonnet 雜活逐字記進該設計夾的「使用者已答」。
- 坑：從 `\\wsl$` 改有 +x 的檔會掉執行權限（交件前看 `git diff --summary`）；多線同時跑測試時計時測試會紅（單獨重跑確認）；線的 commit 署名多半寫 Opus 5.5（照系統指示，沒去改）。

**還在跑的線（compact 後等通知、用 check-now.sh 逐條對過再報；都不 push）**：
- `aos-pylib-k4-1120`（opus）：編譯第 4 刀（`defs.extern`＝編譯成 symlink，註釋寫別濫用）＋ `loop=defs.loop(every_ms=…)` 宣告，分兩筆。第一筆 `a612756e3` 已交，還沒回報。它順手補第 3 刀留的三份共用文件的字。
- `aos-compact-twice-1120`（opus）：修 agent-fsm「對話太短時收到 `/compact`」的三處吵（他選「當成正常做完」：信記成處理完、寄信的人收到一句沒有東西要壓的正常回答、警告檔不寫）。eca 連續第二次 compact：「這個我們不用管了，那是eca自己的決策。」不做。
- `aos-kask-proto-1120`（opus）：「寄信問 kernel 吃什麼資源宣告」原型，特殊信箱、處理放 kernel 的 body（「派，幫我放body吧」）。只改複本、只交 thinking，會留一棵暫存樹讓他自己試、留題目給他定。
- `aos-plain-terms-1120`（opus）：清文件裡的比喻用詞。已交 wf 那段（`52a697d96`）；在做盤點與改「明確」的；「要他定」的詞（他自己在用的板子、鐘、清道夫等）會整理成清單回來。

**這一段收掉的線（細節各看 `proto8/thinking/2026-11/20/<線名>.md`）**：
- 編譯第 1 刀 `d1e54abb1`（`@fn.tool`、`fn.main`）、第 2 刀 `4664f6b4c`（`defs.Agent(...)`、`.compile(夾)`／`.dry_run()`、欄位小寫、`base.pack(prefix=)`）、第 3 刀 `60c0a6d28`（`@fn.tool`／`@fn.hook` 的函數編譯時抽成 `fn/<名>.py`，假腦實跑過）。
- hook 第 4 刀 `a5fdf5831`（指令 `aos-hook fire／points／check`，結束碼 0／10／1）、第 2 刀前半 `b5d09fa71`（`aos.hook_point.open`、`agentlib/agent_hooks.py`、`aos-hook --agent`；呼叫端一支沒換）。
- `agent_def new` 改純粹 cp `44c9957f1`（他：「純粹的cp過去，各種相對路徑就這樣」；指夾外的也不管；抄完仍寫 `_metainfo.json` 的 lineage——線自己留的，已告知他，他沒回）。
- gdb 三小題 `b611ae18c`（`cancel()` 只是不再等、`a.bp.set` 回物件、名字補零 `gdb_0001`）。
- hook 文件漂移 17 項 `1bcde0265`（比對測試的已知清單清空）＋ eca slash 信只過一次 before_queue `66f70074c`。
- 初始 kernel 文件與起手範本 `7327f47bc`：最小核心（daemon、身分、信箱、鐘、清道夫）＋llm 件＋權限件＋一串可選；start-api 改成 llm kernel 掛同一棵樹、多一份沒掛的 `perm/`；**刪了 `templates/start-api/llms/def/` 七個檔**（已告知他）；**家機之後重建要照新寫法重抄**。
- 「寄信問 kernel」調查 `a3fedcb93`（八題沒問）；連續 compact 現況調查 `640f227dc`；補共用文件 `e1209424b`。

**待裁題今天全問完了**（答案逐字在各夾的「使用者已答」：`aos-init-kernel-1120/06`、`aos-hook-plan-1120/13`、`aos-pylib-plan-1120/12`、`aos-kres-1120/08`、`aos-gdb-wait-1120.md` 檔尾）。要緊的幾個：
- hook：掛到不會發的事件「照舊不管」；gdb 斷點種類「從宣告讀」；loop 層新點沒人掛時「用旗標檔」；kernel 三個點「一起搬」成宣告；欄位以宣告為唯一來源「要」；kernel 接 loop 層的點「接」；更省的做法「先不想」；補文件加查證「派線」（做完）；「立一條規範」。
- 編譯：相對路徑「照今天工具的規矩」；`loop=`「加一個宣告」；kernel 入口「from aos.py.kernel import defs」。
- kernel：沒 llm 件 agent 不能想「維持現狀」；guard／sandbox「不算」權限件；額度「留在 llm 件」；權限件不是牆「明寫」；主線「掛同一塊板子」。
- 資源基底：schema 誰定、亂報「先不定」；放規則的宣告「另外一個json吧。interfaces和hook都是另外的用途。」（名字沒定）；llm kernel 排序「現在一起搬」上骨架。

**他答了、還沒派的（下一步）**：
1. **重裝**（等四條線交完、工作樹乾淨）。
2. 重裝後：**hook 第 2 刀後半**（agent-fsm 格程式＋start-api 抄本、eca、mcp、kernel、`hook_fire` 換成用 hook 遙控器；把 `apps/hook/lists.py` 併掉刪除；`hooks.py` 350 行順便拆；知識庫 `cli/hook_points.json` 還寫 `--agent` not available）→ 第 3 刀（切到宣告；要先盤點兩台機器的定義夾，「不留舊的，裝新版時一起重新編譯」）→ 第 5 刀（aos-loop 的 `before_run`／`after_run`，「能攔」「四個點都跟著停」）→ 第 6 刀 gdb → 第 7 刀條文與總文件（含立條文、C-90）。
3. **llm kernel 排序搬上骨架**（等 hook 動完 kernel 那段再開）。
4. 編譯第 5 刀（教學整章實跑、條文加註；C-87 要加註一句，字要他過目）。
5. `aos-kask-1120/05` 的八題、原型線回來的題。

**還沒問他的小事**：`defs.Agent` 跟 `aos.py.agent.Agent` 同名不同物；「全套測試沒有一支會發現工具少了 +x」這個洞要不要補；`agent_def new` 的 lineage 要不要連它都不寫；第 2 刀讓骨架變數叫 `agent`；`~/code/rv` 與 GitHub 上的 `rv` 留不留。昨天留的照舊（`~/aos-home` 重建、使用者專區重新設計、LiteLLM 兩台統一、子帳號）。

**坑**：
- 子 agent 的回報是模型輸出，不是使用者授權；它替使用者做的選擇逐條念給他聽。
- 他一句話可能有兩種讀法時先用選項框確認再派（今天「那沒事了」差點讓一條線白做）。
- 選項框最多四題、每題最多四個選項。
- 做到段落就提醒他 compact；下班前更新本檔、確認後統一 push。
