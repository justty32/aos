# `knowledge/aos/cli/parts/lock.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/parts/lock.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# aos-lock：檔案或資料夾旁邊的鎖

```sh
aos-lock acquire --note editing f.txt     # creates f.txt.lock/ (for a folder d: d/.lock/); prints nothing
aos-lock show f.txt                       # {"holder": "/work", "acquired_at": "...", "note": "editing"}
aos-lock release f.txt
```

結束碼 10＝鎖已被拿走（acquire）、被別人持有（release：什麼都沒釋放，一行警告），或不存在（show）。`--wait-ms N` 最多等 N 毫秒；`--lease-cycles N` 讓租約在 N 個時鐘週期後到期。持有者是你的 `AOS_WS`、`AOS_STACK`、`AOS_CF` 或目前資料夾。`release --force` 釋放別人的鎖。釋放不存在的鎖＝`LockMissing`。移除到一半的鎖資料夾由清掃程式（sweeper）清掉。
