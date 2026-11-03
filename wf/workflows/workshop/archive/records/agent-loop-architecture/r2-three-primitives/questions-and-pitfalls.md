# R2：大家問出來的問題與明顯的坑

> 本輪收攏後仍未回答的六題，以及六個明顯的坑。

## 大家問出來的問題

| 問題 | 它卡住什麼 |
|---|---|
| key 由 caller 給還是 core 配？範圍是單 queue、單 world，還是跨 world？ | 決定去重邊界，也決定兩個世界用同一個 `K` 會不會誤認成同一次投遞／外呼 |
| receipt 的共同格式是什麼？ | 沒有共同欄位，Effect done 就不能在 crash 後可靠地判斷下一次 Deliver 是否已做 |
| Publish 是否公開？接受 temp/source 還是 payload？ | 決定它是穩定 API，還是 Deliver／Effect 的內部實作零件 |
| 目錄 Publish 是否只限同 filesystem？跨平台 no-replace 與目錄 fsync 保證到哪裡？ | 決定 `--durable` 與 directory bundle 能承諾什麼，而不是只在目前機器可用 |
| Effect 是否包所有有副作用的命令？ | 若只包 LLM，其他付費 API／寫外部狀態仍有同一個 unknown 空窗 |
| join／reconcile 能否通用化而不理解 agent turn？ | 決定它們是下一個 core 原語，還是應先留給 T5 腳本暴露共同形狀 |

## 明顯的坑

- **把三項當成三份互不相干的 temp／rename 實作。**Publish 是底座；Deliver 與 Effect 若各自複製一套，
  短寫、durable 與目錄發布語意很快就會分叉。
- **把 Effect resolve 拆成第四套 recover 功能。**retry／lost／abandon／import／adopt 都是在處理同一個
  unknown；分開會讓狀態字、key 與稽核紀錄各走各的。
- **Publish 只支援檔案，卻拿它承諾 event＋cursor 一起提交。**沒有 directory publish，兩者仍會裂開可見，
  cursor 仍可能超前。
- **key 範圍未定就承諾冪等。**同 key 究竟在 BASE、world 還是全域內唯一，會直接改變 Already／Conflict
  與 effect replay 的含義。
- **把 join／reconcile 急著收進 core，順手把 turn、tool、final 也帶進去。**它們還沒證明能脫離 agent
  語意；prompt、解析與停止政策明確不進 core。
- **三項做完就宣稱 agent loop 不再需要腳本。**driver／adapter 仍在；T5 原本就要用這些腳本找出下一批
  重複點，不能把「core 不該收」誤當成「工作已消失」。
