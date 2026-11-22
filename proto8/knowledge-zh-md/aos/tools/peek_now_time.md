# `knowledge/aos/tools/peek_now_time.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/tools/peek_now_time.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/tools/peek_now_time.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Tool peek_now_time`**

# 工具 peek_now_time

取得現在時間：UTC 的 ISO 8601，或用 `{"local": true}` 取這台機器的本地時間。不改任何東西。

只要需要日期或時間就用它；不要用猜的。要 daemon 時鐘的週期用 `peek_clock`。

```json
{}
```
-> `2026-11-11T03:24:34Z`

`Z` 表示 UTC。`{"local": true}` -> `2026-11-13T21:30:00+08:00 Friday`：本地時間，加上它的 UTC 時差和星期幾。

錯誤：`ArgumentsBad`（唯一的鍵是 `local`，布林值；`aos/errors/common.md#/Codes about what you gave`）。
