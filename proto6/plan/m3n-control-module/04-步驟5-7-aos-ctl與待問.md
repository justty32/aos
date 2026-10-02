← [第三段之二：控制模組](../m3n-control-module.md)（分檔 4/5）｜[上一份](03-步驟3-4-socket與環境變數.md)｜[下一份](05-做完了沒.md)


> 〔第二十五批 2026-10-02〕本篇的環境變數已改成新名 `AOS_DAEMON_CTL_SOCKET`（原 `AOS_DAEMON_SOCKET`，舊名不留）；`--socket` 照留（第二十一批加的）。見 [verdicts 11 第二十五批](../../notes/verdicts/11-tick-as-unit/26-1002-第二十五批.md#2026-10-02-第二十五批訊息多扇門)。
## 步驟 5：`aos-ctl` 小工具

- **要做到**：一支普通程式送四個指令，**每個都只對一項**；不另做 `aos-wake`。
- **用法**：

  ```text
  aos-ctl wake [--skip-while-running] [--keep-schedule] [<inst>]
  aos-ctl pause  [<inst>]
  aos-ctl resume [<inst>]
  aos-ctl status [<inst>]
  ```

  - 沒給 `<inst>` 一律用 `AOS_DAEMON_INST`（任務裡最常用：動自己所在的頂層項）。沒有「全部」的寫法。
  - socket **只從 `AOS_DAEMON_CTL_SOCKET` 拿**，不另設參數；人在 shell 手打就 `AOS_DAEMON_CTL_SOCKET=./aos.sock aos-ctl status a`。
  - 兩個旗標只有 wake 認，對應請求的 `skip_while_running`、`keep_schedule`；有給才送 `true`，沒給就不送那個欄位。
  - 連上、送一行、讀一行、關掉。不重試、不另設逾時（默認一切正常）。
- **輸出**：wake／pause／resume 成功時不印；status 成功時把回應那一行原樣印到 stdout（一行 JSON，要好看自己接 `jq`）。
- **結束碼**：daemon 回 `ok:true` 回 0；其餘一律 1，stderr 一行 `代碼: 說明`：
  - 沒有 `AOS_DAEMON_CTL_SOCKET`：`no_daemon:`，不連 socket。
  - 沒給 `<inst>`、也沒有 `AOS_DAEMON_INST`：`no_inst:`，不連 socket。
  - 連不上（檔不在、沒人聽、沒權限）：`connect:`。
  - daemon 回 `ok:false`：照回應的 `error` 印（`unknown_inst:`、`stopped:`、`bad_request:`）。
  - 指令名不在四個裡、多給參數、旗標給錯指令（例如 `pause --keep-schedule`）：`usage:`，不連 socket。
- **依據**：使用者「aos-ctl status應該要只能看一個項的狀態，也就是自己所在的這項」與追補「都是指向某一項inst任務」；結束碼慣例；舊 spec 的 `no_channel`（缺變數客戶端自己擋）改名 `no_daemon`。
- **要使用者裁定的點**：無。
- **驗收**：
  - daemon 開著、任務裡跑 `aos-ctl wake`：回 0，而且自己這一項跑完立刻補一次；`aos-ctl wake --skip-while-running`：回 0、不補；`aos-ctl pause`：回 0，這一項之後不再照週期跑。
  - 下層 node 的任務裡跑 `aos-ctl wake`：叫醒的是頂層那一項。
  - 任務裡跑 `aos-ctl status`：stdout 一行 JSON、`inst` 是自己那一項。
  - 給不存在的 inst：回 1、stderr `unknown_inst:`；沒 `AOS_DAEMON_CTL_SOCKET`：回 1、`no_daemon:`；沒給 inst 也沒 `AOS_DAEMON_INST`：回 1、`no_inst:`；daemon 沒開：回 1、`connect:`；`aos-ctl kill`、`aos-ctl status a b`、`aos-ctl pause --keep-schedule`：回 1、`usage:`。
- **用法上要知道**：任務每一格都無條件 `aos-ctl wake` 自己，那一項就會不停跑（每次補一次；帶 `--skip-while-running` 就不會，因為叫的時候自己正在跑）；任務 `aos-ctl pause` 自己，就要靠外面的人 `resume`。都是用法問題，不擋。

## 步驟 6：socket 檔的開與收

- **做法**（最簡單、默認一切正常下不會撞）：
  - **開**：bind 前路徑上若已有檔就先刪（上次被 `kill -9` 留下的），再 bind。默認沒有兩個 daemon 用同一個 socket，不檢查舊檔還有沒有人在聽；代價是真的開了第二個時會搶走第一個的 socket。
  - **收**：SIGINT／SIGTERM 時先 `unlink` socket 檔再 `os._exit(0)`（m3 的退出方式不變，只多這一行）。
  - 被 `kill -9` 或自己出錯退出時檔會留著；客戶端連過去得到 `connect:`、回 1；下次開 daemon 時照上一條刪掉重建。
- **要使用者裁定的點**：無。
- **驗收**：
  - SIGINT 後 socket 檔不見了；SIGTERM 一樣。
  - 先在路徑放一個普通檔（或上次 `kill -9` 留下的 socket），daemon 照樣開得起來、指令照樣通。

## 步驟 7：整段驗收

- 步驟 1～6 的驗收合成 `tests/test_ctl.py`，一條指令跑完；**不需要 root、systemd、網路**，全部用暫存資料夾、短週期、假 inst，每條幾秒內結束。
- socket 放暫存資料夾裡（unix socket 路徑上限約 108 字元，`tempfile.mkdtemp()` 放 `/tmp` 底下夠短；測試自己用短路徑，程式不檢查）。
- 測試結束自己殺掉 daemon 和留下的子程序（照 m3 步驟 7 的做法）。
- m3 的 `tests/test_daemon.py` 與原有測試（tick、exec、inst）照樣全過。

## 這段不做的

| 不做 | 這版的樣子 |
|---|---|
| 對全部項的指令（全部叫醒、看全部狀態） | 一次一項；要看多項就多叫幾次 |
| reload、shutdown | 改設定就重開；要停就送 SIGTERM（使用者：四個就夠） |
| 身分驗證、憑證（`AOS_TICK_TOKEN`）、分級權限 | 只靠 socket 檔權限，能連就能做所有事 |
| 訊息（aos-mq） | 不走這條 socket（使用者：訊息模組不算在此） |
| 控制下層 node | 指到的是頂層那一項；下層跟著上層的格跑 |
| 暫停寫進檔、重開還在 | 只在記憶體；要持久用擋板檔 |
| 等 wake 那一次跑完再回 | 收到就回 |
| 一條連線送多個請求 | 一請求一連線 |
| 每項自己設「不准別人碰」 | 都能碰；真要時照「模組鍵放進該項設定物件、沒掛時忽略」加 |

## 待問

1. **暫停中、已停時叫醒怎麼辦？resume 要不要順便跑一次？** 〔**照建議先做，使用者可改**（2026-10-01：使用者要直接開工，程式照下面建議寫；要改只動 `lib/aos_daemon_ctl.py` 的 `handle()` 與 `tests/test_ctl.py` 的 `test_wake_while_paused`、`test_stopped`）〕建議：暫停中 wake **會跑一次、跑完照樣暫停**（暫停只停「週期」，不擋人手叫）；被 `stop_on_nonzero` 停掉的項 wake **回 `stopped`、不跑**，要救用 resume；resume **一律立刻跑一次**。另一種是「暫停中 wake 也不跑」，那暫停就等於整個關掉。
