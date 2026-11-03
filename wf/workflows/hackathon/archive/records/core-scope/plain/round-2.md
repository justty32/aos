# 第 2 輪白話導讀

← [本檔索引](README.md)｜[本場索引](../README.md)｜[hackathon](../../../README.md)｜[← 上一份](round-1.md)｜[下一份 →](round-3.md)

## 1. 這一輪到底發生了什麼

待辦還沒被取走時，撞名、覆蓋和人工搬檔問題已能擋住或救回；待辦一旦被取走、卻還沒留下收件證明，現場又會失憶。外面的服務到底收到沒有，這台電腦仍然猜不回來。

## 2. 跟上一輪比，變了什麼

- 人工搬檔降到零、同名投件不再互相蓋掉、盲目重跑確實被量到做了兩次。
- 第 1 輪兩個說法不成立：三行腳本不夠；Deliver 不能只當 Publish 外面一層薄殼，因為檔案被取走後還缺一張由收件方留下的證明。
- scope 答案沒換：仍沒有第二件長期工作需要 core 管，也仍無法替不可查詢的外部服務自動判真相。

## 3. 新冒出來的詞

- **no-replace／`renameat2(RENAME_NOREPLACE)`**：現行 `aos` 沒有；私有 Publish 原型用 Linux `renameat2` 或 hard link，同名時明確回 Already 或 Conflict、不偷偷覆蓋。
- **TOCTOU**：先看在不在、稍後才建立或搬入，中間被另一個投件者插隊；撞出 `FileExistsError` 與無聲覆蓋。
- **consumer acknowledgment**：見 [第 3 輪](round-3.md)。其餘詞見 [BACKGROUND](../../../../workshop/BACKGROUND.md)。

## 4. 這輪新看到的錯誤訊息各是什麼意思

- `FileExistsError: [Errno 17] File exists`：兩個投件者同時建立同一個位置，慢半步的撞到已存在的目錄。
- `mv: cannot stat '...json.temp': No such file or directory`：兩個投件者共用同一份草稿名，一個先搬走，另一個找不到來源檔。
- `conflict`／`exit 73`：同一正式名稱已有不同內容，原型明確拒絕覆蓋；是預期的保護。
- `same_retry_exit=1 ... mv: cannot stat '.../source'`：舊腳本第一次已把來源搬走，事故後用原參數重跑沒有材料可搬。
- `aos exec: warning: .../bad.json: JsonSyntax`：檔名合格所以有取件，但內容不是合法 JSON；錯名檔則安靜略過、回 0。
- 產物 JSON 壞掉但 `aos exec` 回 0：0 只表示 aos 跑完那包，不替產物內容背書。
- `residual temps=...json.temp`：hard-link 做法保住正式檔不被蓋，但事故草稿沒清，久了會堆垃圾。

## 5. 所以呢

三個選項的代價以 [第 3 輪〈所以呢〉](round-3.md) 為準。
