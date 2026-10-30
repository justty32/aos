# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-30 晚（家中 Manjaro；新 session 開場）

1. **授權**：可隨意 push。分工：普通事 opus、簡單工作與雜活 sonnet；做事的 agent（簡單／雜活除外）先讀 wf 規矩；agent 可再派 agent、模型隨意。測試在家機本地跑（不是 WSL）。
2. **狀態**：opus 隊長把 **aos-round 第 2～7 步做完**（每步一個 commit：`771747e1`、`f2818ae5`、`88cd1450`、`86c9f935`、`6f32b6a2`、`ef379dc7`；家機全套 788／0 fail／8 skip；commit 與代定註在 [aos-round 步驟表與文末](../proto8/thinking/2026-10-30-aos-round.md)）。還開著：WAIT_USER 的 aos_ws.py 失敗判法那題（沒裁、維持現況）、aos-round 接真腦的親手試（WAIT_USER 新加一行）。
3. **新規**：無。

## 2026-10-30 白天（公司 Windows；頂層 session 收工）

1. **授權**：可隨意 push；只 `git add <明確的檔>`、不 `git add -A`、不 force／reset、`stash@{0}` 不動。分工：普通事 opus、簡單與雜活 sonnet、規劃 fable（條文那步不派 sonnet）；做事的 agent（簡單／雜活除外）先讀 wf 規矩；agent 可再派 agent；工人不 commit、任務書帶時限。**測試負載**：在 WSL 跑（clone `~/.cache/aos-c8a7-e`，`~/.cache/aos-c8a7-sync.sh`、`~/.cache/aos-c8a7-test.sh`）、`-j2`、`nice -n 15`、同時只跑一個測試程序；全套基準 780 案、0 fail、12 skip。
2. **狀態**：今天完成——介質條文與實作（10-29 起）、queue／daemon execs／改名（[agent-lifecycle](../proto8/thinking/2026-10-29-agent-bob.md#決定10-30)）、eca 九步、歸檔改 daemon 小格（[eca § 決定](../proto8/thinking/2026-10-30-eca.md#決定10-30)）、aos-round 規劃拍板（`cbaf3f4f`）與第 1 步 aos-fsm 分岔（`c06a841c`）。**下一步＝aos-round 第 2～7 步**（[aos-round 步驟表](../proto8/thinking/2026-10-30-aos-round.md)）：2 lib/agent/round 長出 `roundlib.py`、`fsm-stop.json`／`fsm-idle.json`、五個薄格（舊 `_entry` 不刪）→ 3 `bin/aos-round` → 4 agent-nia＋aos-ai → 5 ask_round → 6 刪舊骨架 → 7 條文落正文 → 收尾（步驟註、SESSION-LOG、日誌、WAIT_USER 親手試指令）。開著的題見 [SESSION-LOG](SESSION-LOG.md)；[WAIT_USER](WAIT_USER.md) 有要裁的（aos_ws.py 失敗判法）與親手試的。
3. **今天的 artifact**（桌面各有同名 HTML）：現況地圖 https://claude.ai/artifact/Cjgx6VAwCvMYirsMHdNrji 、親手試指南 https://claude.ai/artifact/WSrwpLQqibw2QC2tfwwM3m 、proto8 概念層 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、proto8 實作想法 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 。概念層、實作想法兩個已整頁重寫（只講現況、舊分頁移除）；另補兩個新的：「aos 指令與格式參考」https://claude.ai/artifact/XFA2HA5WbeBpkJyC7wGSCn 、「proto8 入口與 demo」（實作想法拆出的第二頁）https://claude.ai/artifact/TVnjc4gvpgWjQnU3WJujtt 。
4. **新規**：今天落正文的 C-75、C-54 R13、N-64、P-42、P-43；N-36 分岔還沒落正文（aos-round 第 7 步）。

## 2026-10-29 晚（家中 Manjaro；新 session 開場）

1. **授權**：可隨意 push。分工：普通事 opus、簡單工作與雜活 sonnet；做事的 agent（簡單／雜活除外）先讀 wf 規矩；agent 可再派 agent、模型隨意。
2. **狀態**：今晚做了試驗場 `~/code/playground` 的 A（對話簿＋inbox tool）→ 使用者看完改方向（射後不理／射後有理兩個場景，inbox tool 先擱著）→ agent-bob-1／2 兩場景實跑（say／listen 直接可用）→ 隊長帶回八題 → 頂層再想成三題，使用者說「先等等吧，把這些都記錄到thinking，明天我們繼續想」。明天從 [thinking 10-29 agent-bob § 頂層對八題的再想](../proto8/thinking/2026-10-29-agent-bob.md#頂層對八題的再想10-29-晚使用者幫我多想想後未定) 接（三題也在 [WAIT_USER](WAIT_USER.md) 第一條）。
3. **新規**：無（決定 32 旁已註先擱著）。
