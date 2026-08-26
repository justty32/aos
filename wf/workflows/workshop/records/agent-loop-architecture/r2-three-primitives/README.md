# R2 想法池（收攏成方向）
← [agent loop 的實作架構與基礎 `aos core` 功能](../README.md)

R2 把 [R1](../r1-ideas/README.md) 的不同命名收成最少的功能組。原本一檔，已按主題再拆一次：
三個功能家族一檔、core 的邊界與缺口一檔、問題與坑一檔。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [Publish／Deliver／Effect 三個功能家族](three-primitives.md) | 合併後的功能清單（候選共同簽名、解決什麼、不做的話腳本要自己幹什麼、誰提的）、capture／invoke／effect 與 retry／lost／adopt 各自被併成什麼、三者的依賴鏈，以及「只能先做三樣」時四位完全一致的選擇與順序。 | 想知道基礎 `aos core` 功能收窄成哪三項、先做哪一項 |
| [core 的邊界與還缺的一塊](boundaries-and-gaps.md) | 不該進 `aos core` 的（prompt 組裝、response 解析、final／budget 政策、provider 對帳）；三項之外還缺的兩塊：平行工具 join 與 turn reconcile／barrier，外加 Publish 是否支援目錄這個條件式缺口。 | 想知道什麼刻意留在腳本與 adapter、下一個 core 候選是什麼 |
| [大家問出來的問題與明顯的坑](questions-and-pitfalls.md) | key 誰配、receipt 共同格式、Publish 是否公開、目錄 publish 的跨平台保證、Effect 包不包所有副作用、join／reconcile 能否通用化；以及七個明顯的坑。 | 想知道收攏後還沒回答的、以及最容易踩錯的地方 |
