# Argon（Gemini 4 Argon High）審 aos-gdb-1119 調查稿的原文（11-19，給第一版乙案施工前；逐字，沒改）

← [README](README.md)｜採納表：[08-Argon審與採納](08-Argon審與採納.md)

叫法：agy -p（--mode plan、--print-timeout 840s），提示＝調查稿 13 份全文＋py/aos/agentlib/hooks.py、py/aos/hook_run.py 附行號（約 160 KB，超過命令列上限，寫成檔放 --add-dir 的空夾、叫它只准讀那一個檔）；一次就過，沒遇到 Authentication required。提示裡沒有個資與憑證。

---

以下根據調查稿全文與 `py/aos/agentlib/hooks.py`、`py/aos/hook_run.py` 原始碼，分為 **(A) 審查** 與 **(B) 提案** 兩段回答。

---

## (A) 審查

### A1. 【一定要改】`hooks.py` 預設 `intercept: True` 與 `on_error: "stop"`，直接裝 hook 會因 stdout 非 JSON 或腳本異常觸發 daemon 連環重起（邊緣第 25 條）
- **問題根源**（讀 `hook_run.py` 第 30、169～178、209～217 行）：
  1. `DEFAULTS` 預設 `"intercept": True, "on_error": "stop"`。
  2. 在 `before_queue`、`before_tool`、`after_tool` 三個事件中，`EVENTS[event]["intercept"]` 非空（或 `block: True`）。只要 `intercept` 為 `True` 且退出碼為 `0`，`hook_run._changes()` 就會把 hook 的 `stdout` 當成 JSON object 解析（第 174 行 `json.loads(out)`）；若非空且不是合法 JSON dict，立刻丟 `ValueError("stdout is not JSON...")`。
  3. 只要 `aos-agent ctl pause --no-wait` 印出任何確認字樣到 stdout，或使用者的自訂 shell／Python 條件裡有 `echo`／`print()`，就會觸發 `ValueError` → `on_error == "stop"` 轉拋 `HookFailed` → FSM 該格退 1 → `aos-loop` 以 `RunFailed` 結束 → daemon 自動重起並連撞 4 次後徹底掛掉（`07` 的 T2 實測）。
- **改法**：
  1. `aos-gdb` 寫入 `hooks.json` 的每一格觸發器，必須顯式設 `"intercept": false` 與 `"on_error": "continue"`，並給定合理的 `"timeout_ms"`（例如 `10000`，避免自訂條件卡死整隻 agent）。
  2. 觸發器包裝腳本（wrapper）內部呼叫使用者條件與 `aos-agent ctl pause --no-wait` 時，必須把子呼叫的 `stdout` 重導向至 `stderr`（或 `/dev/null`），且最外層 `try ... except BaseException` 捕捉所有例外並記進除錯日誌，**永遠以 exit code `0` 結束**。

### A2. 【一定要改】`hooks.json` 的 `"condition"` 鍵只支援 4 個事件，寫錯事件或非原子寫檔會丟 `HooksBad` 直接弄死 agent
- **問題根源**（讀 `hooks.py` 第 42～52 行、`hook_run.py` 第 56～61 行）：
  - `EVENTS` 裡只有 `before_tool`、`after_tool`、`brain_failed`、`tool_added` 四個事件的 `"condition"` 為 `"name"`；其餘事件（如 `before_queue`、`after_queue`、`after_start`、`after_stop`、`on_clock`）的 `"condition"` 皆為 `None`。
  - 對 `"condition": None` 的事件在 `hooks.json` 填 `"condition"` 鍵，`validate_entry()` 會在 `hooks.load()` 階段直接丟 `HooksBad("event ... takes no condition")`。注意：**`HooksBad` 發生在載入清單時，不受 `on_error: "continue"` 保護**，會直接讓該格崩潰並引發連環重起。
  - 同理，若修改 `<stack>/hooks.json` 時沒有用「先寫暫存檔再 `os.replace`」（N-05），正在跑的 agent 讀到半截 JSON 也會丟 `HooksBad`。
- **改法**：
  1. 只有在「單純過濾工具名／腦名，且不涉及跨工具連續計數」時，才對上述 4 個事件使用 `hooks.json` 的 `"condition"` 欄位；其他條件一律收進觸發器腳本內判斷。
  2. 修改 `<stack>/hooks.json` 必須走原子替換（寫 `.hooks.json.<pid>.tmp` 再 `os.replace`），寫入前先過一次 `hooks.validate_entry()`。
  3. `attach()` 時先檢查目標定義夾 `interfaces.json` 有無宣告 `"hooks"`（`hooks.declared(def_folder)`，第 66 行）；若為 `None`，在 REPL 當場報錯，因為沒宣告時 `_layers()`（第 122 行）連 `<stack>/hooks.json` 都不會讀。

### A3. 【一定要改】hook 子行程內的 `$AOS_STACK` 是「hook 小格」而非「agent 的 stack」，直接靠環境變數找目標或寫字條會寫錯地方
- **問題根源**（讀 `hook_run.py` 第 134～142 行）：
  - `hook_run.run()` 執行的是 `aos-exec --stack <agent_stack>/hooks/<hook_name>/ <target>`。
  - `aos-exec` 會把 hook 行程的環境變數 `AOS_STACK` 設成 `<agent_stack>/hooks/<hook_name>/`（小格），而**不是** `<agent_stack>`，也不是 daemon 的 `.stack` 根目錄。
  - 真正的 `<agent_stack>` 是放在餵給 hook `stdin`（即小格內 `event.json`）的 `"stack"` 欄位（第 136 行 `doc = {"event": event, "hook": name, "stack": os.path.abspath(stack)}`）。
- **改法**：
  - 觸發器腳本必須從 `stdin`（或 `$AOS_STACK/event.json`）讀出 `doc["stack"]` 取得 `agent_stack`，並由 `os.path.dirname(os.path.dirname(agent_stack))`（或安裝觸發器時寫死在觸發器設定檔裡的 `daemon_stack` 與 `agent_name`）定位 daemon 的 `.stack`，呼叫 `aos-agent ctl pause --no-wait -d <daemon_stack> <agent_name>`。

### A4. 【一定要改】Race 1：hook 發 `ctl pause --no-wait`、寫字條、與 loop 真正停下之間的競態（含同格多工具呼叫與 `wait_paused()` 過早返回）
- **問題根源**：
  1. **字條與 `paused` 狀態的順序競態**：在 `before_tool` 發 `ctl pause --no-wait` 後，**當前這次工具仍然會繼續執行**，直到整個 `act` 格跑完退出，`aos-loop` 在兩格之間讀 `ctl.json` 才會把 `state.json` 改成 `paused: true`。
     - 若 `wait_paused()` 只等「字條檔出現」就返回：此時工具還在跑、`act.py` 還在寫 `history.jsonl`，使用者在 REPL 檢閱或改檔會跟正在跑的 `act.py` 互踩。
     - 反之，若 hook 先叫 `ctl pause --no-wait` 再寫字條：快工具可能在幾毫秒內結束、`state.json` 已變 `paused: true`，`wait_paused()` 醒來立刻叫 `p.why()` 時字條卻還沒寫完。
  2. **同一個 `act` 格內多工具／多事件連發的競態**：腦一次點名 3 個工具（或同一格內 `before_tool` 與 `after_tool` 先後觸發）時，`act.py` 會在**同一個格內**跑完所有工具呼叫才退出給 `aos-loop`。若後面觸發器直接覆寫單一字條檔，第一個真正觸發斷點的原因會被洗掉；若 `once=True` 沒在第一次觸發時立刻標記失效，同一格後續工具又會重複觸發。
- **改法**：
  1. **觸發器內順序固定**：先原子更新計數／`once` 狀態 → **先原子寫入字條** → **最後才執行 `ctl pause --no-wait`**。
  2. **`wait_paused()` 判定條件**：必須輪詢 `<agent_stack>/state.json` 直到 `paused == True`（且 `phase == "running"`），**絕不能**以字條檔出現當作已停下。
  3. **字條採用追加或列表（JSONL／依序紀錄）**：同一個暫停週期內若多個觸發器先後成立，全部追加進當次暫停的字條清單，`p.why()` 按時間列出（標明第一張為主因），不互相覆蓋。
  4. **語意誠實標示**：文件與 API 需明講 `before_tool` 預設是「在 `before_tool` 看到事件並排程暫停，於本格（`act`）結束後停在下一格開頭」；若使用者真的要「擋下這次工具不准跑」，可選填 `block=True`（由 wrapper 發完 `ctl pause --no-wait` 後以 exit code `10` 退出，利用既有 `BLOCK = 10` 機制攔下該工具）。

### A5. 【一定要改】Race 2：字條放哪、誰清，以及「在 shell 用 `aos-agent ctl resume` 放行」造成的過期字條（stale note）競態
- **問題根源**：
  - 使用者的核心體驗是「Python REPL + shell 指令混著用」（`05` 也強調「停住的那隻誰都能用 shell 續」）。
  - 如果字條只在 REPL 的 `p.resume()` 裡清除：當使用者在 shell 打 `aos-agent ctl resume ann` 放行，字條不會被清掉。之後使用者在 shell 手動 `aos-agent ctl pause ann`（或下次在 REPL 看 `p.why()`），`p.why()` 會讀到**上一次**留下的舊字條，謊報停因。
  - 另外，若字條放在 `<agent_stack>/hooks/<name>/` 小格內，`once=True` 的觸發器在觸發後若把自己拿掉（或使用者 `rm` 該觸發器），字條會連同小格一起消失或找不到。
- **改法**：
  1. **字條位置**：統一放在 `<agent_stack>/gdb/notes.jsonl`（與 hook 小格解耦，`once=True` 自刪後字條仍在）。
  2. **綁定控制窗序號（`ctl_seq`）防過期**：
     - `ctl.json` 每次下指令都有遞增的 `"seq"`，`state_flux.json` 會回寫 loop 已處理的 `ctl_seq`（見 `02` 第 543 行）。
     - 觸發器在呼叫 `aos-agent ctl pause --no-wait` **之後**，立刻讀一眼 `<agent_stack>/ctl.json` 的 `"seq"`（或寫字條時記錄當時 `ctl.json` 的 `seq + 1` 與時間戳）寫進字條。
     - `p.why()` 檢查：讀取目前 `<agent_stack>/state.json`（看 `paused` 是否為 `true`）以及 `ctl.json`／`state_flux.json` 的 `seq`。若目前 `paused == true`，但 `ctl.json` 的最新 `pause` 序號大於字條記錄的 `ctl_seq`，代表中間已經被 shell `resume` 過、現在這次是外部手動 `pause` 的，`p.why()` 就據實回答「目前為手動／外部 pause（無對應觸發器字條；上一筆歷史字條為…）」。
  3. **清理時機**：`p.resume()` 會把目前活躍字條標記為已放行（或清空 `active_notes`）；新觸發器發停時，若發現舊活躍字條的 `ctl_seq` 已過期，也會自動歸檔舊字條、只留本次暫停週期的新字條。

### A6. 【一定要改】「連續 N 次才算」（`times=N`）的計數位置與「真連續 vs 累計」陷阱
- **問題根源**：
  1. hook 每次事件都是獨立子行程，計數器必須落盤。
  2. **「連續 N 次」不能把過濾條件塞進 `hooks.json` 的 `"condition"`**：
     例如使用者設「連續 3 次呼叫 `write` 工具就停」（`event="before_tool", tool="write", times=3`）。如果在 `hooks.json` 填了 `"condition": "write"`，那 agent 呼叫 `write` → `read` → `write` → `write` 時，中間那次 `read` 根本不會進到這個 hook（被 `hook_run.matches()` 濾掉了），計數器不會歸零，結果變成「**累計** 3 次 `write` 就停」而非「**連續** 3 次 `write` 就停」！
  3. 同理，「工具連續回錯 N 次」（`after_tool`），中間只要有一次工具成功，計數就必須歸零；而且一旦達到 N 次觸發了 `pause`，**計數器必須當場歸零**，否則 `resume` 後第 `N+1` 次又會馬上停。
- **改法**：
  1. **計數存放位置**：放在該觸發器專屬的狀態檔 `<agent_stack>/gdb/triggers/<id>/state.json`（內含 `{"count": 0, "total_hits": 0, "fired": false}`），用同目錄 `.tmp` + `os.replace` 原子更新。當觸發器被 `rm` 或重新安裝時，一併刪除該目錄，確保不會殘留舊計數。
  2. **過濾下放**：只要 `times > 1`（要求連續 N 次），`hooks.json` 裡**不填** `"condition"`（讓同類事件每次都進 wrapper）：
     - 條件成立 → `count += 1`；若 `count >= times` 則將 `count = 0`（若 `once=True` 則標記 `fired = True` 並從 `hooks.json` 移除自己）、寫字條、發 `ctl pause --no-wait`。
     - 條件不成立 → 若 `count != 0`，將 `count = 0` 寫回狀態檔。
  3. 只有 `times == 1` 且僅比對單純工具名／腦名時，才把 `tool` 填進 `hooks.json` 的 `"condition"` 以省下無關工具的子行程開銷。

### A7. 【一定要改】自訂 Python 函式當條件在 hook 子行程執行的落地方案（避開 REPL `<stdin>` 的 `pickle`／`getsource` 死胡同）
- **問題根源**：
  - 在乙案，REPL 與 hook 是**兩個不同的行程**（且 REPL 關掉後 hook 仍要能跑）。
  - 使用者在標準 Python REPL（`>>>`）裡寫 `p.stop_when("after_tool", py=lambda ev: "error" in ev["content"])` 或互動定義 `def cond(ev): ...` 時：
    - 標準庫 `pickle.dumps(fn)` 對 `lambda` 與 `__main__` 互動函式會直接失敗（`PicklingError`）。
    - 標準庫 `inspect.getsource(fn)` 在標準 `python3` REPL（檔名為 `<stdin>`）會直接丟 `OSError: could not get source code`。
    - 專案限制 `lib` 為純標準庫（`hooks.py` 第 4 行），不能依賴第三方 `cloudpickle`／`dill`。
- **改法**：在純標準庫下支援三種輸入並於註冊時**當場乾跑驗證（dry-run）**：
  1. **Python 表達式／程式碼字串（最穩、首推）或外部檔案**：例如 `py="ev.get('name') == 'write'"` 或 `"./my_cond.py:check"`，直接寫入觸發器目錄的 `cond.py`。
  2. **一般 Python callable（`lambda` 或 `def fn(ev):`）**：
     - 先試 `inspect.getsource(fn)`（若來自 `.py` 檔或 IPython 可直接拿到原始碼）。
     - 若在標準 REPL `<stdin>` 拿不到原始碼，使用標準庫 `marshal.dumps(fn.__code__)` 將 bytecode 序列化，並把 `fn.__defaults__` 與 `fn.__closure__` 中的基本型別（`int/str/float/bool/None/list/dict/tuple`）一併序列化進觸發器設定檔；hook 子行程用 `types.FunctionType(marshal.loads(...), ...)` 還原執行。
  3. **註冊時立刻子行程／沙箱乾跑驗證**：在 REPL 呼叫 `stop_when(..., py=fn)` 的當下，立刻對一筆假 `event_doc` 試跑一次還原後的函式（或檢查 `fn.__code__.co_names` 是否引用了未綁定的 REPL 全域變數）。若引用了無法序列化的外部變數，**在 REPL 下斷點那一刻立刻報錯**，提示改用預設參數綁定（如 `lambda ev, x=x: ...`）或字串表達式，絕不等到 agent 跑到一半才在背景失敗。

### A8. 【建議】乙的設計要預留兩處小接口，才不會在接丙（外部觀察者）與丁時打架
- **問題根源**：
  1. 乙的觸發器是 hook，丙的觸發器是外部觀察者輪詢 stack 檔。如果乙把字條格式綁死在 `hooks/<name>/event.json` 或只認 hook 名字，丙加入時 `p.why()` 就得重寫。
  2. 丙在 REPL 裡寫條件 `w.stop_when(lambda s: ...)` 需要一個讀 stack 檔的視圖物件 `s`；乙在停下來檢閱時也需要讀 stack 檔的薄殼。若兩者各寫一套讀檔方法，API 會分裂。
- **改法**：
  1. **字條格式統一帶 `source` 與 `trigger_id`**：`<agent_stack>/gdb/notes.jsonl` 每筆字條固定含 `{"source": "hook" | "watch", "trigger_id": ..., "reason": ..., "ctl_seq": ...}`，`p.why()` 只讀這份檔，乙和丙就能無縫共用。
  2. **檢閱薄殼直接做在 `AgentDebug`（`p`）身上**：`p.stage()`、`p.state()`、`p.history()`、`p.observed()`、`p.last_request()`、`p.mailbox()` 既是人在 REPL 停下來檢閱的 API，將來做丙時把同一個 `p` 傳給 `w.stop_when(lambda p: ...)` 就能直接當條件的判斷依據。

### A9. 【建議】第一版可以砍掉、讓實作更小更穩的四件事
1. **砍掉「邊跑邊長」的包裝方法（如 `p.add_tool`、`p.set_system`、插 `fsm.json` 格）**：這些已有現成 `aos-agent tools add`、`system set` 可用（或留一個萬用 `p.agent_cmd(*args)` 薄殼即可）。照題目聚焦在「裝／列／拿掉觸發器、等停與看 `why`、檢閱 stack、續 `resume`」。
2. **砍掉丁案的 `action="log"`（只記不停）與 `debug=True` 預設大禮包**：AOS 本來就有 `observed.jsonl` 與 `hooks/<name>/event.json` 記錄事件；第一版觸發器動作只有一種：**條件成立就寫字條並 `ctl pause --no-wait`**。
3. **砍掉透過觸發器改寫事件內容（`intercept` 修改 `arguments`／`content`）**：第一版專注於「斷點＝停下來看」，一律設 `intercept: False`，直接消滅 stdout 污染風險。
4. **把現成條件與自訂條件收斂成同一個 runner**：不需要為「某工具被叫前」「工具回錯」「自訂 shell」「自訂 Python」寫四套不同的 hook 產生器；底層統一產生同一支 `runner.py`，把現成條件當成內建的 Python predicate 即可。

### A10. 總結判斷：有沒有任何一條問題會推翻「先乙」這個方向或使用者的定義？
- **沒有。沒有任何一條問題會推翻「先乙」的方向或使用者的斷點定義。**
- **理由**：
  1. 使用者定義「特定條件發生時，暫停 loop 或 fsm，停下來等待檢閱」，在 AOS 現有架構中，唯一能**事件驅動、不需輪詢、且能看到事件當下資料（如 `before_tool` 的參數、`after_tool` 的回傳內容）**的位置就是 agent 裡的 hook。
  2. 上述 A1～A7 找到的所有問題（`intercept` 預設值導致 stdout 報錯引發連環重起、部分事件不收 `condition`、`$AOS_STACK` 指向小格、字條與 `state.json` 的時序差、shell `ctl resume` 導致字條過期、`times=N` 連續計數歸零、`<stdin>` 函式序列化），**100% 都能在「不改 hook 機制、不改 daemon／aos-agent C++」的前提下，由 `aos-gdb` 的註冊端與觸發器包裝腳本（wrapper）完全解掉**。
  3. 唯一需在使用上對齊預期的語意細節是：`ctl pause` 是停在兩格之間，因此在 `before_tool` 發 `pause` 時，若不擋下工具（不回 `10`），該次工具仍會執行完才在 `act` 格結束後停住；若要在工具執行前攔住副作用，只需在 `stop_when` 提供選填的 `block=True`（發 `pause` 並回 `10`），同樣完全在既有 hook 機制內。

---

## (B) 提案：乙案第一版具體設計

### B1. Python REPL API 形狀（模組 `aos_gdb`）

以「每個動作背後只是讀寫 stack 檔或呼叫一條 `aos-agent` 指令」為原則，REPL 關閉後觸發器仍獨立運作，shell 與 REPL 可隨時混用：

```python
import aos_gdb as g

# 1. 接上已存在的 agent（定位 daemon .stack 與該 agent 的 stack、定義夾，檢查 interfaces.json 有無宣告 hooks）
p = g.attach("ann", stack_root=".stack")   # stack_root 預設從環境變數或 CWD 找 .stack

# 2. 下條件觸發器（回傳 trigger_id，例如 "bp_1"；也可指定 name="my_bp"）
# 2a. 現成條件：某工具要被叫之前（event="before_tool"）
p.stop_when("before_tool", tool="write")
p.stop_when("before_tool", tool="write", once=True)         # 只停一次，觸發後自動從 hooks.json 移除
p.stop_when("before_tool", tool="write", times=3)           # 連續 3 次叫 write 才停
p.stop_when("before_tool", tool="rm", block=True)           # 選填：發 pause 同時回 10 擋下該次工具執行

# 2b. 現成條件：工具回錯（event="after_tool", error=True；可搭配 tool="math" 或不指名工具涵蓋未來新增工具）
p.stop_when("after_tool", error=True)                       # 任何工具回 "<tool>: error: <Code>" 就停
p.stop_when("after_tool", tool="math", error=True, times=2) # math 連續回錯 2 次才停

# 2c. 自訂條件：一段 shell（stdin 為 event.json，環境變數帶 $AOS_GDB_AGENT_STACK；exit 0 為條件成立，非 0 為不成立）
p.stop_when("after_tool", sh='jq -e ".content | length > 5000" >/dev/null')

# 2d. 自訂條件：Python 函式或表達式字串（吃 event dict，回傳 bool）
p.stop_when("before_queue", py=lambda ev: "緊急" in ev.get("content", ""))
p.stop_when("after_tool", py="len(ev.get('content', '')) > 5000", times=2)

# 3. 列出與拿掉觸發器
p.triggers()                  # 回傳 list[dict]：各觸發器的 id, event, condition 摘要, times, count(目前連續次數), once
p.rm_trigger("bp_1")          # 拿掉單一觸發器（先從 hooks.json 移除，再刪 gdb/triggers/bp_1）
p.clear_triggers()            # 拿掉所有 aos-gdb 裝的觸發器（不動使用者原本非 gdb_ 的 hook）

# 4. 看停沒停、等它停、看為什麼停
p.is_paused()                 # 讀 <agent_stack>/state.json 的 paused 欄位 -> bool
p.wait_paused(timeout=30.0, poll=0.1)  # 輪詢直到 state.json 的 paused == True；逾時丟 TimeoutError
p.why()                       # 讀字條並比對 ctl.json/state_flux.json 的 seq，回傳本次停因清單（若在 REPL 直接印出可讀摘要並回傳 list[dict]）

# 5. 檢閱（讀 stack 檔的薄殼，不綁內部未承諾函式）
p.where()                     # 回傳 {"stage": "think", "phase": "running", "paused": True, "pid": 12345}
p.history(last=5)             # 讀 history.jsonl 最後 N 筆
p.observed(last=10)           # 讀 observed.jsonl 最後 N 筆
p.last_request()              # 讀 think/request.json（最後一次送給腦的完整請求 dict）
p.mailbox()                   # 列出 queue/new/ 裡排隊未收的信與 letters.json
p.stderr(lines=20)            # 讀 stderr.txt 最後 N 行

# 6. 續（放行）與互動輔助
p.resume()                    # 清空／歸檔活躍字條，並呼叫 aos-agent ctl resume <name>
p.pause()                     # 手動呼叫 aos-agent ctl pause <name>
p.say("整理 notes")           # 薄殼：subprocess 呼叫 aos-agent say -t <name> ...
```

- **「工具回錯」（`error=True`）的內建判定規則**：
  在 `after_tool` 事件中，檢查 `ev.get("content", "")` 是否包含符合 AOS 規範的錯誤行（即首行或任一行匹配 `^([a-zA-Z0-9_.-]+):\s*error:\s*(\S+)`，或 `ev.get("is_error") is True`），匹配時把抓到的錯誤行寫進字條的 `reason`（例如 `"math: error: ArgBad ..."`）。

### B2. 檔案佈局（全收在 `<agent_stack>` 內，不污染定義夾）

假設目標 agent 為 `ann`，stack 在 `<tree>/.stack/procs/ann/`：

```text
<tree>/.stack/procs/ann/
├── hooks.json                          # stack 疊層的 hook 清單（aos-gdb 只管 "gdb_" 前綴的項目）
├── hooks/
│   └── gdb_bp_1/
│       └── event.json                  # 由 hook_run.py 自動寫入的當次事件（也是 hook 行程的 $AOS_STACK）
└── gdb/                                # aos-gdb 專用夾
    ├── active_notes.jsonl              # 本次暫停週期的字條（可多筆，每行一個 JSON object）
    ├── notes_history.jsonl             # 歷次暫停字條的歷史流水帳（resume 時從 active 歸檔至此）
    └── triggers/
        └── gdb_bp_1/
            ├── spec.json               # 觸發器規格（id, agent, daemon_stack, agent_stack, event, tool, error, sh, py_source/py_code, times, once, block）
            ├── state.json              # 計數與狀態：{"count": 0, "total_hits": 0, "fired": false}
            └── run.py                  # chmod +x 的可執行檔（#!/usr/bin/env python3），作為 hooks.json 的 handler
```

1. **`<agent_stack>/hooks.json` 寫入的單格形狀**（完全符合 `hooks.py` 與 `hook_run.py` 驗證）：
   ```json
   {
     "hooks": {
       "gdb_bp_1": {
         "event": "before_tool",
         "handler": "gdb/triggers/gdb_bp_1/run.py",
         "condition": "write",
         "intercept": false,
         "async": false,
         "on_error": "continue",
         "timeout_ms": 10000
       }
     }
   }
   ```
   - 註 1：`handler` 用相對路徑 `"gdb/triggers/gdb_bp_1/run.py"`，因為 `hook_run.complete()` 將 `entry["base"]` 設為 `hooks.json` 所在目錄（即 `<agent_stack>`），`target()` 會自動解成 `<agent_stack>/gdb/triggers/gdb_bp_1/run.py`。
   - 註 2：只有當 `block=True`（且事件在 `EVENTS` 中 `"block": True`，即 `before_queue` 或 `before_tool`）時，才把 `"intercept"` 設為 `true`（因為 `hook_run.py` 第 211 行規定 `entry["intercept"]` 為 `True` 才會處理 `code == BLOCK`），同時 `run.py` 嚴格保證 stdout 不印任何東西。
   - 註 3：如 A2 與 A6 所述，只有 `times == 1` 且事件屬於 `("before_tool", "after_tool", "brain_failed", "tool_added")` 且無需跨工具重置計數時，才在 `hooks.json` 放 `"condition"`；否則由 `run.py` 內部比對 `spec.json` 的 `tool`。

2. **字條（`active_notes.jsonl` 單行）格式**：
   ```json
   {
     "trigger_id": "bp_1",
     "hook": "gdb_bp_1",
     "source": "hook",
     "event": "after_tool",
     "stage": "act",
     "reason": "after_tool (math): math: error: ArgBad - missing argument x",
     "count": 2,
     "times": 2,
     "blocked": false,
     "ctl_seq": 4,
     "at": 1763515450.123,
     "event_preview": {"name": "math", "content": "math: error: ArgBad - missing argument x"}
   }
   ```

3. **`run.py`（hook 觸發器執行流程，照順序防 race）**：
   1. 最外層 `try ... except BaseException` 包住，確保絕不以非 `0`（或非 `10`）退出。
   2. 從 `sys.stdin` 讀取 `event_doc`，並讀取同目錄的 `spec.json` 與 `state.json`。
   3. 若 `state.get("fired")` 為 `True`（`once=True` 已觸發過，但同一格還沒退完又進來第二次），直接 `sys.exit(0)`。
   4. **判斷條件**：
      - 若 `spec["tool"]` 有指定且 `event_doc.get("name") != spec["tool"]` → `matched = False`。
      - 否則依序檢查 `spec["error"]`、`spec["sh"]`（以 `subprocess.run(sh, shell=True, input=raw_event, stdout=sys.stderr, stderr=sys.stderr)` 跑，returncode 0 為 True）、`spec["py"]`（呼叫還原後的 Python 函式 `fn(event_doc)`，執行期間暫時將 `sys.stdout` 導向 `sys.stderr`）。
   5. **更新連續計數（原子寫 `state.json`）**：
      - 若 `not matched`：若 `state["count"] != 0`，將 `state["count"] = 0` 原子寫回 `state.json`；`sys.exit(0)`。
      - 若 `matched`：`count = state["count"] + 1`。若 `count < spec["times"]`，將 `state["count"] = count` 原子寫回 `state.json`；`sys.exit(0)`。
      - 若 `count >= spec["times"]`（達標！）：將 `state["count"] = 0`、`state["total_hits"] += 1`、若 `spec["once"]` 則 `state["fired"] = True` 原子寫回 `state.json`。
   6. **若 `spec["once"] == True`**：原子讀取 `<agent_stack>/hooks.json`，刪掉 `"gdb_bp_1"` 這一格並 `os.replace` 寫回（保留 `gdb/triggers/gdb_bp_1/` 目錄與字條供檢閱）。
   7. **發停與寫字條（防過期與防競態）**：
      - 讀取 `<agent_stack>/state.json` 與 `<agent_stack>/ctl.json`：若 `state.json` 目前 `paused == False`，且 `active_notes.jsonl` 裡舊字條的 `ctl_seq` 小於等於目前 `ctl.json` 的 `seq`，先把舊的 `active_notes.jsonl` 追加歸檔進 `notes_history.jsonl` 並清空。
      - 預測或讀取即將寫入的 `ctl_seq`（目前 `ctl.json` 的 `seq + 1`），**先將本次字條寫入 `active_notes.jsonl`**。
      - 呼叫 `subprocess.run(["aos-agent", "ctl", "pause", "--no-wait", "-d", spec["daemon_stack"], spec["agent"]], stdout=sys.stderr, stderr=sys.stderr)`。
      - 讀回 `<agent_stack>/ctl.json` 的實際 `seq`，若與預估不同則更新字條的 `ctl_seq`。
   8. 若 `spec["block"] == True`則 `sys.exit(10)`，否則 `sys.exit(0)`。

### B3. 測試情境（驗證第一版必過的 8 個案例）

建議在暫存樹（搭配 `fake`／劇本腦與慢腦）用 Python `unittest` 跑以下 8 個情境：

1. **T1 現成條件 `before_tool` + `once=True` + 檢閱 + `resume`**：
   - 對 `ann` 下 `p.stop_when("before_tool", tool="peek_now_time", once=True)`，`p.say(...)`，`p.wait_paused()`。
   - 驗證：`p.is_paused() == True`、`p.where()["stage"] == "think"`、`p.why()` 顯示 `before_tool: peek_now_time`、`p.triggers()` 中該 `once` 觸發器已自動卸除；呼叫 `p.resume()` 後 agent 答完，第二次再叫同一工具不再停。
2. **T2 現成條件 `after_tool` + `error=True`（工具回錯）**：
   - 讓腦呼叫一個會回 `math: error: ArgBad` 的工具，掛 `p.stop_when("after_tool", error=True)`（不指名工具）。
   - 驗證：正常工具不觸發；回錯工具觸發暫停，`p.why()` 包含 `"math: error: ArgBad"`。停住時用 `aos-agent tools add` 動態新增另一個會回錯的工具 `bad2`，`resume` 後呼叫 `bad2` 也能被同一條觸發器攔住（驗證邊跑邊長相容性）。
3. **T3 「連續 N 次才算」（`times=3`）的真連續重置測試**：
   - 掛 `p.stop_when("after_tool", error=True, times=3)`。
   - 讓劇本依序跑：**錯 → 錯 → 對（成功） → 錯 → 錯 → 錯**。
   - 驗證：前兩次錯後 `count` 為 2；第三次成功後 `count` 歸 0；第四、五次錯不停；第六次（連續第 3 次錯）才真正暫停，且暫停後 `state.json` 的 `count` 已歸 0。
4. **T4 自訂 Python 函式與自訂 shell 條件（含 stdout 雜訊防呆）**：
   - 掛一個內部會 `print("debug noise")` 的 Python lambda `p.stop_when("after_tool", py=lambda ev: (print("noise"), "target" in ev.get("content", ""))[1])`，以及一段會 `echo noise` 的 shell 條件。
   - 驗證：不會因為 `stdout` 非 JSON 而觸發 `HookFailed` 或 daemon 重起；條件成立時正常暫停。
   - 另測：自訂條件故意 `raise RuntimeError("boom")` 或 `exit 1`，驗證 agent **不會掛掉、不會重起**（`on_error: continue` + wrapper 兜底生效）。
5. **T5 標準 REPL `<stdin>` 閉包序列化乾跑失敗保護**：
   - 在測試中模擬 `co_filename == "<stdin>"` 的 lambda，若捕捉了不可序列化的外部物件（如 socket 或開啟的 file object），驗證 `p.stop_when()` **當場拋出明確例外**，不會把壞 hook 裝進 `hooks.json`。
6. **T6 同一個 `act` 格內多個觸發器同時成立**：
   - 同時掛 `before_tool` 與 `after_tool` 兩個觸發器（或單一 `act` 格連叫兩個工具都命中）。
   - 驗證：`p.wait_paused()` 等到 `act` 格真正結束、`state.json` 為 `paused: true` 才返回；`p.why()` 能讀出兩張字條（第一張標為主因），不會被後者洗掉。
7. **T7 REPL 與 shell 混用（過期字條防呆）**：
   - 觸發器停住 `ann` 後，**不叫 `p.resume()`**，改用 shell 跑 `aos-agent ctl resume ann` 放行；接著用 shell 跑 `aos-agent ctl pause ann` 手動暫停。
   - 驗證：此時在 REPL 呼叫 `p.why()`，能透過 `ctl_seq` 比對發現目前是外部手動暫停，不會把上一次觸發器的舊字條當成這次的停因。
8. **T8 `before_tool` 搭配 `block=True`（事前攔截副作用）**：
   - 掛 `p.stop_when("before_tool", tool="write", block=True, once=True)`。
   - 驗證：腦點名 `write` 時，工具**沒有真正執行**（檔案未被寫入），`history.jsonl` 記有 blocked 訊息，且 `act` 格結束後 agent 停在 `paused: true`，`p.why()` 標明 `blocked: True`。
