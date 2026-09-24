# agent 線規範第 4 輪：補 3 條並定稿

← [README](README.md)｜審查：[review-agent3-report.md](review-agent3-report.md)｜上一輪：[agent-round3-changes.md](agent-round3-changes.md)｜改後：[agent.md](../../spec/agent.md)（A）、[aos-agent.md](../../spec/aos-agent.md)（G）、[aos-llm-call.md](../../spec/aos-llm-call.md)（L）

2026-09-24。照第 3 輪審查 D 節的 3 條必改修正，另把 C-4 寫成一條實作提醒。三份標頭改成「第 2 版，2026-09-24 定稿（astra 三輪審查＋第 4 輪補 3 條）；程式未跟」。

## 3 條必改

1. **封存憑據的生命週期（C-1）：已落。**
   - 還被 `intake`／`consuming` 引用的 dst 不准清、不准搬；引用解除後才能清。A §4.1。
   - 「搬的規則」寫明它的前提：被引用中的 dst 沒人動。A §4.4。
   - 要放棄某一對（例如壞輸入），順序是：先 stop，在 state 裡把那一對拿掉，最後才動 dst。只刪 dst、不改 state，恢復時會回頭去搬原路徑上的新檔。A §4.4；G §8 第 3 步。
2. **start 的解析範圍（C-2）：已落。**
   - start 讀 `K/info.json` 時，只解驗 `done_exit`、`bad_after` 兩格。
   - 解的時候帶著原文件與位置、以 K 為中心，所以 `$ref:""` 和相對 `$at` 照常定位。
   - 其他格不解也不驗，start 那邊只需要這兩格用到的 `$env`。
   - 位置：G §11 第 2 步。
3. **讀驗錯的寫入承諾（C-3）：已落。**
   - 「什麼都不寫」只限 §2 第 1 步的起始讀驗。
   - 之後的讀驗錯（輸入檔、回音、K 帳本）、`HistoryChanged`、I/O 錯：已經寫下的紀錄照留，下次接著做。
   - 位置：G §8 第 3 步、§12。

## 順手

- **C-4**：六格 loader 那段加了實作提醒：挑欄位要帶著原文件與位置去解，不能先切出小物件，否則 `$ref:""` 和相對 `$at` 會找錯地方。L §3。

## 調度者裁決、要使用者拍的

- 本輪沒有新增調度者裁決。
- 要使用者拍的仍是上輪那三題：`fail` 狀態、將來 `pause` 的語意、agent 屬於哪個 kernel 記在哪。
- 審查列為可先放的四件，這輪不做：已結清封存檔的自動清理、日常 CLI、取消殘留工作的輸入快照、`.tmp` 殘檔管理。
