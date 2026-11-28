# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-28 凌晨（家機）——使用者又回去跟 main 講話；11-27 一天兩個原型、23:00 推完

**寫這條的是 main-alt**（家機 repo-aos 樹，Claude Code、Opus 5.5、帳號 `.claude-alt`）。上一條（11-27 下午）全文在 git 歷史 `293269f7f`；那條的「分工」照舊有效，這裡只重述重點。

**分工（白天到 21:36）**：main（個人帳號 `~/.claude`、remote control）只轉話與上傳 artifact，因為本週個人帳號只剩 4% 額度（使用者原話：「…這個session，所有工作都必須交給main-alt做，因爲我們本週額度剩4%。所以你就只能當傳話筒…」）。main-alt 做調查、實作、驗收、交件、寫網頁；子 agent 普通工作 opus、想事情 fable；要給使用者看的寫成單檔 HTML 放 `~/.aos/scratch/<名>/`，信裡附路徑，main 上傳。main-alt 少寄中間信（每封都吃 main 的額度）。

**21:36 起改了**：main compact 後就關掉，使用者改直接跟 main-alt 講話（使用者原話：「事情應該都是在main-alt做的，小心不要跟他衝突到。你這邊compact後我就要關掉session了，我會跑去跟main-alt對話。」）。main 說它不再動 repo。main-alt 的帳號沒有 Artifact 工具；使用者 compact 時說：「如果要用artifact的話，你仍然可以先把html做好後直接寄信給main，他那邊仍掛在aos樹上。」所以網頁照舊寫在 `~/.aos/scratch/<名>/report.html`，寄信給 main（box `/home/lorkhan/aos-home/.stack/procs/repo-aos/procs/main/mailbox`）請它上傳。今晚使用者多半只是問今天的細節、要 main-alt 記筆記。

**23:00 後又改回來**：使用者說「這次直接跟你交流，是因爲main那邊每週額度不夠了，這個情況會持續到週六下午四點每週額度重置後，那之後就仍會是以main爲主要交流對象」，接著（23:00 推完後）又說「你先繼續配合main，main那邊還有一些額度沒用完，我先去跟他討論這塊。」所以**現在 main 是對使用者的窗口**，main-alt 回去收 main 的信做事；分工照上面「白天」那段。使用者會臨時在兩邊切換。main-alt 直接講話時解說過的：遮檔案（mount namespace、tmpfs／null／ro、keep 開洞、MNT_LOCKED 讓 pi 拆不掉）與 cgroup（Delegate=yes 拿到 cpu/memory/pids、cpu.max／memory.max＋swap 0／pids.max、cgroup namespace 藏上限、v2 其他能做的）——講在 main-alt 的對話裡，沒寫成檔。

**授權**：**push 一律每晚 23:00**（使用者 11-27 13:05「Push就是一律晚上十一點push」，規矩在 [user/01](workflows/common/user/01-說話授權與記憶.md#每晚-2300-push2026-11-27-定)）。main-alt 的 aos 鐘 `nightly-push`（cron `0 23 * * *`）照那條的步驟推，推的結果寫在 main-alt 的對話裡，使用者來時告訴他（不再寄信給 main）。**11-27 23:00 第一次已推**：fast-forward 推 30 個 commit，遠端 `dfdb2b835..a43bb6153`，推完本地與遠端一致。

**今天做的**（日總覽網頁 `~/.aos/scratch/day-1127/report.html`；決定全在 [pi沙箱-1127](../proto8/thinking/2026-11/27/pi沙箱-1127.md) 定了的第 1～10 條）
- 早上（main）：aos-daemon 在 6.18 修好；封路實驗 channels-1127；pi 原型 pi-sandbox-1127；找輪子 → 使用者「照 A」。
- 中午：照 A 六件（`abcb242dc`）：aos-daemon 每隻 proc 自己一份 IPC namespace、`.aos/interfaces`、擋 `AF_VSOCK`、跟 Codex／srt 對照（716 條）；新夾 [`proto9/pi-sandbox/`](../proto9/pi-sandbox/README.md)。三題都甲（`c6eb37153`）。清掉 phone。
- 下午到晚上：使用者要更小的原型 → [`proto9/mini-sandbox/`](../proto9/mini-sandbox/README.md)（`a492b2289` 起五段）：底層一行 systemd-run＋unshare，上面疊可選的 kernel（資源上限、網路、遮檔案、切帳號、llm），「環境套環境」嵌套、`--kernels a,b,c`、設定在 [`proto8/kernels/`](../proto8/kernels/README.md)、統一介面（name/layer/status、宣告唯讀）、一包 kernel（`_chain.json`）。驗收 accept 31、stack_test 22、llm_test 15、bundle_test 19。
- 調查（scratch，未進 git）：kernel 格式說明 `kernel-format-1127/`、統一介面 `kernel-iface-1127/`、重疊與規模 `kernel-overlap-1127/`（三份全文 overlap/scale/files-report.md）。

**今晚做完的**
1. **七題實作**（使用者「好，都按照推薦」）：`chain.py`（去重、`merge`、`replace`／`without`、uid 排最裡、兩個 llm 沒串起來就拒絕）、`flat_kernel.py`（cg 與 mask 攤平；起之前算 user namespace 層數，主機上限 24【擬】）、`effective.py`（`.aos/effective/`＋`blame`＋`.aos/lock.json`、`--explain`／`--lock`／`--diff`）；修好兩個 bug（撞 33 層時卡死留孤兒、網路疊三層總量被吃光）。驗收 accept 31、stack_test 22、llm_test 15、bundle_test 19、overlap_test 31 全過。實作者標【擬】要問使用者的三點：上限「還能開的層數減 9」、下載佇列 1 秒（多 1 秒延遲）換總量正確、網路與 llm 要不要也攤平。
2. **效能成本進 repo**（使用者「有幫我記錄效能成本嗎」）：[`proto9/mini-sandbox/PERF.md`](../proto9/mini-sandbox/PERF.md)＋[`perf/bench.py`](../proto9/mini-sandbox/perf/README.md)（`--quick` 約 6 秒，公司 WSL 也能跑）；攤平後實測 cg／mask 疊 100 層 0.2 秒起好（以前 33 層起不來）。網路收掉每層 3 秒還沒修。
3. 23:00 鐘推送（今晚第一次，結果寫在 main-alt 的對話裡）。日總覽 `~/.aos/scratch/day-1127/report.html`（含全景圖）。

**架構說明**（使用者回家後「看要不要做一個更細節的，講述整個架構，運作方式的artifact」）：`~/.aos/scratch/arch-1127/report.html`，照 HEAD 程式寫；順手把 mini-sandbox README 的舊句子對齊程式（`97872b8ab`）。新發現的縫：`KernelOrderBad`「網路 kernel 讓 pi 繞過 llm 直連上游」的檢查只比 IP，上游寫成網域名稱時抓不到（`chain.py` `llm_bypasses`），沒修。

**今天上傳給使用者的 artifact**（網址不變；要更新得由有 Artifact 工具的 session 用同一個本機路徑 `~/.aos/scratch/<名>/report.html` 重新上傳）
- 照 A 結果 https://claude.ai/artifact/SGxqBnnHLiEkdWMtXza4VP （proto9-impl-1127）
- 更小版調查 https://claude.ai/artifact/8PE8siKazvHPpPm1UZGdhV （proto9-smallproto-1127）
- 環境套環境 https://claude.ai/artifact/5czYEPZ89qiKSbp1oSV4YM （proto9-mini-1127）
- kernel 設定檔格式 https://claude.ai/artifact/5ajPABGSeNsVXHF2RLbwCi （kernel-format-1127）
- 統一介面 https://claude.ai/artifact/EfJVvzHAgfdyVDjDTLGrBj （kernel-iface-1127）
- 一包 kernel https://claude.ai/artifact/KYdKPB151D9rYSUv818ddv （kernel-bundle-1127）
- 重疊與規模 https://claude.ai/artifact/WdVA9e3A42xR5VxbF2BNsh （kernel-overlap-1127）
- 一日總覽（含全景圖、效能成本） https://claude.ai/artifact/DdSi36oav4qc5gHCDkEPGw （day-1127）
- 架構與運作 https://claude.ai/artifact/E7o1Ww7jdLY2nfDz5faD3M （arch-1127）
- 找輪子摘要（早上的） https://claude.ai/artifact/WCpLpLEQtsVN6gqFFD28yo

**接著做**（main-alt）：
1. ~~23:00 推~~（11-27 已推 30 個，見上）；之後每晚照鐘推，結果寫在對話裡（使用者在跟 main 講話時就寄信告訴 main）。
2. 那三點【擬】還沒得到回答（使用者說「這些設計點先等等」，要先問原理）：層數上限 24、下載佇列 1 秒、網路和腦要不要也攤平。
3. **main 11-28 02:47 來信兩件，等使用者回來找 main-alt 再做**（全文 `~/.aos/scratch/pending-1128/from-main-0247.md`）：cg kernel 加 inotify／fanotify 每層上限（使用者「1.要。」）；README 寫磁碟用 tmpfs＋記憶體上限、IO 提醒使用者自己 delegate io（使用者「磁碟這塊，我們就是建議最簡單的方式：給他tmpfs然後限制記憶體…」）。
4. 其他照下面「還開著」。

**還開著**：網路 kernel 收掉每層 3 秒；perf 的 llm 疊層量法要改成 `upstream: outer`；公司 WSL（aos-daemon `make test`、pi-sandbox、mini-sandbox 都沒在那台跑過；sky-1125／channels 的 abi3 欄）；決策審查第 3 題（`aos/ctl` 形狀，報告在公司機 `~/.aos/scratch/proto9-decisions-review-1126/`）連同介面裡同名不同義的欄位一起定；中文版知識庫落後 36 頁；pi-sandbox 補洞後還沒跑真模型、「沒設 `AOS_ENV` 看 `/`」沒跟上；11-26 的【擬】18 條。Bun 與 `.claude-alt` 的 discord 外掛（停用）還留著。
