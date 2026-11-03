# 第 2 輪評分與意見

← [本檔索引](README.md)｜[本場索引](../README.md)｜[hackathon](../../../README.md)｜[← 上一份](round-1.md)｜[下一份 →](round-3.md)

總分算法同第 1 輪。最終判斷見 [第 3 輪](round-3.md)。

| 參賽者 | 總分 |
|---|---:|
| p1（Carmack persona） | 25 |
| p2（Armstrong persona） | 25 |
| p3（Cantrill persona） | 24 |
| p4（Thompson persona） | 25 |

## 路線判斷

- **no-replace 的需求已證完**：p3 的 v1 race「兩方 exit 0、final target=B」與 p4 的 shared-slot「968 次無聲覆蓋、1,000 件遺失」；雙 producer 第一次 race 還死在 `mkdir` TOCTOU。
- **第 1 輪不成立的兩條**：「Deliver 應薄薄疊在 Publish 上」不成立——queue target 可以在 receipt 前被 consumer 消費，aggregate 後同 key 會失憶；p4 的「三行 shell 已反證 Deliver」不成立——同命令重開把 effect 做了兩次。「選 (b)」仍成立。
- **致命坑**：無 query／idempotency 的遠端 effect 在 acceptance 與 committed result 之間被砍後，本機不可能自動還原真相，自動 exactly-once 判死。consumed-before-receipt 對「獨立 Deliver 自己發完成收據」致命，對 Deliver 本身不是：把 acknowledgment 交給 consumer／aggregate 即可。
- Linux-only `renameat2`、fsync 未做斷電測試、孤兒 temp、receipt 清理、schema 共用與 `.runi` 恢復都只是麻煩，沒有一個為控制平面創造需求。

## 可信度判斷

第一個數字要數「手寫 temp＋rename 幾次」，runtime transaction 次數不能當答案（p3 本輪的 `9`），只能支持 Publish 使用面。
