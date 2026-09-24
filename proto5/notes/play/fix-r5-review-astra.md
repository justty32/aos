主流程大致完成，但仍有六個真問題；目前不能算八條四邊全部對齊。

全程未改檔。完整測試需要建立暫存家，唯讀沙箱下未執行；改用讀碼、記憶體 mock 驗證，以及只載入測試清單。確認共 **32 個測試檔、1133 條**，其中 r5 新增 22＋11 條。

**必修**

1. **第 2／7 條：成功後仍可能卡著「等下一次成功」。**  
   位置：`proto5/lib/aos_agent_pause.py:48`、`:55`；`aos_agent_batch.py:196`。  
   `continue` 先開門，最後才放 `resumed`，期間沒有同步保護。如果程序在中間停頓，tick 已重試成功、刪完標記，`continue` 恢復執行後又把標記放回去；agent 已 idle，沒有下一輪就一直顯示等待成功。記憶體模擬已重現這個順序，`--all` 也共用此流程。  
   **建議：**讓解除暫停與成功結清使用同一套同步機制，或由 tick 統一管理恢復標記；同步補規範及交錯執行測試。目前測試只有依序 continue→tick。

2. **第 2 條：`-v`／`--json` 拿不到承諾的完整舊錯。**  
   位置：`proto5/lib/aos_agent_status.py:135`。  
   收集資料時已用 `lines[-1][:300]` 截斷，後面 verbose 印的「原文」也只剩 300 字。mock 中 372 字的錯誤尾巴確實消失；長路徑還可能讓舊 `touch … 繼續` 被截斷，無法完整改寫。  
   **建議：**收集時保留完整原文，只在一般文字輸出縮短。`test_agent_fix_r5.py:113` 應加超過 300 字、經過完整收集與輸出的案例。

3. **第 3 條：有 `tool_calls` 不一定會警告。**  
   位置：`proto5/lib/aos_agent_listen.py:76`。  
   規範明列「印的那則帶 `tool_calls`」本身就是警告條件，但 `busy` 判斷漏了這項。當 state 是 idle、沒有 batch／新輸入，而最後一則仍帶工具呼叫時，直接略過警告。mock 已確認 stderr 為空；現有測試先設 `state: act`，遮住了缺漏。  
   **建議：**把 `message.get('tool_calls')` 納入判斷，另測 idle／重建 state 的情況。

4. **第 5 條：空模型清單被誤報成「清單裡有模型」。**  
   位置：`proto5/lib/aos_kernel_check.py:83`。  
   回覆 `{"data":[]}` 時，`if listed` 為假，最後竟回 `ok：模型清單裡有 m`。這與規範「清單讀得懂、找不到指定模型就 warn」不符，mock 已重現。  
   **建議：**區分「有效但空的清單」與「格式讀不懂」，有效清單只要缺指定模型就 warn；補空清單測試。

5. **第 5 條：HTTP 回覆中途斷掉會直接噴例外。**  
   位置：`proto5/lib/aos_kernel_check.py:66`、`:88`。  
   `response.read()` 可拋 `http.client.IncompleteRead`，目前這裡與 CLI 外層都沒接住。mock 已確認例外外漏；因此 `check --probe` 不會正常列出 bad、印總結並繼續檢查其他模型。  
   **建議：**接住相應 HTTP 協定例外，轉成 bad，補「宣告長度但內容沒傳完」的測試。

6. **第 8 條：README 新指引仍會讓人找不到工具錯誤。**  
   位置：`proto5/README.md:147`；`proto5/lib/aos_agent_listen.py:175`。  
   README 說工具的 `exit 126／127` 可用 `listen --follow` 看；但 follow 只印 `role: assistant`，不印存放錯誤的 `role: tool`。模型未轉述時，使用者看不到那段原因。  
   **建議：**刪掉這裡的 `listen --follow`，保留查看 `prompts/history.json`；「不在 agent.err」這半句已修對。

**可以之後**

- `test_kernel_fix_r5.py:89` 名稱宣稱驗證「隱藏金鑰」，實際只是連不上空 port；錯誤本來就不含金鑰，尚未驗到遮蔽功能。可補錯誤文字真的含金鑰的 mock。
- `proto5/lib/README.md:35`、`:38` 的 listen／say 摘要仍偏舊，未完整提及本輪新增的時間、stdout 提醒與 kernel／bad 提前退出。

額外文件檢查：三份動到的規範資料夾 `agent`、`aos-agent`、`kernel`，README 標頭版本／日期及 `history.md` 都已補 fix-r5；測試總數核對正確，`code-map.md` 也已同步主要新增職責。

**八條四邊對齊結果**

| 條目 | 結果與理由 |
|---|---|
| 1 | **對齊**：恢復中、連敗重試，以及 daemon 停止後 cpu 不再顯示 running，程式與測試都有對應。 |
| 2 | **沒對齊**：恢復標記有競態；verbose／JSON 的完整舊錯仍被截斷。 |
| 3 | **沒對齊**：時間與一般處理中提示已做，但漏掉 `tool_calls` 本身的獨立判斷。 |
| 4 | **對齊**：同家正常登記退 0；discard、bad、同名別家維持退 1，皆有測試。 |
| 5 | **沒對齊**：主要請求流程與總結符合規範，空清單及 HTTP 中斷仍有漏洞。 |
| 6 | **對齊**：投話提醒、等待前健康檢查與指定情況退 101，已有相應實作及測試。 |
| 7 | **沒對齊**：帳本遍歷、逐家清單及 ls 標記已做，但共用第 2 條的恢復標記競態。 |
| 8 | **沒對齊**：boot、家別提示、init 保護及 cpu 提醒已做；工具錯誤的 README 指引仍不符實作。 |