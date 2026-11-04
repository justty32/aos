# cpu／daemon／kernel 重寫：實作發現

← [proto5 README](../../README.md)｜[模組與 API](../../lib/README.md)

2026-09-23。以下記錄規範歧義、與既有底層的差異及保證邊界；本次未修改 `spec/*.md`。

1. **完整執行結果與舊 tuple 相容。** cpu.md §4.1 要三種目標都有真實 `timed_out`，但既有 `run_target()` 回 `(code, kind)`，agent 等呼叫者仍使用舊契約。本次新增 `run_target_full()`，回 `code`／`kind`／`timed_out`／`stopped`／`ms` 的物件；舊 `run_target()`、`run_inst()` 行為與解包方式保留。新 API 仍以 `kind="usage"` 表達底層用法錯，由 exec cpu 映射成 -32602／Usage；`kind="aos"` 留在 result。

2. **daemon 起不了孩子時沒有可登記的 pid。** 同步 aos-exec 把無執行權／找不到程式算 child 126／127；daemon.md 的 spawn 卻必須登記真孩子再送 go。本次新增 `spawn_target()`：Popen 起不來回 -32000／SpawnFailed，不造 pid、不寫 exit；不存在的非 `.json` 目標與資料夾缺 dir_target 仍為 -32602／Usage，不存在的 `.json` 則為 SpawnFailed。這個差異限於 daemon 的非同步入口。

3. **daemon 的 exit 檔失敗不改重拉判定。** 同步 aos-exec 在 exit 寫失敗時會把結果轉為 aos；daemon.md §4 的重拉條件則依孩子實際退出碼。本次在 `Spawned.finish()` 發現 exit 寫失敗時記 `WriteFailed` 日誌，孩子表 `last_exit` 與 restart 仍使用孩子原碼；因此正常退 0 不會因 exit 檔故障重拉。

4. **ack／stop 帶 id 的處理未明列。** cpu.md §3.3、§4.2 指定兩者為 notification，§4.3 只明列前綴與 method 不符的情況。本次把 `ack-`／`stop-` 檔內帶 id 也視為 -32600，不執行 ack 或 stop；合法 notification 的壞 params／method 只刪原單、不回音。

5. **同格同家可能需要多筆 ack。** kernel.md §1.3 的 `ack-<chain>-<seq>-<c>.json` 假設同格同顆最多一筆，卻可能在第 4 步補前格 ack X、第 6 步收 Y、第 10 步再 ack Y；第 4 步批量清舊 tick 回音也會超過一筆。固定名字會把不同 payload 的 EEXIST 當成已送，漏掉後一筆。本次在上述名字後加被 ack 的 request 名稱之 SHA-256 前 16 個十六進位字元，既可重放，也區分不同回音。

6. **更換 kernel 池必須交接舊、新兩顆。** kernel.md §6 第 2 步只寫 kill 新 info 選出的 c；若帳本釘死的 kcpu 是另一顆，舊鏈仍可能在改帳本時執行。本次先驗舊、新兩個孩子的 target，再依序 kill 舊、新並各等孩子表移除；需要兩筆 kill 時，boot-kill 名稱加 cpu 名區別。新 kcpu 若原本是工作 cpu，保留它的在途 req 給 collect 結清，ack_ticks 跳過該回音，避免把工作結果當舊 tick 刪掉。

7. **自動數字名從 0 開始。** kernel.md §2 說省略 name 用「數字名最大值加 1」，沒有指定完全沒有數字名時的起點。本次選 0；只把 ASCII 十進位名稱納入最大值計算。CLI 的 once 未給 name 時依 §6 使用自己的 request 檔名。

8. **interval_ms 是新增行程的預設。** kernel.md §1.1 要每格重讀 info，§1.2 又指定行程政策在 add 後不改。本次每格套用新的 tick_ms；info.interval_ms／timeout_ms 只影響之後的 add，既有行程保留帳本中的值，包含已排隊與正在跑的行程。

9. **接手舊孩子仰賴孤兒被收屍。** daemon.md §6.1 明訂以 `kill(pid, 0)` 等到 pid 消失，並假設 init 會收孤兒；殭屍也會讓這個檢查回「在」。某些容器 PID 1 不收孤兒，本次測試因此用獨立 driver 當 Linux subreaper，代替 init 收測試孤兒；產品仍照規範輪詢，不把殭屍自行視為已消失、不另設產品收養行為。

10. **boot 清 stops 不會消除已出貨的舊 stop。** kernel.md §6 要 boot 丟掉帳本裡上一代的 stops；但若 stop 已放進 cpu.requests、舊 cpu 在掃到前被 KILL，那份檔仍在，新 cpu 開機會收到而立即停。實作照規範只清帳本 stops，不由外人刪 cpu 家的檔案；這個跨代控制通知邊界仍存在。

11. **kernel.log 沒有與帳本共同交易。** kernel.md §3 第 10 步把 append log 放在出貨、寫帳本之後，實作亦照此順序。若已記下結果且送出 ack，卻在 append 前崩潰，回音可能已被刪、該格 log 也尚未落地；因此正常完成的格會記派工、完整回音與 bad_after 門檻，但不能保證每個崩潰中途的回音都有日誌。要加強此保證需要另訂持久日誌／出貨順序，本次未擅改。

12. **硬砍 kernel cpu 不保證 tick 子程式消失。** cpu.md §5.3 已把主人被 KILL 後工作仍存活列為保證外；aos-exec 的工作使用新的 session／process group，tick 也一樣。daemon 階梯最後 KILL cpu 那組時，已另組的 tick 仍可能存活，因此孩子表移除本身在這個硬砍邊界下不保證 tick 已死；本次未加入 kill-tree，也不宣稱 boot 已解決這個保證外情況。
