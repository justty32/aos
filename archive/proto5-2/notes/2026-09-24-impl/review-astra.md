總評：**池表、宣告式 scale、drain、通知與排程主路徑大致落地，但目前不能認定 boot 交接與故障恢復安全。**最嚴重的是 boot 可能覆蓋舊 tick 的最後提交，以及把仍在 `draining` 的 kernel cpu 當成已退出。以下列出 **7 項必修、3 項建議**；已記錄的決策偏離沒有當成新增實作錯誤。本次全程唯讀，做了原始碼／測試核對及不寫檔的記憶體 mock；沒有重跑會建立檔案的整套測試。

以下程式位置相對於 `proto5-2/lib/`，規範位置相對於 `proto5-2/spec/`。

**P1｜必修：boot 用停機前的帳本快照覆蓋舊 tick 最後提交**

- **位置**：`aos_kernel_boot.py:58、80、86–102`。
- **規範**：`handoff.md §1` 要求先完成交接，再寫新鏈，並保留 `procs／ready／delayed／busy／on／出貨箱`。
- **問題與時序**：boot 在送縮池單以前讀 `old`，等待期間舊 tick 仍可完成派工、收回音、刪 syscall、送 ack。等待結束後卻直接使用先前的 `old`，沒有重新讀帳本。
  - 舊 tick 新登記且已刪原單的工作會從帳本消失。
  - 舊 tick 已結清、且 cpu 已消費 ack 的工作可能被恢復為 `busy`；下一格看到原單與回音都不存在，就再次投遞，造成重跑。
- **驗證**：記憶體 mock 在縮池呼叫期間模擬舊 tick 提交新行程；boot 完成後該行程消失，帳本只讀了一次。即使修好 P2，這個問題仍存在。
- **建議改法**：交接前的快照只用於找舊 kernel 池；確認舊主人退出後，重新讀取帳本，再修改鏈與重宣告欄位。
- **測試缺口**：`test_kernel_boot2.py:71` 沒有讓舊 tick 在 boot 等待期間提交資料；應以 barrier 固定此窗口。

**P2｜必修：boot 漏看 `draining`，舊 kernel cpu 尚活著就開新鏈**

- **位置**：`aos_kernel_boot.py:32–41、80`；`aos_daemon_pools.py:109–115`。
- **規範矛盾**：`handoff.md §1.2` 字面只列 `running 0、killing 0`，但同段要求「沒有任何一格在跑」；`daemon-home.md §4` 又明定移出成員、仍在收的孩子算 `draining`。
- **問題與時序**：kernel 池縮零後，真 daemon 可發布：
  `count=0, running=0, killing=0, draining=1`。
  `_gone_or_idle()` 此時回 `True`，boot 便寫新帳本。
  - 同 daemon：舊 tick 仍可能把舊鏈帳本寫回，讓新鏈斷掉。
  - kernel 池搬到另一個 daemon：新 daemon 可以直接拉新 cpu，形成兩格 tick 同時執行。
  此處不需要硬砍，因此不屬於規範排除的 kill-tree 情況。
- **驗證**：直接以此摘要呼叫 `_gone_or_idle()`，結果為 `True`。
- **建議改法**：boot 至少也要求 `count=0、draining=0`；同步修正 `handoff.md` 與 `proto5-diffs.md` 的等待條件。
- **測試缺口**：`_kernel_fake.py:140–143` 用 `running=1、draining=1` 模擬收尾，掩蓋了問題。現有真跑交接測試沒有固定停在這個窗口。

**P3｜必修：舊 scale 回音會取消 boot 要求的重新宣告**

- **位置**：`aos_kernel_boot.py:93–96`；`aos_kernel_pools.py:144–155`。
- **規範**：`handoff.md §1.3`、`kernel-pools.md §2.3` 明定 boot 後「整份重送」，即使集合相同。
- **問題與時序**：boot 保留舊 `pending` 並設 `redeclare=True`；第一格收舊回音時：
  - 舊成功回音無條件清掉 `redeclare`。當集合已相同，就完全不送新鏈宣告。
  - 舊 `TooMany／NameTaken` 回音也清掉它，並留下禁止自動重試的 `error`；即使 boot 前已修復原因，這次 boot 仍不重新嘗試。
- **驗證**：分別餵入舊成功與 `TooMany` 回音，兩種情況的新 `sends` 都是空的。
- **建議改法**：區分「boot 要求尚未完成的重宣告」與普通重試旗標；只有對應新鏈宣告的成功回音才能清除前者。
- **測試缺口**：已有「boot 丟掉未送出的單 → Interrupted」測試，缺少「舊成功／舊錯誤回音已存在 → boot」的組合。

**P4｜必修：初次宣告撞名後，改 `dpool` 仍永久卡在別人的池**

- **位置**：`aos_kernel_pools.py:95–118、192–205`。
- **規範**：`protocol.md §4` 對 `NameTaken` 的處理指示是「人改 `dpool`」。
- **重現**：
  1. K 初次宣告 `taken`，但該池屬於另一個 owner，收到 `NameTaken`，K 的 `sent` 仍為空。
  2. 使用者把 info 改成未佔用的 `free-name`。
  3. kernel 把它當搬池，先向 `taken` 送縮零，再收到 `NameTaken`。
  4. `retire()` 等 `taken/summary.json` 消失；那是別人的正常池，可能永遠不消失，因此永遠不宣告 `free-name`。
- **驗證**：記憶體 mock 跑過上述轉移，位置一直停在 `taken`，沒有 pending 或後續重試。
- **建議改法**：明確區分「曾成功取得的池」與「被拒絕、從未取得的池」。後者確認無 busy、无未決宣告且 owner 不同時，應能直接放棄舊位置，不能要求刪掉別人的池。
- **測試缺口**：現有 `NameTaken` 測試以假錯誤注入已成功宣告的池，之後只改 count；沒測真正 owner 衝突及改名復原。

**P5｜必修：摘要寫入／刪池失敗後丟掉重試狀態，無法自行收斂**

- **位置**：`aos_daemon_pools.py:190–195、207–218`；`aos_daemon_loop.py:293–301`。
- **規範**：`protocol.md §1` 要求收完孩子後刪池；`kernel-pools.md §2.5` 必須等摘要消失才能搬池。
- **問題**：
  - `write_summary()` 寫失敗仍把 `changed=False`。之後沒有其他事件，就永久保留舊摘要。
  - `publish()` 先從記憶體刪池，再呼叫會吞掉錯誤的 `remove_pool()`。若刪 `summary.json` 暫時失敗，即使權限／I/O 已恢復，也不再嘗試；kernel 搬池或 halt 可永久等待。
- **驗證**：注入摘要寫入失敗後，`changed` 為 `False`；模擬刪除未完成，連續兩圈 publish 也只呼叫一次刪除。
- **建議改法**：成功後才清 dirty／移除記憶體紀錄；失敗保留待發布、待刪除狀態並重試。
- **測試缺口**：`test_daemon.py:448` 只驗成功時的刪除順序，沒有「第一次失敗、恢復後收斂」。

**P6｜必修：讀壞摘要等同摘要不存在，會錯誤放行交接**

- **位置**：`aos_daemon.py:62–74`；`aos_kernel_pools.py:199`；`aos_kernel_boot.py:33–35`。
- **規範**：`protocol.md §1` 用的是「`summary.json` 不在＝池已完全拿掉」，不是「讀不到＝已拿掉」。
- **問題與時序**：`_peek()` 把讀取失敗、壞 JSON、非物件都轉成 `None`。工作池縮零已獲確認、舊孩子仍在 draining 時，只要摘要讀取失敗，`retire()` 就能切到新 daemon；兩邊可能同時持有同一批 cpu 家。boot 與 halt 也會誤判完成。
- **建議改法**：供交接使用的讀取介面區分「確定不存在」「有效摘要」「未知／讀取失敗」。只有確定不存在才放行；未知應等待或報錯。顯示用的寬鬆讀取可另保留。
- **測試缺口**：缺少摘要存在但無法讀取時，確認 boot／搬池／halt 不會前進的測試。

**P7｜必修：合法 JSON 的壞通知可讓每一格 tick 重複失敗**

- **位置**：`aos_kernel_engine.py:89–115`；`aos_kernel_info.py:90–97`。
- **規範**：`kernel-tick.md 第 6 步`：壞通知「只刪、log 一行，絕不讓這格退 1」。
- **重現**：送一張 `responded` notification，`params.home` 含 JSON `\u0000`。型別檢查會通過，但 `realpath()` 拋出未捕捉的 `ValueError`。另一例是 cpu 路徑尾端帶 5,000 位數字，`int()` 超過 Python 轉換限制。
- **後果**：通知雖已加入記憶體 `deletes`，但例外發生於提交點 3 前，磁碟上的通知不會刪除；下一格再次撞同一張，排程持續失敗。
- **驗證**：兩種輸入均以記憶體呼叫重現 `ValueError`。
- **建議改法**：限制／驗證 home 與號碼字串，並把路徑解析失敗統一轉成 `bad_notify`，讓刪除正常提交。
- **測試缺口**：`test_kernel_tick2.py:267` 有壞 JSON、錯 method、錯位置等案例，但沒有會讓路徑解析本身拋例外的字串。

**P8｜建議：已知的「刪池後忘掉 decl」缺口應正式界定保證**

- **位置**：`aos_daemon_rpc.py:117–121`；`aos_daemon_loop.py:297–299`。
- **性質**：這已記在 decisions 的「規範有洞」第 1 條，**不算新增實作偏離**。
- **重現**：接受 `[epoch,1] count=1` → 接受 `[epoch,2] count=0` → 刪池 → 晚到的 `[epoch,1] count=1`。最後一張會成功重建池；記憶體 mock 已確認。
- **影響**：`handoff.md` 所述「舊單會被 Stale 擋住」不能跨池刪除成立。縮零後若仍容許舊單抵達，可能重新拉起已退休位置。
- **建議改法**：若要保留跨刪除的防舊單保證，需要另存宣告序號 tombstone，並定義 owner 換手規則；否則明確收窄保證。不能只改檔名字典排序便視為解決。

**P9｜建議：daemon 的閒置成本仍含全池掃描，規模保證寫得過強**

- **位置**：`aos_daemon_loop.py:296、314`，以及輪流佇列的 `217`。
- **規範**：`daemon-reconcile.md §2`、`scale.md §1` 宣稱每圈只跟有事的項目／有變的池成比例。
- **差異**：每圈對全部池掃一次 dirty，再對全部池掃一次 changed；`rotation.pop(0)` 每次也會搬移剩餘池。
- **影響**：不是逐顆輪詢，但大量單顆池仍會退回 O(總池數) 的閒置成本；這不屬於 Q1～Q3 已接受的帳本／Python 程序成本。
- **建議改法**：dirty／changed 使用待處理集合，rotation 使用 deque；或把目前複雜度限制寫清楚。

**P10｜建議：補上跨邊界的定點崩潰測試**

位置：`test/test_kernel_boot2.py`、`test/test_kernel_crash.py`、`test/test_daemon_crash.py`、`test/test_p52_e2e.py`。現有測試已覆蓋多個單側提交窗口，但尚未看到以下完整組合的定點驗證：

| 誰／停在哪一步 | 應驗證的結果 |
|---|---|
| boot 已讀帳本，舊 tick 才提交並出貨，之後完成交接 | 最後提交不遺失；已 ack 的工作不重跑（P1） |
| daemon 已發布縮零的 `draining=1`，舊 tick 尚未退出 | boot 不寫新鏈；跨 daemon 也沒有兩格重疊（P2） |
| kernel 留著舊成功或錯誤 scale 回音，接著 boot | 舊回音完成 ack，但不能取消新鏈重宣告（P3） |
| daemon 已回 scale 成功，尚未刪原單便崩潰 | 重開保留成功回音、消除原單，kernel 只結帳一次 |
| daemon 已刪 summary，尚未刪 pool.json 便崩潰 | kernel 搬池後，舊 daemon 重開不再拉回舊位置 |
| killing 中的號被重新加回，pool.json 已寫、尚未 reconcile 便崩潰 | 先收乾淨舊程序，再依最新宣告拉一支；不重複、不遺失 |
| fork 已完成，kids 檔尚未寫便崩潰 | 未收到 go 的孩子不碰家；現有測試主要卡在 kids 已寫、go 未送 |
| 摘要寫入／刪池遇到一次 I/O 失敗，隨後恢復 | 無須重啟 daemon 就能完成發布及搬池／停機（P5） |

逐檔核對結果如下；「未發現新增偏離」只表示本次審查未找到確定問題，不表示已完成動態驗證。

| 規範檔 | 核對結論 |
|---|---|
| `README.md` | 導航涵蓋其餘 15 檔；非獨立行為契約 |
| `kernel-info.md` | 池表、成員、讀驗大致一致；永久保留 skip 依 D-4／D-38；搬池復原見 P4 |
| `kernel-home.md` | 模板、envs、補缺不覆蓋、notify 配置未發現新增偏離 |
| `kernel-ledger.md` | 四提交點、busy／on、ready／delayed 大致一致；boot 保留帳本失效見 P1 |
| `kernel-tick.md` | 通知／recent／巡檢及派工主路徑一致；壞通知見 P7 |
| `kernel-pools.md` | 正常 drain、S∩Q∩W、單一 pending 一致；重宣告與搬池見 P3～P6 |
| `kernel-cli.md` | init／cpu 編輯鎖／按池顯示／check 大致一致；halt 判完成受 P5、P6 影響 |
| `daemon-home.md` | 池宣告、kids、摘要計數大致一致；摘要故障處理見 P5、P6 |
| `daemon-reconcile.md` | streak／stable_ms、令牌桶、fd 預算、kill 重拉、failed 換 target、批次階梯、waitpid 主路徑未發現確定新錯；見 P5、P9 |
| `daemon-cli.md` | owner／force、scale／kill、唯讀 ls 未發現新增偏離 |
| `protocol.md` | 基本驗證、回音／ack、Stopping／Stale 主路徑一致；摘要語意見 P6，已知舊單缺口見 P8 |
| `handoff.md` | P1～P3；其中 P2 也需修規範自身的條件矛盾 |
| `cpu-notify.md` | 回音→刪原單→通知、啟動補通知、EEXIST 與一般通知失敗處理一致；D-70～D-72 已記錄 |
| `choices.md` | 多數選擇已實現；「安全交接」「boot 重宣告」尚受 P1～P3 破壞 |
| `scale.md` | Q1～Q3 不列錯；額外的全池掃描見 P9 |
| `proto5-diffs.md` | 路徑、池引用、agent busy／on 適配及單 pipe 大致一致；交接等待條件須隨 P2 修正 |