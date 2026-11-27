# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-27 下午（家機）——main 只傳話、main-alt 做事；照 A 六件做完（`abcb242dc`），三題都甲

**寫這條的是 main-alt**（家機 repo-aos 樹，Claude Code、模型 Opus 5.5、帳號 `.claude-alt`），照 main 的信寫。上一條（11-27 午，main 寫的）全文在 git 歷史 `68e07ede7`：換帳號的經過、找輪子的結論、`wf/ws/main/def` 拿掉 Discord 的理由都在那裡。

**分工（這個 session 有效）**
- **main**（個人帳號 `~/.claude`、remote control、使用者在手機上跟它講）**只當傳話筒**。使用者 11-27 12:2x 對 main 說（main 抄在給 main-alt 的第一封信）：「照A。可以清。對了，請記住，這個session，所有工作都必須交給main-alt做，因爲我們本週額度剩4%。所以你就只能當傳話筒，大部分時候，就是請main-alt把artifact的html做好，你負責上傳」。
- **main-alt**（範本 `$AOS_HOME/templates/agents/eca-claude-alt`、工作區 `~/repo/aos`、沒開畫面、靠收信做）：調查、實作、驗收、交件、寫網頁全包，子 agent 自己派（普通工作 opus、想事情 fable）。使用者也直接對 main-alt 說了：「你是main-alt，請配合main。我現在人在外面，只能用手機跟main交流。麻煩你了。我大約晚上六點回來。事情都會是交給你做。」
- 來回的做法：main 寄信（附使用者原話）→ main-alt 做完寄 DONE／BLOCKED／NEEDS-USER 給 main；要給使用者看的寫成單檔 HTML 放 `~/.aos/scratch/<名>/`（手機好讀、白話、少術語），信裡附絕對路徑與摘要，main 上傳成 artifact。**main-alt 少寄中間的 PROGRESS 信**，每封都會叫醒 main、吃它的額度。

**授權**：沒有 push 授權（本地比遠端多好幾個 commit，等使用者說）。刪 phone 的 stack 是使用者「可以清」（經 main 轉）。

**今天下午做了的**
- **清 phone**：`~/aos-home/.stack/procs/repo-aos/procs/phone` 刪了，`aos-daemon-ctl leftovers` 是 0。
- **照 A 做最小方案六件**（`abcb242dc`，main-alt 派兩隻 opus：一隻在 worktree 改 daemon、一隻做新夾，main-alt 合併、重跑驗收、交件）：
  - aos-daemon：每隻 proc 自己一份 IPC namespace；宣告夾 `__meta/__interfaces/` → `.aos/interfaces/`；內建擋單多擋 `AF_VSOCK`【擬】（驗收時新發現 vsock 穿過 `net none`，Codex、srt 都擋）；鎖與測項跟 Codex、srt 逐條對照（[vs-codex-srt](../proto9/cpp/aos-daemon/vs-codex-srt.md)，照意思改寫、註明出處、沒抄 Apache 程式碼）。642→716 條，家機三次全過；channels-1127 的 SysV／mqueue 列全變不通。
  - 新夾 [`proto9/pi-sandbox/`](../proto9/pi-sandbox/README.md)：llm kernel（可疊）、`/llm/relay`、`aos_pi.py`（標準佈局）、`accept.py`（`--fake` 一隻、疊兩隻 SUMMARY ok）、`compare.py`／[compare.md](../proto9/pi-sandbox/compare.md)（同一支 probe 在 aos-pi、srt 0.0.83、codex 0.172.0 的三欄對照）。真模型一次用 `chatgpt-gpt-6-luna-nothink`（刻意不用 claude-*，省使用者 Claude 額度），5 次請求、四個工具全過。
  - 給使用者的網頁 `~/.aos/scratch/proto9-impl-1127/report.html`，main 上傳成 https://claude.ai/artifact/SGxqBnnHLiEkdWMtXza4VP 。
- **三題都甲**（使用者「都先用推薦」）：pi 在沙箱裡再開一層沙箱照舊不擋；工作夾先只鎖 `.git`；每隻自己一個 PID namespace 等要同時跑好幾隻 pi 時再做。記在 [pi沙箱-1127](../proto8/thinking/2026-11/27/pi沙箱-1127.md) 定了的第 9 條，pi-sandbox README、vs-codex-srt、aos-daemon README 第 8 條跟上。程式沒改（現在的行為就是甲）。

**還開著**
1. **公司 WSL 要跑**：aos-daemon 名字表改產生後在 Ubuntu 編一次、`make test`（照條數推約 722）；`proto9/pi-sandbox/accept.py --fake`；sky-1125／channels 的 abi3 欄對照。
2. **補洞後再跑一次真模型**：真模型那次是在補 IPC、vsock 之前的 daemon 上跑的，之後只跑了 `--fake`。
3. 中文版知識庫落後 36 頁（11-26 收工就說要派，還沒派）。
4. 11-26 子 agent 的【擬】18 條、決策審查停在第 3 題（`aos/ctl` 形狀；`/aos` → `/.aos` 後可能要重看）。
5. 小的：proto9 其他地方（`experiments/pi-sandbox-1127/`、`docs/`）與 thinking 舊檔還寫 `__meta`，是歷史紀錄，沒改；Bun 與 `.claude-alt` 的 discord 外掛（停用）還留著。
