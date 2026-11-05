# 2026-11-05 午 第二輪邊緣實測（edge-round2：跨元件、時間軸、壓力、環境）

← [2026-11-05](../README.md)｜第一輪（不重測）：[edge-daemon](../edge-daemon/README.md)、[edge-llm](../edge-llm/README.md)、[edge-agent](../edge-agent/README.md)、[11-04 edge-basics](../../04/edge-basics/README.md)｜行為說明：[aos-daemon docs/08 當機復原與已知限制](../../../../impls/aos-daemon/docs/08-當機復原與已知限制.md)

使用者 11-05 午：「剛吃飽，想午睡...你繼續多測試一些邊緣狀況吧。」——他在午睡，方向題照推薦代定、不停線。修不修的尺：會壞資料、卡死、誤導的錯誤訊息、文件與行為不符就修；純屬亂用、成本高就寫一句文件（風險自擔）。

做法：WSL `/tmp/edge2-*`，三個測試員分頭測（T1 時間軸與壓力、T2 11-05 新行為的縫與英文化、T3 時鐘／權限／磁碟／訊號／兩人同時），隊長照回報修、再手跑驗。沒有免密 sudo、沒裝 faketime：改系統時間與小 tmpfs 做不到，改用 `touch -d` 假 mtime、`ulimit -f` 模擬寫不進去。

## 要你看的題（推薦放第一）

### 題 1：daemon 的狀態窗寫不進去（磁碟滿、stack 被改唯讀）時，要不要也「記一行、下一圈再試」

**白話**：現在 daemon 寫不了 `state.json`／`procs_state.json` 就整台退 1、把底下的 proc 全收掉（P-36 那套「寫不了狀態＝自己的錯」）。這輪已經修好「再起來時接得回來」（見下「修了什麼」1），所以資料不會丟；但磁碟一滿，整台 daemon 就停了，跟你上午裁的「身體失敗＝記一行、下一圈再跑」精神不太一樣。

1. **（推薦）寫不了＝stderr 一行、下一圈再寫，proc 照顧著**：只改 aos-daemon（aos-loop 照舊）。後果：磁碟滿的期間 `ls` 看到的表是舊的；騰出空間後自己好；要停用 ctl stop 或 Ctrl-C。
2. **照現況（退 1）**：再起時照這輪的修法接回；文件已寫。

## 測了哪些類、結果

| # | 類 | 情境 | 結果 | 處理 |
|---|---|---|---|---|
| 1 | 長跑 | daemon `interval_ms` 10 跑 770 秒（約 7.7 萬拍）＋兩個子 loop | 記憶體、fd、`procs_state.json`、log 都不長；`cur/`、`new/` 空 | 天然 |
| 2 | 長跑 | 子項每 10 ms 印一行 stderr | `stderr.txt` 每秒約 3 KB、一天約 277 MB，不輪替；`truncate -s 0` 可截 | 文件 |
| 3 | 幾千封信 | 3000 封 add＋stop、300 個並行 ctl add／rm、kill -9 後 `cur/` 2000 封重做 | 不漏不重；RSS 2.9→15.7 MB 後持平 | 天然 |
| 4 | 幾千封信 | 一批上千封時每列寫一次整張表 | 修前：1500 封 21 秒、這段 Ctrl-C 33 秒才理；修後 1.2 秒 | 已修 |
| 5 | 大量 proc | 50／100／200 個 loop 型 | 全起 0.1～0.34 秒、`ls` 24～38 ms、收工 65 ms、再開 0.1～0.4 秒；沒 fd 洩漏 | 天然 |
| 6 | 大量 proc | 表 4300 列、`interval_ms` 10；`interval_ms` 0 | 閒著 82% CPU；0＝吃滿一顆 | 文件 |
| 7 | 啟停風暴 | 同一個 proc 400 封 stop／start／sleep／wake；3 個 proc 300 次並行；daemon SIGINT／kill -9 各再起 30 次 | 表、小格、行程一致，沒殭屍孤兒 | 天然 |
| 8 | 當機 | daemon kill -9＋子項也死（斷電、`wsl --shutdown`、OOM） | 修前：表上的列**悄悄丟掉**（信加的永久消失）；修後：loop 型接成 `sleeping`、第一圈醒 | 已修 |
| 9 | 當機 | 列在 `stopping` 時 daemon kill -9 | 修前：**孤兒＋同一格再起一份**、舊的把小格 state 蓋掉；修後：接回接著收、退了留 `stopped` | 已修 |
| 10 | 當機 | 一批起 300 個途中 kill -9（4～8 輪） | 修前：7 個孤兒、6 格各兩支；修後：0 | 已修 |
| 11 | 當機 | resume 那圈在套一大批信時 kill -9 | 修前：再起後**一直暫停**（resume 被當基準線）；修後：照跑 | 已修 |
| 12 | 切檔 | 表超過 100 列、一邊增減一邊 `ls` | 修前：241 次錯 1 次 `StateBad … No such file`；修後 0／200 | 已修 |
| 13 | reason | 子項 stderr 一行 30 KB 以上 | 修前：**整台 daemon SIGSEGV（139）**；修後：截 300 字 | 已修 |
| 14 | reason | 上一次 stderr 有話、這次默默退 4；kill -9／SIGTERM | 修前：**引到前幾輩子的話**；修後：只看這一支之後寫的 | 已修 |
| 15 | reason | CR、ESC 色碼、非 UTF-8、切在多位元組中間 | 修後：控制字元換空白、不切在字中間（ls 也換） | 已修 |
| 16 | reason | `add` 剛起 0.1 秒就退 | 修前寫 `failed while running`；修後 `failed to start` | 已修 |
| 17 | 身體失敗 | 一直退 3、碼在 3／5 交替、執行檔不在、`interval_ms` 0 | daemon 那行碼變了才印（交替＝每圈）；身體／aos-exec 自己的每圈照印；0＝每秒約 500 次 | 文件 |
| 18 | `--reply-to` | 不在、一般檔、少 `new/`、唯讀、相對、空白、30 封同一信箱 | 都對；一般檔的訊息「not found」誤導 → `is not a directory` | 已修 |
| 19 | 權限 | 小格唯讀時 stop | 修前：**整台退 1**；修後：那支改送 SIGTERM、一行 stderr | 已修 |
| 20 | 權限 | 信箱 `new/` 唯讀時有信 | 修前：整台退 1；修後：`mailbox_warning`、下一圈再試 | 已修 |
| 21 | 權限 | stack 唯讀、`ulimit -f` 讓 `procs_state.json` 寫不進去 | 退 1（`WriteFailed`）；修前再起丟 13／16 列，修後接回 | 已修接回；題 1 |
| 22 | 時鐘 | 原始碼盤點 | interval、3 秒、10 秒 KILL、逾時都是 steady clock；牆上時鐘只在 aos-lock 的 mtime 年齡／租約、aos-post 信名、顯示用的時間 | 天然 |
| 23 | 時鐘 | 鎖資料夾 mtime 在未來（`touch -d "+1 day"`） | 修前：`send --ordered` **一直卡著**、沒訊息；修後馬上寄出 | 已修 |
| 24 | 時鐘 | aos-post 無序信名、aos-lock 租約遇時鐘跳 | 只讀程式碼：倒退時先後不保證、租約提早／延後 | 文件 |
| 25 | 訊號 | daemon HUP／TERM、SIGSTOP 30 秒再 CONT、子 loop SIGSTOP、SIGPIPE | 都照文件；USR1／USR2＝直接死（同 kill -9） | 文件 |
| 26 | 訊號 | 子 loop 被 SIGSTOP 後 stop | 列一直 `stopping`、提示只說「等它停」 → 補「卡住就 rm」 | 已修 |
| 27 | 兩人同時 | 15 輪 5 殼同時 add／rm／stop／start、3 殼同時 take、兩殼 take-all | 一致、不重不漏 | 天然 |
| 28 | 兩人同時 | 收工途中另一人起同一份 | `DaemonRunning` 叫人「沿用」→ 改說正在收工、等它退 | 已修 |
| 29 | 兩人同時 | 手把 `procs_added` 加 h1、另一人 rm h1；再刪手把檔 | rm 被宣告蓋回（照設計，寫文件）；**刪檔仍照跑**（跟 N-06 不符）→ 刪＝回初始值 | 已修＋文件 |
| 30 | 兩人同時 | 20 個 `aos-json set` 同時改同一份 | 只剩 1 個 key（文件已寫無鎖）→ docs 補 aos-lock 寫法 | 文件 |
| 31 | ctl | 列 stopped 時 `pause` | 修前：印 seq、退 0、其實丟了；修後 `PhaseBad` | 已修 |
| 32 | 英文化 | 領地八支的輸出全掃 | 沒中文殘留；usage `[flags...]`／`[args...]` 統一成大寫；install.sh 補代號 | 已修 |

## 修了什麼（commit）

- `503b6bab`、`2a0342df`（漏收的新檔 docs/08）aos-daemon：reason 手寫比對（不再 SIGSEGV）、只看這一支的 stderr、控制字元、add 算起來；當機後 running／stopping 的列接回、起 loop 型前小格有活的就接回；起一批時表最多每 200 ms 寫一次；resume 那圈先寫 state；切檔退役留 2 秒；小格 ctl 寫不了改 SIGTERM；信箱認領不了記 warning；收工途中的 `DaemonRunning` 訊息。
- `bdccbefb` aos-daemon：刪掉 procs_ctl.json＝回初始值。
- `60da876d` aos-daemon-ctl：pause／resume 只收 running、PhaseBad stopping 補「卡住就 rm」、ls 換控制字元。
- `819ffe9f` aos-lock：mtime 在未來 10 秒以上也算過期。
- `f6d2e521` aos-post 信箱不是資料夾的訊息；usage 統一；aos-json／aos-post／aos-loop 文件各一句。
- `c1e70dd9` install.sh 代號與字樣。
- 重建：13:47～13:49 aos-exec、aos-json、aos-loop、aos-fsm、aos-lock、aos-post、aos-daemon、aos-llm-kernel、aos-llm；13:53 aos-daemon。code map 01-impls-2 的 daemon.cpp 一列同步（沒新增檔）。

## 代定（可翻案）

1. 當機後 `stopping` 的列看不出當初是 stop、sleep 還是 rm：一律留 `stopped`（上一個 daemon 死時在收工的留 `sleeping`）；被 rm 的會多一列停著，再 rm 一次。不在列上多記「為什麼在收」。
2. 當機後 `running`、行程不在的 loop 型＝接成 `sleeping` 自動醒（同收工後開門），不留 `stopped`；子 loop 自己的 state 窗寫 `done` 的才不接。
3. 起 loop 型前看小格裡子 loop 的 state 窗（pid＋`started_at_ticks`）判有沒有活的；接回的拿不到結束碼，退了照舊下表。
4. 起一批時表最多每 200 ms 寫一次（看進度變粗一點）；切檔退役 2 秒才刪。
5. 小格的 ctl 寫不了＝那支改送 SIGTERM（同沒開 ctl 的），不整台退。
6. aos-lock：年齡 ≤ -10 秒（mtime 在未來）算過期；小幅倒退（10 秒內）照舊等。
7. reason 的 3 秒字樣，add 也算「起來」，原文 `within 3s of wake/start` 不改（別隊文件有引）。
8. 表大時每拍的 CPU、`interval_ms` 0、`stderr.txt` 不輪替、身體失敗時下層每圈印、USR1 等訊號、ctl stop 沒時限：只寫文件。

## 別隊的檔（沒改，給頂層）

- **aos-agent**（`proto8/extras/agent/bin/aos-agent` 的 `reply_mailbox`／`ctl_wait`）：被 SIGTERM、SIGHUP（關終端）、kill -9 時暫時信箱 `$TMPDIR/aos-agent-reply-*` 留著，daemon 信箱裡那封的 `reply_to` 指向不在的資料夾（daemon 照套、回信默默丟）。README 說「用完一律刪」只對 Ctrl-C 成立。可裝 TERM／HUP 處理或文件一句。
- **aos-llm-kernel**（只讀程式碼）：budget 窗用 `time(nullptr)`／`system_clock`，時鐘跳動時預算窗跟著跳。
- **aos-util**（共用庫，不在這次領地）：`InputBad stdin has no JSON` 其實是「不是 JSON」；設定檔讀不了時路徑印兩次、帶 Python 樣式的 `[Errno 2]`；`--max x` 報 `CfgBad`（應是 `ArgumentsBad`）。
  - 後續（頂層轉給本隊）：前兩條已修（stdin 不是 JSON＝`InputBad stdin is not JSON`；設定檔讀不了＝`CfgMissing cannot read X: 原因`、壞＝`CfgBad not JSON: X`，不再印兩次、不帶 `[Errno N]`），重建 13:57～14:00；`--max x` 報 CfgBad 的那句在 aos-loop（`src/engine/config.cpp:222`），不在 aos-util，沒改。

## 沒測到的

真的改系統時間、真的磁碟滿（ENOSPC 時 rename／mkdir 也會失敗）、NFS 上的 flock；判官模式 2 與 llm kernel 在壓力下；procs_ctl.json 整份宣告做風暴；子項每拍 MB 級 stderr。
