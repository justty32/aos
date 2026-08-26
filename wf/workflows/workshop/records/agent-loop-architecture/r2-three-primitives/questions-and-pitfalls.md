# R2：大家問出來的問題與明顯的坑

> 本輪收攏後仍未回答的六題，以及七個明顯的坑。

## 大家問出來的問題

| 問題 | 誰問的 | 它卡住什麼 |
|---|---|---|
| key 由 caller 給還是 core 配？範圍是單 queue、單 world，還是跨 world？ | 工程師問是否跨 world；研究人員問誰配號；開發者問 key 範圍 | 決定去重邊界，也決定兩個世界用同一個 `K` 會不會誤認成同一次投遞／外呼 |
| receipt 的共同格式是什麼？ | 開發者直接問；工程師把 Effect receipt 接到 Deliver | 沒有共同欄位，Effect done 就不能在 crash 後可靠地判斷下一次 Deliver 是否已做 |
| Publish 是否公開？接受 temp/source 還是 payload？ | 開發者直接問；四位的 lib 簽名有兩種 | 決定它是穩定 API，還是 Deliver／Effect 的內部實作零件 |
| 目錄 Publish 是否只限同 filesystem？跨平台 no-replace 與目錄 fsync 保證到哪裡？ | 工程師、架構師、研究人員；架構師另標記跨平台保證不確定 | 決定 `--durable` 與 directory bundle 能承諾什麼，而不是只在目前機器可用 |
| Effect 是否包所有有副作用的命令？ | 架構師 | 若只包 LLM，其他付費 API／寫外部狀態仍有同一個 unknown 空窗 |
| join／reconcile 能否通用化而不理解 agent turn？ | 開發者直接標記不確定；工程師提出 `effect_join(keys)` | 決定它們是下一個 core 原語，還是應先留給 T5 腳本暴露共同形狀 |

## 明顯的坑

- **把三項當成三份互不相干的 temp／rename 實作**。**四位都把 Publish 放底座**；Deliver 與
  Effect 若各自複製一套，短寫、durable 與目錄發布語意很快就會分叉。

- **因為 Publish 被 4／4 選中，就倒推成四位都在 R1 獨立發明它。**原始來源是工程師、架構師
  兩位明確提出；研究人員、開發者在收攏輪把原先內含的動作升成共同底座。兩種訊號都重要，
  不能混寫。

- **把 Effect resolve 拆成第四套 recover 功能。**retry／lost／abandon／import／adopt 都是在處理
  同一個 unknown；分開會讓狀態字、key 與稽核紀錄各走各的。

- **Publish 只支援檔案，卻拿它承諾 event＋cursor 一起提交。**研究人員直接指出：沒有 directory
  publish，兩者仍會裂開可見，cursor 仍可能超前。

- **key 範圍未定就承諾冪等。**同 key 究竟在 BASE、world 還是全域內唯一，會直接改變 Already／
  Conflict 與 effect replay 的含義。

- **把 join／reconcile 急著收進 core，順手把 turn、tool、final 也帶進去。**工程師與開發者只
  提出缺口，沒有證明它能脫離 agent 語意；四位反而都明確排除 prompt、解析與停止政策。

- **三項做完就宣稱 agent loop 不再需要腳本。**四位都留下 driver／adapter；T5 原本就要用這些
  腳本找出下一批重複點，不能把「core 不該收」誤當成「工作已消失」。

