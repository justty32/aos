← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 沿革

原標題：`aos-agent：走一格、登記、取消登記（第 2 版，2026-09-24 定稿（astra 三輪審查＋第 4 輪補 3 條）；已實作）`

> 2026-09-23 草稿；2026-09-24 照 審查報告「定稿前必改」與使用者三件裁決改成第 2 輪；同日照 第 2 輪審查 E／D／B／C 改成第 3 輪；照 第 3 輪審查 D 節補 3 條（第 4 輪）後定稿。（審查與實作紀錄在 [rearch 筆記](../../notes/2026-09-23-rearch/README.md)）
> **已實作**（2026-09-24，T9）：`lib/aos_agent.py`＋`cli/aos-agent`，實作發現見 agent-impl-findings。
> 調度者裁決移到檔尾（09-24 試玩 r2 搬），已拍板的前提在 §14。
> 2026-09-24 fix-r4：命令列改 `--target DIR`、`AOS_K` 改名 `AOS_KERNEL_HOME`、`last` 換成 `listen`（§1.5）、`say --wait [秒]`、加 `pause`（§1.6）與兩種暫停都解的 `continue`、tick 上 flock 並寫下併發分析（§2.1）、think 改叫 `aos-llm call`。
