# 骨架加 md 原型樣本：知識庫三頁改成「json 只留骨架、文章搬進 md」的實際樣子（只給人看，不是正式知識庫）

← [10-骨架加md-原型](../10-骨架加md-原型.md)

三頁照原文搬（英文就英文，不翻、不改寫）：`aos/me.json`（文章多）、`aos/cli/agent.json`（程式碼區塊多）、`aos/tools/glob.json`（短）。來源 commit `fad6bef74`。

| 夾 | 指向 md 的寫法 | 粒度 |
|---|---|---|
| [A-字串-每值一檔](A-字串-每值一檔/aos/me.json) | `"stack": "me/stack.md"` | 一個值一份 md |
| [B-ref-每值一檔](B-ref-每值一檔/aos/me.json) | `"stack": {"$ref": "me/stack.md"}` | 一個值一份 md |
| [C-字串加標記-整頁一檔](C-字串加標記-整頁一檔/aos/me.json) | `"stack": "me.md#/stack"`，md 裡每段前一行 `<!-- #/stack -->` | 一頁一份 md |

`$ref` 指到別份 json 的（`me.json` 的 `self_tools` 等）照原樣不動。產生腳本與查 md 的小腳本在 `~/.aos/scratch/top-1121-mdjson/skel/`（`skel.py`、`mdget.py`），不進 repo。
