← [cpu](README.md)｜[spec 總導航](../README.md)

# 3. 訊息：JSON-RPC 2.0，一個信封走兩條路

| 路 | 一則長怎樣 | 誰對誰 | 載什麼 |
|---|---|---|---|
| 檔案 | `requests/<n>.json` 一份一則；回音 `responses/<n>.json` 同名 | 任何人 → cpu | 工作、ack、stop |
| 控制 pipe | 一行一則（換行結尾，內容不含換行） | 父行程 ↔ cpu | 只有 `go`、`stop` 與 EOF |

信封照 JSON-RPC 2.0 原樣：request `{"jsonrpc":"2.0","id":…,"method":…,"params":…}`；`method` 必須是
字串；`id` 是字串、數字或 `null`。response `{"jsonrpc":"2.0","id":…,"result":…}` 或
`{"jsonrpc":"2.0","id":…,"error":{"code":整數,"message":白話,"data":…}}`。不支援 batch。

收到一份檔，分三類：

| 類 | 怎麼判 | 回不回 |
|---|---|---|
| 讀不出來 | 不是 JSON／UTF-8 壞了／不是物件／缺 `jsonrpc`、`method`／型別不合 | **回**，`id` 抓得到就抓、抓不到是 `null`（-32700／-32600） |
| notification | 信封合法、**沒有 `id` 這個鍵** | **絕不回**，就算 method 不認得、params 壞掉也不回 |
| 有 id 的 request | 信封合法、有 `id` | 一定回，成功 `result`、失敗 `error` |

**兩層身分**：檔名 `<n>` 是運輸層的身分（回音靠它對回去，壞 JSON 也對得回去）；`id` 是協議層的身分
（交件者自己認）。慣例兩者用同一個字串。

## 3.1 怎麼放單

寫同目錄唯一 `.tmp` → `os.link(tmp, requests/<n>.json)` → 刪 `.tmp`。目標已存在＝EEXIST＝交件者
的錯，換個名字再來。（放單的人自己也可以用 EEXIST 當「已經放過了」的訊號——kernel 就是這樣重做派工。）

## 3.2 error.code 怎麼編

JSON-RPC 規定 `code` 是整數。信封、method、params 的檢查用它保留的四個號碼（下表）；其餘 aos 錯誤一律 `-32000`，
真正的代號放 `data.code`（字串，沿用現有的 `NotAHome`／`FieldTypeMismatch`…），`message` 是白話。

| code | 什麼時候 | data |
|---|---|---|
| -32700 | 檔不是 JSON／UTF-8 壞了 | 無 |
| -32600 | 不是物件、缺 `jsonrpc`／`method`、`jsonrpc` 不是 `"2.0"`、`method` 不是字串、`id` 型別不合 | 無 |
| -32601 | 這個 cpu 不認得的 method | 無 |
| -32602 | params 形狀不對，或 aos-exec 會回「用法錯」的情況（§4.1） | `{"code":"FieldTypeMismatch"｜"Usage","position":[…]}` |
| -32000 | 其他 aos 錯誤，含 `Interrupted`（§6.2） | `{"code":"<代號>"}` |

## 3.3 `ack`：收件者說「拿走了」

```json
{"jsonrpc":"2.0","method":"ack","params":{"name":"agent-1790000000000000000-77.json"}}
```

notification，**檔名必須以 `ack-` 開頭**（主人只掃前綴）。主人處理的順序：刪 `responses/<name>`
（不在＝ENOENT＝當成功）→ 刪這份 ack 檔。崩在中間＝下次重來一次，兩步都是可重做的。
回音在 ack 之前一直留著，所以收件者可以「讀 → 自己記下 → 再 ack」，中間崩了重讀同一份，不會漏。
