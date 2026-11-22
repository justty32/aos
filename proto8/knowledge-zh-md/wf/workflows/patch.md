# `knowledge/wf/workflows/patch.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/wf/workflows/patch.md`，跟到正本 commit `33835099a`（正本這頁最後一次改動）。這一庫本來就是中文，內容照抄正本，標題就是尋址。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

獨立 patch 包：建立一包可被 agent 套用到原專案的獨立 patch，交給沒有聊天上下文的接手者（冷啟動 agent）套用與驗證。產物放工作區的 `wf/patches/<patch>/`，結構見 `#/outputs`。

# when

修改需跨 repo 交付、原專案沒有 git 或無法直接推送、或要交給冷啟動 agent 套用；使用者說「做一包 patch 給別的專案／別的 agent 套」。

# not_when

能在同一 repo 直接改碼、跑測試、commit → `wf/workflows/feature-dev.md`；只交付設計方案 → `wf/workflows/planning.md`；原專案有正常 PR 流程且會直接開 PR → 用該 repo 的既有流程。

# done_when

- 工作區的 `wf/patches/<patch>/` 底下 `PATCH.md`、`APPLY.md`、`session_log.md`、`src/`、`tests/` 都存在。
- `PATCH.md` 的必答表（`#/patch_md`）與 `APPLY.md` 的套用對照表已填滿。
- `APPLY.md` 指定的構建與功能驗證指令回傳 0。

# steps

前置條件：
- 已有 `wf/workflows/analysis.md` 產出的工作區 `wf/knowledge/analysis/<source>/` Level 1–2 以上分析，或等價的原專案結構理解。
- 已明確 patch 目標、影響範圍、驗證方式。

1. 確認上面的前置條件，建立工作區的 `wf/patches/<patch>/` 產物骨架。
2. 在 `PATCH.md` 填清目標、範圍、預期結果與分析依據。
3. 依 `#/src_strategy` 放入可套用檔案，並在 `tests/` 放驗證腳本或說明。
4. 寫完 `APPLY.md`（`#/apply_md`），依其中步驟實際套用並跑構建與功能驗證。

# outputs

## 0

- path: PATCH.md
- content: 目標、修改類型、影響範圍、分析依據

## 1

- path: APPLY.md
- content: 冷啟動 agent 套用操作手冊

## 2

- path: session_log.md
- content: 一句話操作日誌，建議上限 50 行

## 3

- path: src/
- content: 最終要套用的完整檔案，模擬原專案相對路徑

## 4

- path: tests/
- content: 驗證腳本或驗證說明

# patch_md

## 0

- item: 目標專案
- required: 名稱、路徑或 URL

## 1

- item: 修改類型
- required: 功能增強、bug 修正、重構或實驗

## 2

- item: 影響範圍
- required: 受影響的模組或檔案

## 3

- item: 預期結果
- required: 可量測或可觀察的變化

## 4

- item: 分析依據
- required: 主要參考的 analysis／research 文件

# src_strategy

- 新增檔案：放完整新檔案。
- 修改檔案：優先放修改後完整檔案，而不是 diff。
- 刪除檔案：在 `APPLY.md` 清楚列步驟。
- 配置變更：放修改後完整配置檔，或在 `APPLY.md` 說明局部修改。

# apply_md

`APPLY.md` 標準結構（**必須讓沒有聊天上下文的 agent 也能獨立完成**）：

```md
# APPLY.md — <Patch 名稱>

## 摘要
<一句話說明做了什麼、為什麼>

## 前置條件
- 目標專案路徑或 URL
- 依賴的分析文件
- 套用前需確認事項

## 套用步驟
1. 備份或確認 git 狀態。
2. 複製新增／修改檔案，提供對照表。
3. 列出需手動修改的部分。
4. 跑構建驗證。
5. 跑功能驗證。

## 回退方式
<如何還原>

## 已知限制
<平台、版本、未驗證項>
```

# handoff

- 套用後仍能在同一 repo 內繼續修改與驗證 → `wf/workflows/feature-dev.md`。
- 發現結構理解不足 → `wf/workflows/analysis.md`；只剩方案缺口 → `wf/workflows/planning.md`。
