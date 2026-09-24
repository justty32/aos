← [agent](README.md)｜[compact.md](compact.md)｜[spec 總導航](../README.md)

# 記憶壓縮續：申請（§5）與保證外（§6）

（09-24 第 4 隊；從 compact.md 搬出來，免得超過 8 KB）

## 5. 申請（模型只能寄申請）

走 [spec/team/mail.md〈申請〉](../team/mail.md)：`kind: "compact"`，登記在 `aos_team_requests.KINDS`（`aos_agent_compact:on_request`）。寄件人模板的 `may` 要有 `compact`（內建領隊、工人有）；模型用 task 包的 `compact_me` 工具寄（只縮自己，不收 `member`）。

| 欄位 | 意思 |
|---|---|
| `member`? | 縮誰的記憶；沒寫＝寄件人自己。只有 `human` 能替別人申請（`NotAllowed`）；名冊外＝`BadRecipient` |
| `keep_rounds`?、`max_tokens`? | 這次用的選項（範圍同 [compact.md §4](compact.md)）；沒寫＝照那個成員的 `info.compact` |
| `reason`? | 500 字內，記進事件 |

處理函式把申請投成那個成員家的 `compact-req/<申請 id>.json`（暫存檔＋link，不覆蓋＝同 id 已在就是投過了），回空的後續動作清單。
tick 看到 `compact-req/*.json` 裡 `compact-req/done/` 還沒有同名收據的就縮（多份一起算一次，選項以檔名排序最後一份有寫的為準），然後在 `done/` 寫同名收據（原申請的副本）；**原檔不搬**：郵差靠「原檔在不在」去重，沒有先查再投的窗口（astra M4）。**先縮再放收據**，崩在中間重跑是空轉＋放收據。
`compact-req/` 由郵差建檔、tick 搬走，跟 `input/` 一樣「一邊投、一邊收」；成員的工具碰不到（在家裡，信任資料）。


## 6. 保證外

- 人在 `say --wait`／`talk` 等回話時剛好被縮（很窄：記下長度之後、那句被收之前）：記憶變短，它們會說「記憶被改短了」而不是印回話；回話照樣在記憶裡，`listen --last` 看得到。
- **封存的輪模型只看得到摘要**：09-24 第一版封存只剩一行，真跑問「剛才 long.txt 幾行」模型答錯（40 答 21）；改成 8 KB 摘要＋「看不到了」那句之後的數字見報告。摘要以外的細節要回頭找原文是二波 T-recall（模型）或人 `history --archive --grep`。
- 手改記憶與縮同時：縮拿了 tick 鎖，但手改的人不一定拿（[tick.md §2.1](../aos-agent/tick.md) 末那句同樣適用）；讀到的 bytes 與讀驗時不同就 `HistoryChanged`、不寫。
- token 是粗估，比端點的真數字少 15～30%；上限要留餘裕。
