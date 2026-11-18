# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-18 17:00 關機前（公司 Windows 機）——有五條線被關機打斷

**先看這個**：使用者 17:00 關機，五條線做到一半被打斷，**工作樹有約 100 個檔未交、五條線混在一起**。各線的交接在 `proto8/thinking/2026-11/18/交接-各線/<線名>.md`（關機前叫它們寫的；哪條沒寫出來，就只能從工作樹 `git status`／`git diff` 與 WSL 暫存夾 `~/.aos/scratch/<線名>/` 還原）。**不要整包 commit**——先照各線清單分清楚、在 WSL 暫存複本跑測試，再分件交。已推到 `205417c65`（之後只有交接檔）。

**授權**：頂層只調度（普通工作 opus、雜活 sonnet、規劃 fable），agent 開工前讀 AGENTS.md、規矩卡、`proto8/knowledge/aos/_description.json`。push 要再問。前端先不動。

**被打斷的五條線**（都沒 commit）：
1. `cooldown-1118`：腦出錯的原因寫進 `cooldown.json`（使用者裁「寫進狀態檔」；無限慢重試「維持現在」、代號 AnswerMissing「不換」）＋三小修（重建步驟單「再起」視窗 B 補 `source env.sh`；set-def 對停著／睡著的做完 `ctl ls` 工作區欄變 `-`；set-def 後 `screen_close.json` 沒清）。狀態顯示跑完但沒收到回報。動到 agent-fsm、`apps/agent/hints.py`、`ctl` 的 set_def／ls、`cpp/aos-daemon`（reconcile.cpp、test_lifecycle、docs/03）、NORMS 附錄 4、knowledge `brain.json`、重建步驟單。
2. `eca-pi-bc-1118`：pi 身做乙案（`pi --mode rpc`，回答途中收信）＋丙案（tmux 畫面＋一支 aos 的 pi 外掛在 `agent_settled` 通知 aos）。使用者：「codex身留下，pi coding agent要做畫面，去吧。每輪生一行外掛，目前就先這樣。…接著做乙丙吧。」甲案已交 `971116be6`。動 `agentlib/cli_*.py`、`apps/eca/`、`templates/eca-pi/`（已出現 screen 夾、interfaces.json）。
3. `rm-treestart-1118`：刪 `aos-tree-start`（使用者：「aos-tree-start這東西就不用了吧，刪掉。」），全 repo 改成 `aos-exec` 寫法。動 `py/entries.json`、兩份起手範本 README／env.sh、docs、步驟單。
4. `kit-merge-1118`：刪 `aos-kit`、功能併進 `aos-agent ctl`（使用者：「aos-kit也不用了，刪掉，功能整合進現有的。」選項框「併進 aos-agent ctl (Recommended)」）。動 `apps/agent/ctl/`、`templates/kits/`、kit 測試。
5. `eca-lab-1118`：小試驗教學 13～19（13 aos-loop 停／續、14 停著時 say、15 aos-tools 加工具、16 手動讓 eca-claude 當 kernel、17 手動看狀態（含「aos json view」）、18 出錯時手動除錯（要短）、19 手動 compact）。關機前 15、16 兩份已寫出，其餘未知。01～12 已交。使用者說 claude 額度不用省（haiku）、之後還會追加題目。

**今天已交已推的重點**（細節看 `git log --since=2026-11-18`）：S3～S7 改名收尾、code map 依賴表、沙箱帶整個家且家先認 `AOS_HOME`、set-def 新做法與 `ctl stop` 延後關、收尾線四項裁定、清紅測試（36→0，缺環境的改跳過）、`stop_cause.json` 不進 git、listen／ask 出錯帶理由、eca 第三種身 pi 甲案、小試驗教學 01～12、沙箱隔離實機檢查、下午改動獨立驗證、litellm 說明、aos-llm 去留調查。

**使用者已裁、還沒做的**：
- `aos-llm` 走丁案（Python 函式庫 `py/aos/llm_client.py`＋同名薄指令；推翻 11-17 X-4 A 的 `llm` 那一半）——使用者：「丁，明天再做」「也有可能往後延」。**要做之前先問他。**
- 真模型端點：等他把家裡的 litellm proxy 帶來公司（「等我回家把那個推回來公司再說吧，要等明天了」）；公司 `~/litellm-proxy/`（1.109.1）留著沒起、沒登入。之後接著做：API 真模型試跑、沙箱裡 agent 跑真模型、重建試跑紀錄補真 API 一節。
- pi：用他自己裝的那份（`~/.local/bin/pi`，1.5.2，已登入 ChatGPT），不釘版；`context_wrap` 在 pi 身先不開、靠 pi 自動壓縮（「這個得再去想想辦法」）；重建樹時 `env.sh` 要加 `export PATH="$HOME/.nvm/versions/node/v24.19.0/bin:$HOME/.local/bin:$PATH"`；家機要他自己換新版 pi。
- 預設 stack（cd 到 agent 夾直接 say）：他「得再想想…之後再來規劃」。
- 試驗抓到的問題「都還好…剩下的都不用管」；絕對路徑 `ctl add` 記成相對路徑那個他自己試。

**還沒問／沒裁的**：沙箱實機檢查的落差（起手範本擺法讓沙箱碰得到 daemon 的 stack〔嚴重〕、開網路的沙箱連得到宿主本機服務、WSL 的 DNS 要綁 `/mnt/wsl/resolv.conf`）；litellm 版本要不要退 `1.106.x`、要不要長駐；hook_run 把 aos-directive 錯誤行照轉 stderr 要不要改回；`--restart` 已拿掉與沙箱兩個代定細節他沒反對。

**機器狀態**：公司 WSL 沒有 aos（等使用者另開 session 照 `proto8/thinking/2026-11/18/公司WSL-重建試跑紀錄.md` 重建）。`~/.aos/scratch/` 有今天各線的暫存（關機後行程都沒了，夾還在）。桌面 `aos-全景-1118` 沒人眼看過。家機重建沒做。
