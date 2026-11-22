# `knowledge/wf/skeletons/ideas.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/wf/skeletons/ideas.md`，跟到正本 commit `33835099a`（正本這頁最後一次改動）。這一庫本來就是中文，內容照抄正本，標題就是尋址。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

planning 的兩張表的骨架：想法表（要不要做）與 roadmap 表（會做，何時）。落點是工作區的 `wf/knowledge/ideas.json`；怎麼用在 `wf/workflows/planning.md`。

# holds

- 放：還在想要不要做的想法（`ideas`）、決定會做的事與它的時機和前提（`roadmap`）。
- 不放：spec／plan——各一檔放工作區的 `wf/knowledge/specs/`、`wf/knowledge/plans/`（`wf/layers.md#/skills 與 memory 分家`）。
- 不放：定下的決定——進工作區的 `wf/knowledge/decisions.json`。

# fields

## ideas

- idea: 想法（短名）
- summary: 一句話說它是什麼
- status: 狀態，只有三種：想想／會做→搬 roadmap／不做＋原因

## roadmap

- item: 事項
- when: 何時／順序
- premise: 前提

# rules

- 兩張表都寫成物件陣列，用 json 工具讀寫。
- 想法狀態變「會做」→ 搬進 `roadmap`；「不做」要寫原因。
- 更新狀態就改既有那筆，不另開一筆。
- `skeleton` 裡的路徑是工作區裡的路徑。

# skeleton

```json
{
 "_description": "planning 的想法表（`ideas`：要不要做）與 roadmap 表（`roadmap`：會做，何時）。想法狀態：想想／會做→搬 roadmap／不做＋原因。怎麼用見 `wf/workflows/planning.md`。",
 "ideas": [],
 "roadmap": []
}
```
