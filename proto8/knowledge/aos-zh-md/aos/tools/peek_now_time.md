# `knowledge/aos/tools/peek_now_time.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/peek_now_time.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# 工具 peek_now_time

取得現在時間：UTC 的 ISO 8601，或用 `{"local": true}` 取這台機器的本地時間。不改任何東西。

只要需要日期或時間就用它；不要用猜的。要 daemon 時鐘的週期用 `peek_clock`。

```json
{}
```
-> `2026-11-11T03:24:34Z`

`Z` 表示 UTC。`{"local": true}` -> `2026-11-13T21:30:00+08:00 Friday`：本地時間，加上它的 UTC 時差和星期幾。

錯誤：`ArgumentsBad`（唯一的鍵是 `local`，布林值；`aos/errors/common.json#/input`）。
