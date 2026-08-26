# aos 工具協作 — 把這場研討會搬到 aos 上

← [本檔索引](README.md)｜[本場索引](../README.md)｜[workshop](../../../README.md)

四位替本場 workshop 自己畫出的 world 版面與四個回合，以及立即卡住的 Deliver 與另外三個實際洞。

---

## 把這場研討會搬到 aos 上

四位身在這個 workshop 裡，畫出的資料夾名稱不同但回合相同：

```text
topic-world/
├─ briefs/R1/                    # 議題與四份角色任務
├─ rounds/R1/responses/<role>.md # 或 raw/R1/<role>.md
├─ sessions.json                 # agent session 只是綁定／快取
└─ record.md                     # 書記最後寫的紀錄
```

1. 主持人把四份參與者工作原子投遞成同一輪；四個 coding agent 可平行執行。
2. 每位結果先完整落到自己 `<role>.md`，連同 exit／完成狀態提交。
3. join 確認四份都完成後，再 Deliver 一筆書記 instruction。
4. 書記只讀 brief＋raw responses，寫 `record.md`；下一輪若續場，session id 只作快取提示。

**四位獨立地都說第一個立即卡點是 Deliver 尚未實作。**其後還有三個實際洞：

- pi／Codex 等 coding agent 的 JSONL、RPC、final event、session id 格式是否穩定，四位都不確定；
- `-o`／stdout capture 不是 aos 的原子發布；遠端可能已完成／付費，本機 raw 尚未落盤，重跑有
  unknown 視窗（工程師、架構師、研究人員、開發者都提到）；
- exit、response file、session 綁定與「這一位真的完成」目前沒有一個共同 commit，join 仍要外部
  driver 判斷。

追問輪刪掉 adapter 的**內容解析**，沒有刪掉行程 adapter 的**傳輸責任**：啟動 agent、捕捉事件、
原子保存 raw、記 exit／unknown，仍要有人做。tool-call Deliver 解的是 agent 如何合法投 instruction，
不是主機如何保證一支遠端 coding agent 的 Markdown response 已落盤。
