# daemon 控制模組：叫醒、暫停、恢復、查詢

← [daemon 目錄](README.md)｜[核心 B-640](core.md)｜[慣例](../conventions.md)｜格式：[P-121](../protocol/daemon/control.md)

本篇只有 B-641，寫控制模組與 `aos-ctl` **做什麼**。socket 上一行 JSON 的確切欄位、錯誤代碼、`aos-ctl` 的 argv 與結束碼，寫在格式篇 [P-121](../protocol/daemon/control.md)。

依據：[第二十批篇末「`insts` 改成物件＋控制模組裁定」與「m3n 待問 1 先照建議做」](../../../notes/verdicts/11-tick-as-unit/07-1001-最核心daemon.md#2026-10-01最核心-daemon待統一更新-spec)、[plan m3n](../../../plan/m3n-control-module.md)；現行程式 [控制模組與 aos-ctl](../../../src/py/README.md#控制模組與-aos-ctlm3n)（`lib/aos_daemon_ctl.py`、`lib/aos_ctl.py`，有出入以程式為準）。

## B-641：控制模組與 aos-ctl〔使用者方向 2026-10-01〕

**控制模組讓人或任務對 daemon 清單上的某一項下指令：現在跑一次、暫停、恢復、看狀態。** 它是 daemon 的一個模組（[B-640](core.md)「模組」），設定檔寫了才有。送指令的小工具叫 `aos-ctl`。

### 怎麼開

- 設定檔寫了 `modules.control.socket`，就開；沒寫，daemon 跟只有核心時一模一樣（不開 socket、不多傳環境變數）。
- **一個 daemon 一個 socket**（Unix socket，就是本機上一個可以連進去講話的檔），路徑照設定，相對的以起點為準（[B-640](core.md)「起點」）。
- daemon 開的時候，路徑上有舊的檔先刪掉再開；收到 SIGINT／SIGTERM 退出前把它刪掉。
- **能連上 socket 就能做所有事，不另外驗身分。** 誰能連，由 socket 檔的檔案權限決定。通道憑證 `AOS_TICK_TOKEN`：現行控制不使用；舊通道憑證暫緩，未來另定（[暫緩區 P-117](../deferred/protocol/daemon/channel.md)）〔astra 報告必修 7〕。
- 訊息模組（`aos-mq`）之後另做，不走這條 socket。

### 六個指令，每個只對一項

指令有 `wake`、`pause`、`resume`、`status`，〔2026-10-01 第十九批〕加 `kill`、`restart`，**每個都指名一項**（用 inst 字面值，逐字比對）。沒有「對全部」的寫法，也不收 reload、shutdown（重讀設定走 SIGHUP，[B-642](reload.md)）。指令只改那一項的狀態、叫醒它，收到就回，不等那一項跑完。

| 指令 | 做什麼 |
|---|---|
| `wake` | 現在跑一次（下面細說） |
| `pause` | 不再照週期跑。正在跑的不殺，已經記下要補跑的那次取消。stdout 印一行 `paused` |
| `resume` | 清掉暫停與「已停」（被 `stop_on_nonzero` 停掉的），**馬上跑一次**。stdout 印一行 `resumed` |
| `status` | 回這一項現在的狀態：在不在跑、有沒有待補、暫停沒、停掉沒、上次的碼與結束時間、下次照週期什麼時候跑 |
| `kill` | 〔第十九批〕殺掉正在跑的那一次（下面細說）；沒在跑什麼都不做 |
| `restart` | 〔第十九批〕殺掉正在跑的那一次，結束後馬上再跑一次；沒在跑就等於 `wake` |

### wake 的細節

- **正在跑時**：預設等這次跑完再補一次。**叫幾次都只補一次。**
- 帶 `skip_while_running`：正在跑就算了，不補（還是回成功）。沒在跑時照樣馬上跑。
- **跑完之後的週期**：預設從這次結束重新算，原本排好的那次不另外跑。帶 `keep_schedule`：不動原本的排程，原本那次照常跑；只有原本那次的時間已經過了，才從這次結束重新算（不補跑漏掉的）。
- 補跑那次帶不帶 `keep_schedule`，照最後一次**沒有被 skip 丟掉**的 wake（`resume` 算一次不帶選項的 wake）。正在跑時帶 `skip_while_running` 的 wake 什麼都不改：不取消已記下的補跑，也不改它的選項〔astra 報告必修 4；使用者 2026-10-01：照程式〕。

### 暫停、停掉時叫醒〔照建議先做，使用者可改〕

下面三條是 plan m3n 待問 1 照建議先寫進程式的，使用者之後可以改：

- **暫停中 wake**：跑一次，跑完照樣暫停。暫停只停「照週期跑」，不擋人手叫。
- **被 `stop_on_nonzero` 停掉的項 wake**：回錯誤 `stopped`、不跑。要救回來用 `resume`。
- **resume 一律馬上跑一次**，等於一次不帶選項的 wake。

### kill 與 restart〔使用者 2026-10-01 第十九批〕

為了「daemon 跑 daemon」時上層停得掉、重開得了下層 daemon（下層永遠不結束，`pause` 只是不排下一次）。使用者：「那就要有這個指令」「按照你的建議」。

- **先客氣、再強制**：先送 SIGTERM；等 `modules.control.kill_grace_ms`（預設 5000 毫秒）那一次還沒結束，就送 SIGKILL，掛了收屍模組（[B-644](cgroup.md)）再把那一項的整個框 `cgroup.kill`。指令送出 SIGTERM 就回，不等它結束。
- **送給誰**：`aos-exec` 把任務開在另一個 session，所以不能只送 `aos-exec` 自己。SIGTERM 送給 `aos-exec` 底下所有後代的程序群組（不含 `aos-exec` 自己）：任務收到後自己收尾、結束，`aos-exec` 照常回任務的碼；底下還沒有任何程序時才送給 `aos-exec`。SIGKILL 送給後代的群組加 `aos-exec` 自己。已經跳出親子樹的（`setsid` 加 double fork 被收養的）找不到，只有掛了收屍模組才清得到。
- **之後**：被殺的那次照常印 `exit=`（碼是 `aos-exec` 回的；被 SIGKILL 就是 137），照週期排下一次。`kill` 殺掉的那次非 0，`stop_on_nonzero` 照算（會停掉）；`restart` 殺掉的那次不算。
- **沒在跑**：`kill` 回成功、什麼都不做；`restart` 等於不帶選項的 `wake`。被 `stop_on_nonzero` 停掉的項 `restart` 回 `stopped`（同 `wake`），要救用 `resume`。
- **帳號模組**（[B-646](account.md)）掛著、那一項是別的帳號時：降權後的主程式送不到別的帳號，請 root 端照同樣的規則送。

### 暫停只在記憶體（掛了記住狀態模組時例外）

暫停、已停、待補這些狀態都只放在 daemon 的記憶體裡，**重開 daemon 就沒了**：每項回到「開起來先跑一次」。〔2026-10-01 第十一批〕掛了記住狀態模組（[B-643](state.md)）時，暫停與已停會寫進狀態檔、重開時讀回（待補照樣不記）。舊設計的 pause 批次存檔不做（[暫緩區 B-603](../deferred/daemon/lifecycle.md)，存檔讀回的部分已被 B-643 取代）。

### 環境變數往下傳

掛了控制模組時，daemon 每次開 `aos-exec` 都在環境裡多放兩個變數（總表見 [C-10](../conventions.md)）：

- `AOS_DAEMON_SOCKET`：控制 socket 的絕對路徑。
- `AOS_DAEMON_INST`：這一項的 inst 字面值（〔第十二批〕掛了訊息模組也放，[B-645](mq.md)）。

inst 的任務、`aos-tick` 跑的任務、再下層 `aos-tick` 跑的任務都繼承得到。所以**不管在哪一層跑 `aos-ctl wake`，叫醒的都是 daemon 清單上那一項**（最頂層那一項），不是自己這一層。

### `aos-ctl`：送一個指令的小工具

- `aos-ctl <指令> [<inst>]`：連上 socket、送一行、讀一行回應、關掉。
- **socket 從 `AOS_DAEMON_SOCKET` 拿**。人在 shell 手打時自己設這個變數。〔[第二十一批](../../../notes/verdicts/11-tick-as-unit/23-1001-第二十一批.md#2026-10-01-第二十一批跨-daemon-用-socket-路徑當前綴)〕給了 `--socket <控制 socket 路徑>` 就改連那個 socket，用來對**別的 daemon** 的項下指令（跨 daemon＝前綴是對方 daemon 的 socket 路徑）；這時**一定要明寫 `<inst>`**——`AOS_DAEMON_INST` 是自己 daemon 裡的名字，不能拿去別的 daemon 用（AI 隊定）。daemon 不轉送，`aos-ctl` 自己直接連過去。
- 沒給 `<inst>` 就用 `AOS_DAEMON_INST`，也就是「自己所在的那一項」。任務裡最常見的用法就是不帶 `<inst>`。
- `wake` 可以帶 `--skip-while-running`、`--keep-schedule`。`kill`、`restart` 不帶旗標。
- 成功回 0；`status` 把 daemon 回的那一行原樣印到 stdout，其他指令成功時什麼都不印。
- 失敗一律回 1（[C-08](../conventions.md)），stderr 印一行代碼與說明：用法錯、不在 daemon 底下（沒有 `AOS_DAEMON_SOCKET`）、沒指名哪一項、連不上，或 daemon 回的錯。
- 不重試、不另設逾時（默認一切正常）。確切格式見 [P-121](../protocol/daemon/control.md)。

### 一條連線出錯只影響那一條

〔使用者方向 2026-10-01〕POC 默認一切正常；唯一的例外是一條連線自己的錯（不是 JSON、對面先關、超過 1 秒沒送完一行），只影響那一條，daemon 繼續收下一條。連線一條一條處理。

依據：使用者方向 2026-10-01（`insts` 改成物件＋控制模組裁定：有寫就開、一個 socket、能連就能做、四指令各對一項、wake 兩個選項、status 只看一項、`AOS_DAEMON_SOCKET`／`AOS_DAEMON_INST`、訊息模組不走這條）；m3n 待問 1 照建議先做；[第十九批](../../../notes/verdicts/11-tick-as-unit/21-1001-第十九批.md#2026-10-01-第十九批daemon-上下層用到的三件事)（`kill`、`restart`）；[第二十一批](../../../notes/verdicts/11-tick-as-unit/23-1001-第二十一批.md#2026-10-01-第二十一批跨-daemon-用-socket-路徑當前綴)（`--socket`）。

**驗收：**沒寫 `modules.control` 時不建 socket、不傳變數；`wake` 讓一項立刻跑一次，正在跑時連叫三次只補一次，帶 `skip_while_running` 不補；帶 `keep_schedule` 時原本的週期照舊；`pause` 後不再照週期跑、正在跑的沒被殺；暫停中 `wake` 跑一次後仍暫停；停掉的項 `wake` 回 `stopped`，`resume` 後馬上跑；任務裡不帶參數的 `aos-ctl status` 看到的是自己那一項；daemon 退出後 socket 檔被刪。〔第十九批〕收到 TERM 會收尾的任務 `kill` 後很快結束、碼是任務自己的；不理 TERM 的任務過了寬限被 SIGKILL（137）；任務底下 setsid 的孫子也收到 TERM；掛了收屍模組時整個框清空；沒在跑時 `kill` 回成功；`restart` 殺掉後馬上再跑、不因 `stop_on_nonzero` 停掉；帳號模組底下別的帳號的項也殺得到。〔第二十一批〕`aos-ctl --socket <另一個 daemon 的控制 socket> status|wake <inst>` 對那個 daemon 的項有效；給了 `--socket` 沒寫 `<inst>` 回 1、`usage:`。測試見 `proto6/src/py/tests/test_ctl.py`、`test_daemon_kill.py`。
