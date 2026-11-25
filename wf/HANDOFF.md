# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-25 12:5x（公司）——9P proc 談了兩輪、第一波報告收完；使用者要換帳號用 fable 開新畫面

**寫這條的是公司 repo-aos 樹的 `eca-aos`**（這時是 Opus）。細節在 [`wf/ws/eca-aos/notes.md`](ws/eca-aos/notes.md) 最後三節（11:0x、11:1x、12:0x、12:4x 起）。上一條（11-25 10:4x）在 git 歷史 `6bc0b5918`。

**接手先做**：這次是換帳號開的新對話，aos history 裡的摘要是錯的（慢一拍，見下），**不要靠它**；先讀這條、筆記最後幾節、[9p-proc-1125](../proto8/thinking/2026-11/25/9p-proc-1125.md)、[架構規劃入口](../proto8/thinking/2026-11/25/aos-proc介面架構規劃-1125/README.md)。

**使用者最後的話（逐字）**：「來聊一下，看看報告內容，我們看看有哪些是可以做的」→ eca-aos 回了一份「可以做的」分四類（見下）；他接著說「你等等，我要用另一個帳號開fable。請你先收尾，整理」。**他還沒答那份建議**。

**授權（11-25 當場）**
- **push**：「今天四點五十五push」——16:55 推一次 `origin main`，只這一次；鐘 `push-1655` 已登記（寄進 eca-aos 自己的 queue）。推前看 `commit-request claims`、工作樹、`git pull --rebase`。本地領先 origin 約 27 個 commit。repo 根有一個沒追蹤的檔 `ls`（內容「1」，11:01 建，來源不明）——推前刪掉或問一句。
- 子 agent：使用者 12:4x 說「停」，第二波（綜合）、第三波（檢查）**不做**，除非他再說。

**9P proc 已定的**（全文與原話在 9p-proc-1125「定了的」）：介面＝目錄長相＋檔案內容格式，實作（硬碟、tmpfs、FUSE、真 9P）一個一個來；ctl／status 純文字（寫 ctl 回來＝收到；status 一行一個「名稱: 值」，目前只給 status）；_metainfo 照現有 json；token 各自報；daemon＝Linux 與 aos 的橋、也是 aos proc、有 procs 夾；kernel＝普通 aos proc；入口是根 daemon 的 PID（實測要寫 `/proc/<PID>/cwd`）；stack＝活著的 proc 的身體、要留的放 `procs/<名>/persist`；persist 位置以 proc 的 settings 為準、daemon 預設在 /tmp 開一塊；活著走 unix socket，掛了問 daemon 或 kernel 信箱在哪改寄信；叫醒是 daemon 可選設定。

**給使用者的建議（等他答）**
1. 今天就有、跟新模型無關：同時寫 ctl 會丟一道且誤報成功（報告 01）；eca 沒有 token 帳（14）；兩處條文與程式不符（01 第 6 節 → kb）。
2. 加法、不停機的第一步：a 多寫純文字 `status`（改名換檔）、b `ctl` 收純文字 stop／pause／resume、c 寫 `settings`、d daemon 給純文字 `procs_status`、e json 工具只讀認「名稱: 值」、f eca 自報累計 token。a～d、f 派 core，e 派 kb；1 跟 a、b 同處一起做。
3. 先要他裁：報告 18 第 8 節問 1～3（ctl 字表、daemon 管列寫 `procs_ctl`、停著的列用 `procs_status`，都推薦照推薦）；16 的四處衝突（no-pid、可遷移性、不依賴 symlink、一般 proc 只看 kernel——11-17「新的覆蓋舊的」，只要他看後果接不接受）；子帳號／沙箱走不進 `/proc/<PID>/cwd`（不急）。
4. 先不做：閒置輪詢第 5、6 刀暫緩（17；**還沒跟 core 說**，等使用者點頭）；socket 那條（20）排在 a～f 之後；FUSE／真 9P 以後。

**還在跑**
- core：閒置輪詢第 2 刀 `aos-idle`（工作樹那幾個改動的檔都是它的）→ 第 3 刀掛範本前會回 PROGRESS 等一句 → 1125f：/compact 後 history 摘要慢一拍（`cli_hook.py:283`）＋「人先開口就不補送前情」（兩封信：`01795575799313822211…`、`01795581936374875417…`）→ compact 第 3 刀 clear-tools。
- kb、templates：空。

**今天其他**：掛了子 daemon `mine_skyrim`（/mnt/c/code/mine/modding_skyrim）、`mod_tome4`（/mnt/c/code/mine/modding_tome4），各一隻 `main`（eca-claude-alt）；mine_paper、mine_mecha、mine_arena 的 .env 加了 `CLAUDE_CONFIG_DIR=${HOME}/.claude-alt`（mine_paper 已重起生效，另兩棵下次起樹）；guanyu 那棵沒動。repo-aos 四隻答信本來就走 ~/.claude-alt，**開畫面要同帳號**：`CLAUDE_CONFIG_DIR=~/.claude-alt aos-agent -t eca-aos open`。

**等使用者（不催）**：上面第 3 類；第二類親手試、三類 12～14 先放著（照上一條）。
