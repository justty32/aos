# mailbox 工具包

讀自己的信箱。信箱在 `<home>/inbox/<來源>/`。一個來源一個資料夾。

| 工具 | 做什麼 |
|---|---|
| `inbox_sources(unread_only?)` | 看有哪些來源，各有幾封未讀與已讀。 |
| `inbox_list(source)` | 列出一個來源的未讀信。 |
| `inbox_read(source, id)` | 讀一封信，並搬進 `read/`。 |
| `inbox_read_all(source)` | 一次讀完一個來源。 |

一般信不會整封塞進 prompt。agent 只會看到「哪個來源有幾封」。模型再自己叫工具讀。

`user` 是例外。它的內容會直接進記憶，檔案也會當場搬進 `read/`。

同一封未讀信只通知一次。模型沒讀，它仍留在原處，但不會一直重叫 LLM。
