# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-31 夜（家中 Manjaro；頂層 session 收工，使用者要重開新 session 做其他事）

1. **授權**：這個 session 給的是：可隨意 push；普通事 opus、簡單與雜活 sonnet、規劃與收斂 fable（盡量少用）；做事的 agent（雜活除外）先讀 wf 規矩、可再派 agent；工人不 commit 或只 `git add <明確的檔>`、不 `-A`、不 force／reset；`stash@{0}`（10-29 舊 stash，午間工人誤動後已由頂層照 8bab15e2 復原）不動；未追蹤的 `proto8/impls/aos-gate/`、`aos-kernel-llm/` 不碰、等使用者點頭刪。腦走 LiteLLM（`http://localhost:4000/v1`）用 GPT（`chatgpt-gpt-6-sol`），claude 那層用 haiku；測試在家機 `nice -n 10`、一次一個程序。**新 session 照 [user/01](workflows/common/user/01-說話授權與記憶.md#push-授權) 重問一次 push 與模型分配**。下午使用者在外時的代定清單在今日摘要頁；傍晚／夜間的兩件代定記在 [10-31 日誌 § 代定](session_logs/2026-10/2026-10-31.md#傍晚夜間代定)。
2. **狀態**：最新 commit 是本收尾那筆（前一筆 `5859dbbc` fable 收斂）。驗證基準（最近一次 main 全套）：root ctest 8/8、proto8 800 案 0 fail 8 skip（LiteLLM 沒開＋python-dotenv 缺）、wf-lint broken=0。今天做完：artifact 回寫、eca／命名批次（aos-eca-turn、`--on-empty`／`--on-busy`、AOS_ 前綴 49 個，五點代定使用者回「都按照預設」）、thinking 35 份拆檔、aos-ai 與 test_round 拆檔。**最後一題**：parts 組合化＋round 重切草圖已由 fable 收斂（parts 退成 aos-exec 格式的約定＋`which`／`run` 薄殼、round 不重切、只吸收 `--on-empty` 改 argv）→ [thinking 10-31 parts-round](../proto8/thinking/2026-10-31-parts-round.md)；**衝突 3 條、方向題 2 題在 [WAIT_USER](WAIT_USER.md) 前兩條等使用者裁**；實作計畫 A 題四步寫好、**等使用者裁衝突 1 後才動工**，B 題零步。使用者最後一句：「先等等，按照wf/規矩整理收尾吧，我想要重開新session做其他事情」——新 session 是做別的事，上面這題不主動推，他問起再講。開著的其餘題見 [SESSION-LOG](SESSION-LOG.md)。唯讀 session aos-ce 已關；另有 peer session aos-9a，頂層沒聯絡過它。**新 session 開場第一次動日誌時順手做 10 月月摘要**（[user/02](workflows/common/user/02-交接與收工.md#日誌怎麼寫2026-10-26-定)：已進 11 月；做法：每日檔濃縮成 `session_logs/2026-10.md`、原檔封存、commit 訊息寫「內容精簡」）；11 月日誌開 `session_logs/2026-11/`。
3. **artifact**（桌面各有同名 HTML）：現況地圖 https://claude.ai/artifact/Cjgx6VAwCvMYirsMHdNrji 、親手試指南 https://claude.ai/artifact/WSrwpLQqibw2QC2tfwwM3m 、proto8 概念層 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、proto8 實作想法 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 、aos 指令與格式參考 https://claude.ai/artifact/XFA2HA5WbeBpkJyC7wGSCn 、proto8 入口與 demo https://claude.ai/artifact/TVnjc4gvpgWjQnU3WJujtt （10-31 早與午兩次回寫、同網址；公司那台桌面副本是舊版，回公司時重存）；bob-1 說明 https://claude.ai/artifact/LMYYuQs3kueatcQyM9TXim 、bob-2 說明 https://claude.ai/artifact/3a2NLJtXrez8T75L4Zq1oM ；今日摘要 https://claude.ai/artifact/FbYPqXyn8Pj2K1mWZ6b8Wf （v2，下午版；**沒含傍晚／夜間的 aos-var 收回、round 重切草圖、fable 收斂**，新 session 要的話補 v3）。
4. **新規**：10-31 沒有新條文。白天兩條加註：C-74 加 parts（「與 fsm 平級的標準庫」）、C-51 加註（固定名字限縮到單一入口檔）；**收斂的衝突 1 就是建議把 C-74 這條加註改口**（parts 改列 agent 慣例層的約定）、衝突 2 是 C-51 加註跟 10-28 決定 16「註冊檔沒寫＝固定名字」的 fallback 打架（建議先留）——都等使用者裁，條文這輪沒動。
