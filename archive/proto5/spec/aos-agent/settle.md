← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 7. 結清

全部 `done` 齊了、都 ack 了，才做。記憶的寫法固定是「**前 `base_len` 則＋這批的訊息**」整份重寫（`.tmp` 再 rename），
所以崩在寫記憶之後、寫 state 之前，下次再結清一次寫出來的是同一份，不會接兩次。

先檢查記憶跟當批對得上，不對＝`HistoryChanged`、退 1、不動（人改過記憶，要人處理）：
記憶長度必須是 `base_len`（還沒接），或是 `base_len`＋這批要接的則數、而且尾巴逐則等於這批要接的訊息（上次接過、崩在寫 state 之前）；
其他長度（例如人在途中加了訊息）一律 `HistoryChanged`，不悄悄截掉。act 另外要求第 `base_len` 則（從 1 算）是 assistant、它的 `tool_calls` 的 id 依序等於 `calls[].tool_call_id`。
**檢查的範圍就這些**：前 `base_len` 則被人等長改寫不偵測、也不擋——寫回用的前綴就是這次讀到的那份，人的改動照樣保留。

| 當批 | 寫記憶 | 然後**一次寫 state** |
|---|---|---|
| think、`{"ok": true}` | 前 L 則＋`work/N.out` 那則 message | `state`＝有非空 `tool_calls` → `act`，否則 `idle`；`errors: 0`；`batch: null`；`sweep` 加這批 |
| think、`count: true` | 不動 | `errors`＋1（到 3 見 §9）；`state` 留 `think`；`batch: null`；`sweep` 加這批。stderr 一行 `aos-agent: engine: <fail>` |
| think、`count: false` | 不動 | `errors` 不動；`state` 留 `think`（下一格重問）；`batch: null`；`sweep` 加這批 |
| act | 前 L 則＋每筆 call 一則 `{"role": "tool", "tool_call_id": …, "content": done.content}`（照 `calls` 順序） | `state: think`；`batch: null`；`sweep` 加這批有名字的 |

連敗計數跟「這批結清了」在同一次寫裡，所以不會漏算、也不會重算。成功（act 結清、或 think 問到了）退 **103**（09-24 tick-gap：下一步馬上能做，kernel 馬上再排）；問模型失敗退 0（等 `interval_ms` 當退避）。
（09-24 fix-r5 補）think `{"ok": true}` 那次寫完 state 之後，家裡有 `resumed`（§1.4 `continue` 放的）就刪掉（ENOENT＝已刪）：`status` 從這一刻起才把舊錯標「已恢復」。崩在寫 state 之後、刪之前＝`resumed` 留著，下一次成功再刪（只是多標一陣子「等下一次成功」）。
同一則 assistant 叫多個工具，只保證接回的順序，**不保證執行順序**（可能派到不同 cpu 平行跑）。
