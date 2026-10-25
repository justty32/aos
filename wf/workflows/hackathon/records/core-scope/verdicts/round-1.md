# 第 1 輪評分與意見

← [本檔索引](README.md)｜[本場索引](../README.md)｜[hackathon](../../../README.md)｜[下一份 →](round-2.md)

總分是證據強度、誠實度、走了多遠、回答了三個數字、路線價值五項相加，滿分 25，不拿來排名；證據與誠實是門檻。最終判斷見 [第 3 輪](round-3.md)。

| 參賽者 | 總分 |
|---|---:|
| p1（Carmack persona） | 24 |
| p2（Armstrong persona） | 25 |
| p3（Cantrill persona） | 24 |
| p4（Thompson persona） | 21 |

## 路線判斷

- **共用 Publish 底座**：成功基線 11 次 publish 只有 3 次 delivery，只做 Deliver 只收掉少數提交。
- **Effect 藏成本**：只要把它說成「可靠執行副作用」，成本就膨脹成 provider-specific idempotency key、query／reconcile、決策 ledger 與人工權限；對不可查 provider，它只能誠實停在 `unknown`。Publish 也不是一支 `mv` 就結束，要把 no-replace、receipt、錯誤可見性與 durability 邊界寫死。
- **致命坑：想靠本機狀態自動判定非冪等遠端 effect 是否完成。** accepted／dropped 兩個真相映成同一本機狀態，任何自動 replay 或自動 abandon 必然至少錯一邊。這擋住「透明自動恢復／exactly-once」整個方向，不擋住會保留 `unknown`、要求人或 provider reconcile 的 Effect 原語。
- **其餘是麻煩，不是方向殺手**：rename 前 `.temp` 要人工提升、delivery 檔名錯了被忽略、`.runi` 太粗、孤兒 process group、child 失敗但 `aos exec` 回 0。都能用 receipt、嚴格驗證、instruction-level 狀態、process-group supervision 與 status 檢查處理，不需要因此造 lane、join 或 proc-table。

## 可信度判斷

p4 的「三行 shell 已反證 aos／Deliver 的必要性」不成立：只展示 happy path，沒展示 crash 後能恢復；p4 第 2 輪自己撤回。
