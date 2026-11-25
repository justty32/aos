# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-25 16:2x（公司）——proto9 開了：介面草稿、C++ 小庫、daemon 在寫；aos 自動叫收尾（context 38%）

**寫這條的是公司 repo-aos 樹的 `eca-aos`**（這個畫面用主帳號 `~/.claude`、模型 Fable；答信的 loop 走 `~/.claude-alt`）。細節在 [`wf/ws/eca-aos/notes.md`](ws/eca-aos/notes.md) 最後三節（13:4x、14:0x 起）。上一條（11-25 12:5x）在 git 歷史 `76a776975`。

**接手先讀**：這條 → 筆記「2026-11-25 14:0x：換成 Fable，9P proc 第二輪」那節到底 → [proto9/README](../proto9/README.md)、[介面草稿](../proto9/docs/01-aos-proc介面草稿.md)（【定】【擬】【開】三種記號；第 12 節是還沒定的）。使用者原話全在 [9p-proc-1125](../proto8/thinking/2026-11/25/9p-proc-1125.md)（第 10～21 段是今天下午）。

**授權（11-25 當場）**
- **push**：「今天四點五十五push」——16:55 推一次 `origin main`，只這一次；鐘 `push-1655` 會寄進 eca-aos 的 queue。推前：`commit-request claims` 空、`git pull --rebase`、16:50～17:00 不交件；repo 根那個沒追蹤的檔 `ls`（內容「1」，來源不明）推前刪掉或問一句（沒追蹤，不影響 push）。
- 使用者五點下班（昨天如此，今天沒說，照舊當作會）。
- 子 agent：proto9 的施工用 Claude Code 的 Agent 工具派 opus（背景），不 commit，回來 eca-aos 自己重編、跑測試、查殘留再交。

**今天下午定的大事**（全文在草稿）
- 「落檔...不算，我們直接起proto9」：proto8 的 aos-loop／daemon 不改造；新介面在 `proto9/` 從頭做；基礎用 C++；第一步每隻 proc 用 FUSE 把自己的目錄掛出來（當場回答）。proto8 照常跑照常修。
- 介面：`ctl`（一行一道、寫回來＝收到、從寫進到做完鎖住、回饋 `aos_ctl_*` 四行、state 有 doing／done／failed／rejected）、`status`、`settings`、`attrs`（`aos_kind`、`aos_live`…）、`_metainfo.json`、`persist`；`aos_` 開頭＝標準行；daemon 多 `procs/`、`procs_ctl`（add／rm／stop／start／kill／register；做完＝daemon 這邊動作做完）、`procs_status`（`名字.欄`，含 want、stuck）。
- 卡住：每隻 proc 至少留一條線回答別人；回答只用自己記憶裡的東西（「總之就是要守規矩，就是要自己承擔風險」）；daemon 定期查、只記不收、卡住的從 `procs/` 拿掉；被 Linux 暫停的算卡住；daemon 掛了底下的不管；死掉的掛載由 daemon 收。
- 基礎 IPC 機制兩類：寫檔（普通檔、FUSE）與串流（unix socket）；aos post 建在寫檔之上。活著的 proc 收信：`mailbox/`（照 Maildir，先做）、`msg`（照 plumber）、`sock`，各 proc 自己選。socket 八點照推薦。
- 可遷移性現在不動，遠期目標 `cp AOS_ROOT` 搬走一切。`AOS_ROOT` 由人手動 export。

**做出來的**（都交了、沒 push）
- `proto9/docs/01-aos-proc介面草稿.md`（第 1 版）、`02-可以抄的現成做法.md`、`refs/前例調查-1125.md`、`pages/aos-proc.html`。
- `proto9/experiments/fuse-proc-1125/`（Python 玩具）。
- `proto9/cpp/aos-procfs/`（C++ 小庫，35 條測試過；eca-aos 重編重跑過）。
- Artifact：<https://claude.ai/artifact/CaD7a7bwGkh2WxLTRHfMVN>（用 `~/.claude-alt` 帳號發佈、預設私人；沒人預覽過，等使用者看了說哪裡要改；原始檔 `proto9/docs/pages/aos-proc.html`）。

**還在跑**
- **寫 daemon 的子 agent**（opus，背景，16:0x 派出）：`proto9/cpp/aos-daemon/`，暫存 `~/.aos/scratch/proto9-daemon-1125/`，可小改 aos-procfs。回來後：`make`、跑 `proto9/cpp/aos-daemon/tests/run.py` 與 `proto9/cpp/aos-procfs/tests/run.py`、`grep aosproc /proc/mounts` 查殘留、看 README、交件、報使用者。**compact 之後它的完成通知可能收不到**：直接看那個夾有沒有 README 與 tests，自己驗。
- **上網的幫手**（不在 aos 體系）：`tmux -L webref`，`~/.aos/scratch/web-ref-1125/launch.sh` 起的 Claude Code（`~/.claude-alt`、sonnet、dontAsk，放行上網、讀寫、Skill、Artifact）。送話：用 `proto8/lib` 的 `aos.agentlib.cli_a2a.wire` 包信封，寫 `/run/user/1000/cc-socks/<它的 PID>.sock`（PID：`pgrep -f "claude --model sonnet --permission-mode dontAsk"`）。使用者說先留著。改版 artifact：改 repo 的 html → 抄到 `~/.aos/scratch/web-ref-1125/artifact/aos-proc.html` → 請它對同一個檔再發佈。
- core：閒置輪詢做到第 3 刀就停（第 4～6 刀不做，已寄信）；1125f（摘要慢一拍＋人先開口不補送前情）；compact 第 3 刀。工作樹裡 `proto8/cpp/aos-idle/` 等改動是它的。kb、templates 空。

**daemon 回來之後要派的下一批**（同一批檔，不能跟 daemon 那隻同時）
1. 小庫加 `failed`（現在記 done＋error）。
2. 孫子行程會原樣拿到 `AOS_NAME`／`AOS_MOUNT`：抄 systemd 的 `LISTEN_PID`，多給一個「這是給哪個 PID 的」。
3. 小庫支援 Maildir 式的 `mailbox/`（別人照 aos post 放信；要 MKDIR／CREATE／RENAME）。
4. 之後：plumber 式的 `msg`、socket 上一行一則加回條。`src/answer.cpp` 391 行超過 300 行門檻，順手拆。

**等使用者（不催）**：看 artifact 哪裡要改；草稿第 12 節還沒定的（token 檔、persist 怎麼擺、register 的權力、sleep／wake、掛載點放哪、agent 的身體、換帳號）；小庫挑的幾個保守做法（草稿第 11 節末）。上一條留下的舊題照舊。
