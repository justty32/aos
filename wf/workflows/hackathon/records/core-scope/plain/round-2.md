# 第 2 輪白話導讀

← [本檔索引](README.md)｜[本場索引](../README.md)｜[hackathon](../../../README.md)｜[← 上一份](round-1.md)｜[下一份 →](round-3.md)

## 1. 這一輪到底發生了什麼

四個人把上輪撞壞的地方做成「出事後重下同一條命令」的版本，再用兩個人同時投件、半路中止和重開去砍它。待辦還沒被取走時，多數撞名、覆蓋和人工搬檔問題已能擋住或救回；待辦一旦被取走卻還沒留下收件證明，現場又會失憶。外面的服務到底收到沒有，這台電腦仍然猜不回來。

## 2. 跟上一輪比，變了什麼

上輪只是知道「人得搬檔、盲目重跑可能做兩次」，這輪換到三件實物：人工搬檔降到零、同名投件不再互相蓋掉、盲目重跑確實被量到做了兩次。也推翻了兩個上輪說法：三行腳本並不足夠，Deliver 也不能只當 Publish 外面一層薄殼，因為檔案被取走後還缺一張由收件方留下的證明。沒有換到的是 scope 答案：仍沒有第二件長期工作需要 core 管，也仍無法替不可查詢的外部服務自動判真相。

## 3. 新冒出來的詞

- **no-replace／`renameat2(RENAME_NOREPLACE)`**<br>
  白話：見 [BACKGROUND](../../../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：現行 `aos` 沒有這支公開命令；本輪三份私有 Publish 原型用 Linux `renameat2(..., RENAME_NOREPLACE)`，另一份用 hard link，做到同名時明確回 Already 或 Conflict、不偷偷覆蓋。

- **consumer acknowledgment**<br>
  白話：見 [BACKGROUND](../../../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：目前不存在，是下一輪提案；現行 `core/inst/src/handoff.cpp` 的 `aggregate_instructions()` 取走並刪除 delivery 後，沒有另留一張「已收走」的證明。

- **TOCTOU**<br>
  白話：見 [BACKGROUND](../../../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：不是 aos 命令；本輪私有原型先看目錄／檔案在不在、稍後才建立或搬入，中間被另一個投件者插隊，分別撞出 `FileExistsError` 與無聲覆蓋。

- **stable key、ledger、fsync、Publish、Deliver、Effect、receipt、`unknown`**<br>
  白話：見 [BACKGROUND](../../../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：本輪仍全是私有試作；公開命令尚未存在，現行投遞入口仍是 `aos exec <world>` 讀 `.aos/inst.tempd/*.json`。

- **canonical parser／schema**<br>
  白話：見 [BACKGROUND](../../../../workshop/BACKGROUND.md) 的 ABI／schema。<br>
  在 aos 裡具體是什麼：正式的整批讀取在 `core/inst/src/format.cpp` 的 `read_all()`；本輪兩份 Python validator 沒有共用它，若直接做成 Deliver 會多長一套規則。

## 4. 這輪新看到的錯誤訊息各是什麼意思

- `FileExistsError: [Errno 17] File exists`：兩個投件者同時建立同一個位置，其中一個慢半步撞到已存在的目錄；這次是原型自己的競爭漏洞。
- `mv: cannot stat '...json.temp': No such file or directory`：兩個投件者共用同一份草稿名，其中一個先搬走後，另一個回頭已找不到自己的來源檔。
- `conflict`／`exit 73`：同一個正式名稱已有不同內容，新版原型明確拒絕覆蓋；這是預期的保護，不是檔案莫名壞掉。
- `same_retry_exit=1 ... mv: cannot stat '.../source'`：舊腳本第一次已把來源搬走，事故後用原參數重跑時沒有材料可搬，所以無法自救。
- `aos exec: warning: .../bad.json: JsonSyntax`：檔名合格所以 aos 有取件，但內容不是合法 JSON；相對地，錯名檔仍是安靜略過、回 0。
- `kill: Illegal number: -`：恢復腳本把負的行程群組編號交給不支援該寫法的 shell 內建 `kill`；改叫 `/bin/kill` 後才成功。
- `final JSON` 壞掉但三次 `aos exec` 都回 0：測試把收據文字混進本來應是純 JSON 的輸出；0 只表示 aos 跑完那包，不能替產物內容背書。
- `patch rejected: writing outside of the project; rejected by user approval settings`：參賽者想寫上一輪場地，但沙盒不准；所以四份本輪成果改放 `/tmp`，不是原型本身失敗。
- `residual temps=...json.temp`：窄版 hard-link 做法成功保住正式檔不被蓋，但事故草稿沒有清掉，久了會堆垃圾。

## 5. 所以呢

這輪仍直接影響 [OPEN-QUESTIONS 第 2 題](../../../../workshop/OPEN-QUESTIONS.md#2-近期-core-要回撤到哪裡)，但沒有替使用者把三選一改成唯一答案：

- **只留最小 Deliver**：core 最小；賠掉共用 Publish、外部結果的 `unknown`／resolve，以及本輪已證實需要的收件歷史，這些仍得由上層或人各自補。
- **保留 Publish → Deliver → Effect 三項**：得到共用的安全發布、投遞與外部結果記錄；賠掉的是 Deliver 不能再假定只是薄殼，還要決定收件證明和 ledger 放在 Deliver、aggregate 還是 core，Effect 也只能誠實停在 `unknown`，不能保證只做一次。
- **連完整控制平面一起保留**：得到日後同時管理多件長期工作、等待與收尾的空間；賠掉的是現在就背 lane、proc-table、join 等整套設計與驗證成本，而兩輪實驗仍只找到多個短命投件者，沒有找到第二件需要長期管理的工作。

所以多跑這輪改變的是中間選項的內部代價與分界，不是三個選項本身：最小 Deliver 比上輪看起來少算了一張收件證明，三項 core 比上輪看起來不再是三層簡單相疊，完整控制平面則仍沒有新增的實測需求。
