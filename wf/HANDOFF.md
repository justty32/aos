# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-02 晚收工（家中 Manjaro；明早開新 session 接）

1. **授權**：今晚隨意 push、普通事 opus、簡單與雜活 sonnet、規劃 fable、做事的 agent（雜活除外）先讀 wf 規矩、可再派 agent。**明早開新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問一次**。頂層 Bash 裡 `ls` 寫 `/bin/ls`。工人只 `git add <明確的檔>`、不 `-A`、不 force／reset、不碰 stash——今晚多個 agent 同一工作樹 commit 時兩度把別人 staged 的檔帶進去，commit 前一定 `git diff --cached --stat`；子 agent 的完成通知會送到頂層、不送給派它的隊長，頂層要轉。家機試驗場 `~/code/playground`（不在 git）今晚重建：env.sh、agents/bob、agents/resident_bob、agents/eca_bob、daemons/main；`daemon_ws/` 是使用者自己開的 daemon，別碰。
2. **今晚做完並 push**：公司 33 個 commit 快轉；digest 舊字樣（`721bdc46`）；aos-listen 翻案（`4fcc483f`，只留 `aos-say … && aos-listen`）；compact `endpoint` bug（`e31f7921`）；eca 盤點與「收工了」（`53f1d6b6`、`b11987f0`、`983a2632`）；**aos-eca-hub（11-03 改名 aos-eca-ctl）三對指令** open／close、start／stop（stop 留小格）、add／remove（remove 刪小格、不封存），reap 自動掛 `eca_reap`（`bd0f3d4a`，代定 11 條在 [eca 15](../proto8/thinking/2026-10-30-eca/)）；`letter_warning`→`mailbox_warning`（`c8ac6bfc`）；刪 demo agent-dan、agent-dan-q（`7dcc3dc6`，假腦小幫手搬 `tests/fake_brain.py`）；ctl/state 規劃（`bdf9283a`，[ctl-state-names](../proto8/thinking/2026-11-02-ctl-state-names.md)）與實作（`971811ce`＋`5a6b600f`：daemon 自己的窗改回 `ctl.json`／`state.json`、常駐 bob 控制器同、aos_ws 只認 `state.json`；全套 800 OK／11 skip、ctest 8/8）。使用者親手玩 hub 畫面：「體驗不錯」；常駐 bob「等之後有空」。eca 圖解 https://claude.ai/artifact/1DW3vC6ENR4VWUfGs7qXco （第 2 版；三對指令已實作、reap 已會自動掛，頁面還寫「還沒實作」，要更新）。
3. **明早要接的**：
   - **整體瘦身**（使用者：「明天早上再說，或者我們這樣子一點一點的，也算是了」）。候選清單：`demo/llm-kernel`、`demo/self-improve`（使用者「完全沒有印象」「明天應該會刪掉」；刪了環境變數第 4 題的 `AOS_IVY_BRAIN`、`AOS_IMPROVE_RUN` 就消失）；Lua／Janet 的 `agent_dan` 範例與 nvim 外掛的 smoke（讀已刪的 agent-dan，測試先 skip，待使用者定）；10-23 agent-dan artifact。
   - **proc 改名想法**（ctl/state 方向題 1，未定）：使用者「exec和loops，其實都屬於proc，所以...改名？…exec是基石，loop是另一種基本形式，搞不好以後還會有更多形式」；今晚 `loops_ctl`／`loops_state` 不動 → [ctl-state-names](../proto8/thinking/2026-11-02-ctl-state-names.md)。
   - **amy 刪掉**（使用者「刪掉」）：公司 WSL `~/code/playground/agents/amy`，WAIT_USER／SESSION-LOG 相關條目若今晚沒清就清。
   - eca 以後再優化：每封信 `--resume` 起退、依資源縮短閒置（使用者「以後再說」）→ eca 14。
4. **artifact**：現況地圖 https://claude.ai/artifact/Cjgx6VAwCvMYirsMHdNrji 、親手試指南 https://claude.ai/artifact/WSrwpLQqibw2QC2tfwwM3m 、proto8 概念層 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、proto8 實作想法 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 、aos 指令與格式參考 https://claude.ai/artifact/XFA2HA5WbeBpkJyC7wGSCn 、proto8 入口與 demo https://claude.ai/artifact/TVnjc4gvpgWjQnU3WJujtt （11-01 版，今天 11-02 的改動還沒回寫）。

