# 第 3 輪白話導讀

← [本檔索引](README.md)｜[本場索引](../README.md)｜[hackathon](../../../README.md)｜[← 上一份](round-2.md)

## 1. 這一輪到底發生了什麼

四個人沒有再把整套東西重做一遍，而是專打上輪還沒釘死的幾個縫。收件方肯留下證明時，半路被砍後已能自己接回去；外面的服務若無法查詢，這台電腦仍然不可能猜出它到底做了沒。這輪也抓到自己另寫的資料檢查規則，已經跟 aos 真正接受的規則不一樣。

## 2. 跟上一輪比，變了什麼

上輪只是推定「收件方留證明」可能救回檔案被取走後的失憶，這輪把四個中止位置都跑通了，還證明重跑不會多做一次；但不留證明的收件方仍只能停住。外部服務那邊則只補實了「已有答案或已有人的處置決定時，重開只做收尾」，沒有換回未知那一段的真相。scope 沒翻案：中間選項的可行性變硬、代價也更清楚，完整控制平面仍沒有第二件長期工作替它提供理由。

## 3. 新冒出來的詞

- **consumer acknowledgment／completion ack／ack gate**<br>
  白話：見前；就像收件人簽收後，門口才准把下一箱貨放行。<br>
  在 aos 裡具體是什麼：仍是私有提案；本輪原型讓收件方在 `claim → aggregate publish → delete delivery → ack commit` 後留證明，並在 `aos exec` 前設 gate，現行 `core/inst/src/handoff.cpp` 的 `aggregate_instructions()` 還沒有這段。

- **terminal projection**<br>
  白話：見 [BACKGROUND](../../../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：不是現行 aos 命令；本輪私有 `effect.sh resolve EFFECT adopt-ready-response`／`effect.sh resolve EFFECT abandon` 只補 `done`，Effect／resolve 本身仍是提案。

- **C ABI／conformance／canonical parser／schema**<br>
  白話：見 [BACKGROUND](../../../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：單筆公開入口在 `core/inst/include/aos/inst.h`，正式整批讀取規則在 `core/inst/src/format.cpp` 的 `read_all()`；後者尚無公開 C ABI，本輪只做對照，沒有新增命令。

- **retention／GC**<br>
  白話：見 [BACKGROUND](../../../../workshop/BACKGROUND.md) 的 ledger。<br>
  在 aos 裡具體是什麼：目前不存在，是 completion ack／receipt 若進 core 後仍待決的保存與清理提案。

- **Publish、Deliver、Effect、receipt、ledger、`unknown`、no-replace、fsync、idempotency key**<br>
  白話：見前／見 [BACKGROUND](../../../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：本輪仍是 `/tmp` 裡的 Python／shell 私有原型；公開入口仍只有 `aos exec <world>`，沒有 `aos publish`、`aos deliver`、`aos effect` 或 `resolve` 命令。

## 4. 這輪新看到的錯誤訊息各是什麼意思

- `r2_present=no`／`round2=missing`：上一輪放在 `/tmp` 的現場已被系統清掉，不是本輪原型跑壞。
- `victim_exit=137`：見前；這是測試故意把行程強制砍掉，用來驗重開。
- `unknown-consumer-history: producer published, but ready, claim, and ack are absent`／`rogue_recover_exit=1`：東西曾投出去，但現在待辦、取件痕跡和簽收證明全不在，程式拒絕猜它是否已被處理。
- `Unknown key=K evidence=temp-without-target-or-ack`／`exit=5`：只剩草稿，既看不到正式件也看不到簽收單，所以同一條重試命令只能回答「不知道」。
- `3:NotAnObject`：拿整批陣列去問只會檢查單筆資料的公開入口，它看到的不是單一物件；這也表示整批檢查尚無可用的公開入口。
- `cat: .../child.pgid: No such file or directory`：測試太早動手，子行程編號檔還沒寫好；該次結果已作廢重跑。
- `/bin/kill: failed to parse argument: '-'`：上一個缺檔讓殺行程命令拿到空值，因而只剩一個無法解析的減號；不是被測功能本身的錯。
- 第一次 audit 顯示四案 exit 都是 `0` 筆：檢查腳本找錯資料夾，不是四案都沒執行；改看 world 根目錄後每案各找到一筆內容為 `0` 的退出紀錄。
- `st_nlink=2`：第一版測法留下兩個檔名指向同一份內容，意外洩漏了先前發生過什麼，因此那次「兩種歷史看起來一樣」的證明不成立，已作廢重跑。

## 5. 所以呢

這輪仍影響 [OPEN-QUESTIONS 第 2 題](../../../../workshop/OPEN-QUESTIONS.md#2-近期-core-要回撤到哪裡)，三個選項仍都在，但各自要賠的東西更明確：

- **只留最小 Deliver**：得到最小 core；賠掉共用的安全發布與外部結果記錄，而且若 Deliver 不含收件方的簽收證明，待辦被取走後仍會失憶。若把簽收也算進「最小 Deliver」，就得一併承擔簽收順序、保存多久與清理責任。
- **保留 Publish → Deliver → Effect 三項**：得到本輪已跑通的共用發布、收件證明與有證據才收尾的邊界；賠掉的是三項不能只是薄薄相疊，還要處理整批資料共用同一套檢查規則、並行取件、簽收保存，以及外部服務無法查詢時永遠只能停在 `unknown`。
- **連完整控制平面一起保留**：得到未來同時管理多件長期工作、等待、取消與收尾的空間；賠掉 lane、join、proc-table 等整套設計與驗證成本，而三輪的「第二件需要同時管理的工作」仍是 0，這輪沒有替那些成本換到新證據。

因此，多跑這輪沒有替使用者選答案；它把中間選項從「看起來可試」推到「幾個窄故障點確實跑通」，同時把它必須包含的簽收、共用檢查與保存責任攤開。最小選項的界線也變得不能只用一層薄包裝帶過；最大選項則仍沒有新增實測需求。
