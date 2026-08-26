# R1 想法池
← [四個懸而未決的設計選擇](README.md)

這份想法池已再按「哪一題」拆進 [`r1-per-choice-tradeoffs/`](r1-per-choice-tradeoffs/README.md)。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [一、`World` 抽象要不要收](r1-per-choice-tradeoffs/q1-world.md) | 收／不收 `World` 的「得到什麼／付出什麼／什麼時候會後悔／能不能反悔」對照表。 | 想知道 `World` 這層抽象現在收、之後補，各自的代價 |
| [二、`kernel.json` 要單層，還是分層合成](r1-per-choice-tradeoffs/q2-kernel-layering.md) | 單層／分層／第三條路三行對照表；`.runi` 只存 hash 為何不夠。 | 想知道 kernel 政策放哪一層、事故要不要能重播 |
| [三、子行程拓樸選 A、B，還是先固定磁碟 ABI](r1-per-choice-tradeoffs/q3-topology.md) | A／B／C 三行對照表與各自的主要代價。 | 想知道子行程拓樸三條路各換到什麼、反悔要不要搬資料 |
| [四、親緣綁路徑、綁 UUID，還是把身分／親緣／位置拆開](r1-per-choice-tradeoffs/q4-identity.md) | 綁路徑／綁 UUID／混合三行對照表。 | 想知道身分、親緣、位置該不該是同一件事 |
| [不專屬單題的部分](r1-per-choice-tradeoffs/open-threads.md) | 還在生長的想法、大家問出來的問題、明顯的坑。 | 想知道四題共同還沒解的、以及最容易踩錯的地方 |
