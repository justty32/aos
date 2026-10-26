[← 回入口](../2026-10-12-loop-daemon.md)｜上一份：[01-原文結論與三json](01-原文結論與三json.md)｜下一份：[03-遷移與未決](03-遷移與未決.md)

## 3. 決定：loop

- **每一圈**：等暫停解除 → 跑一次 → `runs` 加一 → 等間隔；inst 自己出錯那次至少隔 `error_wait_ms`。
- **`times` 是總數**：`runs < times` 才再起一次；跑到 `times` 就結束、退出（有 ctl 也一樣），想再跑就重新起；save 存 `times`。
- **ctl.json 定期讀**：每 `ctl_poll_ms` 看一次，跑的途中、等間隔途中都看。loop 從不寫 ctl.json。誰都能寫：人手、agent、daemon、kernel；兩個 loop 共用一個也不擋。
- **狀態物件**：`id`、`state`（waiting／running／paused／done／stopping／stopped）、`times`、`runs`、`last_code`、`last_error`、`ctl_mtime`、`pid`、`skipped`（叫 `stopping`／`stopped` 不叫 removing／removed：「移除」是表的事）。有給 `state` 就有變時整份寫（格式見 ctl 規範 §3.5）。
- **`last_code`**：每次跑完讀 inst.json 的 `exit` 檔；沒寫 `exit`＝null。
- **`run(path)`**：正常跑完回 None；loop 自己出錯丟 `LoopError`（含繼承 inst 的）。
- **收到 SIGINT／SIGTERM／SIGHUP**：收掉正在跑的子程式（SIGTERM，過 grace 再 SIGKILL）、不再起新的，退出碼 128＋N（參考）。
- **單獨跑**：ctl.json、state.json 慣例不放進 node 的資料夾，例如放在起它的人的工作目錄。

**loop 的退出碼**（只有 0／非 0 確定，數字供參考）：

| 算什麼 | 哪些情況 | 退出碼 |
|---|---|---|
| 繼承 inst | 這一次 inst 自己出錯、子程式根本沒起來（單子壞、找不到程式、不能執行、串流開不了…） | 沿用 inst 的碼 |
| loop 自己的 | 用法／參數不對（times、interval_ms 型別、TARGET 不對）；被訊號停掉 | 自己一個非 0（參考 125／128＋N） |
| 不算錯 | 子程式回非 0（只在 exit 檔）；ctl.json 不在、壞掉、不見；`times` 改小提早 done；`stop` 正常收工 | 0 |

結束時看最後一次：最後一次是 inst 自己出錯就沿用那個碼，被訊號停掉就 128＋N，否則 0。中途 inst 出錯但後來好了就繼續跑，只留在 `last_error`。

## 4. 決定：daemon

**daemon 是一個 loop**：身體＝掃一次控制資料夾；`times`、`interval_ms`、`paused`、`stop`、狀態物件、ctl.json 都跟 loop 一樣。

- **控制資料夾**＝身體的輸入（表的指令與轉給某個 loop 的指令），指令式、`.done`、照檔名順序，**維持現狀**（規則見 ctl 規範 §4）。
- **daemon 自己的 ctl.json**：`paused`＝不掃資料夾（指令堆著、底下的 loop 照跑；改回 false 就醒）；`stop`＝跟收到 SIGTERM 同義（有 `save` 先存、收掉全部 loop）；`stop.now`＝底下的 loop 也 `now`。不想存就送 SIGINT。`ctl` 路徑落在 `control_dir` 底下就拒絕。

**底下的 loop 是子程序**（使用者「用子程序」），daemon 跟它之間只靠兩個檔：寫它的 ctl.json、讀它的 state.json。

- **add**：`{"op": "add", "id": "/abs/clock-loop.json"}`，收 loop.json 路徑；id＝realpath。daemon 用 `Popen(["aos-loop", path], start_new_session=True)` 起它（整群收的是起它的人的選擇，不違反「argv[0] 程式自己不 setsid」）。daemon 不 `chdir`，相對路徑從 daemon 的 cwd 算。
- **add 也收 inst.json**（使用者 10-12 夜定）：當成只跑一次的 loop——daemon 自動包成 `{"inst": {"$ref": ...}, "times": 1}`，再照常起 aos-loop。判斷方式：頂層有 `"inst"` 的就是 loop.json。
- **包裝檔**：loop.json 有寫 `ctl`／`state` 就用它寫的；沒寫的，daemon 在 `work_dir/loops/<編號>/loop.json` 生一份包裝檔——用指示詞指回原檔（`"inst": {"$ref": "/abs/x.loop.json#/inst"}`，`times`、`interval_ms` 同樣 `$ref`），只補 `ctl`、`state` 指到同一個資料夾——然後起包裝檔。
- **控制**：pause／resume／set／add_times／remove 都變成「daemon 改那個 loop 的 ctl.json」（讀現在的、改欄位、寫暫存再改名）。daemon 是主要寫者但不獨占，人也可以直接改，後寫的算。`add_times`：daemon 讀 state.json 拿 `times`，加完寫回 ctl.json（不限次數＝Conflict）。
- **看狀態**：`get`／`list`／`state` 讀 state.json；state.json 還沒出現＝回 `starting`。「pause／remove 等停了才回」＝每圈看 state.json 是不是 `paused`／`stopped`（或行程已經結束），到了才寫 `.done`。
- **remove**：寫 `{"stop": {"val": true, "now": !wait}}` → 等行程結束 → 收屍、整群補 SIGKILL → 從表拿掉；回覆帶最後一份 state.json。
- **收到 SIGTERM**：有 `save` 先存；對每個 loop 的 session 送 SIGTERM；等 daemon.json 的 `grace_ms`，沒走的整群 SIGKILL；收屍；結束。SIGINT 同樣收、不存。
- **save／load**：每筆 `{"loop": "/abs/x.loop.json", "ctl": {…當下 ctl.json 的內容…}}`；`runs` 不存，load 回來從 0 數（要接續就自己把 `times` 調小）。load 時某個 loop.json 不在＝NotFound、全有全無；state.json 裡的 `pid` 還活著＝Exists。
- **巢狀 grace**：只當慣例（使用者定，記在 NORMS 待定）——daemon 10000、loop 2000、inst 自定，外層宜大於內層。
- **daemon 被 pause** 就是字面：不掃資料夾、指令堆著、loop 照跑。「把表上每個 loop 都 pause」另開指令，等 kernel 要用再說。
