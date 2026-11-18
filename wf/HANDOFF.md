# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-18 22:30（家機收工）——家機重建完、全推上去；明天在公司機接著做

**授權**：頂層只調度（普通 opus、雜活 sonnet），agent 開工前讀 wf/ 規矩與 `proto8/knowledge/aos/_description.json`。push：使用者 22:30「可以推了，確保我明天在另一臺電腦上可以繼續」——這次已推；**之後的 commit 不自動推、要再問**。明天在公司。

**今晚（家機）做完的**（細節 `git log --since="2026-11-18 20:00"`）：五條被打斷的線全交；前端跟上新流程；沙箱只寫 README（使用者：風險使用者自負）；三份調查（預設 stack、Linux 當硬體、aos-compile）；**家機 `~/aos-home` 照重建步驟單重建好**（紀錄 [家機-重建紀錄](../proto8/thinking/2026-11/18/家機-重建紀錄.md)，`1548bd455`，含真模型 luna 試跑要點）；使用者裁「舊樹都可以刪掉」→ 已刪 `~/aos-home-old-1118`（含其 agents／defs／backups／aos-user／aos-view）、`proto8/impls/`、`~/.zshrc.bak-1118`、三份 aos 備份（`.claude.json.bak-1113-aos-mcp`、`aos-proto8.pth.bak-1113-simple_tools`、tag `home-local-abed65ecd-1118`）。

**家機現況（明天回家才相關）**：新 daemon（根＋llm kernel）用 setsid 跑著，`ann` 假腦；`~/.zshrc` 第 92～93 行已改成 `AOS_HOME=~/repo/aos/proto8`，要重開 session 才生效。**全景頁 aos-view 與使用者專區 aos-user 壞著**（使用者裁「先壞著」；aos-user 原本只存在舊樹、已隨舊樹刪掉，要用得從公司機或 git 歷史找回／重寫；`aos-user-tick.timer` 每分鐘失敗）。所以問使用者的題目暫時**直接在終端問**，不走 `aos-user send`。`~/.local/bin` 28 個舊 `aos-*` 斷連結已照使用者「也都可以刪了」刪掉（含 `aos-mcp`，所以 Claude Code 設定裡的 aos MCP 伺服器連不上，要改指新 bin 才會好）。aos-user 的資料 `~/.aos/user/` 還在（信箱 3 封），只是程式沒了；頂層建議明天開線照 `thinking/2026-11/13/user-zone-plan/` 重做 aos-user 並放進 repo、全景頁 unit 改指 repo 的 frontend，使用者 22:45「推，但可能是後天的事情了」——**明天不做，後天（11-20）再看**。

**預設 stack**：使用者 22:00 選「還是先擱著」（丁、戊都不做），progress `default-stack` 照掛。

**明天（公司機）要做的**：① 11-19 開工 aos-compile 庚（agent 版 tool_spec，見 `proto8/thinking/2026-11/18/aos-compile-1118/07-使用者裁定.md`）；② 子帳號（linux-as-hw 那一哩）；③ litellm 1.109.1 實測、兩台版本統一、公司 litellm；④ T7 第 8、9 步（先改頁面上的舊指令）；⑤ 重建步驟單照家機紀錄修七處（zsh、systemd 先查、28 支、常駐起法、`&&` 串等），還沒改。公司機開工先 `git pull`。

**先拖著／之後再說**：thinking 11-13／11-14 精簡範圍、eca-claude 範本預設權限；aos-llm 丁案；pi context 壓縮；guard；codex 身剩項；家機 proxy 不加 key；`~/.aos/scratch` 先不清；前端三小毛病；自動記憶「我們管不着」；aos-view／aos-user 怎麼救。

**坑**：家機 `~/.tmux.conf` 開新伺服器會自動復原使用者的 session——私人 tmux 一律 `-f /dev/null`。家機 pi 預設 deepseek，範本寫明 `openai-codex/gpt-6.1-sol`。工作樹未追蹤只剩 `proto8/templates/tests/kits/_index.json`（使用者放的，照留）。
