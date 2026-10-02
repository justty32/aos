← [整理區名詞：tick 核心、四類程式與 daemon 核心](../terms.md)（分檔 3/3）｜[上一份](02-T-10-四類程式.md)

## T-11．daemon 核心與模組

〔使用者方向 2026-10-01〕現行的 daemon 只是「一個定期叫 `aos-exec` 的 cron」，其餘功能做成可掛的模組。

| 詞 | 意思 | 正本 |
|---|---|---|
| daemon 核心 | `aos-daemon` 本身：定期叫 `aos-exec` 跑設定檔 `insts` 裡的每一項，等它結束、印一行結果。不認得工作資料夾與 node、不讀任務表、不碰鎖與擋板 | [B-640](../daemon/core.md) |
| 項（inst 字面值） | `insts` 的一個鍵就是一項，鍵就是交給 `aos-exec` 的 inst 字面值（資料夾或檔）。核心沒有 id，一項就是它的字面值 | [B-640](../daemon/core.md) |
| 跑 tick 的項 | 就是一份 `argv` 開頭是 `aos-tick` 的 inst；把它加進 `insts`，daemon 就會定期跑那個工作資料夾的 tick。daemon 不認得工作資料夾；node 這個詞留給之後的 node 模組〔使用者 2026-10-01 改名〕 | [B-640](../daemon/core.md)、[B-620](../tick.md) |
| 模組 | 設定檔頂層 `modules` 底下，一個鍵一個模組；寫了才掛上。核心只認得 `modules` 這個鍵，不解讀別的模組的內容 | [B-640](../daemon/core.md) |
| 控制模組 | 模組 `control`：開一個 Unix socket（任務拿到 `AOS_DAEMON_CTL_SOCKET`，第二十五批改名），收 `wake`、`pause`、`resume`、`status`、`kill`、`restart`（後兩個第十九批）六種指令，每個指令只對一項；送指令的小工具是 `aos-ctl` | [B-641](../daemon/control.md) |
| 鎖檔（daemon） | 〔第十九批〕daemon 開起來對 `<設定檔>.lock`（或 `lock_path`）取的獨占鎖；拿不到＝同一份設定已經有 daemon 在跑，回 1。跟 tick 的 `.aos/tick.lock` 不同 | [B-640](../daemon/core.md) |
| 重讀設定模組 | 模組 `reload`：收到 SIGHUP 重讀同一份設定檔，加減項、改週期免重開；`cwd`、`modules`、`exec_out_path`、`exec_err_path` 改了只印警告 | [B-642](../daemon/reload.md) |
| 記住狀態模組 | 模組 `state`：設定寫成 `{"$ref": "<狀態檔>"}`，把每項的暫停、已停記進那個檔，重開時讀回 | [B-643](../daemon/state.md) |
| 訊息模組 | 模組 `mq`：〔2026-10-02 第二十五批〕開幾扇**門**（`modules.mq` 的「門名 → 路徑」，各一個 Unix socket），daemon 的每一項一個信箱（記憶體、先進先出），每項用 `mq` 陣列訂幾扇門；從某扇門寄進來的信（JSON 原樣）放進訂了那扇門的每一項的信箱並叫醒它們（合併叫醒）。任務用 `aos-mq send <門> <JSON>` 寄、`aos-mq take`／`peek <門>` 取／看自己的信；跨 daemon 就寄到對方的門。取代第二十一、二十二批的 `--socket`／`from_socket`／`--all`／`--channel`／信的 `to` | [B-645](../daemon/mq.md) |
| 帳號模組 | 模組 `account`：要用 root 開；開出 root 端 `aos-daemon-root` 後主程式永久降成預設帳號，名單（`allow`／`deny`，結尾 `*` 當前綴）准的別的帳號的項由 root 端用那個帳號開 | [B-646](../daemon/account.md) |
| 收屍／cgroup 模組 | 模組 `cgroup`：以 daemon 自己所在的 cgroup 當子樹根，每項一個框 `i-<h>`；每次 `aos-exec` 結束後把框裡留下的程序殺光、清空才算結束（收屍）；每項的 `cgroup` 鍵寫上限 | [B-644](../daemon/cgroup.md) |

- 「daemon 管 node」（自動找 node、上下層、叫醒往上傳）之後另做成 node 模組，還沒排程（[node 模組方向](../../../notes/verdicts/11-tick-as-unit/08-1001-node模組與統一更新.md#node-模組方向2026-10-01記錄用未排程)）。
- 舊 daemon 的登記、通道、收尾等用語在暫緩區（[T-09](../deferred/terms.md)、[舊 daemon](../deferred/daemon/README.md)）。

依據：第二十批篇末「2026-10-01：最核心 daemon」（daemon 只叫 `aos-exec`、核心沒有 id、`modules`、`insts` 物件、控制模組）。
