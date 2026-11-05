# 和既有紀錄、參考來源的關係

← [roadmap 導覽](README.md)｜[文件索引](../README.md)

> 這個檔裝的是：這份 roadmap 和 repo 內既有紀錄的關係表，以及從外部參考來源借了什麼、沒借什麼。

## 七、和既有紀錄的關係

| 檔案 | 關係 |
|---|---|
| [`wf/workflows/ideas/`](../../wf/workflows/ideas/README.md) | **模型真源**。本檔只排順序，不定義模型 |
| [`wf/SESSION-LOG.md`](../../wf/SESSION-LOG.md) | open 活狀態。llms／tooljson 是失敗作那條，落地方式就是本檔的 T5 |
| [`wf/WAIT_USER.md`](../../wf/WAIT_USER.md) | S2 的決策已被 [D5](decisions.md#d5) 改寫，並跟著 [D4](decisions.md#d4) 一起延後 |
| [`reference/PORTING.md`](../../reference/PORTING.md) | S1／S3／S4 已落地的部分仍然有效；S2／S5 停用，改由 T5 決定 |

## 八、參考來源借了什麼

- [`../agent-machine`](../../../agent-machine/START-HERE.md)：借的是**第五節那三條鐵律**與
  「先提交意圖 → 造成作用 → 驗證證據 → 才算完成」的次序感。**沒借**它的
  Function／Task／Receipt 詞彙與中央 store 架構——那套是為了 exactly-once 與 crash
  recovery 付的代價，aos 現在不付。
- [`../freepy`](../../../freepy/README.md)：借的是 `llmkit`／`tooljson` 的**格式與錯誤
  契約**（已經在 `reference/llmkit/` 有原文）。**沒借** `agentloop` 的 Round／Handle
  ／Controller——那是「常駐在記憶體裡的 loop」，正好是第二節診斷出來的那個病。
