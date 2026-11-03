# 第 1 輪紀錄 — 結算

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：R2 →](../round-2/wrap-up.md)

最終答案以 [第 3 輪結算](../round-3/wrap-up.md) 為準。

## 4. 三個數字

- **① 自己手寫了幾次 temp＋rename**：四位口徑不一（實作份數、靜態呼叫點、commit 次數、含人工 `mv`），不能橫比；第 3 輪起固定取實作份數。
- **② 哪種「不知道做了沒」本機補不回來**：四位都報 **1 類**——provider 可能已接受非冪等 request，但 receipt／response／result 尚未在本機提交。
- **③ 有沒有冒出第二個要同時管的工作**：四位都報 **0 個**。都是一個 world、一條 logical job、串行 instruction，沒有 parallel、lane、join、scheduler 或第二個耐久工作；子行程、假 provider process、不同事故 world 都不算第二個 logical job。沒有建立並行 workload。

## 5. 仍然不知道的

仍開著的見 [第 3 輪〈6. 仍然不知道的〉](../round-3/wrap-up.md)。本輪沒有試真模型 CLI，也沒有網路，四路都用假模型。
