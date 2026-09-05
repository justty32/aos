> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# 指定資料夾的回合制演化模型 — 導航
← [ideas](../README.md)｜[WORKFLOWS](../../../WORKFLOWS.md)

aos 的核心心智模型：指定資料夾是被演化的世界，一份 `inst` 推進一回合。這個資料夾把原本一整檔的內容按職責分成四塊——模型本身、當初推導版面的脈絡、怎麼跑起來、以及決策狀態。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [model](model.md) | 核心理想（回合制而非 delta time）、`aos exec` 就是這個模型的實作、抽象 CPU 疊在 `inst` 之上 | 要理解回合制模型本身與「轉介到另一顆 CPU 就是 `exec`」為什麼成立 |
| [layout-handoff](layout-handoff.md) | 當初推導出來的命名標準、`.aos` 檔案版面、投遞／彙整／取件協定、`--loop` 兩種節奏、名詞與動詞（規格已抽到 `docs/aos-folder.md`，這裡留脈絡） | 想知道這些形狀是怎麼想出來的、為什麼不是別的樣子 |
| [usage-and-agent-loop](usage-and-agent-loop.md) | 最基礎的 aos 使用方式、agent loop 如何建立在回合模型上、與目前 aos 元件的關係、單回合流程 | 要看這個模型實際怎麼跑一回合、agent loop 怎麼疊上去 |
| [decided-and-open](decided-and-open.md) | 已經定下來的（不必再問）與開放問題（尚未拍板） | 要確認某個設計點是已定案還是還沒拍板 |
