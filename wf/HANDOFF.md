# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-01 下午（家中 Manjaro；使用者在試驗場邊說邊做，接著 compact 或開新 session）

1. **授權**：可隨意 push；普通事 opus、簡單與雜活 sonnet；做事的 agent（雜活除外）先讀 wf 規矩、可再派 agent；工人只 `git add <明確的檔>`、不 `-A`、不 force／reset、不碰 stash。**若是開新 session**：照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問一次 push 與模型分配，其餘照本條接著做。頂層 Bash 裡 `ls` 要寫 `/bin/ls`（eza 會掛住，gotchas 04）。
2. **正在做（compact 後或新 session 接著做）**：使用者在 `~/code/playground/ws`（已 `source env.sh && cd ws`，`ws/` 空、新建 `agents/`），**一步一步說他想幹嘛，頂層告訴他要下什麼指令、先把東西備好、把他途中說的想法逐字記進 [thinking 11-01 playground-bob](../proto8/thinking/2026-11-01-playground-bob.md)**。目前做到：`agents/bob`＝`_entry.json`（claude -p haiku、工具 Read／Write／Edit／Glob／Grep、acceptEdits、`--add-dir {$env AOS_WS}`、`--append-system-prompt-file system.txt`）＋`system.txt`，`aos-exec ../agents/bob -- "題"` 實跑過、使用者自己也跑了詠桃花那題（「體驗還不錯」）；他問過 `--` 後面是否直接進 claude、stdout 是否直通終端（都是：argv 陣列入口＝exec）。**他剛定的原則**：環境變數像 Janet 的 `dyn`、只在必要時用（原文在 thinking；待他展開哪些 `AOS_*` 算必要）。下一步等他說。測 bob 時 stdin 要 `</dev/null`、ws 跑完清回空（`hello.txt`、`.stack/`）。
3. **今天其他已做**：A 題 parts 瘦身（`562117c3`、`632d44c1`、`d61e17eb`：aos-parts 刪、parts.json 換 aos-exec 格式、`--on-empty`）、使用者裁五題（[決定（11-01）](../proto8/thinking/2026-10-31-parts-round.md#決定11-01-使用者)）、條文改口（C-74／C-61／C-51 加註，沒有新條號）、10 月月摘要、八份 artifact 回寫（`c806886c`）、分支與舊建置殘骸刪。round 五格收不收等使用者深思（SESSION-LOG open）。
4. **artifact**（家機桌面只有 bob-1、bob-2 的 HTML 副本）：現況地圖 https://claude.ai/artifact/Cjgx6VAwCvMYirsMHdNrji 、親手試指南 https://claude.ai/artifact/WSrwpLQqibw2QC2tfwwM3m 、proto8 概念層 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、proto8 實作想法 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 、aos 指令與格式參考 https://claude.ai/artifact/XFA2HA5WbeBpkJyC7wGSCn 、proto8 入口與 demo https://claude.ai/artifact/TVnjc4gvpgWjQnU3WJujtt （10-31 早與午兩次回寫、11-01 照 parts 瘦身再回寫，都同網址，[11-01 校對表](session_logs/2026-11/2026-11-01-artifact-回寫.md)；公司那台桌面副本是舊版，回公司時重存）；bob-1 說明 https://claude.ai/artifact/LMYYuQs3kueatcQyM9TXim 、bob-2 說明 https://claude.ai/artifact/3a2NLJtXrez8T75L4Zq1oM （bob-1 11-01 改一處、同網址，桌面副本已同步；bob-2 不用改）；今日摘要 https://claude.ai/artifact/FbYPqXyn8Pj2K1mWZ6b8Wf （v2，10-31 下午版）。
