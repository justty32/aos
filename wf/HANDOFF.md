# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-27 晚（家機）——main 只傳話、main-alt 做事；一天下來兩個原型，七題實作中

**寫這條的是 main-alt**（家機 repo-aos 樹，Claude Code、Opus 5.5、帳號 `.claude-alt`）。上一條（11-27 下午）全文在 git 歷史 `293269f7f`；那條的「分工」照舊有效，這裡只重述重點。

**分工**：main（個人帳號 `~/.claude`、remote control）只轉話與上傳 artifact，因為本週個人帳號只剩 4% 額度（使用者原話：「…這個session，所有工作都必須交給main-alt做，因爲我們本週額度剩4%。所以你就只能當傳話筒…」）。main-alt 做調查、實作、驗收、交件、寫網頁；子 agent 普通工作 opus、想事情 fable；要給使用者看的寫成單檔 HTML 放 `~/.aos/scratch/<名>/`，信裡附路徑，main 上傳。main-alt 少寄中間信（每封都吃 main 的額度）。

**授權**：**push 一律每晚 23:00**（使用者 11-27 13:05「Push就是一律晚上十一點push」，規矩在 [user/01](workflows/common/user/01-說話授權與記憶.md#每晚-2300-push2026-11-27-定)）。main-alt 的 aos 鐘 `nightly-push`（cron `0 23 * * *`）照那條的步驟推，推完寄信給 main。今晚是第一次；寫這條時本地比遠端多 24 個以上 commit。

**今天做的**（日總覽網頁 `~/.aos/scratch/day-1127/report.html`；決定全在 [pi沙箱-1127](../proto8/thinking/2026-11/27/pi沙箱-1127.md) 定了的第 1～10 條）
- 早上（main）：aos-daemon 在 6.18 修好；封路實驗 channels-1127；pi 原型 pi-sandbox-1127；找輪子 → 使用者「照 A」。
- 中午：照 A 六件（`abcb242dc`）：aos-daemon 每隻 proc 自己一份 IPC namespace、`.aos/interfaces`、擋 `AF_VSOCK`、跟 Codex／srt 對照（716 條）；新夾 [`proto9/pi-sandbox/`](../proto9/pi-sandbox/README.md)。三題都甲（`c6eb37153`）。清掉 phone。
- 下午到晚上：使用者要更小的原型 → [`proto9/mini-sandbox/`](../proto9/mini-sandbox/README.md)（`a492b2289` 起五段）：底層一行 systemd-run＋unshare，上面疊可選的 kernel（資源上限、網路、遮檔案、切帳號、llm），「環境套環境」嵌套、`--kernels a,b,c`、設定在 [`proto8/kernels/`](../proto8/kernels/README.md)、統一介面（name/layer/status、宣告唯讀）、一包 kernel（`_chain.json`）。驗收 accept 31、stack_test 22、llm_test 15、bundle_test 19。
- 調查（scratch，未進 git）：kernel 格式說明 `kernel-format-1127/`、統一介面 `kernel-iface-1127/`、重疊與規模 `kernel-overlap-1127/`（三份全文 overlap/scale/files-report.md）。

**今晚做完的**
1. **七題實作**（使用者「好，都按照推薦」）：`chain.py`（去重、`merge`、`replace`／`without`、uid 排最裡、兩個 llm 沒串起來就拒絕）、`flat_kernel.py`（cg 與 mask 攤平；起之前算 user namespace 層數，主機上限 24【擬】）、`effective.py`（`.aos/effective/`＋`blame`＋`.aos/lock.json`、`--explain`／`--lock`／`--diff`）；修好兩個 bug（撞 33 層時卡死留孤兒、網路疊三層總量被吃光）。驗收 accept 31、stack_test 22、llm_test 15、bundle_test 19、overlap_test 31 全過。實作者標【擬】要問使用者的三點：上限「還能開的層數減 9」、下載佇列 1 秒（多 1 秒延遲）換總量正確、網路與 llm 要不要也攤平。
2. **效能成本進 repo**（使用者「有幫我記錄效能成本嗎」）：[`proto9/mini-sandbox/PERF.md`](../proto9/mini-sandbox/PERF.md)＋[`perf/bench.py`](../proto9/mini-sandbox/perf/README.md)（`--quick` 約 6 秒，公司 WSL 也能跑）；攤平後實測 cg／mask 疊 100 層 0.2 秒起好（以前 33 層起不來）。網路收掉每層 3 秒還沒修。
3. 23:00 鐘推送（今晚第一次）。日總覽 `~/.aos/scratch/day-1127/report.html`（含全景圖）。

**還開著**：網路 kernel 收掉每層 3 秒；perf 的 llm 疊層量法要改成 `upstream: outer`；公司 WSL（aos-daemon `make test`、pi-sandbox、mini-sandbox 都沒在那台跑過；sky-1125／channels 的 abi3 欄）；決策審查第 3 題（`aos/ctl` 形狀，報告在公司機 `~/.aos/scratch/proto9-decisions-review-1126/`）連同介面裡同名不同義的欄位一起定；中文版知識庫落後 36 頁；pi-sandbox 補洞後還沒跑真模型、「沒設 `AOS_ENV` 看 `/`」沒跟上；11-26 的【擬】18 條。Bun 與 `.claude-alt` 的 discord 外掛（停用）還留著。
