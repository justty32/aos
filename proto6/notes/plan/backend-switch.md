# 執行後端切換附註

← [本輪規劃](README.md)｜[S-404 留存](../../spec/scheduling/operations.md)

2026-09-29，依[使用者裁定](../2026-09-29-verdicts.md) 3：proto6 是**新寫**，不在 proto5 上就地演進，所以不從 proto5 的 worker 後端遷移過來。原本寫在 spec S-404 的遷移段移到這裡，只當成日後 proto6 內部若要切換執行後端或回退時的參考；不是 spec 條文，也沒有強制驗收。本檔不是收錄快照。

## 原 S-404 遷移段（原文）

切換舊worker後端與direct exec前停止新的派出、核對在途attempt；任何一件工作只有一個選定執行後端。舊版不能讀新帳本時，回退需要已驗證的資料轉換或一致快照，不能只切旗標。遷移後保留版本與對帳證據。

原驗收：Given 同一job已由新後端starting，When 要切回舊後端，Then 先收斂或明確標unknown，不向舊worker再投同一attempt；恢復後仍可查原owner與結果。
