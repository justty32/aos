# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-31 早（家中 Manjaro；頂層 session 收工，使用者要開新 session）

1. **授權**：上個 session（10-30 晚～10-31 早）給的是：可隨意 push；普通事 opus、簡單與雜活 sonnet、規劃 fable；做事的 agent（簡單／雜活除外）先讀 wf 規矩；agent 可再派 agent；工人不 commit；只 `git add <明確的檔>`、不 `-A`、不 force／reset、`stash@{0}` 不動。**新 session 要重新問一次**。10-31 新 session 使用者已重給：可隨意 push；普通 opus、簡單與雜活 sonnet；agent 做事前先讀 wf 規矩、可再派 agent。腦走 LiteLLM（`http://localhost:4000/v1`）一律用 GPT（`chatgpt-gpt-6-sol`），claude 那層用 haiku。測試在家機本地跑，`nice -n 10`、一次一個程序；基準全套 794 案、0 fail、3 skip（`AOS_TEST_REAL=0`）。10-31 下午使用者在外，原話：「我現在人在外面，沒辦法想很多，所以想請你繼續推進，playground和artifact都持續更新。」「目標是四點前把token消耗完。對了，重構拆檔和tody也順便做」「不用試玩」。頂層照 [user/01](workflows/common/user/01-說話授權與記憶.md) 出門規則代定，代定清單在摘要頁。
2. **狀態**：10-30 晚四隊全收線——aos-round 第 2～7 步（`771747e1`～`ef379dc7`）、SESSION-LOG 三件收尾（aos-util 下放、round `letter_warning`、回信走 `reply_to`）、真腦實測（WAIT_USER 親手試六條代跑過、刪）、家機試驗場 `~/code/playground` 重建（舊的在 `playground-old-10-29/`）、真腦實測兩件小事修好（`57545c59`、`d069c6f7`）；最新 `13b45c7a`＋wf 兩筆。使用者親手跑過 bob-1、bob-2，兩份 ELI5 說明頁在桌面 `~/Desktop/bob-1-說明.html`、`bob-2-說明.html`（產生腳本在上個 session 的 scratchpad，沒進 git）；**試驗場剩 hub 畫面那段**（`~/code/playground/README.md` 第 5 節）。**正在討論**：使用者看了兩份說明頁後說「心中有些想法」「AI 能把東西做出來，但還需要人微調一下」——**內容還沒講，新 session 開場先聽他說**，照 [user/03](workflows/common/user/03-討論紀錄與規劃.md) 記原文、方向題交 fable 規劃。開著的題見 [SESSION-LOG](SESSION-LOG.md)；[WAIT_USER](WAIT_USER.md) 14 條（要裁的：aos_ws.py 失敗判法、`wip/hub-step6` 刪不刪、eca 代定；其餘親手試）。兩個舊建置目錄 `proto8/impls/aos-gate/`、`aos-kernel-llm/` 未追蹤、沒刪、等他點頭。**10-31 午隊長批次做完**：turn 改名 aos-eca-turn（`proto8/bin/`）、`--on-empty`／`--on-busy` 兩個 argv、AOS_ 前綴一次性全改（`a8d42682`、`9424ff9b`＋文件一筆）；代定已照預設定案（見下）。10-31 中午 eca／命名批次四件已做完 push（a8d42682、9424ff9b、ea8cea8d、a22dca43；代定五點使用者 10-31 回「都按照預設」、WAIT_USER 那行已刪，→ [eca § 實作時代定（10-31）決定](../proto8/thinking/2026-10-30-eca.md#決定10-31)）；工人誤動 stash，10-29 舊 stash 已由頂層照 8bab15e2 復原為 stash@{0}，仍不動。；15:20～15:40 tidy 35 份、refactor 2 件已 merge push；條文與 3 份 thinking 單段超標兩題進 WAIT_USER；傍晚新待議：aos-var（[thinking 10-31 aos-var](../proto8/thinking/2026-10-31-aos-var.md)）
3. **artifact**（桌面各有同名 HTML）：現況地圖 https://claude.ai/artifact/Cjgx6VAwCvMYirsMHdNrji 、親手試指南 https://claude.ai/artifact/WSrwpLQqibw2QC2tfwwM3m 、proto8 概念層 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、proto8 實作想法 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 、aos 指令與格式參考 https://claude.ai/artifact/XFA2HA5WbeBpkJyC7wGSCn 、proto8 入口與 demo https://claude.ai/artifact/TVnjc4gvpgWjQnU3WJujtt 。10-31 早已回寫（709f50cc 校對表）；公司那台桌面的六份 HTML 副本還是舊版，回公司時從網址重存。bob-1 說明 https://claude.ai/artifact/LMYYuQs3kueatcQyM9TXim 、bob-2 說明 https://claude.ai/artifact/3a2NLJtXrez8T75L4Zq1oM （10-31 早從桌面兩份 HTML 發成 artifact；bob-2 頁裡連 bob-1 的連結已改指 artifact 網址）；今日摘要 https://claude.ai/artifact/FbYPqXyn8Pj2K1mWZ6b8Wf （10-31 下午）
4. **新規**：10-30 晚無新條文；N-36 分岔已落正文（`ef379dc7`）。
