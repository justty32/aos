# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-01 晚收工（家中 Manjaro；明天開新 session 接）

1. **授權**：今晚是隨意 push、普通事 opus、簡單與雜活 sonnet、做事的 agent（雜活除外）先讀 wf 規矩、可再派 agent。**明天開新 session**：照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問一次 push 與模型分配。頂層 Bash 裡 `ls` 要寫 `/bin/ls`（eza 會掛住，gotchas 04）。工人只 `git add <明確的檔>`、不 `-A`、不 force／reset、不碰 stash。
2. **正在做／明天要接的**：
   - **旋鈕改 argv／檔＋刪 aos-round**：opus 隊長在 git worktree `.claude/worktrees/agent-a279443ccbe53ca97`（分支 `worktree-agent-a279443ccbe53ca97`，起點 `80786461`）做；使用者 11-01 晚說「弄一弄，全部上main，push」，由頂層 11-01 晚收尾時併入 main 並 push（寫這條時還沒併，詳見 git log）；試驗場 `nia-idle`（loop.json、README）跟著改。明天先確認 main 上有沒有併進來、ctest 與 proto8 測試綠。
   - **整體瘦身**：使用者定方向「就是整體要瘦身」「這塊等明天再說」——範圍等他明天定，頂層不代開 → [02 § 整體要瘦身](../proto8/thinking/2026-11-01-playground-bob/02-環境變數要使用者裁的問題.md#整體要瘦身11-01-晚使用者定方向明天再說)。
   - **環境變數第 4 題（傳話筒）仍待裁**：剩 `AOS_IVY_BRAIN`、`AOS_IMPROVE_RUN`（`AOS_ROUND_AGENT` 隨刪 aos-round 消失）；使用者兩次沒聽懂、第三次頂層用例子講，他沒回。
   - **試驗場 agents/amy 原型**（`d6e50ea7`）：兩個視窗（視窗一 `aos-exec ../agents/amy -- "題"` 進 claude 畫面、視窗二 `aos-say … && aos-listen`），實測 say 進畫面 2.5 秒拿到回答；使用者有沒有親手試過不確定。他收工前說「好煩，整個都怪怪」「算了，今天先這樣，明天再說」，頂層問哪裡怪、他沒答——明天先問這個 → [thinking 11-01 playground-bob](../proto8/thinking/2026-11-01-playground-bob.md)、WAIT_USER 最上面那條。
   - **今晚裁定清單**（環境變數五題，→ [02 § 使用者裁定](../proto8/thinking/2026-11-01-playground-bob/02-環境變數要使用者裁的問題.md#使用者裁定11-01-晚)）：1 hub 型不用改；2 腦三個到時候再說（之後腦由某 kernel 統一管、大多 agent 向 kernel 遞請求，可有 `AOS_BRAIN` 指向 kernel）；3 改（「這就是濫用...除非真的有必要的，否則不要用」）；4 待裁；5 `AOS_ENTRY` 不拿掉；另裁刪 aos-round 整支（「這應該整個都不需要吧」「刪掉」，→ [02 § 刪 aos-round](../proto8/thinking/2026-11-01-playground-bob/02-環境變數要使用者裁的問題.md#刪-aos-round11-01-晚使用者裁定)）。
   - 試驗場 `~/code/playground/ws/` 裡還有使用者下午自己跑的 `詠桃花.md` 與空 `.stack/`，沒清。
3. **今晚沒有新條號**。thinking 裡的情緒句已照使用者要求刪除、git 歷史已改寫（main 自 `80786461` 之後的 commit 改寫、強制推上 origin）；公司那台 clone 要 reset 到改寫後的 main（WAIT_USER 有）。
4. **artifact**（家機桌面只有 bob-1、bob-2 的 HTML 副本）：現況地圖 https://claude.ai/artifact/Cjgx6VAwCvMYirsMHdNrji 、親手試指南 https://claude.ai/artifact/WSrwpLQqibw2QC2tfwwM3m 、proto8 概念層 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、proto8 實作想法 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 、aos 指令與格式參考 https://claude.ai/artifact/XFA2HA5WbeBpkJyC7wGSCn 、proto8 入口與 demo https://claude.ai/artifact/TVnjc4gvpgWjQnU3WJujtt （11-01 照 parts 瘦身回寫過，[11-01 校對表](session_logs/2026-11/2026-11-01-artifact-回寫.md)；公司那台桌面副本是舊版，回公司時重存）；bob-1 說明 https://claude.ai/artifact/LMYYuQs3kueatcQyM9TXim 、bob-2 說明 https://claude.ai/artifact/3a2NLJtXrez8T75L4Zq1oM ；今日摘要 https://claude.ai/artifact/FbYPqXyn8Pj2K1mWZ6b8Wf （v2，10-31 下午版）。
