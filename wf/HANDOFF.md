# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：新條目插在最上面（本段說明之下），標題用二級標題加日期時間；舊條目已被新的取代就直接刪，最多留兩三條，細節靠 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-10-22（公司，WSL）

1. **授權**：本 session 使用者說可隨意 push，但 git 一律走 WSL（justty32）：`wsl git -C /mnt/c/code/mine/simple_tools/aos ...`；push／pull 加 `-c 'url.git@github.com:.insteadOf=https://github.com/'`（走 SSH，否則會卡住）。分工同 10-21：普通工作 opus、簡單雜活 sonnet、fable 只在點名時用；頂層只跟使用者交流；做事的 agent 先通讀 wf/ 規矩。
2. **今天做的**：s6／runit 對照寫進 proto8/notes；修 10-21 晚教學的小毛病；記使用者裁定（C++ 不補、不擋、aos-tick 擱置、第 3 點照舊、impls 等回家）；把公司帳號 commit 改寫成 justty32 並強推（新 main 2cd76e2d，對照表 [hashmap](session_logs/2026-10/2026-10-22-author-rewrite-hashmap.csv)）；simple_tools 的 gitlink 更新到 2cd76e2d（commit 7ecd5309）。
3. **open**：(a) **回家先 reset**：家裡 clone 是舊歷史，`git fetch` 後 `git reset --hard origin/main`，不要 pull/merge；上層 simple_tools 也 pull；見 [SESSION-LOG](SESSION-LOG.md) 最新進度。(b) impls 等回家：公司這台沒有 impls，要碰的都暫停。(c) fable 正在研究 aos-exec 能借用／直接呼叫 s6／runit 的地方，成果之後放 proto8/notes。(d) [WAIT_USER](WAIT_USER.md) 三個方向題（tasks、tool_calls、兩種 kernel）仍等使用者。

## 2026-10-21 晚（在家）

1. **授權**：本 session 使用者說「可以隨意 push」，在家。分工：普通工作 opus、簡單雜活 sonnet、fable 只在點名時用；頂層只跟使用者交流；做事的 agent（雜活除外）先通讀 wf/ 規矩。
2. **今晚完成並 push**：aos-tick（9d618174、72e9eb26）；10-21 下午代定 11 條使用者確認（7600357a）；impls 對齊 bin 10-21 全部改動，含 aos-exec 的 `--ws`／`.env`／AOS_CO（impls 未追蹤，備份在 `proto8/impls/backup/2026-10-21-night/`），規範的「impls 尚未對齊」字樣已清（6ee07ce0）；七份 proto8 相關 artifact 已更新到現況。
3. **open**：[WAIT_USER](WAIT_USER.md) 剩三個方向題（tasks、tool_calls、兩種 kernel）＋ aos-tick 8 條代定；待問使用者：impls 要不要補 C++ 版 aos-tick。
