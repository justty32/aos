# proto6 — Linux agent 架構規劃

proto6 承接 2026-09-28 的 Linux 身分、資源管理與萬 agent 討論。**目前有 [規格](spec/README.md)、可跑的 Python POC [src/py](src/py/README.md)、[notes](notes/README.md)、可重跑隔離探針，以及早期原型 [proto/](proto/README.md)，還不是完整的 agent 產品。**

> **10-03 起新架構在 [proto7](../proto7/README.md)**（[核心 spec](../proto7/spec/core.md)）。本資料夾的 spec 與程式是到 10-03 為止的現況。

## 現行入口

- **[spec 入口](spec/README.md)**：唯一事實（第二十七批，2026-10-02）。行為與格式的正本是程式（`src/py/lib`）加測試（`src/py/tests`）加 schema 與範例，spec 只留程式看不出的原則。
- **[現行程式 src/py](src/py/README.md)**：`aos-tick`（照任務表跑一格，掛 hooks 與 tasks-blocked 模組）、`aos-daemon`（定期叫 `aos-exec`，掛控制、重讀設定、記住狀態、收屍／cgroup、訊息、帳號六個模組）、`aos-exec`、`aos-ctl`、`aos-mq`。
- **[plan](plan/README.md)**：各段做完、暫緩、還沒做的狀態；細部檔是施工紀錄。
- **[notes 入口](notes/README.md)**：裁定紀錄、背景與探針、歷史。最新裁定在 [verdicts 11](notes/verdicts/11-tick-as-unit.md) 篇末各批。

## 舊設計（歷史，不再是規格）

- 2026-10-02 之前的舊 spec（node／kernel／agent、LLM 排程、舊協議、CLI、驗收場景）：封存在 [notes/archive/spec-2026-10-02/](notes/archive/spec-2026-10-02/README.md)。
- 第二十批（09-30）「tick 核心四件＋系統級任務（`kind:"system"`）＋tick–daemon 通道」的結構：系統級任務 10-01 起全搬[暫緩區](spec/deferred/README.md)、通道被 daemon 控制模組取代；原文見 [第二十批方向](notes/verdicts/11-tick-as-unit.md)。
- 第十九批（09-30）三層架構（核心、標準配備、其他掛載）：已被第二十批取代，見 [第十九批方向](notes/verdicts/10-tick-minimal-core.md)。
- 09-28 的[三大概念](notes/concepts.md)：用語已兩度被取代。
- [proto5](../proto5/README.md)：上一代程式；proto6 從它原樣複製了 inst 解析、指示詞與 `aos-exec`，其餘不是現行。
