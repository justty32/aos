# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-27 午（家機）——main 換個人帳號當調度、main-alt 做事；最小方案等「照 A」

**寫這條的是家機 repo-aos 樹的 `main`**（Claude Code，模型 Opus 5.5）。上一條是家機 11-25 23:0x（中間夾了公司 eca-aos 11-26 的進度），全文在 git 歷史 `4e6baf17c`。細節在 [`wf/ws/main/notes.md`](ws/main/notes.md)「2026-11-27 早（家機）」、思考紀錄 [pi沙箱-1127](../proto8/thinking/2026-11/27/pi沙箱-1127.md)，原話 [9p-proc-1125](../proto8/thinking/2026-11/25/9p-proc-1125.md) 第 145～160 段。

**授權**：沒有 push 授權（本地比遠端多 6 個以上 commit，等使用者說）。子 agent：照往例用 Agent 工具，普通工作 opus、想事情 fable，不 commit，回來 main 驗再交；fable 寫不進 `.md` 報告，全文從回覆存進 `~/.aos/scratch/<名>/report.md`。

**今天做了的**
- 開場 pull、同步 11-26 公司的進度給使用者。家機重跑：sky-1125 10 PASS；aos-daemon 起初 619／623（seccomp 名字表缺新 Linux 的 12 個、測試沒收前一組的 daemon），opus 修好：名字表改 make 時從標頭產生，642／642×3（`8d4fa83fc`）；README「要使用者定的」第 7 條（名單寫了不認得的名字怎麼辦，推 a）。
- 封路實驗 `proto9/experiments/channels-1127/`（`81776b63f`）：預設下 SysV IPC／mqueue 三方向全通（沒開 IPC namespace）、`/proc/1/net`、照 PID 改兄弟與 daemon 的 nice／上限；封路建議五條。
- **pi 原型 `proto9/experiments/pi-sandbox-1127/`**（`a815a05a8`）：pi 整隻在 aos-daemon 的 proc（預設的鎖、`net none`），腦只經 `/llm`（unix socket＋宣告，proxy 數次數、上游家機 LiteLLM、不握金鑰），四個工具通、三件不該做到的做不到；`--fake` 不花錢。宣告還寫舊的 `__meta`。
- fable 三份報告（`~/.aos/scratch/proto9-onlykernel-1127/`、`proto9-exec-1127/`、`proto9-pisandbox-1127/`）：約 18 題，**使用者都沒答**，改要一個最小方案。

**使用者今天定的**（細節在 pi沙箱-1127「定了的」「天空的佈局」）
- 目標三句：讓 pi coding agent（read／write／edit／shell）安全行動的沙箱，基底之上層層疊 kernel（最輕＝純檔案遮蔽器）；基於 Plan 9／aoslua、只取概念用 Linux 輪子；**選配與介面是核心**，懶得管的漏給 Linux。自述 Linux 新手，問他要用「pi 在裡面會怎樣」講。
- 原型照甲（pi 整隻在沙箱、經 `/llm` 連腦）；`__call` 之後另外規劃；執行不攔（傾向）。
- **元表夾 `__meta` 改 `.aos`**，裡面名字不再加 `__`（`.aos/index`、`.aos/interfaces/aos/llm`）。
- **預設 Unix 標準佈局**（第 159 段）：`/` 是管它的那一方的地方（唯讀），`/.aos` 是管它的那一方的宣告（取代 `/aos`、`/daemon`）；proc 家目錄 `/home/<名字>/` 可寫、`~/.aos` 是它自己的；由起 proc 的人選。普通程式什麼都不用知道；daemon 寫的事實留在 daemon 目錄（外面看），proc 預設看不到。

**最小方案（回來了，使用者答了）**：全文 `~/.aos/scratch/proto9-minplan-1127/report.md`。第 161 段：兩題都甲——一隻 proc 在哪些 kernel 上，起它前就排好（跑到一半再加是很久以後）；pi 先用使用者本人帳號（切帳號是中期）；**實作前先上網找現成的開源輪子，注意 MIT**。已寫進 pi沙箱-1127 定了的第 6～8 條（`926dd8195`）。

**在跑／接著做**
1. **找輪子調查做完了**（重派那次在重開前就跑完了）：全文在 `~/.aos/scratch/proto9-wheels-1127/report.md`，手機版摘要 artifact https://claude.ai/artifact/WCpLpLEQtsVN6gqFFD28yo 。結論：沒有現成的一整套；推薦 A＝aos-daemon 照做、零件挑輪子（6 件裡 5 件自己做，小轉接沿用原型的 launch.mjs，socat 當備案），測項抄 Codex、sandbox-runtime（Apache 授權）。B 是改用 bwrap（會推翻 11-26 第 41 條），C 是整套換成 srt／Codex，D 是最外面再套虛擬機（中長期）。
2. **等使用者回「照 A」**：回了就派 opus 照最小方案做六件，測項加上跟 Codex、srt 的對照。

**新分工（使用者 11-27 12:1x：「你掛一個用$AOS_HOME/templates/agents/eca-claude-alt的main-alt…留下handoff，我幫你compact後，我改用~/.claude來aos-agent open。然後事情都讓那個main-alt做」）**
- **main**（這隻）：使用者 compact 後，會用 `CLAUDE_CONFIG_DIR=~/.claude aos-agent open -t main` 開畫面，也就是改用個人帳號，再開 remote control 在手機上跟它講話。公司帳號 `.claude-alt` 的政策不准 remote control，Discord 那條路已經放棄。main 只負責跟使用者講話和調度，**實際的工作都寄信交給 main-alt**，不在 main 自己的帳號上跑子 agent 隊。
- **main-alt**：已經掛上 repo-aos daemon，範本是 `$AOS_HOME/templates/agents/eca-claude-alt`（`.claude-alt` 帳號、工作區 `~/repo/aos`），沒開畫面，靠收信一輪一輪做。父 stack 是 main，它的通知會回到 main。寄信用 `mailbox_send` 或 `aos-post send`；**信裡要給齊脈絡**，它沒有這段對話：指到本檔、`~/.aos/scratch/proto9-minplan-1127/report.md`、`~/.aos/scratch/proto9-wheels-1127/report.md`、pi沙箱-1127。
- main 的定義 `wf/ws/main/def/`：Discord 拿掉了（外掛只裝在 `.claude-alt`，換成 `~/.claude` 後找不到會出事）。**跳選項加回來，權限改成 default**，因為 remote control 在手機上就能點。`--strict-mcp-config` 也恢復了。
- 接續：已經在 `~/.claude/projects/-home-lorkhan-repo-aos/` 放了這段對話（`c273d56e…`）的 jsonl 和資料夾的連結，指回 `.claude-alt` 那份，換帳號用 `--resume` 照理接得上（沒實測）。記憶兩邊都有：`look-for-wheels-first`、`main-alt-does-the-work`。
- 我掛錯過一隻 `phone`（用 eca-claude 加 `--envs CLAUDE_CONFIG_DIR`，結果畫面沒吃到這個設定），已經 `ctl rm`。stack 還留在 `procs/phone`，要清就 `ctl rm --purge`，或等使用者說。
- Bun（`~/.bun`、`~/.local/bin/bun`）和 `.claude-alt` 的 discord 外掛（使用者層 disabled）都留著，沒有在用。

**接著做**：使用者回「照 A」，就寄信給 main-alt：照最小方案做六件，測項加上跟 Codex、sandbox-runtime 的對照，子 agent 由它自己派；做完由它驗過再走 commit-request。main 驗收它的結果，再用 artifact 或跳選項給使用者看。

**還開著**：中文版知識庫落後 36 頁（11-26 收工就說要派，還沒派）；公司那台：sky-1125／channels 的 abi3 欄要在 WSL 跑一次對照、aos-daemon 名字表改產生後要在 Ubuntu 編一次；11-26 子 agent 的【擬】18 條、決策審查停在第 3 題（`aos/ctl` 形狀，`/aos`→`/.aos` 後可能要重看）。
