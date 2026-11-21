# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-21 上午（家機，使用者在場，session 進行中）——三條線還在跑；交齊後要更新 `~/aos-home`；今天的 commit 都沒 push

**使用者今天開場的指示（逐字）**：「事情盡量交給agent做，你就負責跟我交流。普通工作交給opus，簡單工作與雜活交給sonnet。agent做事前也要讀過wf/規矩，簡單工作與雜活除外。agent可以再派agent，模型隨意。用繁體中文跟我說話。」另設了 /goal：「我要去睡回籠覺。一件一件持續做。litellm proxy我開了，你隨意」（他已醒，goal 還掛著）。

**授權（11-21 當場；只限這個 session）**：
- push：開場問了他沒答 → **不推**。本地領先 origin 很多筆（`git log origin/main..HEAD`）。
- **`~/aos-home` 更新**：他說「可以開始改，改好後去幫我把~/aos-home更新一下，把更新過程寫成html放到桌面」「好，install.py你跑就行」。頂層事先講過會做的事（他沒反對）：確認樹關著（開著就停下問他）→ 在 repo 跑 `python3 install.py` → 備份後改 `~/aos-home/llm/kernel.json`（加 `reasoning_effort_levels`、四個 gpt 包加 `"api": "responses"` 與 `reasoning_efforts`，寫法見 `llm-effort-1121.md`）→ 備份後更新 `agents/ann`（他自己改過的檔先列差異、不直接蓋）→ `llm`、`perm`、`root` 跟新範本比 → 起樹用真模型驗（問一句、換思考程度、看快取、省略 `-t`），驗完關回原狀。不刪檔、不動 LiteLLM。**要等 `hook_fire`、`-t` 可省略兩條線交件後才派**（`self_history` 那條能等就一起）。
- 刪檔：只同意刪 `proto8/py/tools/agent/hook_fire` 那一支（已交給 hookfire 線），不延伸。
- LiteLLM 代理是他起的（localhost:4000），不停不改。

**還在跑的線（Claude 子 agent，背景；回報會自己來，顯示 completed 可能只是在等自己的測試）**：
| 線名 | agent id | 做什麼 |
|---|---|---|
| `top-1121-hookfire` | `add8f5381a88fb657` | `hook_fire` 換成 `aos-hook fire` 並刪掉 `hook_fire`；順手在 `agent_spec_parts.py` 的 `LLM_KEYS` 加 `reasoning_effort`；記他對 k5b 的回應 |
| `top-1121-deft` | `a4d93cc2a0e40bb77` | `aos-agent` 的 `-t` 可省略：`-d` 不能省（`-d` 或 `AOS_DAEMON`）；目標順序 `-t` → `AOS_AGENT` → `./.stack`（要有特徵檔）→ `./`；要定義夾的子指令拿 stack 路徑去 daemon 的表反查；不把 daemon 寫進 agent 的檔 |
| `top-1121-histrange` | `aafc1320bd1cb4366` | `self_history`：減號開頭的值被當旗標（先查證）、查其他同類工具、`range` 支援最後 N 則（他「派線去修，三樣都做」） |

**交齊後要派的**：
1. `~/aos-home` 更新（上面授權那段）＋過程頁 html 放 `~/Desktop/`（風格：圖多、結論在前、細節摺疊、白話、不連外部資源）。
2. 一條 sonnet 雜活：`self_llm` 的 `_tooldef.json` 說明照瘦身風格補（參數名已是 `reasoning_effort`；用 `tool-desc-瘦身-1121/03-套用.py`）；三份範本文件的「11 包、40 支」改成 36 支（`templates/agent-fsm/README.md`、`templates/start-api/agents/ann/README.md`、`templates/docs/02-agent-fsm.md`）。
3. 昨晚排的第 3 件「編譯：kernel 入口 `from aos.py.kernel import defs`」還沒派（等 hookfire 交，兩邊都動 `agent_spec`）；第 4 件以後見 git 歷史裡 11-21 00:55 那條交接。

**今天已交的（都在 `proto8/thinking/2026-11/21/`，日索引有列）**：
- `session_key`：四個 gpt 包加 `"session_key": "litellm_session_id"` 快取約 99% 命中；範本兩份與 `~/aos-home/llm/kernel.json` 已改（備份 `kernel.json.bak-1121`）、新增 `astra` 包。他說：「以後公開發佈的時候，我怕別人誤以爲aos需要依賴litellm」「以後應該會是endpoints/example,endpoints/default這類，url那塊就走AOS_LLM_ENDPOINT_DEFAULT」——只記錄，沒動手。
- hook 第 5 刀後半（k5b，`a71fd65b0`）：他「剛剛那個hook我覺得OK，畢竟hook體系的唯一約定，就是要在interfaces.json中宣告，有宣告就能用，至於怎麽實作的，就是各家自己的事情。」
- 思考程度（`110294e33`、`4a2ede307`）：他「走乙吧」「effort...改叫reasoning_effort吧，說清楚」「換了思考程度就沒了快取，不對吧…去想辦法」「kernel轉送不帶effort...要補」。結果：信裡帶 `reasoning_effort`、llm kernel 處理；範本四個 gpt 包改走 `"api": "responses"`（靠 `configuration_update` 保住快取）——**預設路徑變了這點已告訴他，他沒表態**。
- 工具說明瘦身（`19020832c`、`2c3225a07`）：他選「只留一兩句＋指去知識庫」「self 只留兩支」；40→36 支、`prompt_tokens` 12,553→5,837。`self_llm` 因此預設關掉（已提醒他）。
- `AOS_DAEMON` 調查＋搬到另一個 daemon 可行（`8dbd48397`）、shell 指令比喻發想（`ea3e81a11`）：兩份 html 在 `~/Desktop/aos-AOS_DAEMON調查-1121.html`、`~/Desktop/aos-shell指令的比喻-1121.html`。他：「調查這塊我慢慢看，就先放着，我只是想找一些用來思考的材料，可能要過一段時間才能出結果。」→ **不催、不追問那三題**。他另說：「agent記自己在哪個daemon底下...這個想法我覺得不行，agent不該和daemon耦合。這是爲了可遷移性」。

**還沒問／還沒答的**：`hook_points.json` 宣告格式他要先審（第 6、7 刀等他）；gpt 包預設走 Responses 要不要改成「設了程度才走」；`templates/kernel/llm-team/README.md` 的端點名單沒補 `astra`；量測線在 `/tmp/claude-1000/x` 留了一份範本抄本沒清；昨晚交接那串小事（見 git 歷史）。

**派線的做法（家機，今天實際用的）**：直接用 Agent 工具派 Claude 子 agent（普通 opus、雜活 sonnet、發想 fable 只派過一隻）；任務書寫明：先讀知識庫入口與規矩卡、線名 `top-1121-<名>`、暫存樹在 `~/.aos/scratch/<線名>/`、乾淨複本＝`git archive HEAD` 只疊自己的檔、不在 repo 跑 `install.py`、不碰 `~/aos-home`、收行程只准兩種、不刪檔不 push、交件走 `commit-request`（zsh 不拆變數，路徑逐檔列）、別線未交的檔不碰。續派同一條線用 SendMessage 給它的 agent id。收到回報先 `git log`／`git show --stat` 核對再轉述；它替使用者做的選擇逐條念給他聽。

**坑**：
- 問句不是指示；一句話有兩種讀法先確認（今天「不過litellm_session_id...」停下來問是對的）。
- 選項框不標推薦；最多四題、每題最多四個選項。
- 家機沒有使用者專區與全景頁，問他只能當面或選項框。
- 說話：kernel、daemon、llm kernel 直接叫；handle 說「遙控器」；agent.py→定義夾說「編譯／重新編譯」。
- 多條線同時跑全套測試時機器負載高，一輪 40 分鐘以上是正常的。
- 自動記憶夾（`~/.claude-alt/projects/-home-lorkhan-repo-aos/memory/`）還有 11-14～11-18 的舊條目，規矩是不寫自動記憶、以 `wf/` 為準，沒動。
