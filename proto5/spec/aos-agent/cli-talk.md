← [aos-agent](README.md)｜[spec 總導航](../README.md)

## 1.2 `say`：投一則話（09-24 試玩 r2 補）

（09-24 fix-r4 改）位置參數恰好一個＝TEXT，家用 `--target`；給兩個（舊的 `say dir TEXT`）＝用法錯 2、提示改用 `--target`；TEXT 空＝用法錯 2。
`--wait` 後面緊接的那個字不是數字、而且還沒有 TEXT 時，那個字就當 TEXT（`say --wait "你好"` 照樣是等 300 秒）。先讀驗 info 與 state（錯＝退 1），取 `input` 解出來的**第一條**當投遞點，
投 `{"role": "user", "content": TEXT}`，照 [agent.md §4.1](../agent/state.md) 的原子投檔：

- 投遞點是資料夾：寫 `<資料夾>/say-<epoch ns>-<pid>.json`（同資料夾 `.` 開頭 `.tmp` 結尾的暫存檔再 rename；資料夾不在就建）。
- 投遞點是單一檔：暫存檔 `link` 到那個名字，不蓋掉還沒被收的檔；EEXIST＝上一則還沒收，每 200 ms 重試、最多 10 秒，還在＝`InputBusy`、退 1。

沒 `--wait`：印 `said -> <投遞的絕對路徑>`、退 0。不要 `AOS_KERNEL_HOME`：它只放檔、讀檔，agent 沒登記也放得進去（只是沒人收）。
（09-24 試玩 r3 補）沒登記（K 取 `AOS_KERNEL_HOME`、沒設就用 `tick.json` 記的；兩個都沒有、或 K 帳本裡沒有 `agent-<資料夾名>`）時照樣投、照樣退 0，但 stderr 多一行 `aos-agent: warn: 目前沒登記、沒人處理：aos-agent start --target <dir>`；帳本讀不到就不警告。
（09-24 fix-r5 補）沒登記時 stdout 在 `said -> …` 下面再印一行 `已投入，start 後會處理，不要再說一次：aos-agent start --target <dir>`——話已經在 `input` 裡，start 之後會收，再說一次就會進記憶兩次。
（09-24 fix-r4 補）**暫停中照收**：手動暫停（§1.6）時照樣投、退 0，stderr 多一行 `aos-agent: warn: 已暫停，continue 後才會處理：aos-agent continue --target <dir>`；連敗暫停時同樣照投，警告說「連敗暫停中，修好原因後 continue 才會處理」。話留在 `input` 裡，`continue` 之後下一格照常收。
例子：`cd <家> && aos-agent say "現在幾點？" --wait`、`aos-agent say "現在幾點？" --target ~/agents/amy --wait 60`（`say -h` 也印這兩行，並寫明 `--wait` 不帶數字＝300 秒）。

**`--wait [秒]`**：（09-24 fix-r4 改：舊的 `--timeout-ms` 拿掉）投之前記下記憶長度 H0，投完就走 [§1.5](cli-listen.md) `listen --wait` 的**同一套等法**（程式裡是同一個函式），只多兩個條件：
投的檔已不在原路徑；記憶第 H0 則以後有一則 `content` 等於 TEXT 的 user、而且在最後那則 assistant 之前。
等法本身：每 200 ms 重讀 `state.json` 與記憶（讀到一半壞掉就下一輪再讀），`state` 是 `idle` 且 `batch`、`intake` 都是 null、最後一則是 assistant 而且是第 H0 則以後的 → 照 `listen --last` 的格式印那則回話、退 0。
逾時 stderr `aos-agent: Timeout: 等了 N 秒沒有新回話…`、stdout 印 `status`、退 101。
（09-24 fix-r5 補）**開始等之前先看一次、之後每輪都看**：下面這幾種不會自己好，立刻退 101，stderr 一行原因、stdout 先印一行 `已投入 <投遞路徑>，不要再說一次（照上面的原因修好後會處理）`（沒登記那種改成上面那句 `已投入，start 後會處理…`），再印 `status`。話都已經投了，不收回。
不等到逾時、立刻退 101 的，照這個先後判：（09-24 fix-r5 補）**kernel 家有問題**（§1.3 health 的 `kernel`：K 家缺目錄、停機中、daemon 沒在跑、kernel cpu 不在、tick 停住、帳本讀不到）＝`aos-agent: kernel: <health 那句>`；（09-24 試玩 r3 補）**沒登記**（判法同上；包括等到一半被 `stop`）＝stderr `aos-agent: unregistered: 目前沒登記、沒人處理：aos-agent start --target <dir>`；
（09-24 fix-r4 補）**手動暫停**＝`aos-agent: paused: 已手動暫停，continue 後才會處理：aos-agent continue --target <dir>`；**連敗暫停**（§9 的門）＝`aos-agent: stuck: …`；（09-24 fix-r5 補）K 帳本那筆 **`bad`**＝`aos-agent: bad: kernel 判壞了…`。
`恢復中`（池少 N 顆、daemon 在補，或搬池中）與 `重試中`（連敗未滿 3 次）會自己好，照常等。

（09-24 listen 微調）§1.5 `listen` 搬到 [cli-listen.md](cli-listen.md)。
