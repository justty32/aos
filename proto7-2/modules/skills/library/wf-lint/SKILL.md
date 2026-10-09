---
name: wf-lint
description: Check the wf/ documentation tree for broken links, broken anchors, oversize files, big lists that belong in data files, and leftover placeholders. Use after editing, moving, or splitting markdown files under wf/, or before committing doc changes. （檢查文檔、壞連結、錨點、佔位）
---

# wf-lint：檢查文檔

在 repo 根目錄（只掃 `wf/` 與 `.claude/commands/`，不要掃 `.`，worktree 副本會產生假 BROKEN）：

```sh
bash wf/tools/wf-lint.sh wf .claude/commands
```

- `BROKEN`（含 `BROKEN-ANCHOR`）一定要修到 0。
- `BIGLIST`：同質記錄表 >1 KB，抽成資料檔；`BIGLIST-LINKS` 只是提醒。
- 結果回報 BROKEN 清單與各項計數。
