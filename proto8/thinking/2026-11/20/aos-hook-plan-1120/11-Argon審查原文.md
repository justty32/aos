Argon（Gemini 4 Argon High）11-20 對本線設計稿與施工計劃的審查原文，一字未改；逐條採納與否在 12-採納表。

← [README](README.md)｜[12 採納表](12-採納表.md)

送審方式：公司 Windows 的 `agy`，plan 模式，提示檔放在只裝本線材料的空夾；提示＝當時的 01～10 全文＋`hook_run.py` 的 fire 與 `loop.cpp` 主迴圈兩段。原文裡的「Line 數字」是提示檔的行號。送審後設計改過（見 12），下面講的有些已經不是現在的樣子。

---

以下根據設計稿（`01`～`10`）與附上的兩段原始碼（`hook_run.py`、`loop.cpp`），分 **(A) 審查** 與 **(B) 提案** 兩段回答。

---

## (A) 審查

### 一、Race Condition（旗標檔、清單重讀、暫停與扣住）

* **A1【一定要改】`aos-hook fire`「發現沒人聽就刪旗標」與新增 hook 之間的 TOCTOU Race**
  * **位置**：`06-loop層的點.md`「沒人掛時怎麼做到零成本」；`09b-施工計劃-逐刀.md`「刀 5」（`agentlib/hooks.py`、`apps/agent/hook.py`、`apps/hook/main.py` 旗標維護）。
  * **問題**：設計規定「旗標在、其實沒人掛：`aos-hook fire` 發現沒人聽，退 0 並把旗標刪掉」；同時 `agentlib/hooks.py` 每次讀清單（包含長住的 `aos-mcp`、每格的 `clock_tick`）、`aos-agent hook add`、`self_hook` 也會各自讀清單並補／刪旗標。
    當 `aos-hook fire`（或某個剛讀完舊清單的行程）判定沒人掛 `before_run`、準備執行 `unlink(hook_before_run.flag)` 的瞬間，若外部（`aos-agent hook add`、`self_hook add` 或 gdb 下斷點）剛好寫入新的 `before_run` hook 並建立了 `hook_before_run.flag`，後執行的 `unlink` 會**把剛建好的旗標檔誤刪**。一旦誤刪，下一圈 `aos-loop` 看到沒旗標就直接跳過 `on_before_run`，導致剛掛上的 `before_run`（或 gdb 斷點）在第一圈漏發。

* **A2【一定要改】gdb 下 `before_run`／`after_run` 斷點時沒維護旗標檔，第一圈必漏扣**
  * **位置**：`03-誰讀宣告.md`「gdb 怎麼從宣告讀」；`06-loop層的點.md`「沒人掛時怎麼做到零成本」；`09b-施工計劃-逐刀.md`「刀 5、刀 6」。
  * **問題**：`03` 宣稱附帶得到 `a.bp.add.before_run("act")` 能扣在 `act` 跑之前；但 `06` 的「誰維護旗標」表裡只列了 `agentlib/hooks.py`、`aos-agent hook`、`self_hook`、`aos-hook fire/check`，**沒有列 `py/aos/gdb/`**（`09b` 刀 6 也沒列）。
    gdb 下斷點是直接寫 stack 的 `hooks.json`。若 agent 正處於 `waiting` 或 `paused`，使用者在 gdb 下了 `a.bp.add.before_run("idle")` 後放行，`hook_before_run.flag` 此時根本還不存在（要等身體跑進 `idle` 格開頭呼叫 `clock_tick` 讀清單時才會補旗標），結果 `aos-loop` 在跑這一格前看到沒旗標檔，**直接不發 `before_run` 就跑進 `idle` 格**，斷點在第一格完全扣不住。

* **A3【一定要改】扣在 `on_before_run` 期間收到 `ctl`（如 `pause`／`stop`），放行後不重讀 `ctl` 就直接跑身體**
  * **位置**：`06-loop層的點.md`「一圈裡的順序與每個結束碼的意思」、「跟現有的關係」；對照 `loop.cpp:1203-1250`。
  * **問題**：`loop.cpp` 只在迴圈頂端（Line 1203）呼叫一次 `read_ctl()`。當 agent 被 gdb 扣在 `before_run`（或 `on_before_run` 的 handler 跑很久）時，`aos-loop` 阻塞在 `run_once(on_before_run_)`。這段期間若外部對 `ctl` 送了 `stop` 或 `pause`，等 `on_before_run` 結束退 `0` 返回 `main_loop` 時，程式若直接往下走 `runs_ += 1; run_once(exec_);`，**身體還是會硬跑一圈**，直到下一圈頂端才看到 `stop`／`pause`。

---

### 二、順序與狀態機（`before_run`／次數／`state`／`next_at`／訊號／`on_stop`）

* **A4【一定要改】`on_before_run` 退 10（跳過這一圈）時若未推進 `next_at`，會造成 100% CPU 無限忙迴圈**
  * **位置**：`06-loop層的點.md`「一圈裡的順序與每個結束碼的意思」；`09-施工計劃.md`「F6」；對照 `loop.cpp:1227-1278`。
  * **問題**：在 `loop.cpp` 中，`next_at` 是在身體跑完後的最後一行（Line 1277：`next_at = Clock::now() + std::chrono::milliseconds(iv);`）才更新的。當時間到了通過 Line 1228（`wait <= 0`）進入 `on_before_run` 時，`next_at` 已經是**過去的時間點**。
    如果 `on_before_run` 退 `10` 時只做 `continue` 回到迴圈頂端、沒有先設定 `next_at = Clock::now() + std::chrono::milliseconds(iv)`，下一輪頂端算出來的 `wait` 永遠 `<= 0`，**根本不會進 Line 1230 的 `nap(wait)`**，而會以 100% CPU 狂跑 `on_before_run`！
    此外，若上一圈跑過身體（state 為 `"running"`）且 `iv == 0`（或上一圈耗時超過 `iv` 導致這圈沒進 Line 1229），這圈被 `on_before_run` 退 10 跳過時，若沒確保 `write_state("waiting", Json())`，狀態窗會一直卡在 `"running"`，違反 `06` Line 619「表上是 waiting」。

* **A5【一定要改】`on_before_run` 執行期間的 `state` 視窗狀態未定義（扣住時外部以為還在 `waiting`）**
  * **位置**：`06-loop層的點.md`「一圈裡的順序與每個結束碼的意思」；`09-施工計劃.md`「F6」；對照 `loop.cpp:1229, 1245`。
  * **問題**：F6 寫道：「`runs_ += 1`、`write_counter()`、寫 `running` 都在跑身體之前（`loop.cpp:200-213`），`before_run` 要插在它們前面，被跳過的一圈三樣都不做。」
    照這樣插在 `write_state("running")` 前面：當 gdb 把 agent 扣在 `before_run` 時，agent 的 `state` 檔案還停在 `"waiting"`（若是第一圈，甚至還沒寫過任何 `state`！），gdb 或外部監控看 `state` 完全不知道它已經進了這一圈並被扣住；但若先寫 `"running"`，被退 10 跳過時又得寫回 `"waiting"`，每圈都退 10 時 `state_flux` 就會每 300ms `running` ↔ `waiting` 翻轉兩次。必須明確規範 `on_before_run` 期間的 `state` 行為。

* **A6【一定要改】`AOS_LOOP_RUNS` 在 `before_run` 與 `runs_ += 1` 的先後矛盾（差 1 錯誤）**
  * **位置**：`02-現有的點改寫成宣告.md`「loop 那份」（Line 154, 157）；`06-loop層的點.md`「一圈裡的順序」；`09-施工計劃.md`「F6」。
  * **問題**：`02` 定義 `before_run` 的 `counter_runs` 是 `"which run this will be (from 1)"`（第一圈應為 `1`），而 `06` 與 F6 規定 `on_before_run` 在 `runs_ += 1` **之前**執行（那時 `runs_` 還是 `0`），`on_after_run` 在 `runs_ += 1` **之後**執行（那時 `runs_` 是 `1`）。
    因此 `loop.cpp` 在設 `AOS_LOOP_RUNS` 環境變數時，**`on_before_run` 必須傳 `runs_ + 1`，而 `on_after_run` 必須傳 `runs_`**。施工計劃 `09b` 刀 5 完全沒提這個差異，若共用同一個讀取 `runs_` 的 helper，同一圈的 `before_run` 與 `after_run` 拿到的 `counter_runs` 會差 1（第一圈 `before_run` 會拿到 `0`）。

* **A7【一定要改】`before_run` 與 `after_run` 讀同一個 `stage.txt`，導致第一圈比不中、`after_run` 的 `condition: "stage"` 比到「下一格」**
  * **位置**：`02-現有的點改寫成宣告.md`「loop 那份」（Line 153-161）；`06-loop層的點.md`「loop.json 多的四個鍵」、「事件帶什麼」；`09-施工計劃.md`「F7」。
  * **問題**：
    1. **第一圈 `before_run` 漏攔**：fsm 起跑第一圈還沒有 `$AOS_STACK/stage.txt`，`stage` 為 `null`（F7 雖有發現，但只說「說明寫明」）。這表示使用者掛 `before_run` 設 `condition: "idle"` 或在 gdb 下 `a.bp.add.before_run("idle")`，**起跑第一格 `idle` 永遠不會觸發**。
    2. **`after_run` 的 `condition: "stage"` 語意錯亂**：`aos-fsm` 跑完一格（例如 `act`）成功時，在退出前已經把 `stage.txt` 更新成**下一格**（例如 `idle`）了；失敗時則停在原格（`act`）。因此 `after_run` 去讀 `stage.txt` 拿到的 `stage`，成功時是「下一格」、失敗時是「剛跑完的這一格」。使用者對 `after_run` 下 `condition: "act"`（想在 `act` 跑完後檢查），結果在 `act` 成功跑完時根本不會觸發（因為 `stage.txt` 已變成 `"idle"`），反而在 `wait` 跑完準備進 `act` 時觸發！

* **A8【一定要改】`loop.json` 接線用了 `aos-directive` 不存在的 `"$prefix": "stage="` 指示詞，且非 fsm 的 `eca` 範本也誤接 `stage.txt`**
  * **位置**：`06-loop層的點.md`「loop.json 多的四個鍵」（Line 541）；`01-宣告格式.md`（Line 94）；`09b-施工計劃-逐刀.md`「刀 5」（Line 986）。
  * **問題**：
    1. `06` Line 541 寫了 `{"$env": "AOS_STACK", "$path": "/stage.txt", "$prefix": "stage="}`。`aos-directive` 只有 `$env` 與 `$path`（後接），並沒有 `$prefix` 這個標準鍵；若 `aos-loop` 解 `loop.json` 時 `aos-directive` 不認得 `$prefix`，會直接炸錯或組不出 `"stage=/path/to/stage.txt"`。
    2. `09b` Line 986 把六份 `loop.json`（含 `eca-claude`、`eca-pi`、`start-eca/agents/ann`）列在一起寫「加四鍵（F2 的路徑寫法）」，但 `eca` 身體根本不是 fsm、沒有 `stage.txt`（雖然檔不在時 `--field-file` 給 `null`，但 `eca` 的 `loop.json` 不該無故多讀一個永遠不存在的 `stage.txt`）。

---

### 三、失敗路徑（指令起不來、逾時、被 SIGTERM、環境變數殘留）

* **A9【一定要改】`on_before_run` 或 `on_after_run` 執行期間收到訊號（`received != 0`）時，會被誤判成 hook 失敗（`error`）而非訊號收工（`signal`）**
  * **位置**：`06-loop層的點.md`「一圈裡的順序與每個結束碼的意思」；對照 `loop.cpp:1263-1268`。
  * **問題**：`06` 只寫了「身體跑時 loop 這一圈收到訊號就不跑 `on_after_run`，直接收工」，卻漏了**「跑 `on_before_run` 或 `on_after_run` 的子行程期間，`aos-loop` 收到 SIGTERM／SIGINT」**（例如停樹時，agent 正好在那 18~37ms 的 `aos-hook fire` 裡，或正被 gdb 扣在 `before_run`）。
    那時 `run_once(on_before_run_)` 回傳的 `Run` 會有 `r.received != 0`（且 `r.code != 0`）。若 `loop.cpp` 沒有比照 Line 1263 **最優先檢查 `if (r.received != 0)` 並設 `got_ = r.received; return end(128 + r.received, "stopped", StopCauseWindow::signal);`**，就會掉進 `r.code != 0` 的分支，把正常停樹當成 hook 失敗（退碼變 1、`AOS_LOOP_CAUSE` 變 `"error"`、`AOS_LOOP_SIGNAL` 變 `null`）！甚至若 `on_before_run` 剛退 `0` 的同時收到訊號卻沒檢查 `r.received != 0 || signal_got() != 0`，還會繼續往下跑身體 `exec_`。

* **A10【一定要改】身體 `exec_` 起不來（`run_once` 丟 `Error`）或身體失敗／退 10 時，`on_after_run` 的呼叫條件與退碼覆蓋規則未定**
  * **位置**：`06-loop層的點.md`「一圈裡的順序與每個結束碼的意思」；對照 `loop.cpp:1249-1275`。
  * **問題**：
    1. 當身體 `exec_` 連起都起不來時，`loop.cpp:1251` 的 `run_once(exec_)` 會 **throw `const Error& e`** 並直接 `return end(1, ...)`。此時 `Run b` 根本沒有 `code`、`signal`、`elapsed_ms`，**絕不能跑 `on_after_run`**（設計稿寫「身體失敗都跑」，必須明確排除 `run_once` throw `Error` 的情況）。
    2. 當身體正常退 `10`（`body_exit`，loop 原本退 `0`）時，若 `on_after_run` 失敗（退 `1`），loop 最終退碼與 `AOS_LOOP_CAUSE` 是變成 `1`／`"error"` 嗎？
    3. 當身體失敗（例如 `b.code == 2`）時，原本 Line 1273 的 `fail_line(code::RunFailed, ...)` 是在 `on_after_run` **之前**印還是**之後**印？若 `on_after_run` 也失敗（退 `1`），loop 的最終退碼是用身體的 `2` 還是 `on_after_run` 的 `1`？這幾條分支在 `loop.cpp` 是一定會寫到的 if-else，設計稿沒定清楚。

* **A11【一定要改】`AOS_LOOP_RUN_SIGNAL` 在身體未被訊號終止（`b.signal == 0`）時的環境變數設法與還原**
  * **位置**：`02-現有的點改寫成宣告.md`（Line 159）；`05-發事件指令.md`（Line 437）；`06-loop層的點.md`（Line 560）；`09b-施工計劃-逐刀.md`（Line 978）；對照 `loop.cpp:1260`。
  * **問題**：`02` 規定 `after_run` 的 `signal` 是 `"the signal that ended the body, or null"`（`type: "int"`）；`05` 規定「從環境變數取（空字串＝null，`int` 型別轉成整數）」。
    在 `loop.cpp` 中，當身體正常結束時 `b.signal == 0`（見 Line 1260：`b.signal == 0 ? Json() : Json(b.signal)`）。`loop.cpp` 在跑 `on_after_run` 前，若 `b.signal == 0`，**必須把 `AOS_LOOP_RUN_SIGNAL` 設為空字串 `""` 或 `unsetenv`**，絕不能設成 `std::to_string(b.signal)`（即 `"0"`），否則 `aos-hook fire` 會把它轉成整數 `0` 而非 `null`。而且跑完 `on_before_run`／`on_after_run` 後必須 `unsetenv` 全部 `AOS_LOOP_RUN*`，避免汙染身體 `exec_` 與 `on_stop` 的環境。

* **A12【一定要改】`hook_point.open` 的 `fail=` 回呼若自己丟出例外（如 `eca` 的 `Fail`、`mcp` 的 `HookStop`），不能被小庫攔截或覆蓋**
  * **位置**：`04-小函式.md`「結論」、「`aos.hook_point` 給什麼」、「刻意不收的」、「邊緣」（Line 324, 340, 389, 399）。
  * **問題**：`04` Line 389 說 `eca` 的 `after_queue` 失敗要先記著、等回答進 history 才報，所以「它照舊自己接 `Fail`」；`mcp` 則是讓 `fail=` 丟 `HookStop`，外層接 `HookStop` 轉成 `isError`。但 Line 399 又說「庫在 `fail()` 之後自己再丟一個例外」。
    實作時必須明確：**只有在 `fail(code, msg)` 正常 return（沒有 raise）時，小庫才補丟保底例外**；若 `fail()` 自己已經 `raise Fail(...)` 或 `raise HookStop(...)`，小庫必須讓該例外原樣往外穿透，絕不能包在小庫自己的 `try...except` 裡轉成別的例外，否則 `eca` 與 `mcp` 外層的 `except Fail`／`except HookStop` 會全部接不到！

---

### 四、宣告驗證規則與引擎接口的漏洞

* **A13【一定要改】`change` 的型別檢查必須作成 `check` callback 傳進 `hook_run.fire`，不能在 `hook_run.fire` 返回後才驗**
  * **位置**：`04-小函式.md`「`aos.hook_point` 給什麼」（Line 339-346）；對照原始碼 `hook_run.py:1160-1188`。
  * **問題**：`04` 寫「`change` 的型別檢查由庫做」、「`check(event, key, value)` 給型別以外的檢查」、「引擎 `hook_run.py` 不動」。
    看 `hook_run.py:1173-1180`：當同一個事件掛了多個 hook 時，引擎是在**每一個 hook 跑完的當下**呼叫 `_changes(event, out, events, check)`；若 `check` 丟 `ValueError`，引擎會看**那一個 hook** 的 `on_error` 是 `"stop"` 還是 `"continue"`——若是 `"continue"`，引擎會印 warning、**丟棄該 hook 改壞的值**，並帶著原本合法的 `result["data"]` 繼續跑下一個 hook！
    如果 `hook_point.py` 是在 `hook_run.fire()` 整個跑完返回後才對 `r["data"]` 做 `change` 型別檢查：
    1. 某個設了 `on_error: continue` 的 hook 吐了錯誤型別（例如把 `content` 改成空字串或把 `arguments` 改成非 dict），會等到最後才爆出無法歸責給哪支 hook 的錯誤，且讓 `on_error: continue` 失效；
    2. 前一個 hook 改壞的非法型別會直接被塞進下一個 hook 的 stdin！
    **正解**：`hook_point.py` 必須在內部將「宣告的 `change` 型別檢查」與使用者傳入的 `check` 組合成一個 `combined_check(event, key, value)`（不合時丟 `ValueError`），傳給 `hook_run.fire(..., check=combined_check)`。另外要注意 JSON 的 `"object"` 在 Python 要驗 `isinstance(v, dict)`（不是 `isinstance(v, object)`）。

* **A14【一定要改】`01-宣告格式.md` 的五條驗證規則漏驗 `if_blocked`、`fields` 內部結構與型別，遇錯型別會丟 `TypeError` 而非 `PointsBad`**
  * **位置**：`01-宣告格式.md`「每個點的鍵」、「讀的時候驗什麼」（Line 58-81）；`05-發事件指令.md`「`fire` 的進出」（Line 437）。
  * **問題**：
    1. Line 67 表格明訂「`if_blocked`：`block` 為 true 時必填」，但 Line 74-80 的「讀的時候驗什麼（1～5 條）」與 `09b` 刀 1（Line 894「驗 01 的五條」）**漏了驗 `if_blocked`**。
    2. 第 3 條「`condition`、`key`、`change` 的每個鍵都要在 `fields` 裡」：若宣告檔把 `condition` 或 `key` 誤寫成 list 或 dict（非字串），Python 執行 `condition in fields` 會直接丟 `TypeError: unhashable type` 而非 `PointsBad`。
    3. `fields` 的值允許寫成物件 `{"about": ..., "env": ..., "type": "int"|"string"}`（Line 62），但驗證規則完全沒驗 `fields` 是不是 dict、物件值裡的 `env` 是不是非空字串、`type` 是不是只能為 `"int"` 或 `"string"`。
    4. `05` Line 437「stdin → env → 旗標，同名時後者蓋前者；空字串＝null」：如果某欄位宣告了 `env`，但執行時該**環境變數未設定（或為空）**，而呼叫端是透過 **stdin** 傳入該欄位的值（例如測試或手動呼叫 `aos-hook fire`），未設定的 `env` 轉成 `null` 後會不會把 stdin 傳入的合法值蓋成 `null`？必須規定「環境變數**有設且非空**時才覆蓋 stdin（或未設定時不蓋）」，且 `int` 轉型失敗時要報 `ArgumentsBad` 退 1 而非裸拋 `ValueError` traceback。

* **A15【一定要改】`01` 驗證第 5 條允許同名點並存，但未定義 `read(paths)` 合併時 `fields`／`entry_keys`／`subject` 衝突怎麼合**
  * **位置**：`01-宣告格式.md`「讀的時候驗什麼」第 5 條（Line 80）；`04-小函式.md`（Line 337）。
  * **問題**：第 5 條規定同一隻 agent 的幾份宣告出現同名的點時，只要求 `phase`、`condition`、`change`、`block`、`key` 相同，`when` 與 `fields` 可以不同。那 `hook_point.read(paths)` 把多份宣告合成一張 `{點名: 點}` 時，同名點的 `fields`、`entry_keys`、`subject`、`if_blocked` 是後蓋前還是聯集？若後蓋前，前一份宣告的 `fields` 欄位會在 `aos-agent hook events` 與編譯線檢查時靜靜消失。

* **A16【一定要改】`hook_point.open` 的把手缺少列出事件已掛項目（或讀取 `entries`）的介面，無法支撐 `kernel` 的 `after_verdict` 逐格觸發**
  * **位置**：`04-小函式.md`「`aos.hook_point` 給什麼」（Line 337-341）、「刻意不收的」（Line 391）；`02-現有的點改寫成宣告.md`（Line 221）。
  * **問題**：`kernel` 的 `after_verdict` 是「fired hook by hook（一格一格發，約 50 行）」，因為每個 hook 改了 `verdict`／`next` 之後，kernel 中間要跑自己的判決邏輯，所以要對掛在 `after_verdict` 上的每個 hook 逐一呼叫 `fire("after_verdict", data, only=[name])`。
    但 `04` 設計的把手只有 `.fire(event, data, only=None)`、`.has(event)`、`.points`，**沒有提供取得該事件匹配的 hook 名稱清單（或 `.entries`）的方法**，kernel 拿到把手後根本不知道有哪些 `name` 可以傳給 `only=[name]`。

---

### 五、施工順序會讓活的 agent 壞掉的時刻

* **A17【一定要改】`09b` 刀 2 沒有落實 F1 的「拆 2a／2b」，改格程式存檔的那一刻活樹所有 `std.fsm()` agent 會立刻退 1 死掉**
  * **位置**：`09-施工計劃.md`「總表」、「install 與活樹」、「F1」（Line 788, 823, 856）；`09b-施工計劃-逐刀.md`「刀 2」（Line 909-927）。
  * **問題**：`09` F1 已經指出：活樹上所有 `std.fsm()` 編譯的 agent 與 `templates/reviewer` 直接跑 repo 裡的 `$AOS_HOME/templates/agent-fsm/*.py`（存檔即生效），但它們 import 的 `agentlib/hooks.py` 在 `$AOS_HOME/lib/`（要 `install.py` 後才生效）。
    然而 `09b` 的「刀 2」卻還是把 `py/aos/agentlib/hooks.py` 與 `templates/agent-fsm/*.py` 放在同一刀改！按照硬規則，施工者要先在 repo 改好檔、用 `git archive` 到 scratch 複本跑完測試、回報使用者等放行，**最後才在活樹跑 `install.py`**。這意味著從「在 repo 改完 `templates/agent-fsm/*.py` 存檔」到「獲准在活樹跑 `install.py`」的整個空窗期，活樹上所有借用格程式的 agent 每 300ms 跑一格就會因找不到 `hooks.open` 而退 1 崩潰！
    **必須在 `09b` 硬性拆成兩步**：刀 2a 只改 `py/aos/` 底下的庫（保留舊函式）→ 測試、交件並在活樹 `install.py` → 刀 2b 才改 `templates/agent-fsm/*.py`。刀 3 拿掉舊函式時亦同（先確保沒有任何活定義叫舊函式並完成 install，再刪舊函式）。

* **A18【一定要改】刀 3 直接刪 `agentlib.hooks.EVENTS` 並去改 `py/aos/gdb/__init__.py` 做暫頂，會與鄰線 `aos-gdb-wait-1120` 未交件的工作樹直接衝突**
  * **位置**：`09-施工計劃.md`「順序與可並行」、「F11」（Line 817, 866）；`09b-施工計劃-逐刀.md`「刀 3」（Line 936, 945）。
  * **問題**：`09` Line 781 與 817 明言鄰線 `aos-gdb-wait-1120` 已經改了工作樹的 `py/aos/gdb/*` 且未交件，所以刀 6 要等鄰線交件。但刀 3（不依賴鄰線）卻要在 `agentlib/hooks.py` 拿掉 `EVENTS`，並去改 `py/aos/gdb/__init__.py` 做「暫頂」！這會讓刀 3 直接踩進鄰線未交件的檔案。
    **解法**：刀 3 在 `agentlib/hooks.py` 裡**保留 `EVENTS`（可改由宣告動態算出）**，刀 3 就完全不必碰 `py/aos/gdb/__init__.py`，等到刀 6 鄰線交件後再一起清除。

* **A19【一定要改】刀 5 活樹更新順序若未「先停樹 → 再 install 刪 `hook_fire` 與改舊定義 `loop.json` → 再起樹」，活著的 loop 停下時 `after_stop` 會靜默失效**
  * **位置**：`09-施工計劃.md`「install 與活樹」（Line 827）；`09b-施工計劃-逐刀.md`「刀 5」（Line 989, 999）。
  * **問題**：`aos-loop` 是在啟動時（`Loop::Loop`）讀一次 `loop.json` 並把 `on_stop` 的 `argv` 記在記憶體裡。如果刀 5 在活樹還沒停樹時就先跑了 `install.py`（刪掉 `hook_fire`），或者先改了 `loop.json` 再停樹，那些**已經在跑的舊 `aos-loop` 行程**記憶體裡握的 `on_stop` 仍然指著 `hook_fire`；當停樹送 SIGTERM 給它們時，它們跑 `on_stop` 就會找不到 `hook_fire`，導致所有活 agent 最後一次 `after_stop` 靜默不發。`09` Line 827 寫「盤點；改舊定義的 loop.json；停樹換檔」，順序必須改為：**盤點 → 停樹 → install 換檔＋改舊定義的 `loop.json` → 起樹**。

* **A20【建議】`templates/reviewer` 借用 `agent-fsm` 格程式卻漏在刀 3／刀 5 的範本修改清單外**
  * **位置**：`09-施工計劃.md`「F1、F19」（Line 856, 874）；`09b-施工計劃-逐刀.md`「刀 3、刀 5」（Line 942, 986）。
  * **問題**：`templates/reviewer` 借用 `templates/agent-fsm/*.py` 格程式。雖然它預設沒有 `hooks.json`，但到了刀 3 格程式會呼叫 `hooks.open`，若使用者或測試對 `reviewer` 用 `aos-agent hook add` 或用 gdb 下斷點，因為 `reviewer/interfaces.json` 沒補 `hook_points`、`reviewer/loop.json` 沒接四鍵，就會立刻報 `HooksBad` 或無法在 gdb 用 `before_run` 停住。應在刀 3、刀 5 把 `templates/reviewer` 一起納入。

---

### 六、設計自相矛盾之處

* **A21【一定要改】`02-現有的點改寫成宣告.md` 中 `after_verdict` 的 JSON 範例寫 `"phase": "after", "block": true`，直接違反 `01` 的第 2 條驗證規則**
  * **位置**：`01-宣告格式.md`「讀的時候驗什麼」第 2 條（Line 77）；`02-現有的點改寫成宣告.md`「kernel 那份」（Line 221 vs Line 231）。
  * **問題**：`01` 第 2 條規定「`block: true` 只准出現在 `phase: before`」。`02` Line 231 雖然文字寫「設計預設：`phase` 記 `before`」，但緊貼在上面的 Line 221 JSON 程式碼區塊卻還是寫 `"phase": "after"` 與 `"block": true"`。施工時若照抄 Line 221 的 JSON，刀 1 的驗證測試當場就會失敗；且把名叫 `after_verdict` 的點標成 `phase: "before"`，會在 `aos-hook points` 輸出時呈現自相矛盾的資訊（見提案 B4）。

* **A22【一定要改】`entry_keys` 在 `01` 說「不拿來擋」，在 `03` 與 `08` 卻說「拿來驗」，且誤把通用鍵 `config` 放進 `on_clock` 專屬的 `entry_keys`**
  * **位置**：`01-宣告格式.md`（Line 69）；`02-現有的點改寫成宣告.md`（Line 196）；`03-誰讀宣告.md`（Line 252）；`08-給編譯線的接口.md`（Line 722）；`09-施工計劃.md`「F16」（Line 871）。
  * **問題**：
    1. `01` Line 69 與 `09` F16 說 `entry_keys`「只拿來說明與提示，不拿來擋」；但 `03` Line 252 的表格寫 `aos-agent hook add`、`self_hook add` 會驗 `entry_keys`，`08` Line 722 也寫編譯線用 `entry_keys` 驗 `@fn.hook` 的額外關鍵字「是不是這個事件收的」。前後直接矛盾。
    2. 造成 F16 不敢拿 `entry_keys` 來擋的唯一原因，是 `02` Line 196 把所有事件都能寫的通用鍵 `"config"` 錯放進了 `on_clock` 的 `entry_keys: ["clock", "every_cycles", "every_ms", "config"]`。如果 `entry_keys` 不拿來擋，那麼要么還得在程式碼裡留寫死的 `CLOCK_KEYS`（違背宣告化初衷），要么別的事件誤寫 `every_ms` 就不會被擋（行為倒退，見提案 B5）。

* **A23【建議】`interfaces.json` 裡的 `hook_points` 路徑在 `01` 與 `02` 混用 `lib/` 與 `py/`，在未 install 的原地測試與 install 後環境會不一致**
  * **位置**：`01-宣告格式.md`（Line 88 vs Line 100）；`02-現有的點改寫成宣告.md`（Line 133-137）；`09-施工計劃.md`「F21」（Line 876）。
  * **問題**：`01` Line 88 的 JSON 範例寫 `{"$env": "AOS_HOME", "$path": "/lib/aos/apps/hook/loop_points.json"}`，但 Line 100 的表格對 `eca-claude` 卻寫 `py/aos/apps/eca/hook_points.json`＋`py/aos/apps/mcp/hook_points.json`。F21 也提醒「測試在 `py/` 原地跑時不能寫死 `lib` 路徑」。若 `interfaces.json` 寫死 `/lib/aos/...`，在不跑 `install.py` 的單元測試裡讀 `$AOS_HOME/lib/...` 就會讀到舊檔或找不到檔（見提案 B3）。

* **A24【建議】`test_hook_point.py` 驗 `fired_in` 的規則對 `loop_points.json` 不成立**
  * **位置**：`01-宣告格式.md`（Line 70）；`02-現有的點改寫成宣告.md`（Line 150-165）；`03-誰讀宣告.md`（Line 294）；`09b-施工計劃-逐刀.md`「刀 1」（Line 899）。
  * **問題**：`03` 與 `09b` 刀 1 寫道：「測試：`fired_in` 列的原始檔裡找得到那個事件名的字串」。但在 `02` 的 `loop_points.json` 中，`after_start` 的 `fired_in` 是空陣列 `[]`，其餘三個點（`before_run`、`after_run`、`after_stop`）連 `fired_in` 鍵都沒寫（因為它們是由 `loop.json` 呼叫 `aos-hook fire` 發的，不在提供者的程式碼裡）。測試對 `fired_in` 為空或未寫時怎麼處理（例如規定 `provider == "aos-loop"` 時改驗範本 `loop.json`），需在刀 1 寫明。

---

## (B) 提案（讓設計變小、砍掉機制或更好的替代）

* **B1：砍掉「`agentlib/hooks.py` 每次讀清單順手補刪旗標」與「`aos-hook fire` 沒人聽自己刪旗標」，消除 Race 與讀清單的寫檔副作用；並把 `loop.json` 的四鍵縮成兩鍵**
  * **怎麼砍**：
    1. **旗標只由「寫入入口」與「啟動時」單向同步**：寫一個純函式 `sync_loop_flags(def_folder, stack)`，**只在**改變 hook 清單的地方（`aos-agent hook add/rm/reset`、`self_hook`、**gdb 下／刪斷點**）以及 agent 起跑那一次（`after_start` / `aos-hook check --agent`）呼叫。
    2. **拿掉 `agentlib/hooks.py` 每次讀清單時順手改旗標檔**，也**拿掉 `aos-hook fire` 發現沒人聽就反手刪旗標檔**。如此一來，`hooks.open` 與 `fire` 保持 100% 純讀取、無副作用，A1 的 TOCTOU Race 與 A2 的 gdb 漏扣問題同時徹底消失。
    3. **`loop.json` 不用多 `on_before_run_if`、`on_after_run_if` 兩個頂層鍵**：直接在 `aos-loop` 的 `Target` 單子物件裡支援一個通用選填鍵 `"if_exists": "<path>"`（例如 `"on_before_run": {"if_exists": {"$env": "AOS_STACK", "$path": "/hook_before_run.flag"}, "argv": [...]}`）。`loop.json` 頂層只多 `on_before_run`、`on_after_run` 兩個鍵（4 鍵變 2 鍵），且 `Target` 的 `if_exists` 語意內聚、不膨脹設定表。

* **B2：砍掉 `--field-file` 與 `loop.json` 裡的 `$prefix` 拼裝，改由 `--agent`（或宣告的 `fields`）自動讀取 `stage`，一次修掉 A7 與 A8**
  * **怎麼砍**：
    1. 既然 `loop.json` 已經傳了 `--agent {"$env": "AOS_CD"}` 且 `aos-hook` 本來就認得 `$AOS_STACK`，不需要在每份 `loop.json` 的 `argv` 裡手寫 `--field-file {"$env": "AOS_STACK", "$path": "/stage.txt", "$prefix": "stage="}`。
    2. 直接砍掉 `aos-hook fire` 的 `--field-file` 旗標（以及根本不存在的 `$prefix` 指示詞），讓六份範本的 `on_before_run`／`on_after_run` 跟 `on_start`／`on_stop` 長得一模一樣：
       `{"argv": ["aos-hook", "fire", "-q", "--agent", {"$env": "AOS_CD"}, "before_run"]}`。
    3. 由 `--agent` 在發 `before_run`／`after_run` 時自動填 `stage`：
       * 若 `$AOS_STACK/stage.txt` 存在，讀它；
       * **若 `stage.txt` 不存在（第一圈）且定義夾有 `fsm.json`，直接取 `fsm.json` 的 `start` 格（如 `"idle"`）**！這直接修掉了「第一圈 `stage` 是 `null`、`condition: "idle"` 比不中」（A7／F7）的缺陷；
       * 對沒有 `fsm.json` 的身體（如 `eca`），自然就是 `null`，也不用讓 `eca` 的 `loop.json` 寫死 `stage.txt`。
    4. 針對 A7 中 `after_run` 的 `stage` 是「轉移後的下一格」導致 `condition: "stage"` 語意錯亂的問題：建議把 `after_run` 的欄位正名為 `next_stage`（或由 `before_run`／`aos-fsm` 留下剛跑的那一格作為 `stage`），避免與 `before_run` 的 `stage` 混淆。

* **B3：在 `interfaces.json` 的 `hook_points` 支援「內建提供者名稱（或套件相對定位）」，砍掉 Python 端自寫 `$env`/`$path` 解析器（F3）並解決 `py/` vs `lib/` 路徑問題（A23／F21）**
  * **怎麼砍**：
    1. 原本設計要求在每隻 agent 的 `interfaces.json` 寫 `{"$env": "AOS_HOME", "$path": "/lib/aos/apps/hook/loop_points.json"}` 等長路徑，為此必須在 `hook_point.py` 裡重寫一套行程內 `$env`＋`$path` 解析器、寫 C++ 對照測試（F3），還會遇到未 install 時檔案在 `py/` 而非 `lib/` 的問題（F21）。
    2. **替代做法**：規定 `interfaces.json` 的 `hook_points` 清單項若是：
       * 內建提供者名（如 `"aos-loop"`、`"aos-eca"`、`"aos-mcp"`、`"agent-fsm"`），由 `hook_point.py` 直接以 Python 模組路徑（`os.path.dirname(__file__)` 相對位置）定位對應的 `.json` 檔；
       * 含 `.json` 的字串（如 `"hook_points.json"`），則照舊當成定義夾內的相對路徑。
    3. **好處**：
       * **完全砍掉 F3**（不用在 Python 裡解析 `{"$env": ..., "$path": ...}`，也不用跑 `aos-directive` 子行程）；
       * `interfaces.json` 變得極簡且易讀（例如 eca 只要寫 `"hook_points": ["aos-loop", "aos-eca", "aos-mcp"]`，fsm 寫 `["aos-loop", "hook_points.json"]`）；
       * 無論是在 `py/` 原地跑測試還是在 `install.py` 後的 `lib/` 跑，Python 套件內定位永遠指到同一棵樹下的宣告檔，徹底消除 `py/` 與 `lib/` 不一致。

* **B4：刪掉 `01` 驗證第 2 條「`block: true` 只准出現在 `phase: before`」（改為只禁 `phase: on`），讓 `after_verdict` 誠實保持 `phase: "after"`**
  * **怎麼改**：
    * 一個點能不能攔，已經由 `"block": true | false` 明確表達；gdb 要「扣住」還是「暫停」，則只看 `phase == "before"`（且 kernel 根本不用 gdb）。
    * 把第 2 條驗證改為「`block: true` 不得與 `phase: "on"` 同時出現」（或直接由 `block` 布林值自身決定能不能攔），就能讓 `kernel` 的 `after_verdict` 誠實記為 `"phase": "after", "block": true"`，不用為了遷就一條人造規則而把名叫 `after_verdict` 的事件謊報成 `"phase": "before"`（消除 A21）。

* **B5：把 `"config"` 歸入所有事件通用的標準格鍵，從 `on_clock` 的 `entry_keys` 拿掉，讓 `entry_keys` 直接取代寫死的 `CLOCK_KEYS`**
  * **怎麼改**：
    * 在 `hooks.json` 的驗證中，將 `"config"` 列入所有事件的通用合法鍵集合 `COMMON_ENTRY_KEYS = {"event", "run", "condition", "intercept", "async", "on_error", "timeout_ms", "config"}`。
    * `on_clock` 的 `entry_keys` 只寫 `["clock", "every_cycles", "every_ms"]`。
    * 任何事件的格只要出現不在 `COMMON_ENTRY_KEYS | set(point.get("entry_keys", []))` 裡的有名鍵（或反之：出現在任何宣告的 `entry_keys` 裡、卻不屬於當前事件的鍵），一律報 `HooksBad`。
    * **好處**：直接刪掉 `agentlib/hooks.py` 裡寫死的 `CLOCK_KEYS`，同時消除 `01`、`03`、`08`、F16 之間關於「`entry_keys` 到底拿不拿來擋」的自相矛盾（A22）。

* **B6：用一個「5 行薄殼或預設回退」消除刀 3、刀 5 對活樹與鄰線的破壞性時間窗**
  * **怎麼做**：
    1. **刀 2 拆 2a／2b**：2a 只加 `hook_point.py` 與 `agentlib/hooks.py` 的新把手（保留舊函式）並完成活樹 `install.py`；2b 再改 `templates/agent-fsm/*.py` 格程式（消除 A17）。
    2. **刀 3 保留 `hooks.EVENTS` 動態別名到刀 6**：刀 3 在 `agentlib/hooks.py` 留一行由預設宣告算出的 `EVENTS`，完全不碰 `py/aos/gdb/__init__.py`，等鄰線 `aos-gdb-wait-1120` 交件後在刀 6 一次收乾淨（消除 A18）。
    3. **刀 5 先停樹再換檔**：若堅持「proto8 當成沒有舊版、不留 `hook_fire` 轉呼叫殼」，則在 `09` 與 `09b` 的刀 5 明確把「**先停樹** → `install.py` 換 `aos-loop` 並刪 `hook_fire` ＋ 改活樹定義的 `loop.json` → **再起樹**」定為唯一合法的部署順序（消除 A19）。
