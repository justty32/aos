# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-01 早（家中 Manjaro）

1. **授權**：可隨意 push；普通事 opus、簡單與雜活 sonnet；做事的 agent（雜活除外）先讀 wf 規矩、可再派 agent；工人只 `git add <明確的檔>`、不 `-A`、不 force／reset、不碰 stash。
2. **已做（11-01）**：A 題（parts 瘦身）做完——`aos-parts` 整支刪、沒留殼，器官共用 `lib/agent/parts.py` 找格（註冊檔 → 固定名字），`parts.json` 換 aos-exec 格式（`632d44c1`）；`AOS_ROUND_ON_EMPTY` 改 `aos-round --on-empty`（`562117c3`）；文件與條文改口另一筆 → [thinking 10-31 parts-round § 05 實作計畫](../proto8/thinking/2026-10-31-parts-round/05-方向題與實作計畫.md#實作計畫)。使用者今早裁了五題（[決定（11-01）](../proto8/thinking/2026-10-31-parts-round.md#決定11-01-使用者)）：parts 改列 agent 慣例層的約定；註冊檔與固定名字共存；round 不重切、使用者要深思（SESSION-LOG 一行 open）；parts.json 不併；收五格的門檻只當參考、比技術棧優缺點。分支 `wip/hub-step6` 與未追蹤的 `aos-gate/`、`aos-kernel-llm/` 已刪。10 月月摘要已做。
3. **artifact**（家機桌面只有 bob-1、bob-2 的 HTML 副本）：現況地圖 https://claude.ai/artifact/Cjgx6VAwCvMYirsMHdNrji 、親手試指南 https://claude.ai/artifact/WSrwpLQqibw2QC2tfwwM3m 、proto8 概念層 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、proto8 實作想法 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 、aos 指令與格式參考 https://claude.ai/artifact/XFA2HA5WbeBpkJyC7wGSCn 、proto8 入口與 demo https://claude.ai/artifact/TVnjc4gvpgWjQnU3WJujtt （10-31 早與午兩次回寫、11-01 照 parts 瘦身再回寫，都同網址，[11-01 校對表](session_logs/2026-11/2026-11-01-artifact-回寫.md)；公司那台桌面副本是舊版，回公司時重存）；bob-1 說明 https://claude.ai/artifact/LMYYuQs3kueatcQyM9TXim 、bob-2 說明 https://claude.ai/artifact/3a2NLJtXrez8T75L4Zq1oM （bob-1 11-01 改一處、同網址，桌面副本已同步；bob-2 不用改）；今日摘要 https://claude.ai/artifact/FbYPqXyn8Pj2K1mWZ6b8Wf （v2，10-31 下午版）。
4. **新定**：沒有新條號；C-74、C-61 10-28 再補、C-51 10-31 加註改口（連帶 CONVENTION P-25 的 10-28 補、NORMS／CONCEPTS 總覽與附錄的「標準庫」一句）。
