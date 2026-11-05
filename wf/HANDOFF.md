# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-05 夜家機（使用者去運動、「盡量做」；程式隊長代做）

1. **授權**：今晚隨意 push（origin main）；普通事 opus、簡單與雜活 sonnet（碰程式碼不派 sonnet）；在家（家機 Manjaro）。LM Studio 開著、只用已載的 `google/gemma-4-e4b`、不切模型。殺程序只用自己記的 pid。新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問。
2. **今晚做完並 push**：lib 共用模組 `proto8/lib/tool_io.py`（規則 9 改寫、沙箱綁它、複製出 repo 走 PATH 上 aos-tools 找）`5deb73a6`、`079466e9`；listen paused bug `644b9789`；知識庫接三種 agent K1～K6、K8＋R1 `3753027e`；`thought` 工具 `233f5fd0`；兩輪邊緣測試 `3023de4b`、`4ba10460`、`03df2e9a`；fable 的 arch-refactor 收進 repo `d62101e5`；試驗場家機重建（WAIT_USER）`1d32dfa7`。
3. **明天要接**：架構大重構七題等使用者（[arch-refactor](../proto8/thinking/2026-11/05/arch-refactor/README.md)）；知識庫 K7 先派 fable；今晚留給使用者的題記在 WAIT_USER「11-05 夜」那行。

## 2026-11-05 收工（公司 Windows＋WSL；明天開新 session 接）

1. **授權**：今天隨意 push；普通事 opus、簡單與雜活 sonnet、規劃 fable（fable 可再開 fable）；做事的 agent（雜活除外）先讀 wf 規矩。新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問。WSL clone 與 Windows 工作樹都對齊 origin；**一律在 WSL 改檔**（Windows 端改會掉 +x）；殺程序只用自己記的 pid，別用 `pkill -f`（B 線誤殺過別 session 的程序）。Windows 工作樹 stash 有兩筆舊副本（內容都比 origin 舊，可丟）。
2. **今天做完並 push**：portable-flow（相對 daemon stack、sleep/wake、DaemonRunning、tools 只存差異、ctl 收進 `aos-agent ctl`）；kernel-daemon（llm kernel 一台 daemon、`AOS_LLM_KERNEL`＝它的 stack、問腦掛 daemon 下 proc、判官兩模式）；兩輪邊緣測試（edge-llm／daemon／agent／round2，約 30 處修）；feat-proto 五件（self_tools、能力包、priority 排程、agents new／add＋配額、limits）；層級式記憶 `memory`＋`proto8/knowledge/aos/`；程式輸出全英文＋三扇門與結束碼統一（stdio-unify）；say 讀 stdin；新規矩：proto8 沒有舊版、輸出格式只在共用介面改。試驗場 `~/code/playground`（WSL）與桌面 `aos-試驗場教學.html` 已更新到 317a88f9 前狀態；桌面另有 `aos-三扇門與結束碼.html`。**每日進度頁「本日進度」**：https://claude.ai/artifact/HazekvnmhUAgG8pwDr3Khd （之後每天更新這份，用 `url` 參數）；新功能說明頁 https://claude.ai/artifact/LoFTkSuuFREyGksrEzfpqy 、aos-agent 用法 https://claude.ai/artifact/9joBCStEMXvNMXadMGXqCT 、工具箱與腦設定參考（11-05 重寫）https://claude.ai/artifact/HLMpsX3T76ndC7E8VQ8Nit ；artifact 一律「圖多、只講結論、細節摺疊、白話」（user.md）。
3. **明天要接**：lib 工具 die 收成共用模組（使用者已裁「收成共用模組」）→ [stdio-unify](../proto8/thinking/2026-11/05/stdio-unify/README.md#剩下的)；知識庫接三種 agent、工具說明改寫 K1～K8 → [agent-knowledge](../proto8/thinking/2026-11/05/agent-knowledge/README.md)；`thought` 工具實作 T1～T6 → [small-thought](../proto8/thinking/2026-11/05/small-thought/README.md)；之後找時段做架構大重構（先 fable 規劃）。疑似 bug 待查：pause→resume→stop→start 之後 `aos-agent listen` 仍報 paused、等滿逾時（寫 aos-agent 用法頁時實跑發現）。等使用者：真腦（LM Studio）、`aos-agent open` 畫面 → WAIT_USER。
