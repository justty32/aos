← [daemon 控制模組：叫醒、暫停、恢復、查詢](../control.md)（分檔 2/2）｜所在段落：B-641：控制模組與 aos-ctl〔使用者方向 2026-10-01〕｜[上一份](01-B-641-指令與細節.md)

### `aos-ctl`：送一個指令的小工具

- `aos-ctl <指令> [<inst>]`：連上 socket、送一行、讀一行回應、關掉。
- **socket 從 `AOS_DAEMON_CTL_SOCKET` 拿**（〔第二十五批〕改名，舊名 `AOS_DAEMON_SOCKET` 不讀）。人在 shell 手打時自己設這個變數。〔[第二十一批](../../../../notes/verdicts/11-tick-as-unit/23-1001-第二十一批.md#2026-10-01-第二十一批跨-daemon-用-socket-路徑當前綴)〕給了 `--socket <控制 socket 路徑>` 就改連那個 socket，用來對**別的 daemon** 的項下指令（跨 daemon＝前綴是對方 daemon 的 socket 路徑）；這時**一定要明寫 `<inst>`**——`AOS_DAEMON_INST` 是自己 daemon 裡的名字，不能拿去別的 daemon 用（AI 隊定）。daemon 不轉送，`aos-ctl` 自己直接連過去。
- 沒給 `<inst>` 就用 `AOS_DAEMON_INST`，也就是「自己所在的那一項」。任務裡最常見的用法就是不帶 `<inst>`。
- `wake` 可以帶 `--skip-while-running`、`--keep-schedule`。`kill`、`restart` 不帶旗標。
- 成功回 0；`status` 把 daemon 回的那一行原樣印到 stdout，其他指令成功時什麼都不印。
- 失敗一律回 1（[C-08](../../conventions.md)），stderr 印一行代碼與說明：用法錯、不在 daemon 底下（沒有 `AOS_DAEMON_CTL_SOCKET`）、沒指名哪一項、連不上，或 daemon 回的錯。
- 不重試、不另設逾時（默認一切正常）。確切格式見 [P-121](../../protocol/daemon/control.md)。

### 一條連線出錯只影響那一條

〔使用者方向 2026-10-01〕POC 默認一切正常；唯一的例外是一條連線自己的錯（不是 JSON、對面先關、超過 1 秒沒送完一行），只影響那一條，daemon 繼續收下一條。連線一條一條處理。

依據：使用者方向 2026-10-01（`insts` 改成物件＋控制模組裁定：有寫就開、一個 socket、能連就能做、四指令各對一項、wake 兩個選項、status 只看一項、`AOS_DAEMON_SOCKET`／`AOS_DAEMON_INST`、訊息模組不走這條）；[第二十五批](../../../../notes/verdicts/11-tick-as-unit/26-1002-第二十五批.md#2026-10-02-第二十五批訊息多扇門)（環境變數改名 `AOS_DAEMON_CTL_SOCKET`、socket 一律 666 權限靠資料夾）；m3n 待問 1 照建議先做；[第十九批](../../../../notes/verdicts/11-tick-as-unit/21-1001-第十九批.md#2026-10-01-第十九批daemon-上下層用到的三件事)（`kill`、`restart`）；[第二十一批](../../../../notes/verdicts/11-tick-as-unit/23-1001-第二十一批.md#2026-10-01-第二十一批跨-daemon-用-socket-路徑當前綴)（`--socket`）。

**驗收：**沒寫 `modules.control` 時不建 socket、不傳變數；〔第二十五批〕寫了時任務拿到 `AOS_DAEMON_CTL_SOCKET`（沒有 `AOS_DAEMON_SOCKET`）、socket 檔是 666（沒掛帳號模組也是）、只設舊名 `AOS_DAEMON_SOCKET` 時 `aos-ctl` 回 1、`no_daemon:`；`wake` 讓一項立刻跑一次，正在跑時連叫三次只補一次，帶 `skip_while_running` 不補；帶 `keep_schedule` 時原本的週期照舊；`pause` 後不再照週期跑、正在跑的沒被殺；暫停中 `wake` 跑一次後仍暫停；停掉的項 `wake` 回 `stopped`，`resume` 後馬上跑；任務裡不帶參數的 `aos-ctl status` 看到的是自己那一項；daemon 退出後 socket 檔被刪。〔第十九批〕收到 TERM 會收尾的任務 `kill` 後很快結束、碼是任務自己的；不理 TERM 的任務過了寬限被 SIGKILL（137）；任務底下 setsid 的孫子也收到 TERM；掛了收屍模組時整個框清空；沒在跑時 `kill` 回成功；`restart` 殺掉後馬上再跑、不因 `stop_on_nonzero` 停掉；帳號模組底下別的帳號的項也殺得到。〔第二十一批〕`aos-ctl --socket <另一個 daemon 的控制 socket> status|wake <inst>` 對那個 daemon 的項有效；給了 `--socket` 沒寫 `<inst>` 回 1、`usage:`。測試見 `proto6/src/py/tests/test_ctl.py`、`test_daemon_kill.py`。
