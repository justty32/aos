# agents — 生、問、收自己的子 agent，保留公開宣告的子帳。

`ask` 等待結束時（含失敗）與 `rm` 移除前，同步子帳到工具小格的 `observed/<名>/`；`say` 不同步。

子 stack 取自已登記的 children 紀錄；帳只透過各層 `interfaces.json` 的 `aos-observed.file` 找，保留相對路徑及觀測宣告，讓孫抄本也能再被抄走。同步不到的部分少算，不影響工具原本結果。呼叫端把這次抄本位置記進 `tool.child`。
