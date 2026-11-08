---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T11:32:06+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# 準備工作完成：資料、題庫盤點、量具都就緒，開始第一輪

## 做了什麼
1. 環境：兩個 submodule 已下載，pytest 224 全綠；identity 基線 training/evaluation 都 0/400。
2. 題庫盤點：training 400 題分 14 類。整張圖一步就解的（幾何變換、換色、放大平鋪）只有 32 題；最大兩類「加筆填色」123 題、「同尺寸綜合」63 題很雜。用 re-arc 現成 DSL 解答行數當難易代理：易 106／中 145／難 149。re-arc 覆蓋全部 400 題（因此 training 分數有洩漏風險，成績以 evaluation 為準）。
3. 量具：任何語言的外部程式可直接跑整份評測（eval --external，檔案進檔案出，附 sh、C 範例）；每題嘗試軌跡（試了哪些程式、訓練範例驗證結果、選哪個、耗時、推理文字）存成 JSONL 供蒸餾；arcagi compare 做多方法逐題對照、新增解出／退步、按題型分組；附 Python 求解器範本。
4. wf 工作流已參考 aos 與 ~/repo/workflows 更新（dispatch、team-model、experiments、交接書模板）。
## 產出（檔案路徑 / commit / 分支）
- 盤點：/home/lorkhan/repo/arcagi/docs/inventory/training.html（commit 4af1160）
- 量具：docs/solvers.md、docs/traces.md（commit 677b966）
- 交棒總表：/home/lorkhan/repo/arcagi/notes/rounds/README.md
## 沒做到、或證據不足的部分
題型分類是自動粗分，「加筆」「綜合」兩大類還需細分。
## 需要對方或使用者決定的事
無。接著開第一輪，方向問題代定後在收輪 PROGRESS 列出。
