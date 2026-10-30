# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-30 16:40（公司 Windows＋WSL；aos-round 實作隊長，時限 17:00 收線）

1. **授權**：可隨意 push；只 `git add <明確的檔>`、不 `-A`、不 force／reset、`stash@{0}` 不動；寫程式派 opus、雜活 sonnet，條文那步不派 sonnet；工人不 commit。測試在 WSL clone `~/.cache/aos-c8a7-e`（`~/.cache/aos-c8a7-sync.sh`、`~/.cache/aos-c8a7-test.sh`，`-j2`、nice 15、一次一個測試程序）；全套基準 780 案、0 fail、12 skip。工人共同規矩草稿在隊長 scratchpad（`r_common.md`），要重寫一份。
2. **題目**：[thinking 10-30 aos-round](../proto8/thinking/2026-10-30-aos-round.md) 使用者「都照建議」（[§ 決定](../proto8/thinking/2026-10-30-aos-round.md#決定10-30)，`cbaf3f4f`）。實作八步：**第 1 步 aos-fsm 分岔做了**（`c06a841c`）；**下一步＝第 2 步** lib/agent/round 長出 `roundlib.py`、`fsm-stop.json`／`fsm-idle.json`、五個薄格（舊 `_entry` 不刪），接著 3 `bin/aos-round` → 4 agent-nia＋aos-ai → 5 ask_round → 6 刪舊骨架 → 7 條文落正文（自己做或派 opus）→ 收尾（八步註 commit、SESSION-LOG、日誌、WAIT_USER 親手試指令）。
3. **新條目**：沒有落正文的；WAIT_USER 加了 aos_ws.py 判失敗那題。

## 2026-10-29 晚（家中 Manjaro；新 session 開場）

1. **授權**：可隨意 push。分工：普通事 opus、簡單工作與雜活 sonnet；做事的 agent（簡單／雜活除外）先讀 wf 規矩；agent 可再派 agent、模型隨意。
2. **狀態**：今晚做了試驗場 `~/code/playground` 的 A（對話簿＋inbox tool）→ 使用者看完改方向（射後不理／射後有理兩個場景，inbox tool 先擱著）→ agent-bob-1／2 兩場景實跑（say／listen 直接可用）→ 隊長帶回八題 → 頂層再想成三題，使用者說「先等等吧，把這些都記錄到thinking，明天我們繼續想」。明天從 [thinking 10-29 agent-bob § 頂層對八題的再想](../proto8/thinking/2026-10-29-agent-bob.md#頂層對八題的再想10-29-晚使用者幫我多想想後未定) 接（三題也在 [WAIT_USER](WAIT_USER.md) 第一條）。
3. **新規**：無（決定 32 旁已註先擱著）。

## 2026-10-28 晚（家中 Manjaro；新 session 開場）

1. **授權**：可隨意 push。分工：普通事 opus、雜活 sonnet；做事的 agent（雜活除外）先讀 wf 規矩；agent 可再派 agent、模型隨意。
2. **狀態**：開場只看了狀況、還沒動工；設計已定等實作的是 agent-round（[SESSION-LOG](SESSION-LOG.md) 第一條）。
3. **新規**：無。

## 2026-10-27（家中 Manjaro；playground 重來、aos-mcp、aos-hub）

1. **授權**：可隨意 push。分工：普通事 opus、雜活 sonnet；做事的 agent（雜活除外）先讀 wf 規矩。
2. **狀態**：playground（`~/code/try/playground`）10-26 砸掉一步一步重來：`_entry` 一行轉 `main.py`（ELI5 注解），`claude -p` 經 aos-mcp 叫 aos 工具；aos-hub 管多個 claude，使用者說是 demo、以後再完善。下一步等使用者說 → [SESSION-LOG](SESSION-LOG.md) 第一條、統整頁 https://claude.ai/artifact/W7aXZvCPTf1u2qExH6CEMM
3. **新規**：無；代定在 [thinking 10-26 playground](../proto8/thinking/2026-10-26-playground.md)、[10-27 claude-switch](../proto8/thinking/2026-10-27-claude-switch.md)。

## 2026-10-26（家中 Manjaro；整理與精簡全部完成）

1. **授權**：可隨意 push（commit 後直接 push origin main）。分工：普通事 opus、雜活 sonnet；做事的 agent（雜活除外）先讀 wf 規矩。
2. **狀態**：今天 proto8 頂層整理與文件內容精簡全部完成，經過見 [session log 10-26](session_logs/2026-10/2026-10-26.md)。使用者還在改 `proto8/user-advice/README.md`，等他說好再動，不碰該資料夾。10-25 的「問題點」仍待使用者說（見 [WAIT_USER](WAIT_USER.md)），說之前不要自己續做兩隊。
3. **新規**：日誌每日檔每條一行、結論只連過去（[user/02](workflows/common/user/02-交接與收工.md#日誌怎麼寫2026-10-26-定)）；wf-lint 改可選。

