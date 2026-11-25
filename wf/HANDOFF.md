# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-25 23:0x（家機）——proto9 做減法：daemon 當容器、名字交給 kernel；睡前推一次

**寫這條的是家機 repo-aos 樹的 `main`**（Claude Code，模型 Opus 5.5）。細節在 [`wf/ws/main/notes.md`](ws/main/notes.md)「2026-11-25 晚（家機）」那節。上一條是公司 `eca-aos` 的 11-25 17:0x（proto9 小庫、daemon、aos-exec 交件與下一批 1～6），全文在 git 歷史 `3cc5beb2e`；還有效的摘在下面「公司那條還有效的」。

**接手先讀**：這條 → [daemon當容器-1125](../proto8/thinking/2026-11/25/daemon當容器-1125.md)（第一～九輪：每輪定了的、實測數據、提案）→ 原話在 [9p-proc-1125](../proto8/thinking/2026-11/25/9p-proc-1125.md) 第 30～39 段 → progress `proto9-sky-1125`。

**授權（11-25 晚當場）**
- **push 用掉了**：使用者 23:0x「差不多了，我想睡覺了，東西收拾收拾 push吧」→ 推了今晚的 commit 和這條交接；小實驗回來、驗完的那批照同一句再推一次。**之後要推得他再說。**
- 小實驗：「可以來做小實驗，隨意做」（第 34 段）。下一批四樣（就緒、事件、按需起 kernel、進天空的工具）他說「看起來都OK，就先這樣吧」（第 37 段），**還沒派**。
- 子 agent：實驗用 Claude Code 的 Agent 工具派 opus（背景），不 commit，回來 main 重跑、查殘留再交。

**今晚使用者定的**（原話與理由在上面兩份）
- **做減法**：`procs/<名>/` 底下不規定任何東西；ctl、sock、status、mailbox、ctl 的鎖都歸之後的 agent 界面；aos-procfs 變成寫 agent、kernel 時用的庫。**這動到下午草稿 01 的前提；草稿怎麼跟上，等他看過實驗再說，別先改。**
- **界面**＝檔案布局＋格式內容正確＋在指定條件下存取得到（權限、限時回應），做得到就是那個東西；量得出來，量到的是 `_metainfo` 客觀那半。不提供界面的程式，daemon 也能粗管（訊號、cgroup freeze）。
- **daemon 只管碰 Linux 權力的五樣**：起收行程（自己 PID namespace 的 1 號）、組天空（每隻 proc 一個 mount namespace）、給身分（uid）、起動前上鎖（丟 caps、Landlock、seccomp、cgroup 上限）、把開關發給 kernel。**kernel 管所有決定**（排程、額度、准不准、名字給誰）。起 proc 直接用 bwrap（或 runc／crun），我們只寫上面那層。
- **攔截**：把名字交給 kernel（天空裡擺 stub、socket、FUSE 或靜態夾），不攔系統調用。靜態的夾也算 kernel（登記表標 `dir`／`exec`／`fuse`／`socket`）；要握呼叫者不該有的東西才需要自己的行程。
- **登記與天空**：kernel 登記只代表「提供」，起 proc 的一方明寫才算「選用」；只能往下傳自己有的；天空起來時定好、記成表（可印出來，像 Plan 9 的 `ns`），跑的時候改得了，但要明確下指令。
- **PID namespace 開**：daemon 一死，底下整片收掉（取代下午「daemon 掛了底下還活著的不管」）；推薦用名字、盡量不用 PID。
- **繞圈不限制**（風險自負）；依賴鏈做軟性檢查（kernel 登記時寫依賴、起 proc 的人自己問 daemon；daemon 可開「不准成圈，有就拒絕登記」）。
- **天空是共用的路由、不是牆**；要牆就另開一台 daemon（以後 daemon 也許能把 uid 分給 proc）。替別人做事花的資源，各 kernel 自己處理。
- **之後訂「aos proc 界面」＝能跟著 daemon 一起重起**；不符合的也能當 proc，風險自負。（跟下午草稿 01 的「aos proc 介面」不是同一件：那份的 ctl、status 已搬去 agent 界面。）
- /usr 先不管（可重現是很遠以後的事）。

**之後再談（不催）**：網路；每個呼叫者一條 socket；daemon當容器 第八輪第 7～11 條（合併目錄、天空表記是誰要的、界面怎麼寫與改版、上千隻的掛載傳播、persists 誰清）；aos proc 界面的內容；agent 界面；daemon 分 uid 給 proc。main 第九輪補的兩點（隔壁 daemon 要真隔開，得有自己的 network namespace、不掛外面的 `/proc`；「重起得了」用 kill -9 再照設定起回來量）他還沒回。

**還在跑**
- 小實驗 `proto9/experiments/sky-1125/`（十項，Python 標準庫＋unshare／nsenter）：家機 opus 背景在做最後一遍驗證。回來 main 重跑、查殘留、交件（線 `home-proto9-1125`）、推。**origin 上沒有它的 commit，就是家機還沒收完；別在公司重做。**

**公司那條（17:0x）還有效的**
- 下一批 1～6（daemon 的 `add` 交給 aos-exec、`aos_obey` 擋冒名、程式裡 `persist`→`persists`、daemon 測試的競態、欄位表、plumber 式 `msg`）都還沒派。**今晚做減法動到其中幾條的前提**（ctl、status 不再是每隻 proc 必有），派之前先跟他確認，別照舊單子做。
- 等使用者（不催）：artifact 哪裡要改；aos-exec 要砍什麼；agent 檔案布局；草稿第 12 節；小庫與 daemon 挑的保守做法。
- 公司那台：上網的幫手 `tmux -L webref`（使用者說先留著，用法見 `3cc5beb2e` 那條）；core 閒置輪詢做到第 3 刀就停；repo 根的不明檔 `ls`。
- 家機 sonnet 讀 proto9 程式看到的（main 只對過第一條那行，都沒改）：`aos-daemon/src/main.cpp:132` 靠「`AOS_ROOT` 沒設」判斷自己是不是根，殼裡殘留舊的 export 就會誤判；`procs/<名>` 的 symlink 帶 PID；stop 用 `hold_until_exit`，行程不結束，鎖就一直停在 doing。

**其他 open 的 progress**：`aos-goals-1124`（等使用者）；`narr-amber-fb-1124`（等某個 session 重開、用上新的 aos-mcp 後，實地試 listen 時叫 mailbox_peek，過了就刪）。今晚沒有新的規範條目。
