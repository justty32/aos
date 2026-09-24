← [kernel](README.md)｜[spec 總導航](../README.md)

# 4. 回音怎麼判

回音是範式 §4.1 的 aos-exec 回音。先看 `busy` 那格的 `discard`：是 → 丟掉、行程紀錄拿掉，不計數
（`once` 的 pending 在 rm 時就回過 `Removed` 了）。再分兩種：

**`once`**：把 cpu 回音的 `result` 或 `error` 原樣抄過來，外層 `id` 用原 add 的 id、檔名用原 add 的檔名，進 `replies`；
行程紀錄拿掉。`stopped:true` 也原樣交，交件者自己決定。

**反覆**：照順序第一個命中的列做，每列寫清楚兩個計數：

| 回音 | `runs` | `fails` | 之後 |
|---|---|---|---|
| `result.stopped = true` | 不動 | 不動 | 回 queue（`not_before` 不動） |
| `error`（含 `Interrupted`） | 不動 | +1 | 看退件 |
| `result.kind = aos` | +1 | +1 | 看退件 |
| `result.code = done_exit`（done_exit ≠ 0） | +1 | 歸 0 | `status=done`，不回 queue |
| `result.code` 是 0 或 101 | +1 | 歸 0 | 回 queue（101＝在等，不算錯） |
| （09-24 停車）`result.code` 是 102 | +1 | 歸 0 | **停車**：回 queue，`not_before = 現在 + park_ms / 1000`、記 `parked: true`；但這格跑的時候被叫醒過（`woken`）→ 當成 101 |
| 其他非零 | +1 | +1 | 看退件 |

看退件＝`fails` 達 `bad_after`（≠ 0）→ `status=bad`、不回 queue；沒達 → 回 queue。
判完這格（不管哪列）`woken` 清掉，跟判定同一次存帳本（提交點 B）；`park_ms` 取行程紀錄的，舊行程沒有就取 info 的。`done_exit` 先比，所以 `done_exit` 是 102 時 102＝完成、不停車。
回 queue＝`status=queued`、`not_before = 現在的 epoch 秒 + interval_ms / 1000`（`stopped:true` 那列不改 `not_before`）；已到的接那池 `ready` 尾，沒到的推進 `delayed` 堆積（§3 第 8 步）。
**每次派工對應恰好一則回音**，計數才準；沒有 quantum、沒有 runs 差值、沒有另外的 aos 計數。
