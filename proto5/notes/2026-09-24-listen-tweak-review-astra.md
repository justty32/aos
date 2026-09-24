整體主流程與規範大致一致，`--last 1` 的既有輸出及 `say --wait` 沒看到正常資料下的回歸；但工具名稱配對、異常記憶處理、封存時間還有必修問題。全程未修改檔案。指定測試的 460 條都因唯讀沙箱無法建立暫存目錄而卡在初始化，不能視為測試通過或程式失敗；以下另以無檔案寫入的 mock 案例驗證。

**必修**

1. **工具結果會被「後面的呼叫」改名。**
   - 在哪：[aos_agent_listen_render.py:180](/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a6135c65212b10639/proto5/lib/aos_agent_listen_render.py:180)、同檔 213；`aos_agent_listen.py:217`。
   - 重現：第一輪 `id=same` 呼叫 `read`，第二輪同 id 呼叫 `write`；印兩輪時，第一輪結果變成 `[結果 write：old]`。已重現。規範只禁止**同一則訊息**重複 id，因此這是合法記憶。
   - 建議：按記憶順序更新名稱表，結果只對到它**之前最近的呼叫**；follow 同一次讀到多輪時也要如此。

2. **fallback 接受未驗證記憶，新印法會直接崩潰。**
   - 在哪：[aos_agent_listen.py:55](/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a6135c65212b10639/proto5/lib/aos_agent_listen.py:55)、`aos_agent_listen_render.py:186、192、216`。
   - 重現：預設記憶為 `[user, null, assistant]`，執行 `--last --show-calls`：正常讀驗失敗後 fallback 接受整個陣列，最後拋出 `AttributeError`。舊 assistant 的 `tool_calls:[null]` 也會讓不帶 show-calls 的 `--last 2` 崩潰，因為 `render()` 無條件掃描全部 calls。均已重現。
   - 建議：明確統一 fallback 策略——驗證後回報可辨識錯誤，或容錯略過／標示異常項；不要讓 Python traceback 洩出。非字串 arguments/content 目前有些會被轉成 Python 表示法、有些異常形狀會崩潰，也應一起定義。

3. **超長合法數字會讓 CLI 崩潰。**
   - 在哪：[aos_agent_cli.py:98](/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a6135c65212b10639/proto5/lib/aos_agent_cli.py:98)。
   - 重現：`main(['listen', '--last', '9' * 4301])` 拋出 Python 整數轉換位數限制的 `ValueError`；發生在主要例外處理外。已重現。
   - 建議：以十進位字串比較、對實際回話數飽和處理；若要限制位數，需同步規範並回用法錯 2。目前規範沒有 N 上限。

4. **封存分組與排序無法完整還原收件順序。**
   - 在哪：[aos_agent_listen_render.py:76](/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a6135c65212b10639/proto5/lib/aos_agent_listen_render.py:76)、同檔 83。
   - 重現①：兩份封存 ns 相同、pid 不同，會被合併成一次收件；已驗證第二輪因此沒有時間。規範要求依完整消費 id 分組。
   - 重現②：資料夾內原檔 `a.json`、`a.json-2.json` 的收件排序，與加上封存後綴後的排序相反，導致「第一句 user」選錯。
   - 建議：以 `(ns, pid)` 分組，依 input 路徑順序與**原檔名**排序重建內容。

5. **不合理的封存時間戳會讓回話印不出來。**
   - 在哪：[aos_agent_listen_render.py:97](/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a6135c65212b10639/proto5/lib/aos_agent_listen_render.py:97)。
   - 重現：放入檔名符合格式、ns 為 `10**30`、內容與 user 相同的封存；`datetime.fromtimestamp()` 拋出 `OverflowError`。已用 mock 重現。
   - 建議：逐筆捕捉時間轉換錯誤，略過該时间，照規範退回只有輪號的標頭；輔助時間資訊不應阻止讀回話。

6. **簡化呼叫行不保證只有一行。**
   - 在哪：[aos_agent_listen_render.py:128](/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a6135c65212b10639/proto5/lib/aos_agent_listen_render.py:128)。
   - 重現：合法 arguments JSON 為 `{"a\nb":1}`，輸出包含真正換行；已重現。目前只處理值裡的 LF，key 與工具名稱未處理。
   - 建議：對行內所有文字欄位統一轉義換行及 CR，再計算截斷，符合「一個呼叫一行」。

7. **follow 真程序測試可能永久卡住。**
   - 在哪：[test_agent_listen_tweak.py:219](/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a6135c65212b10639/proto5/lib/test/test_agent_listen_tweak.py:219)、同檔 237。
   - 重現條件：程序啟動超過 0.5 秒，父程序先更新記憶；子程序把更新後長度當起點。第一條接著無期限 `readline()`，無法走到後面的 `communicate(timeout=5)`；第二條則可能漏輸出或過早收到 SIGINT。
   - 建議：等待明確的初始化完成訊號，所有讀取加總期限；cleanup 應 kill 後 wait 回收。這是靜態確認的競態，本環境無法執行真程序案例。

**建議**

1. **重複問句的時間應標明只是推定。**
   - 在哪：[aos_agent_listen_render.py:94](/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a6135c65212b10639/proto5/lib/aos_agent_listen_render.py:94)、規範 `cli-listen.md:32`。
   - 重現：兩輪都問「繼續」，只刪第一輪封存；第二輪時間會被配給第一輪，第二輪反而沒時間。已重現。
   - 建議：這符合目前規定的貪婪比對，但無法保證真實輪次；有歧義時省略時間，或明寫限制。截掉記憶前半段、改 input 路徑、一次輸入含多段 user/assistant，也有同類限制。

2. **封存掃描應排除特殊檔，並控制成本。**
   - 在哪：[aos_agent_listen_render.py:61](/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a6135c65212b10639/proto5/lib/aos_agent_listen_render.py:61)、同檔 71。
   - 重現條件：符合名稱的 FIFO 會被 `read_text()` 開啟而可能阻塞；symlink 會跟到別處。大量封存則每次完整讀取，即使只看最後一則加 show-calls。
   - 建議：限定可接受的普通檔、避免重複掃描；大資料量再考慮索引。資料夾模式也無法區別同目錄中的門消費封存與真正輸入封存。

3. **补齊重要測試空缺。**
   - 在哪：[test_agent_listen_tweak.py:93](/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a6135c65212b10639/proto5/lib/test/test_agent_listen_tweak.py:93) 起。
   - 重現方式：目前 `test_last_one_unchanged` 只驗 stdout；full 截斷主要只驗結果，不驗長參數。
   - 建議：加入上述必修案例，以及 stderr 相容、檔案型／多路徑 input、壞 state、follow 改短、wait/follow 搭 full/JSON、40／120／60／4000 邊界與中文案例。

4. **help 與規範有兩處容易過度承諾。**
   - 在哪：[aos_agent_cli.py:24](/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a6135c65212b10639/proto5/lib/aos_agent_cli.py:24)、`cli-listen.md:38`。
   - 重現：help 範例說「回傳全印」，實際有 4000 字上限；同輪先有帶文字的工具呼叫、再有最終答案時，`--last 1 --show-calls` 不含前一則回話上的呼叫。
   - 建議：改成「最多 4000 字」及「所選區段內的工具」，避免讀者以為一定涵蓋完整一輪；目前区段計算本身符合規範公式。

**不用改**

- 裸 `listen`、模式互斥、show-calls 互斥、一般非法 N，以及實際 `listen -h` 的主要參數說明，都與規範一致。
- `pick()` 的回話計數、最後一則純工具 assistant 例外、時間順序及不足 N 的 note，符合定義。
- 正常記憶下，`--last`／`--last 1` 仍選最後一則 assistant，沿用原 stdout、警告及 mtime 路徑；三組前後版本 mock 比對一致。
- `say --wait` 仍走同一個 `wait_reply()`，預設 `calls=None`，既有等待與輸出分支未變。
- 連續兩則 user 算同輪、記憶開頭 assistant 算第 0 輪，符合規範且已驗證。
- 無可配對封存或 state 讀驗失敗時可退回無時間標頭；一般檔案型 input 有原檔名過濾。
- 合法記憶下 `--json --show-calls*` 不加標頭、包含 tool，short/full 無差別；無任何對應呼叫的 tool 顯示 `?`。
- follow 確實觀察到記憶縮短後會重設長度，再印後續新增訊息；已用 mock 驗證。
- 截斷以 Python Unicode 字元計數，不會切壞 UTF-8 多位元組；4000 字邊界及超限註記已驗證。它不保證保留完整組合 emoji，但不是位元組截壞。