# 探針 supervisor：Erlang 式 supervisor 樹 kernel

← [probes](../README.md)｜出處：[Linux 報告 §12.3](../../notes/research/2026-10-03-linux-kernel-borrow.md)（D-18）

**是什麼**：一個 keep 的 supervisor（`sup.py`）照 `sup.json` 監督同一個 node 的子工作（`child.py`），只用現有的 tasks.json／spawn／task ctl。約 3 秒，不打 LLM。

- **chain**（rest_for_one、依序起：前一個 ready 了才起下一個）：db → cache → web。cache 第一代 ready 後 3 個 tock 就 crash；照規則要收掉 web，再依序重起 cache、web，db 不動。
- **pool**（one_for_one）：w1 每一代 1 個 tock 後 crash，w2 正常。30 回合內最多重啟 3 次，退避 1、2、4 回合。第 4 次 crash＝用完 → 升級：寫 `escalation.json`、收掉 w2、整組不再起。
- **tmp**：job 是 temporary，做兩步 exit 0，不該再起。

三個 node 跑同一份政策，差在 supervisor 怎麼起子工作、什麼時候看：

| node | 起子工作 | 退避／停用 | 什麼時候看 |
|---|---|---|---|
| keep_tock | 加進 tasks.json 的 keep 項 | 把項目拿掉（`edit_json` 拿鎖），到期再加回 | 每個自己的 tock（S-17「在 tick-tock 時」） |
| keep_poll | 同上 | 同上 | 每 20 ms |
| spawn_tock | 寫 `spawn/sup-*.json` | 不寫 spawn 就好 | 每個 tock |

supervisor 記下「哪個 tid 是我 kill 的」，才分得出 crash 和被收掉。它會先處理結束、再認新出生的實例。所以如果新實例在 supervisor 做決定之前就被 keep 起了，記錄會是 `unsanctioned`：它在退避中、group 已放棄，或 temporary 已經做完。

## 結果（6 個 check 全綠，連跑 4 次）

- **spawn_tock**：照政策走，違規 0。
  - w1 起 4 次後升級，之後 pool 沒有再起。
  - rest_for_one：db 起 1 次，cache、web 各起 2 次；每一代 cache、web 起來時，依賴都已經 ready。
  - job 只起 1 次。
  - 所有重起都不早於 not_before。
- **keep_tock**：每次都有違規，4 次分別是 4、2、3、4 次。
  - 有 crash 的 w1、cache 在退避中被起回來。
  - 有一次 temporary 的 job 做完了又被起。
  - 從上一代 exit 到 keep 起出新一代，只隔 27～67 ms。原因是子工作多半收到 tock 才動作，而 tock 之後緊接著就是下一個 tick。supervisor 下一次看要等下一個 tock，那時 keep 早就起好了。
- **keep_poll**（20 ms 輪詢）：違規少一些，4 次是 1～3 次，但從沒做到 0。
  - crash 後 30 ms 內 tick 就到，supervisor 拿掉項目常常趕不上。
  - **已經拿掉了也可能被起**：supervisor 做完決定、`edit_json` 寫完之後，正在跑的 tick 可能已經讀過舊的 tasks.json（tick 讀的時候不拿鎖），照樣起了。在 `early_vs_backoff` 看得到，例如 birth round 4 早於 not_before 6。
  - 升級之後還起過一次 w1，supervisor 只好再 kill 一次。
- **keep 起的實例誰起的、算不算重啟，看不出來**：birth.json 沒有 `restart_of`、沒有 `spawn`。supervisor 只能用「我剛剛有沒有要它起」來猜。
- **反過來看 spawn 模式的代價**：supervisor 是唯一的起任務者。supervisor 自己死掉、還沒被 keep 起回來的那段時間，子工作 crash 了就沒人起。keep「沒人管也會一直在」的保證沒了。這個探針沒有量 supervisor 自己重起，只把狀態放在記憶體。

## 逼出的 daemon／tick 需求

- **N-79（對應 D-18，應該）起任務的准入要有單一來源**。keep 項目要能帶 `not_before`（第幾回合前不起）、`enabled`，以及 `restart: always｜on-failure｜never`，supervisor 才不用搶著增刪 tasks.json。現在只有兩條路，各有代價：
  - 讓 keep 起：keep 一定贏，退避和 temporary 都守不住。
  - 全部改 spawn：失去 keep 的保底。

  這條把 N-28（別再起我）、N-29（crash loop 退避）合起來看：supervisor 要的不只是「停」或「退避」，是同一份准入狀態。
- **N-80（對應 D-18 的「套用回條」，可以）tasks.json 改了，要看得出 tick 用的是哪一版**。tick 讀 tasks.json 不拿鎖。supervisor 拿掉項目後，還在途的 tick 可能照舊版起。rounds.jsonl 只記起了什麼，沒有記讀的是哪一版（revision／mtime），supervisor 無從判斷「我的修改生效了沒」。
- **沒逼出新需求、現有夠用的**：
  - 退出碼（`exit.json` 的 code）、`ended` 的 `by_ctl`（N-30）足以分辨 crash 與被收掉。
  - rest_for_one 的「先收後起」用 task ctl kill 加上依序 spawn 做得到。
  - 「依序起、前一個 ready 才起下一個」靠 ready 檔加一次一個 spawn 做得到，代價是每個子工作慢一回合。
