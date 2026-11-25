# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-25 10:4x（公司）——上午派工收一段落；使用者 compact 後要聊 9P 的 aos proc 介面

**寫這條的是公司 repo-aos 樹的 `eca-aos`**，細節在 [`wf/ws/eca-aos/notes.md`](ws/eca-aos/notes.md) 最後一節「2026-11-25 上午」。上一條（家機 11-24 晚）在 git 歷史 `6fa990e80`。

**使用者 compact 前的話（逐字）**：「那你這邊整理一下，我compact。compact後來聊9p proc。」——**聊想法，不是派工**：聽、整理、擺選項，方向他定（鐵律 5）；談出來的記進 thinking（接 `proto8/thinking/2026-11/24/aos的目標-1124/`，或開 11-25 新夾）與 progress `proc-interface-spec`、`aos-goals-1124`，別自己開工。

**9P proc 的前情（他今天說的，逐字）**：「先不寫。因為整個aos體系可能會有大改動。就是以昨天講的那些為基礎，現有的aos-loop/daemon等實作都會變成普通實作，我們會規劃一套基於p9介面的aos proc介面，能支援這套的就是aos proc，這套介面昨天是說都用json。不過我可能會稍微改一下，改成部分用json」；相對路徑：「我希望是用具名錨點，一個最重要最根本的錨點就是離自己最近的頭上的那個daemon的stack。沒有的話那你就是root daemon，你是特殊存在。」昨天的討論在 progress `plan9-ns-1124`（FUSE／9P、每隻 agent 各自命名空間、會卡住等信的檔）與 aos的目標-1124 README 第 29～34、70～74 行（界面已有 ctl／state／state_flux、缺一頁規格、「怎麼知道你還活著」不能靠 pid）。tmpfs 量測結論：省的是 fsync 每次約 10 ms，閒置 CPU 在起行程（progress `fs-tmpfs-1124`）。

**授權（11-25 當場）**
- **push**：「今天四點五十五push」——16:55 推一次 `origin main`，只這一次；鐘 `push-1655` 已登記（寄進 eca-aos 自己的 queue）。推前看工作樹沒人在交件（`commit-request claims`）、pull --rebase。推了 Pages 就上線（MIT＋docs/ 另 CC BY 4.0）。
- 「一、可以，都可以動手」已用完（清家目錄、Codex 信任紀錄、Pages 發佈）。

**還在跑**
- core：idle-polling 第 2 刀 `aos-idle`（工作樹有它未交的 cpp/aos-idle/、Makefile、hook_clock.py 等）；第 3 刀掛範本 gate 前會回 PROGRESS 等我一句（會影響四個位子自己）。之後 compact 第 3 刀 clear-tools。
- kb、templates：空。

**等使用者（不催）**：第二類親手試（aos-compile、aos-inherit、setfacl、公司 WSL 兩件驗證）等他有空或回家；三類 12、13、14 先放著；aos 目標下午談。
