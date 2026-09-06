# memory 工具包

讓 agent 整理對話，也能留下長期筆記。

記憶就是 `<home>/prompts.json`。

## 工具

| 工具 | 什麼時候用 |
|---|---|
| `memory_list(offset?, count?)` | 整理前先看序號、角色與短預覽。預設從 0 列 20 則。 |
| `memory_summarize_old(keep_recent?)` | 取出要摘要的舊原文。最近預設 20 則不動。 |
| `memory_replace_old(summary)` | 下一輪把剛才的舊原文換成摘要。 |
| `memory_forget(from, to)` | 明確忘掉一段。頭尾都包含。 |
| `note_save(title, text)` | 把以後還會用的資料存成 Markdown。 |
| `note_find(keyword?)` | 找筆記。沒給字就列檔名；有給字就列命中行。 |
| `note_read(name)` | 讀 `note_find` 找到的檔案。太長會截斷。 |
| `self_note(text)` | 加一句給以後自己的提醒。只能追加。 |

摘要分兩格。

第一格叫 `memory_summarize_old`。它只回舊原文，不改記憶。

下一格自己寫摘要，再叫 `memory_replace_old`。
舊原文會先放進 `<home>/memory/forgotten/`。

長期筆記在 `<home>/memory/notes/`。
自我提醒在 `<home>/memory/self-note.md`，每次會接進 system prompt。
它不會改掉使用者寫的人格。

## 自動整理

這包開著時，每個 idle 格會看一次記憶字數。

- 超過 40000 字：往自己的 `inbox/self/` 放一封提醒。一段過長期間只放一次。
- 超過 80000 字：先備份，再把最舊一半換成一則截斷標記。

門檻目前寫死，沒有設定。

## 坑

摘要走到一半沒叫第二段，待換範圍會留在 state。

筆記只是逐檔找字，沒有索引，也不會自動去重。

`forgotten/` 不會自動清理。資料久了會一直長。
