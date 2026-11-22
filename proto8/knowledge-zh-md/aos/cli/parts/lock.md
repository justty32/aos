# `knowledge/aos/cli/parts/lock.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/parts/lock.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/parts/lock.md#/…` 對的就是它。改請改正本，再照 [README](../../../README.md) 的做法跟上這份。

---

**`#/aos-lock: a lock next to a file or folder`**

# aos-lock：檔案或資料夾旁邊的鎖

```sh
aos-lock acquire --note editing f.txt     # creates f.txt.lock/ (for a folder d: d/.lock/); prints nothing
aos-lock show f.txt                       # {"holder": "/work", "acquired_at": "...", "note": "editing"}
aos-lock release f.txt
```

結束碼 10＝鎖已被拿走（acquire）、被別人持有（release：什麼都沒釋放，一行警告），或不存在（show）。`--wait-ms N` 最多等 N 毫秒；`--lease-cycles N` 讓租約在 N 個時鐘週期後到期。持有者是你的 `AOS_WS`、`AOS_STACK`、`AOS_CF` 或目前資料夾。`release --force` 釋放別人的鎖。釋放不存在的鎖＝`LockMissing`。移除到一半的鎖資料夾由清掃程式（sweeper）清掉。
