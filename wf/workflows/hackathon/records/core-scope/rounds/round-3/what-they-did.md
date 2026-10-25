# 第 3 輪紀錄 — 各人這輪改了什麼

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R2](../round-2/what-they-did.md)

## 1. 各人這輪改了什麼

四位不再重做整條 loop，只攻上輪沒釘死的窗口。

- **Carmack persona**：Effect 的 response 已 commit／done 未 commit、decision 已 commit／done 未 commit 兩窗，同一 resolve 連跑兩次。
- **Armstrong persona**：consumer acknowledgment——completion ack 由 aggregate consumer 在 `claim → aggregate publish → delete delivery → ack commit` 中留下，`aos exec` 前過 ack gate；四刀加一個不合作 consumer 反例。
- **Cantrill persona**：第一個數字固定取實作份數；以 `ctypes` 呼叫現有 `libaos_inst` C ABI，逐案對照私有 validator 與 canonical parser。
- **Thompson persona**：publish 成功但 receipt 未回、consumer 已取走但 ack 未寫兩窗；只回 `Already`／`Unknown`／`Conflict` 的窄 Deliver 分類器。
