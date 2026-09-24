← [kernel](README.md)｜[spec 總導航](../README.md)

# 2. syscall（`K/requests/`）

| method | params | 回音 |
|---|---|---|
| `add` | `target` 必填（絕對路徑）；`dir_target`／`args` 可省（同範式 §4.1；`args` 沒給就不要放這個鍵）；`name` 可省（省＝數字名最大值加 1）；`once`（預設 false）；`pool`（預設 `default`，必須是 info.cpus 裡有的、且不是 `kernel`）；`interval_ms`／`timeout_ms`（預設照 info） | **反覆**行程：`{"name": NAME}`。**`once`**：回音等到那一次跑完才寫，內容就是那次的 exec 回音（`result` 或 `error` 原樣）；交件者等 `K/responses/<自己的檔名>.json` 一個檔、讀完放 ack |
| `rm` | `name` | `{"name": NAME}`；不在＝`-32000`／`NotFound`。細節見下 |
| `stop` | notification | `phase` 改 `stopping`（§3 第 9 步）。daemon 不動，由人停 |
| `ack` | 範式 §3.3 | kernel 是一個家，別人收了 `K/responses/` 的回音要放 ack，處理方式照範式（刪回音、刪 ack 檔） |

沒有 `ls` syscall：看狀態就偷看 `K/state.json`（§6 的 `ls` 就是這樣做，鏈斷了也看得到）。
同名 `add`（不管 `status` 是什麼、含被 rm 但還在 cpu 上跑的）回 `-32000`／`AlreadyExists`；
params 形狀或 pool 不合回 `-32602`。kernel 不解指示詞、不驗 inst、不看檔在不在——那些都是跑起來的回音。
（09-24 補）省略 `name` 時只計 ASCII 十進位名稱：有數字名取最大值加一，沒有就從 `0` 開始。CLI 的 `--once` 沒給 `--name` 時仍用自己的 request 檔名（§6）。

**每則 syscall 都是「一次帳本寫入」＋出貨**：收到 `add`／`rm` → 判定 → 把結果（行程紀錄、queue、pending）跟
出貨待辦**一次**寫進帳本 → 出貨。待辦是：原單名進 `deletes`（一定有）；要馬上回的回音進 `replies`
（反覆的 add、rm）；`once` 的 add 只記 `pending`，跑完或取消時才進 `replies`。`ack`／`stop` 照各自的規則，不產生回音。
**`once` 的回音只報執行狀態**（code／kind／timed_out…），不含模型的答案或工具的輸出——要輸出就在工作 inst 裡
指定 `stdout` 檔，收到成功的回音後再去讀那個檔。
重掃看到某份原單，先看 `deletes`：**在裡面＝已收過**，只補刪、不重判——去重憑據是出貨箱，不是行程紀錄
（行程紀錄會被別的 rm 刪掉，靠不住）。`deletes` 在原單真的刪掉之後才清。

**`rm` 的三種情況**：
- 行程 `queued`／`done`／`bad`：從帳本拿掉（含 queue）。`once` 且 `queued`：它 `pending` 的 add 回 `-32000`／`Removed`（進 `replies`）。
- 行程 `running`、那顆 cpu 的 `req` 是它：照範式順序查——`cpus/<c>/requests/<req>` **在** → 在途，標 `discard`、
  行程紀錄留著（回音到了才拿掉，同名 add 在那之前都 `AlreadyExists`）；原單不在再看回音，**在** → 同上；
  兩個都不在 → 上一格記了沒放，直接取消：`req`／`proc` 清 null、行程拿掉。
- **`once` 不管在途還是取消，`rm` 當下就把 pending 的 add 回 `Removed`**、`pending` 清掉；之後那顆 cpu 的回音只是被 discard 掉。
