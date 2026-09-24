← [daemon](README.md)｜[spec 總導航](../README.md)

# 10. 替 kernel 開 tick

（2026-09-24 one-boot 新節。使用者拍板「開機合一、家不合一」，見 [§8](README.md)；kernel 那邊見 [kernel §3](../kernel/tick.md)、[§6 boot](../kernel/boot.md)、[§7](../kernel/no-overlap.md)。實作在 `lib/aos_daemon_ticks.py`。）

一句話：**daemon 除了當 cpu 的爸爸，也替登記過的 kernel 家「開一格 `aos-kernel tick`」**——時間到、或 kernel 家來了新單，就開一格當孩子，不等它。
同一個 kernel 家同時只開一格。daemon 只認得 kernel 家在哪、多久開一格；**不讀 kernel 家任何檔的內容**，也不用 root。

以前（第 2 版）是 kernel 自己在一顆專用 cpu（kernel cpu）上一格排下一格（tick 鏈）；那顆 cpu、那條鏈、boot 時的交接都拿掉了。

## 登記

kernel 的 boot 往 `D/requests/` 放一張 `tick` 單（形狀見 [§3 `tick`](methods.md)）：「請替 K 開 tick，每 `every_ms` 一格，一格最多跑 `timeout_ms`」。
kernel 停好那格再放一張 `off: true` 的撤登記。

登記存在 **`D/kernels/<id>.json`**，一個 kernel 家一檔；`id`＝K 絕對路徑的 SHA-256 前 16 個十六進位字元。

```json
{"home": "/abs/K", "cli": "/abs/proto5/cli/aos-kernel", "every_ms": 1000, "timeout_ms": 60000,
 "fails": 0, "last_exit": null, "last_error_at": null}
```

| 鍵 | 意思 |
|---|---|
| `home` | kernel 家的絕對路徑 |
| `cli` | 用哪支 `aos-kernel` 開（絕對路徑，boot 給的） |
| `every_ms` | 多久開一格（kernel 的 `tick_ms`） |
| `timeout_ms` | 一格最多跑多久（kernel 的 `tick_timeout_ms`；0＝不限） |
| `fails` | 連敗幾次（0＝沒事） |
| `last_exit` | 最近一次失敗那格的退出碼（逾時被 KILL＝137；開不起來＝null；失敗後恢復時寫 0） |
| `last_error_at` | 最近一次失敗的時間（epoch 秒） |

- **只在登記、失敗、從失敗恢復時重寫**，不是每格寫。平常一格一格開，這個檔不動。
- 一次原子寫（`.tmp` 再 rename）。外人（kernel 的 `ls`、health、`check`、`halt`、`cpu add`，還有 `aos down`）隨便偷看。
- **重登記**（同一個 K 再 boot）：更新 `cli`／`every_ms`／`timeout_ms`、連敗歸零、馬上開一格。
- daemon 重開：照 `D/kernels/*.json` 接著開（壞的檔、檔名跟內容對不上的，stderr 記一行、略過）。登記一直留著，直到 kernel 撤登記。

## 什麼時候開一格

daemon 每圈（`poll_ms`，預設 20 ms）看每個登記的 kernel 家。**沒有一格在跑**，而且下面任一成立，就開一格：
- **時間到**：上一格「開始」之後過了 `every_ms`。登記當下、daemon 剛開機時馬上開第一格。
- **來了新單**：`K/requests/` 出現「上一格開始時還沒有」的 `.json` 檔。
  daemon 只 stat 這個資料夾的修改時間，變了才列一次目錄、比檔名，**不讀任何檔的內容**。
  新 syscall（`add`／`rm`／`stop`…）、`wake`、cpu 丟來的回音通知（`resp-*`）都是往這裡丟檔，所以都會馬上開一格，不用等 `every_ms`。

開法：`<cli> tick --target K`，當 daemon 的孩子，放進新的 session（自己一組，逾時整組砍得到）；stdin、stdout 接 `/dev/null`，**stderr 跟 daemon 的 stderr**（用 `aos up` 開的 daemon 就是 `D/daemon.log`）。
daemon 不等它：開了就回去做別的，收屍時再看退出碼（[§4](loop.md) 第 3 步認得它是 tick）。

## 一格退出之後

| 退出碼 | 意思 | daemon 做什麼 |
|---|---|---|
| 0 | 好 | 之前有連敗就歸零、重寫登記檔 |
| 75 | `K/.tick.lock` 被佔：別的一格正在跑（人手跑的、上一任 daemon 留下的孤兒） | **不算失敗**；`every_ms` 後再試 |
| 其他（含逾時被 KILL、開不起來） | 失敗 | 連敗 N 加 1、重寫登記檔、stderr 一行（見下）、退避 |

失敗時 stderr：`aos-daemon: TickFailed: K=<K> 這格<原因>（連敗 N，W ms 後再試）`。原因是 `退出 <碼>`、`逾時（跑超過 <timeout_ms> ms）`、`停機時還沒跑完` 或 `開不起來：…`。

**退避**：W＝min(max(`every_ms`, 100) × 2^(N−1), `restart_max_ms`)。例：`every_ms` 1000、預設上限 60000：1 秒、2 秒、4 秒…最多 60 秒。
退避期間 `K/requests/` 來了新檔也**不開**。**daemon 不會自己放棄**：一直失敗就一直按上限重試，直到哪一格成功、或人重新 boot（重登記連敗歸零）。

## 逾時

一格跑超過 `timeout_ms`（0＝不限）：daemon 對它那一組送 SIGKILL，算一次失敗。
kernel 那邊也設了同樣長的鬧鐘（[kernel §3](../kernel/tick.md) 第 1 步），所以就算 daemon 不在了，卡住的那格也會自己死。

## 停機

daemon 收到 stop（[§5](shutdown.md)）：
- 不再開新的格；新的登記回 `Stopping`（撤登記照收）。
- 正在跑的那格給它 `stop_wait_ms`＋`kill_wait_ms` 自己跑完，再不退就整組 KILL（這也記一次失敗）。
- 等它收完屍 daemon 才退出。
- **登記檔留著**：下次開 daemon 照開。不想要，就先讓 kernel 停好（它自己會撤登記；`aos down` 就是這樣做）。

## daemon 被 kill -9

- 正在跑的那格變孤兒，自己跑完退出（卡住的話被自己的鬧鐘結束）。新 daemon 開機時**不殺它**（它不在 kids 檔裡）。
- 新 daemon 照登記馬上開一格；撞到孤兒還拿著 `K/.tick.lock` 就退 75、`every_ms` 後再試。
- 所以任何時候最多只有一格在改 kernel 的帳本（[kernel §7](../kernel/no-overlap.md)）。

## `ls` 看得到

`aos-daemon ls`（[§6.3](cli.md)）第一行多 `kernels N`，池表下面每個登記的 kernel 一行：

```text
kernel /abs/K  每 1000 ms 開一格 tick
kernel /abs/K2  每 1000 ms 開一格 tick  連敗 3（最後退出 1）
```

`--json` 多一格 `kernels`；`ls` method 回的 result 也多 `kernels`（[§3](methods.md)）。

## 保證外

- 兩支 daemon 替同一個 kernel 家開 tick（例如改了 info 頂層 `daemon` 之後舊的那支沒撤登記）：鎖保證不會兩格同時跑，但兩邊都會開、都會算連敗。要撤只能停掉舊 daemon 並刪它的 `D/kernels/<id>.json`。
- `D/kernels/` 被人手改壞：那一檔略過，那個 kernel 沒人開 tick，kernel 的 `ls` 報 `tick`；再 boot 或 `aos up` 就重寫。
