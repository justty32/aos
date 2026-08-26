# core scope 黑客松 — 白話導讀（祕書）

← [本場索引](README.md)｜[hackathon](../../README.md)

**使用者從這裡開始讀。** 每輪祕書把發生的事翻成白話，錯誤訊息一條一句翻譯，最後一塊講「所以呢」。

---

## 第 1 輪白話導讀

### 1. 這一輪到底發生了什麼

四個人都用現成的 aos 把「想一步、做一步、把結果交回去」連跑三次。正常時都跑得完，但半路被停掉後都要人查現場、搬檔或重排剩下的事，而且有一種情況光看這台電腦永遠無法知道外面到底做了沒。實驗中沒有出現需要同時照看的第二件工作，所以這輪沒有替最大套方案提供實際理由。

### 2. 冒出來的新詞

- **`.runi`**
  白話：見 [BACKGROUND](../../../workshop/BACKGROUND.md)。  
  在 aos 裡具體是什麼：`aos exec <world>` 取走 `.aos/inst.json` 後改成的 `.aos/inst.json.runi`；目前只能說「這整包沒正常收尾」。

- **Publish**
  白話：見 [BACKGROUND](../../../workshop/BACKGROUND.md)。  
  在 aos 裡具體是什麼：目前還不是公開命令，是把檔案先寫好再一次換成正式名稱的提案；本輪的私有 `atomic-publish.sh` 是試作。

- **Deliver**
  白話：見 [BACKGROUND](../../../workshop/BACKGROUND.md)。  
  在 aos 裡具體是什麼：現在是投件者手寫 `.temp` 再 `mv` 成 `<name>.json`，交給 `aos exec <world>` 取件；`aos deliver` 還是提案。

- **Effect 與 `unknown`**
  白話：見 [BACKGROUND](../../../workshop/BACKGROUND.md)。  
  在 aos 裡具體是什麼：指呼叫外部服務及「可能已做、可能沒做」的結果；目前沒有 aos 命令處理，`Effect＋resolve` 仍是提案。

- **receipt**
  白話：見 [BACKGROUND](../../../workshop/BACKGROUND.md)。  
  在 aos 裡具體是什麼：目前 `aos exec` 沒有這種可重開後查驗的收據；Publish 與 Effect 要不要留它仍是提案。

### 3. 看到的錯誤訊息各是什麼意思

- `aos exec: refusing ... .aos/inst.json.runi already exists`：aos 看到上次沒收好的整包現場，因為不知哪些已做過，所以拒絕自動再跑。
- `restart_exit=3` 或 `immediate_restart_exit=3`：重開命令不是自己壞掉，而是因上面那份 `.runi` 刻意停下來等人處理。
- `...=present` 與 `...=missing`：前者是檔案還在，後者是應有的結果或退出紀錄沒寫下來；兩者同時出現就是「有做過的跡象，但收尾不全」。
- `deliver_exit=137`、`schedule.exit=137`、`tool.exit=137` 或 `kill9_exit=137`：該行程是被 `kill -9` 強制砍掉的，137 就是 128＋第 9 號訊號。
- `Killed`：這是 shell 把「行程已被強制殺掉」直接印出來，不是另一個新錯誤。
- `ctrl_c_exec_exit=130`：這次 `aos` 是因 Ctrl-C 中止的，130 就是 128＋第 2 號訊號。
- `schedule.exit=66`：負責排下一步的測試腳本自己回報失敗，所以後面沒有新工作可跑；66 不是 `aos exec` 本身的總結果。
- `rejected_exit=70` 與 `accepted_exit=70`：這個 70 是測試腳本用來表示「本機沒收到可信的答案」，所以外部其實收了或沒收，本機看起來都一樣。
- `restart_exit=0`、`blind_restart_exit=0`、`plain_restart_exit=0` 但 `result=missing` 或 `final_exists=no`：命令本身沒找到可執行的東西並正常結束，不代表整條工作真的完成。
- `temp=yes ready=no`：內容還停在草稿名稱，aos 故意不讀；`manual_fix=rename_temp` 表示這次是人檢查後手動改名才救回來。
- `ledger_lines=1`、`ledger_lines=0` 但 `local_snapshot_diff_exit=0` 或 `client_worlds_diff_exit=0`：外面一份已收到、一份沒收到，但兩份本機現場比對完全沒差異。
- `provider_ledger_lines=2` 或 `oracle_ledger_lines_after_retry=2`：原本那次其實已被外面收到，不查就盲目重試後又做了一次。
- `aos_after_tool_group_kill_exit=0` 但 `tool.exit=137` 與 `schedule.exit=66`：aos 只報「這包命令處理完了」，包裡的工具被砍掉、下一步失敗並不會讓它改報失敗。
- `orphan_alive_after_manual_kill=1`：這裡的 1 是 `kill -0` 查無此行程，意思反而是人工殺掉後孤兒已不存在。
- `od` 印出 `65 66 66 65 63 74 6e`：檔案確實有 `effectn` 這 7 個字元，先前 `wc -l` 報 0 只是因為它數的是換行符。
- `aos exec` 連續回 0 但錯名的 `delivery-turn1.timestamp.pid.json` 原封不動：檔名多了點就不符取件規則，現行實作會安靜略過，所以它沒有可翻的錯誤訊息。

### 4. 所以呢

這輪直接對到 [OPEN-QUESTIONS 第 2 題](../../../workshop/OPEN-QUESTIONS.md#2-近期-core-要回撤到哪裡)「近期 core 要回撤到哪裡」。現在仍是三個選項：

- **只留最小 Deliver**：得到最小的 core；賠掉的是這輪已實際出現的多處通用安全寫檔仍要由各人自備，外部到底做了沒也繼續交給上層或人處理。
- **先做 Publish、Deliver、Effect 三項**：得到一套共用的寫檔、投遞與外部結果記錄邊界；賠掉的是必須現在就定義命名、碰撞、收據、重開與耐久範圍，而無法查詢的外部服務仍只能留給人判斷。
- **保留完整控制平面**：得到日後可同時管多件工作、等待與收拾子工作的容量；賠掉的是要先背負一整套本輪尚未出現實際需求的設計與驗證成本。

## 第 2 輪白話導讀

### 1. 這一輪到底發生了什麼

四個人把上輪撞壞的地方做成「出事後重下同一條命令」的版本，再用兩個人同時投件、半路中止和重開去砍它。待辦還沒被取走時，多數撞名、覆蓋和人工搬檔問題已能擋住或救回；待辦一旦被取走卻還沒留下收件證明，現場又會失憶。外面的服務到底收到沒有，這台電腦仍然猜不回來。

### 2. 跟上一輪比，變了什麼

上輪只是知道「人得搬檔、盲目重跑可能做兩次」，這輪換到三件實物：人工搬檔降到零、同名投件不再互相蓋掉、盲目重跑確實被量到做了兩次。也推翻了兩個上輪說法：三行腳本並不足夠，Deliver 也不能只當 Publish 外面一層薄殼，因為檔案被取走後還缺一張由收件方留下的證明。沒有換到的是 scope 答案：仍沒有第二件長期工作需要 core 管，也仍無法替不可查詢的外部服務自動判真相。

### 3. 新冒出來的詞

- **no-replace／`renameat2(RENAME_NOREPLACE)`**<br>
  白話：見 [BACKGROUND](../../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：現行 `aos` 沒有這支公開命令；本輪三份私有 Publish 原型用 Linux `renameat2(..., RENAME_NOREPLACE)`，另一份用 hard link，做到同名時明確回 Already 或 Conflict、不偷偷覆蓋。

- **consumer acknowledgment**<br>
  白話：見 [BACKGROUND](../../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：目前不存在，是下一輪提案；現行 `core/inst/src/handoff.cpp` 的 `aggregate_instructions()` 取走並刪除 delivery 後，沒有另留一張「已收走」的證明。

- **TOCTOU**<br>
  白話：見 [BACKGROUND](../../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：不是 aos 命令；本輪私有原型先看目錄／檔案在不在、稍後才建立或搬入，中間被另一個投件者插隊，分別撞出 `FileExistsError` 與無聲覆蓋。

- **stable key、ledger、fsync、Publish、Deliver、Effect、receipt、`unknown`**<br>
  白話：見 [BACKGROUND](../../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：本輪仍全是私有試作；公開命令尚未存在，現行投遞入口仍是 `aos exec <world>` 讀 `.aos/inst.tempd/*.json`。

- **canonical parser／schema**<br>
  白話：見 [BACKGROUND](../../../workshop/BACKGROUND.md) 的 ABI／schema。<br>
  在 aos 裡具體是什麼：正式的整批讀取在 `core/inst/src/format.cpp` 的 `read_all()`；本輪兩份 Python validator 沒有共用它，若直接做成 Deliver 會多長一套規則。

### 4. 這輪新看到的錯誤訊息各是什麼意思

- `FileExistsError: [Errno 17] File exists`：兩個投件者同時建立同一個位置，其中一個慢半步撞到已存在的目錄；這次是原型自己的競爭漏洞。
- `mv: cannot stat '...json.temp': No such file or directory`：兩個投件者共用同一份草稿名，其中一個先搬走後，另一個回頭已找不到自己的來源檔。
- `conflict`／`exit 73`：同一個正式名稱已有不同內容，新版原型明確拒絕覆蓋；這是預期的保護，不是檔案莫名壞掉。
- `same_retry_exit=1 ... mv: cannot stat '.../source'`：舊腳本第一次已把來源搬走，事故後用原參數重跑時沒有材料可搬，所以無法自救。
- `aos exec: warning: .../bad.json: JsonSyntax`：檔名合格所以 aos 有取件，但內容不是合法 JSON；相對地，錯名檔仍是安靜略過、回 0。
- `kill: Illegal number: -`：恢復腳本把負的行程群組編號交給不支援該寫法的 shell 內建 `kill`；改叫 `/bin/kill` 後才成功。
- `final JSON` 壞掉但三次 `aos exec` 都回 0：測試把收據文字混進本來應是純 JSON 的輸出；0 只表示 aos 跑完那包，不能替產物內容背書。
- `patch rejected: writing outside of the project; rejected by user approval settings`：參賽者想寫上一輪場地，但沙盒不准；所以四份本輪成果改放 `/tmp`，不是原型本身失敗。
- `residual temps=...json.temp`：窄版 hard-link 做法成功保住正式檔不被蓋，但事故草稿沒有清掉，久了會堆垃圾。

### 5. 所以呢

這輪仍直接影響 [OPEN-QUESTIONS 第 2 題](../../../workshop/OPEN-QUESTIONS.md#2-近期-core-要回撤到哪裡)，但沒有替使用者把三選一改成唯一答案：

- **只留最小 Deliver**：core 最小；賠掉共用 Publish、外部結果的 `unknown`／resolve，以及本輪已證實需要的收件歷史，這些仍得由上層或人各自補。
- **保留 Publish → Deliver → Effect 三項**：得到共用的安全發布、投遞與外部結果記錄；賠掉的是 Deliver 不能再假定只是薄殼，還要決定收件證明和 ledger 放在 Deliver、aggregate 還是 core，Effect 也只能誠實停在 `unknown`，不能保證只做一次。
- **連完整控制平面一起保留**：得到日後同時管理多件長期工作、等待與收尾的空間；賠掉的是現在就背 lane、proc-table、join 等整套設計與驗證成本，而兩輪實驗仍只找到多個短命投件者，沒有找到第二件需要長期管理的工作。

所以多跑這輪改變的是中間選項的內部代價與分界，不是三個選項本身：最小 Deliver 比上輪看起來少算了一張收件證明，三項 core 比上輪看起來不再是三層簡單相疊，完整控制平面則仍沒有新增的實測需求。

## 第 3 輪白話導讀

### 1. 這一輪到底發生了什麼

四個人沒有再把整套東西重做一遍，而是專打上輪還沒釘死的幾個縫。收件方肯留下證明時，半路被砍後已能自己接回去；外面的服務若無法查詢，這台電腦仍然不可能猜出它到底做了沒。這輪也抓到自己另寫的資料檢查規則，已經跟 aos 真正接受的規則不一樣。

### 2. 跟上一輪比，變了什麼

上輪只是推定「收件方留證明」可能救回檔案被取走後的失憶，這輪把四個中止位置都跑通了，還證明重跑不會多做一次；但不留證明的收件方仍只能停住。外部服務那邊則只補實了「已有答案或已有人的處置決定時，重開只做收尾」，沒有換回未知那一段的真相。scope 沒翻案：中間選項的可行性變硬、代價也更清楚，完整控制平面仍沒有第二件長期工作替它提供理由。

### 3. 新冒出來的詞

- **consumer acknowledgment／completion ack／ack gate**<br>
  白話：見前；就像收件人簽收後，門口才准把下一箱貨放行。<br>
  在 aos 裡具體是什麼：仍是私有提案；本輪原型讓收件方在 `claim → aggregate publish → delete delivery → ack commit` 後留證明，並在 `aos exec` 前設 gate，現行 `core/inst/src/handoff.cpp` 的 `aggregate_instructions()` 還沒有這段。

- **terminal projection**<br>
  白話：見 [BACKGROUND](../../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：不是現行 aos 命令；本輪私有 `effect.sh resolve EFFECT adopt-ready-response`／`effect.sh resolve EFFECT abandon` 只補 `done`，Effect／resolve 本身仍是提案。

- **C ABI／conformance／canonical parser／schema**<br>
  白話：見 [BACKGROUND](../../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：單筆公開入口在 `core/inst/include/aos/inst.h`，正式整批讀取規則在 `core/inst/src/format.cpp` 的 `read_all()`；後者尚無公開 C ABI，本輪只做對照，沒有新增命令。

- **retention／GC**<br>
  白話：見 [BACKGROUND](../../../workshop/BACKGROUND.md) 的 ledger。<br>
  在 aos 裡具體是什麼：目前不存在，是 completion ack／receipt 若進 core 後仍待決的保存與清理提案。

- **Publish、Deliver、Effect、receipt、ledger、`unknown`、no-replace、fsync、idempotency key**<br>
  白話：見前／見 [BACKGROUND](../../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：本輪仍是 `/tmp` 裡的 Python／shell 私有原型；公開入口仍只有 `aos exec <world>`，沒有 `aos publish`、`aos deliver`、`aos effect` 或 `resolve` 命令。

### 4. 這輪新看到的錯誤訊息各是什麼意思

- `r2_present=no`／`round2=missing`：上一輪放在 `/tmp` 的現場已被系統清掉，不是本輪原型跑壞。
- `victim_exit=137`：見前；這是測試故意把行程強制砍掉，用來驗重開。
- `unknown-consumer-history: producer published, but ready, claim, and ack are absent`／`rogue_recover_exit=1`：東西曾投出去，但現在待辦、取件痕跡和簽收證明全不在，程式拒絕猜它是否已被處理。
- `Unknown key=K evidence=temp-without-target-or-ack`／`exit=5`：只剩草稿，既看不到正式件也看不到簽收單，所以同一條重試命令只能回答「不知道」。
- `3:NotAnObject`：拿整批陣列去問只會檢查單筆資料的公開入口，它看到的不是單一物件；這也表示整批檢查尚無可用的公開入口。
- `cat: .../child.pgid: No such file or directory`：測試太早動手，子行程編號檔還沒寫好；該次結果已作廢重跑。
- `/bin/kill: failed to parse argument: '-'`：上一個缺檔讓殺行程命令拿到空值，因而只剩一個無法解析的減號；不是被測功能本身的錯。
- 第一次 audit 顯示四案 exit 都是 `0` 筆：檢查腳本找錯資料夾，不是四案都沒執行；改看 world 根目錄後每案各找到一筆內容為 `0` 的退出紀錄。
- `st_nlink=2`：第一版測法留下兩個檔名指向同一份內容，意外洩漏了先前發生過什麼，因此那次「兩種歷史看起來一樣」的證明不成立，已作廢重跑。

### 5. 所以呢

這輪仍影響 [OPEN-QUESTIONS 第 2 題](../../../workshop/OPEN-QUESTIONS.md#2-近期-core-要回撤到哪裡)，三個選項仍都在，但各自要賠的東西更明確：

- **只留最小 Deliver**：得到最小 core；賠掉共用的安全發布與外部結果記錄，而且若 Deliver 不含收件方的簽收證明，待辦被取走後仍會失憶。若把簽收也算進「最小 Deliver」，就得一併承擔簽收順序、保存多久與清理責任。
- **保留 Publish → Deliver → Effect 三項**：得到本輪已跑通的共用發布、收件證明與有證據才收尾的邊界；賠掉的是三項不能只是薄薄相疊，還要處理整批資料共用同一套檢查規則、並行取件、簽收保存，以及外部服務無法查詢時永遠只能停在 `unknown`。
- **連完整控制平面一起保留**：得到未來同時管理多件長期工作、等待、取消與收尾的空間；賠掉 lane、join、proc-table 等整套設計與驗證成本，而三輪的「第二件需要同時管理的工作」仍是 0，這輪沒有替那些成本換到新證據。

因此，多跑這輪沒有替使用者選答案；它把中間選項從「看起來可試」推到「幾個窄故障點確實跑通」，同時把它必須包含的簽收、共用檢查與保存責任攤開。最小選項的界線也變得不能只用一層薄包裝帶過；最大選項則仍沒有新增實測需求。
