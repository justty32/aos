# R2 想法池（收攏成方向）
← [agent loop 的實作架構與基礎 `aos core` 功能](README.md)

這份想法池已再按主題拆進 [`r2-three-primitives/`](r2-three-primitives/README.md)。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [Publish／Deliver／Effect 三個功能家族](r2-three-primitives/three-primitives.md) | 合併後的功能清單、三者的依賴鏈、「只能先做三樣」的一致選擇。 | 想知道基礎 `aos core` 功能收窄成哪三項、先做哪一項 |
| [core 的邊界與還缺的一塊](r2-three-primitives/boundaries-and-gaps.md) | 不該進 `aos core` 的，以及平行 join、turn reconcile 這兩塊缺口。 | 想知道什麼刻意留在腳本與 adapter、下一個 core 候選是什麼 |
| [大家問出來的問題與明顯的坑](r2-three-primitives/questions-and-pitfalls.md) | 六題未解問題與七個明顯的坑。 | 想知道收攏後還沒回答的、以及最容易踩錯的地方 |
