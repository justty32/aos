# 第 3 輪白話導讀

← [本檔索引](README.md)｜[本場索引](../README.md)｜[hackathon](../../../README.md)｜[← 上一份](round-2.md)

## 1. 這一輪到底發生了什麼

收件方肯留下證明（簽收）時，半路被砍後能自己接回去，重跑不會多做一次；不留證明的收件方仍只能停住。外面的服務若無法查詢，這台電腦仍不可能猜出它做了沒；已有答案或已有人的處置決定時，重開只做收尾。自己另寫的資料檢查規則，已經跟 aos 真正接受的規則不一樣。scope 沒翻案。

## 2. 新冒出來的詞

- **consumer acknowledgment／completion ack／ack gate**：就像收件人簽收後，門口才准把下一箱貨放行。仍是私有提案：收件方在 `claim → aggregate publish → delete delivery → ack commit` 後留證明，`aos exec` 前設 gate；現行 `core/inst/src/handoff.cpp` 的 `aggregate_instructions()` 沒有這段。
- **terminal projection**：私有 `effect.sh resolve EFFECT adopt-ready-response`／`abandon` 只補 `done`；Effect／resolve 本身仍是提案。
- **C ABI／conformance／canonical parser**：單筆公開入口在 `core/inst/include/aos/inst.h`，正式整批讀取在 `core/inst/src/format.cpp` 的 `read_all()`，後者沒有公開 C ABI。
- **retention／GC**：completion ack／receipt 若進 core，保存多久、誰清理，仍待決。
- Publish、Deliver、Effect、receipt、ledger、`unknown`、no-replace、fsync、idempotency key：見 [BACKGROUND](../../../../workshop/BACKGROUND.md)。公開入口仍只有 `aos exec <world>`，沒有 `aos publish`、`aos deliver`、`aos effect` 或 `resolve`。

## 3. 這輪新看到的錯誤訊息各是什麼意思

- `unknown-consumer-history: producer published, but ready, claim, and ack are absent`／`rogue_recover_exit=1`：東西曾投出去，但待辦、取件痕跡和簽收證明全不在，程式拒絕猜它是否已被處理。
- `Unknown key=K evidence=temp-without-target-or-ack`／`exit=5`：只剩草稿，看不到正式件也看不到簽收單，同一條重試命令只能回答「不知道」。
- `3:NotAnObject`：拿整批陣列去問只檢查單筆的公開入口；整批檢查沒有可用的公開入口。

## 4. 所以呢

這輪影響 [OPEN-QUESTIONS 第 2 題](../../../../workshop/OPEN-QUESTIONS/direction.md#2-近期-core-要回撤到哪裡)，三個選項仍都在，各自要賠的東西：

- **只留最小 Deliver**：得到最小 core；賠掉共用的安全發布與外部結果記錄，而且若 Deliver 不含收件方的簽收證明，待辦被取走後仍會失憶。若把簽收也算進「最小 Deliver」，就得一併承擔簽收順序、保存多久與清理責任。
- **保留 Publish → Deliver → Effect 三項**：得到已跑通的共用發布、收件證明與有證據才收尾的邊界；賠掉的是三項不能只是薄薄相疊，還要處理整批資料共用同一套檢查規則、並行取件、簽收保存，以及外部服務無法查詢時永遠只能停在 `unknown`。
- **連完整控制平面一起保留**：得到未來同時管理多件長期工作、等待、取消與收尾的空間；賠掉 lane、join、proc-table 等整套設計與驗證成本，而三輪的「第二件需要同時管理的工作」都是 0，沒有證據替那些成本撐腰。

中間選項的幾個窄故障點確實跑通，同時攤開它必須包含的簽收、共用檢查與保存責任；最小選項的界線不能只用一層薄包裝帶過；最大選項沒有實測需求。
