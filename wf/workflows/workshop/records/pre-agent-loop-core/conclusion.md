# 總結論（三輪之後，等使用者拍板）

← [agent loop 之前要做哪些 core 小專案？](README.md)

> 本檔是三輪之後的總結論，**末尾的四件轉交建議還沒經使用者拍板**。

**T5 之前只做一件事**：`core/inst` 補原子投遞——handoff 加 `deliver(base, bytes)`，
CLI 是 `aos enqueue <folder> [file|-]`，只保證「完整且可見」，驗證與隔離仍在彙整那一步。
它不是新小專案。（3:1，反對票主張等第二個生產者出現。）

**T5 之前不做**：`core/eval`（主張者自己撤回）、`wait`／`func` 進 core（無人主張）、
`c/` 熱快取層分名（3:1 等量到成本）、中途死掉的洞（4:0 明確不做）、任何有限資源的佇列原語
（一致認為 T5 後、且第一版在 module）。

**模型上的收穫**（與「該做什麼」無關，但比它重要）：
1. 使用者的「cache」是**兩層**——`k/` 續體不可丟、`c/` 熱快取可丟且可重建。register／L1
   的直覺對，但不能拿來稱呼續體。
2. `wait` 與 `func` 是**同一個「續體推進一步」機制**的兩種薄前端（時間續體／序列續體）。
3. `fence` 是續體的對偶。有限資源在求值模型裡是 effect：`submit` → `await` → 重投。
4. `.aos/inst.tempd/` 已經是 submission queue，但**缺順序、容量、fence、doorbell** 四樣。

**轉交建議**（需使用者拍板，議會不自己改規格文件）：
- `deliver`／`aos enqueue` → 進 [`docs/roadmap.md`](../../../../../docs/roadmap.md)，插在 T5 之前。
- 「中途死掉的洞」4:0 明確不做 → 進 roadmap 第六節「明確不做的事」。
- `k/`／`c/` 兩層與命名 → 進 [`docs/aos-folder.md`](../../../../../docs/aos-folder.md)。
- 有限資源／`aos queue`／fence → 獨立成一份 idea（`wf/workflows/ideas/`），不要塞進本記錄。
