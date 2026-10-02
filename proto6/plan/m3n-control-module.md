# 第三段之二：控制模組

← [plan 入口](README.md)｜**接在 [m3-daemon-core](m3-daemon-core.md) 之後。**｜依據：[verdicts 11 篇末「`insts` 改成物件＋控制模組裁定」](../notes/verdicts/11-tick-as-unit/07-1001-最核心daemon.md#2026-10-01最核心-daemon待統一更新-spec)｜結束碼：[aos 結束碼慣例](../notes/verdicts/11-tick-as-unit/04-1001-結束碼慣例.md#aos-結束碼慣例待統一更新-spec)｜spec 正本：[B-641](../spec/daemon/control.md)、格式 [P-121](../spec/protocol/daemon/control.md)｜舊 spec 參考（暫緩區）：[B-612 通道](../spec/deferred/daemon/channel/01-B-610-B-612-診斷與通道.md#b-612tickdaemon-通道)、[P-117 通道變數](../spec/deferred/protocol/daemon/channel.md)、[B-607 叫醒暫停](../spec/deferred/daemon/registration/03-B-607-叫醒暫停與故障停格.md#b-607叫醒暫停故障停格與格次序號)

**做完的樣子**：m3 的 `aos-daemon` 設定檔寫了 `"modules": {"control": {"socket": "./aos.sock"}}`，daemon 開起來就多開一個 unix socket，收四個指令，**每個都只對一項**（用 inst 字面值指名）：**叫醒**（現在跑一次，可帶兩個選項）、**暫停**、**恢復**、**看狀態**。小工具 `aos-ctl` 送指令。daemon 開 `aos-exec` 時把 socket 位置與該項 inst 放進環境變數，一路傳到 tick 的任務、再傳到下層 `aos-tick 下層` 的任務，所以**任何一層的任務跑 `aos-ctl wake` 就叫醒自己所在的頂層那一項**。沒寫 `modules.control` 時 daemon 就是 m3 原樣。

> **使用者裁定（2026-10-01，原話）**：「daemon config中，其實可以是{"insts":{"jobs/report.json":{...},"haha.json":{...}}}。然後控制模組這塊，wake的功能改一下，改成可以調設定，比如正在跑的話是否就不跑了(但仍然叫幾次都只補一次)，或是這次跑完，原本後續週期性的那次就不跑了，或是弄成單獨指令也可以。aos-ctl status應該要只能看一個項的狀態，也就是自己所在的這項。1.夠了。2.可以。3.隨便放，就一個。4.算。5.訊息模組不算在此。」追補：「應該說wake/pause/resume/status都是指向某一項inst任務」。
>
> 1～5 的意思：只收 wake／pause／resume／status 四個（不收 reload、shutdown）；能連 socket 就能做所有事、不另設權限；一個 daemon 一個 socket、路徑寫在設定裡；叫醒算控制模組的一部分；訊息模組（aos-mq）不走這條 socket。更早已定：模組設定放 `modules` 底下、有寫就開（不要 `enable_control`）；核心沒有 id，項目以 inst 字面值指名；變數 `AOS_DAEMON_CTL_SOCKET`、`AOS_DAEMON_INST`；整份設定先展開指示詞再讀；「不要用檔案，必須用 socket」「不要管上下層」「daemon 只需要管理最頂層」。

> **第二十五批（2026-10-02）**：環境變數 `AOS_DAEMON_SOCKET` 改名 `AOS_DAEMON_CTL_SOCKET`（舊名不留；本篇已照新名改寫），控制 socket 檔一律 chmod 666、誰能連由所在資料夾的權限決定。見 [verdicts 11 第二十五批](../notes/verdicts/11-tick-as-unit/26-1002-第二十五批.md#2026-10-02-第二十五批訊息多扇門)。

> **POC 總原則**：默認一切正常——socket 建得起來、路徑不超長、沒有兩個 daemon 用同一個 socket、客戶端照規矩送一行。不為這些寫處理，出事自然丟錯、回 1。唯一例外見步驟 3：客戶端送壞了不能讓整個 daemon 掛掉。

> **結束碼**：0＝預料之中；非 0＝要額外處理；1＝通用錯誤，本段沒有特別指定的碼，錯一律 1。

## 分檔目錄

> 2026-10-02 整理：原檔約 26 KB 超過 8 KB 門檻，按標題逐字拆進 `m3n-control-module/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-結論介面與步驟1.md](m3n-control-module/01-結論介面與步驟1.md) | 先講結論；收哪些指令；跟 m3 的介面（對照目前的 `lib/aos_daemon.py`）；步驟 1：設定檔 |
| 2 | [02-步驟2-週期迴圈.md](m3n-control-module/02-步驟2-週期迴圈.md) | 步驟 2：叫得醒、停得住的週期迴圈 |
| 3 | [03-步驟3-4-socket與環境變數.md](m3n-control-module/03-步驟3-4-socket與環境變數.md) | 步驟 3：socket 與協議；步驟 4：往下傳環境變數 |
| 4 | [04-步驟5-7-aos-ctl與待問.md](m3n-control-module/04-步驟5-7-aos-ctl與待問.md) | 步驟 5：`aos-ctl` 小工具；步驟 6：socket 檔的開與收；步驟 7：整段驗收；這段不做的；待問 |
| 5 | [05-做完了沒.md](m3n-control-module/05-做完了沒.md) | 做完了沒 |
