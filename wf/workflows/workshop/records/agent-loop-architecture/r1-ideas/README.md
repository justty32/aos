# R1 想法池
← [agent loop 的實作架構與基礎 `aos core` 功能](../README.md)

R1 四位各自發想的完整想法池。原本一檔，已按主題再拆一次：core 該補的原語一檔、agent loop 的形狀一檔、
還沒收攏的一檔。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [本場任務與 `aos core` 該收掉的原語](core-primitives.md) | 本場開題、T5 的做法、「投遞只有口頭約定」這個缺口；`aos core` 該收掉什麼的候選表（deliver／effect／publish／recover：簽名、誰提的、為什麼腳本自己做不好）；斷點續跑的硬邊界——本機可以原子，遠端付費不能假裝 exactly-once。 | 想知道 `aos core` 要補哪些原語、`unknown` 為什麼不能自動重跑 |
| [agent loop 的形狀](loop-shape.md) | agent loop 是磁碟上的耐久狀態機而不是新的 `exec` 模式（四份版面對齊成一張區域表）、一個完整循環的六個步驟、前一場四個選擇為什麼可以繼續懸著。 | 想知道 agent 在磁碟上長什麼樣、一輪怎麼跑、driver 與 `exec` 的分工 |
| [還沒收攏的](open-threads.md) | 還在生長的想法（CLI 名字與簽名未對齊、`publish` 要不要公開、capture 屬 core 還是 adapter、effect 包不包所有副作用、parallel join、耐久等級）、七題大家問出來的問題、八個明顯的坑。 | 想知道本輪還沒定下來的、以及最容易踩錯的地方 |
