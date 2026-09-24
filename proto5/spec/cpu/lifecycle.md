← [cpu](README.md)｜[spec 總導航](../README.md)

# 6. 主人的一生

```text
aos-cpu [DIR]      # （09-24 fix-r4 改）DIR 可省略，省略＝.（目前資料夾）
```

DIR（或省略時的目前資料夾）必須是存在的資料夾，不是＝用法錯 2。

## 6.1 啟動

1. 若 fd 0 是 pipe：**先等 `go`**。用非阻塞讀一行一行組，讀到 `{"jsonrpc":"2.0","method":"go"}` 才往下；
   先讀到 EOF＝拉它的人在登記前就死了，**什麼都不碰**（不讀 info、不寫 state）、退出碼 0。
   `SIGPIPE` 一律忽略（往關掉的 pipe 寫只會得到 EPIPE，不會被訊號打死）。
2. 讀驗 `info.json`；`requests/`、`responses/` 沒有就建。
3. 若 fd 0 是 pipe：把 fd 0／fd 1 **搬到高位 fd、標 close-on-exec** 當控制 pipe，然後 fd 0 接 `/dev/null`、
   fd 1 接 fd 2。這樣工作繼承串流時拿到的是 `/dev/null` 與 `cpu.log`，高位那兩個又因 close-on-exec 跟不
   進工作——工作既拿不到控制訊息、也握不住回程寫端（fork 到 exec 之間的那一瞬間有副本，exec 就沒了）。
   （2026-09-24 池式納入補）父行程（daemon）給的 fd 1 現在本來就是 `/dev/null`、不一定是 pipe；cpu 照樣把它搬到高位（不會往那裡寫），程式不用改。
   fd 0 不是 pipe（人在終端跑、或 stdin 接 `/dev/null`）就沒有控制 pipe，只認檔案與訊號，也不等 `go`。
   用程式包 `aos-cpu` 的人注意：`stdin=PIPE` 就等於「我要用控制協議」，得送 `go`、還得一直握著那條 pipe。
4. **先讀舊 `state.json` 做開機對帳（§6.2），對帳完才寫**新的 `state.json`（pid、current=null、runs 照舊）。
   沒有舊 `state.json`（第一次跑）＝當作 `current: null`、`runs: 0`。
5. （2026-09-24 池式納入加）有 `notify`：對 `responses/` 裡每一份回音（檔名 `.json` 結尾的）補丟一次通知（[§6.4](notify.md)），然後進迴圈。

## 6.2 開機對帳

上一任可能停在哪，看 `current`（含 name、id、notify）＋兩個檔在不在。前提：名字不重用（§1）、
只有主人會刪這兩個檔（ack 也是主人處理的）。

| `current` | `requests/X` | `responses/X` | 可能停在哪 | 做什麼 |
|---|---|---|---|---|
| null | — | — | 閒著 | 沒事 |
| X | 在 | 不在 | 還沒開始、執行中、或跑完還沒發回音 | 有 id：用 `current.id` 寫 `-32000`／`Interrupted`，再刪原單。notification：只刪原單 |
| X | 在 | 在 | 發了回音、還沒刪原單 | 刪原單 |
| X | 不在 | 在 | 刪了原單、還沒清 current | 沒事 |
| X | 不在 | 不在 | notification 的正常路徑（沒回音、原單刪了、current 還沒清）；有 id 的不該出現 | 沒事 |

然後 current 清 null。對帳自己崩了再來一次也是同一張表（每列的動作都可重做）。
`requests/` 裡其他還沒開始的單不在對帳範圍，照常一件一件做。

## 6.3 迴圈

```text
掃 requests/ 的 ack-（§3.3 兩步）與 stop-（設旗標）
看旗標（§5.1 四來源）→ 有就收尾退出
取 requests/ 第一份非 ack-／stop- 的 X
  (1) 寫 state.current={name,id,notify}
  (2) 跑（run_target）；跑的期間每 poll_ms 看一次控制 pipe 與訊號旗標，只記、不動手（強制停除外）
  (3) 原子寫 responses/X（notification 跳過）
  (4) 刪 requests/X
  (4.5) 有 notify：放通知（§6.4；失敗只記 stderr 一行 NotifyFailed，不退出、不重試）
  (5) 寫 state.current=null、runs+1
沒單就睡 poll_ms
```

**(3) 在 (4) 前**是開機對帳那張表的根據：回音一定先於原單消失。收件者查「做完了沒」也要照這個
順序看——先看原單在不在、再看回音——才不會看錯（[kernel §3 第 6 步](../kernel/tick.md)）。
(3) 寫不出去（ENOSPC、EACCES…）是**主人層級**的錯：stderr 一行、`state.current` 留著、退出碼 1；
下一任開機看到「原單在、回音不在」就補 `Interrupted`——結果丟了但不會重跑、不會失單。
磁碟一直壞就會一直退 1、一直被 daemon 重拉（[daemon §4](../daemon/loop.md)），這是接受的。

沒有父行程也能跑（終端直接 `aos-cpu [DIR]`）。沒有「自己反覆跑同一份 inst」的模式——要反覆是 kernel 的事。

# 7. 退出碼與 stderr

| 碼 | 什麼時候 |
|---|---|
| 0 | 正常停（§5.1／5.2）、或等 `go` 等到 EOF |
| 1 | `info.json` 讀驗不過、`state.json`／回音寫不進去、佇列目錄建不起來；stderr 一行 `aos-cpu: <代號>: <白話>` |
| 2 | 用法錯：DIR 不是資料夾、多餘旗標 |

一則 request 本身的錯誤都回在 response 裡，不影響退出碼；子程式的 stderr 照 inst 走。
