# communication 工具包

這包讓 agent 用名字寄信給別的 agent。收信還是用 `mailbox` 包。

## 工具

| 工具 | 什麼時候用 | 參數 | 回傳 |
|---|---|---|---|
| `mail_send` | 寄一封新信。 | `to`、`content` | 成功、收件人、信件 id。 |
| `mail_reply` | 回覆剛讀過的信。 | `source`、`id`、`content` | 跟寄信一樣，另有 `reply_to`。 |
| `mail_broadcast` | 同一句寄給多人。 | `content`；`to` 可省略。 | 成功名單與失敗名單。 |
| `mail_who` | 不確定名字時先查。 | `alive_only` 可省略。 | 名字、關係、路徑、資料夾在不在。 |
| `mail_wait` | 寄完要等回信。 | `id`；`note` 可省略。 | 回等待 id，agent 睡到回信。 |

`mail_broadcast` 沒給 `to` 時，只寄給父與直接小孩。

`mail_wait` 走共用 pending。`reply_to` 對上時，回信內容直接接回對話。

## 設定

在 `tools.json` 同時開收信與寄信：

```json
{"packs": ["mailbox", "communication"], "tools": []}
```

通訊錄在 `<home>/contacts.json`。最簡單的寫法：

```json
{"B": "/tmp/world-B"}
```

值是對方的世界資料夾，不是 home。相對路徑從自己的世界資料夾算。

有設 `AOS_USER_DIR` 時，`user` 會出現在通訊錄。agent 每次對外回話，也會寄一份到使用者的信箱。

## 坑

- 寄信只認通訊錄名字。名字不存在會直接回錯誤。
- 信寄出後，要等對方下一格才會看見。
- `mail_reply` 的 `source` 與 `id` 要照 `inbox_read` 的結果填。
- 通訊錄名字、相對路徑與絕對路徑都由 `Ctx` 解析。
- `mail_wait` 預設 120 格逾時；失敗會直接回聊天錯誤。
- 只認直接父子。孫子不會自動出現在通訊錄。
