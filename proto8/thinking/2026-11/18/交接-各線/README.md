# 11-18 關機前各線交接

← [18 日索引](../README.md)｜主交接 [wf/HANDOFF.md](../../../../../wf/HANDOFF.md)

使用者 17:00 關機，五條線被打斷。公司機工作樹上沒交的改動全部存成一個補丁，換機器（家機）也接得上：

```
git pull
git apply --index "proto8/thinking/2026-11/18/交接-各線/工作樹未交改動-1118.patch"
```

- 補丁是對它前一筆 commit（只含交接檔）的 `git diff --binary`，含新增、刪除、改名，五條線混在一起；`--index` 會一併放進暫存區。套不上就先 `git stash` 自己的改動、確認 HEAD 是含這份補丁的那筆或之後只動過交接檔。
- **補丁裡的程式是半成品**：有的檔改到一半（例如當時 `proto8/py/aos/agentlib/cli_a2a.py` 編不過），測試沒跑完。先讀各線的交接檔分清楚哪些檔是誰的，在 WSL 暫存複本跑過測試再分件交，不要整包 commit。
- 公司機若先接手：工作樹原樣還在，不用套補丁。兩台都動過就會衝突——只在一台接。
- 各線交接：同夾 `<線名>.md`（關機前寫出來的才有；沒有的看 HANDOFF 那條的摘要）。

## 家機 11-18 晚已分件

- 總補丁已套、分件：rm-treestart-1118（`93e0acc0c`）、cooldown-1118（`2b4320644`）已交；前面一筆修補 `dc4218e8a` 讓 main 裝得起來（aos-kit 先拿回、entries.json 拿掉 aos-tree-start、codemap_lib 檔頭判讀）。
- kit-merge-1118、eca-pi-bc-1118、eca-lab-1118 程式或文件寫到一半、沒交：改動留在家機工作樹，另各存一份 `<線名>-未交.patch`（同夾，對 `2b4320644` 之後的 main，`git apply` 套得上；kit-merge 那份含 aos-kit 19 檔的刪除）。各剩什麼見 [wf/HANDOFF.md](../../../../../wf/HANDOFF.md) 與各線交接檔。
- 總補丁 `工作樹未交改動-1118.patch` 已用完、留底；別再整份套（會跟已交的撞）。
