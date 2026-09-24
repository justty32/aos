以 **HEAD a93bd89** 已提交版為準；工作樹乾淨，全程唯讀。

**A. 三條必改：3 已解、0 部分、0 沒解**

1. **封存憑據生命週期：已解。**  
   [agent.md:175](../../spec/agent/state.md) 禁止清理、搬走仍被 `intake`／`consuming` 引用的 dst；[agent.md:223](../../spec/agent/state.md) 與 [aos-agent.md:224](../../spec/aos-agent/idle.md) 補齊放棄配對的順序：stop、等行程消失、移除 state 配對，最後才動 dst。

   **重走 C-1：** consume A → 配對持久化 → rename A 到 dst → 清 `consuming` 前崩潰。此時：
   - **原反例照走**「人清 dst → 再投同名 B」：恢復仍會搬走 B；但「人清 dst」現在已明文違反契約。這次修正是補上操作前提，沒有增加偵測誤刪的機制。
   - **遵守新契約**：保留 dst、再投 B；恢復看到 dst 存在，只清舊 `consuming`，不碰 B（[aos-agent.md:48](../../spec/aos-agent/tick.md)）。
   - **人要提前清理**：先停妥、解除舊配對，再刪 dst、投 B；恢復已無舊配對，不會把 B 當成 A。B 留待之後符合條件的收取。

2. **start 解析範圍：已解。**  
   [aos-agent.md:252](../../spec/aos-agent/register.md) 限定只解驗 `done_exit`、`bad_after`，保留原文件、位置與 K 中心。先前 `cpus.w.pool` 使用 `WORK_POOL`、start shell 缺此變數的反例，不再因該無關欄位而失敗；兩格自身及其引用依賴仍須可解析。

3. **錯誤寫入承諾：已解。**  
   [aos-agent.md:296](../../spec/aos-agent/tick.md) 將「什麼都不寫」限於 §2 第一步；[aos-agent.md:224](../../spec/aos-agent/idle.md) 明訂後段輸入讀驗失敗保留 intake 與已搬檔案，與先記錄、再搬、再驗的順序一致。

**B. 第 4 輪未發現新增阻擋性矛盾**

- **人工修復與 kernel 停止契約相容。** 新規要求等行程消失，不把收到 rm 回音當成已停妥；符合 [aos-agent.md:286](../../spec/aos-agent/register.md) 與 [kernel.md:264](../../spec/kernel/echo.md) 的在跑工作收尾、丟棄回音語意。也沒有授權人工刪 cpu／kernel 回音，未衝撞 cpu 的 ack 契約。
- **局部解析與 kernel 整份解析不衝突。** 前者是 start 的相容性預檢，後者是 kernel 自己載入設定；兩格預設及判定仍符合 [kernel.md:107](../../spec/kernel/home.md)、[kernel.md:277](../../spec/kernel/echo.md)。
- **六格 loader 補記與三份契約一致。** [aos-llm-call.md:90](../../spec/aos-llm/request.md) 保留原文件及位置，沒有擴大載入範圍。
- **局部失敗文字可一致解讀。** [aos-agent.md:156](../../spec/aos-agent/collect.md) 的「不動任何東西」指該回音讀驗失敗後不繼續處理；§10 清理時 K 帳本讀不到仍依特例跳過。新版 §12 不要求回滾先前寫入，也不取消這些局部規則。

**C. 可以：在明訂的單一驅動者與封存憑據保護前提下，三份整組可作為「照它實作」的定稿。**