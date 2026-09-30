# daemon 訊息：暫存與急件

← [daemon 目錄](README.md)｜[整理區](../README.md)

## B-614：暫存訊息與急件

**同一個 daemon 底下的 tick 可以經 daemon 互傳訊息（系統訊息佇列）；不保證送達。** tick 那一側由系統級任務 `aos-mq` 送與取（[B-623](../tick.md)、[B-624](../tick.md)）。

- **格式**：訊息是一份請求物件或回應物件（[P-301](../../protocol/messages.md)）；daemon 只驗外形，不解析正文。〔使用者方向 2026-09-30，修正輪暫定的裁定〕請求與回應放同一個佇列，`node.take` 一起取出。
  - 〔暫定，交接疑點「通道訊息放寬」照 a〕照 [C-07](../../contracts.md)：通道請求的外層（`node.send` 的 params）照 daemon IPC 嚴格；夾帶的 `message` 照檔案 RPC 放寬，不認得的欄位忽略。
- **送**：`node.send` 帶收件 tick 的 id、訊息與是否急件。收件 tick 要在這個 daemon 登記，否則回 `not_registered`；掛載行程沒有收件匣（`kind_mismatch`）。
- **誰能送**：看寄件 tick 的執行帳號對收件 tick 的 `.aos/mq/get/` 有沒有寫權——能不能在那裡建檔（`.aos/mq/get/` 的寫與穿越權，以及上層各段的穿越權）；沒有就回 `forbidden`。〔使用者方向 2026-09-30，修正輪暫定的裁定：改看 `.aos/mq/` 底下的資料夾，不再看 `requests/`；選 `.aos/mq/get/`：使用者 2026-09-30 同意照暫定〕這個資料夾只拿來當判準，`aos-mq get` 要不要用它放取出的訊息由它自己定（[P-200](../protocol/node.md)）。首版不用 ACL，所以 daemon 以那個帳號的 UID 與群組，對權限位計算即可。「投件權就是執行權」同樣適用（[T-08](../../terms.md)）。
- **存**：放 daemon 記憶體，按收件 tick 分開、先進先出。daemon 當掉、重啟、立即停機，或收件 tick 被解除，暫存的都丟掉。〔建議預設〕每個收件 tick 最多 256 件、合計 16 MiB，滿了回 `mailbox_full`；單件訊息序列化後最多 196608 bytes（192 KiB），超過回 `message_too_large`，這樣一件一定裝得進一個 `node.take` 回應。
- **取**：收件 tick 裡只有系統級任務 `aos-mq get` 在它的那一格上通道用 `node.take` 取，其他任務不直接取（[B-623](../tick.md)）。取走的 daemon 同時刪掉，之後怎麼分派、落地、去重 aos 不管。一次回應裝不下就分幾次取，回應會說還有沒有。daemon 分不出是哪一項在取，「只有它取」是 node 裡的約定。
- **急件**：送到時 daemon 照 `node.wake` 叫醒收件 tick（合併、paused 只記 pending、停機中不叫，B-607）；一般件等它自己的下一格。〔暫定，改寫計畫疑-9 使用者未答〕急件直接叫醒，不問上層，不受上層 kernel 的節流：它會越過上層排程任務的同時叫醒上限（`max_active_members`，[S-202](../../scheduling/admission.md)），這是「反應速度就是一格」唯一的例外（第二十批追答 7）。
- 排空停機時通道照常收送（B-604）。

依據：第十九批第 9 條與疑點裁定 6、7；astra 審整理區裁定裁-1 與同日定案（系統訊息佇列 `aos-mq`，只有 `aos-mq get` 取）；修正輪暫定的裁定（回應也走佇列；授權判準改看 `.aos/mq/` 底下的資料夾）。

**驗收：**寄件帳號對收件 `.aos/mq/get/` 沒寫權被拒，對 `requests/` 有沒有寫權不影響；回應物件照樣送得進、取得到；一般件不叫醒、下一格取得到；急件送到後收件 tick 被叫醒；取過的再取不到；daemon 重啟後暫存的都不見；超過上限回 `mailbox_full`、`message_too_large`。

