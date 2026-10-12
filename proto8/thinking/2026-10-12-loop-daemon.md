# 2026-10-12 loop／daemon：loop 包一個 inst，daemon 管多個 loop、自己也是一個 loop

← [討論紀錄](README.md)｜程式現況：[proto8/lib](../lib/README.md)｜規範：[NORMS](../NORMS.md)｜前一份：[tasks 與 tick-tock](2026-10-12-tasks-ticktock.md)｜同夜：[inst 進 json](2026-10-12-inst-json.md)、[ctl 規範](2026-10-12-ctl-norms.md)

> 10-12 夜照使用者要求精簡成「原文整理、決定、結論、未決」；AI 的現況分析、好處與坑、各題選項、被推翻的設計（loop 的 ctl 是資料夾、daemon 底下的 loop 是執行緒、`want()`、命令列旗標、`now` 獨立旗子）、轉述錯誤的段落都拿掉了。

## 0. 使用者原文（語音轉文字，大意照記）

第一段（10-12 晚回頭看程式，說現在的架構不對）：

> inst 這塊沒啥好說的，就那樣，從命令行，到 python 函數，就那樣。只是 loop 這塊，我認為他是一個 inst 的包裝，也就是對單一 inst，添加多次、間隔時間這樣的呼叫，並且添加 ctl，也就是 daemon 那塊的 ctl，只是說這是只針對單一 id 的。然後 daemon 則是管理多個 loop 的，而 daemon 本身也是一個 loop，會持續吃 ctl。

第二段：

> loop 這塊，他應該更簡單一些，就是只指定一個 ctl.json 檔案，定期讀，或是每次間隔的時候讀。然後 daemon 這塊才是資料夾。

第三段（10-12 深夜）：結束碼不要想太多，唯一確定的慣例是 0＝正常、非 0＝錯誤，其他只供參考；loop 本身出錯（包括跑 inst 的過程出錯）就回非 0，其他順其自然；**loop 要有命令列**；inst 的 `run()` 只吃一個 inst json 檔的路徑，跟命令列一致。

第四段（更正）：

> inst 那塊錯了，我是說，就直接返回 inst 本身的結束碼就好，json 寫的那個呼叫的結束碼會自然輸出到 json 中定義的 exit 那邊。loop 也是，loop 本身的出錯就是那樣，只是說 loop 他本身是 inst 的擴展，所以他的錯誤碼有些會繼承於 inst。

第五段：「全部按照我說的改。寫。」

第六段：

> inst 格式就這樣。然後 loop 那塊，我們在使用 aos-loop xxx.json 的時候，那個 xxx.json 的格式可以是繼承於 inst 格式，但是添加更多 key。我是建議把 inst 格式的東西包進 "inst":{...}，然後外層再去添加 aos-loop 需要的東西，比如 ctl.json 的路徑，間隔之類。

第七段：

> daemon 也可以。這樣子 aos-inst/loop/daemon 的命令行，就都可以是很簡單的 aos-zzz xxx.json。

第八段：

> 間隔那塊有疑慮的話就用選項。用子程序。ctl 格式之後要定下規範。剩下都按照建議。

同夜順帶講了代理人＝一個 loop 跑「切狀態機一步」的 inst，原話在 [inst 進 json §5](2026-10-12-inst-json.md#5-使用者順帶講的代理人)。

## 1. 結論：三層各一句

- **inst**：跑一次。`aos-inst x.json`／`run(path)`。
- **loop**：**一個** inst，跑 N 次、隔 M 毫秒，一邊定期讀**一個 ctl.json**（宣告式）。`aos-loop x.json`／`run(path)`。
- **daemon**：很多個 loop 的表；ctl 是**資料夾**（指令式、`.done`）；它**自己也是一個 loop**——身體（每一圈做的事）＝掃一次控制資料夾，自己另有一個 ctl.json。

這是 10-11「inst → loop → node → daemon」（CONCEPTS C-36）落到程式：loop 服務一個 node，daemon 統管很多個 loop。

## 2. 決定：三個 json，一個手感

命令列一律 `aos-zzz xxx.json`、一個引數，`run(path)` 也只吃那個路徑；**相對路徑一律從呼叫者的 cwd 算**。

- **只在啟動時讀一次**（使用者 10-12 夜定）：loop 啟動時讀一次 loop.json，包括 `inst` 那格和其中的指示詞，之後不再重讀；執行中要改設定只能透過 ctl.json。daemon.json 也比照辦理。

| 檔 | 命令列 | 外層 key | 裡面 |
|---|---|---|---|
| inst.json | `aos-inst x.json` | `argv`、`cwd`、`envs`、`stdin`／`stdout`／`stderr`、`exit`＋布林、`timeout_ms`、`grace_ms`（見 [inst 進 json](2026-10-12-inst-json.md)） | — |
| loop.json | `aos-loop x.json` | `times`、`interval_ms`、`interval_mode`、`grace_ms`、`ctl`、`ctl_poll_ms`、`state`、`error_wait_ms` | `inst`：一份 inst.json 格式，或 `{"$ref": …}` |
| daemon.json | `aos-daemon x.json` | loop 那一組（`times`、`interval_ms`、`ctl`、`ctl_poll_ms`、`state`、`grace_ms`）＋ `control_dir`、`load`、`save`、`work_dir` | 沒有 `inst`（身體內建＝掃資料夾）；表上每個 loop 是一支 `aos-loop` 子程序 |

### 2.1 loop.json

```jsonc
{
  "inst": {                          // 一份完整的 inst.json 格式，原樣照 inst 規則解
    "argv": ["aos-tick", "clock"],
    "exit": "clock.exit", "exit_append": true
  },
  // 要指向一份現成的 inst.json，用既有的指示詞："inst": {"$ref": "job/inst.json"}

  "times": null,                     // 總共跑幾次（總數，含已跑過的）；null＝不限；沒寫＝1
  "interval_ms": 5000,               // 間隔；沒寫＝0
  "interval_mode": "after",          // "after"＝跑完再隔 interval_ms（預設）；"fixed"＝每 interval_ms 到點起一次，
                                     //   跑超過週期就跳過錯過的拍、對齊下一拍起（不補跑、不重疊），state 記 skipped
  "grace_ms": 2000,                  // 收掉 loop 時給子程式多久
  "ctl": "clock-ctl.json",           // 選填：ctl.json 路徑；沒寫＝沒有控制，只能用訊號
  "ctl_poll_ms": 1000,               // 選填：多久看一次 ctl.json
  "state": "clock-state.json",       // 選填：狀態回寫到哪；在 daemon 底下沒寫的，daemon 替它補
  "error_wait_ms": 1000              // 選填：inst 自己出錯後至少隔多久再試
}
```

- 外層只放 loop 自己的事；`timeout_ms` 是單子的事，在 `inst` 那格。
- **誰蓋過誰**：loop.json 外層是初始值；ctl.json 有寫的欄位蓋過，沒寫的回初始值（ctl.json 的格式見 [ctl 規範](2026-10-12-ctl-norms.md)、NORMS N-06～N-08）。
- **相對路徑**：`inst` 裡照 inst 規則（`cwd` 從呼叫者 cwd 算，串流與 `exit` 從解出來的 `cwd` 算）；外層的 `ctl`、`state` 也從呼叫者 cwd 算；`$ref` 的檔名同樣（指示詞 lib 的 base_dir 整趟不換）。
- **只讀一次**：`inst` 那格與外層的 key 都只在起來時讀一次；途中要改走 ctl.json。
- **id**＝loop.json 的 realpath。兩份 loop.json `$ref` 同一份 inst.json＝兩個 loop，合法。

### 2.2 daemon.json

```jsonc
{
  "control_dir": "ctl/",             // 必填：身體的輸入（指令資料夾、.done）
  "load": "table.json",              // 起來先載（失敗＝起不來）
  "save": "table.json",              // 收到 SIGTERM／ctl 的 stop 先存

  "times": null,                     // 掃幾圈就走；null＝不限（1＝把這批指令處理完就走）
  "interval_ms": 200,                // 每圈隔多久（原 control_poll_ms）
  "ctl": "daemon-ctl.json",          // 控制 daemon 這個 loop（paused＝不掃、stop＝收工、interval_ms）；不能放在 control_dir 裡
  "ctl_poll_ms": 1000,
  "state": "daemon-state.json",      // 選填
  "work_dir": "loops/",              // 替沒寫 ctl／state 的 loop 生包裝檔的地方；預設 control_dir 旁的 loops/
  "grace_ms": 10000                  // 收 loop 行程時等多久
}
```

- 跟舊 config 的差別：`control_poll_ms` 改名 `interval_ms`；`stop_poll_ms` 拿掉（併進 `ctl_poll_ms`）；多 `times`、`ctl`、`ctl_poll_ms`、`state`、`work_dir`、`grace_ms`。
- 沒有 `inst` 格：daemon 的身體是內建的掃資料夾。
- daemon 自己的退出碼 0／1 不動；SIGINT 收、不存，SIGTERM 先存再收。

## 3. 決定：loop

- **每一圈**：等暫停解除 → 跑一次 → `runs` 加一 → 等間隔；inst 自己出錯那次至少隔 `error_wait_ms`。
- **`times` 是總數**：`runs < times` 才再起一次；跑到 `times` 就結束、退出（有 ctl 也一樣），想再跑就重新起；save 存 `times`。
- **ctl.json 定期讀**：每 `ctl_poll_ms` 看一次，跑的途中、等間隔途中都看；原本的 `stop_poll_ms` 併進來。loop 從不寫 ctl.json。誰都能寫：人手、agent、daemon、kernel；兩個 loop 共用一個也不擋。
- **狀態物件**：`id`、`state`（waiting／running／paused／done／stopping／stopped）、`times`、`runs`、`last_code`、`last_error`、`ctl_mtime`、`pid`、`skipped`。舊的 `removing`／`removed` 改叫 `stopping`／`stopped`（「移除」是表的事）。有給 `state` 就有變時整份寫（格式見 ctl 規範 §3.5）。
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

- **add**：`{"op": "add", "id": "/abs/clock-loop.json"}`，收 loop.json 路徑，`how` 不用了；id＝realpath。daemon 用 `Popen(["aos-loop", path], start_new_session=True)` 起它（整群收的是起它的人的選擇，不違反「argv[0] 程式自己不 setsid」）。daemon 不 `chdir`，相對路徑從 daemon 的 cwd 算。
- **add 也收 inst.json**（使用者 10-12 夜定）：當成只跑一次的 loop——daemon 自動包成 `{"inst": {"$ref": ...}, "times": 1}`，再照常起 aos-loop。判斷方式：頂層有 `"inst"` 的就是 loop.json。
- **包裝檔**：loop.json 有寫 `ctl`／`state` 就用它寫的；沒寫的，daemon 在 `work_dir/loops/<編號>/loop.json` 生一份包裝檔——用指示詞指回原檔（`"inst": {"$ref": "/abs/x.loop.json#/inst"}`，`times`、`interval_ms` 同樣 `$ref`），只補 `ctl`、`state` 指到同一個資料夾——然後起包裝檔。
- **控制**：pause／resume／set／add_times／remove 都變成「daemon 改那個 loop 的 ctl.json」（讀現在的、改欄位、寫暫存再改名）。daemon 是主要寫者但不獨占，人也可以直接改，後寫的算。`add_times`：daemon 讀 state.json 拿 `times`，加完寫回 ctl.json（不限次數＝Conflict）。
- **看狀態**：`get`／`list`／`state` 讀 state.json；state.json 還沒出現＝回 `starting`。「pause／remove 等停了才回」＝每圈看 state.json 是不是 `paused`／`stopped`（或行程已經結束），到了才寫 `.done`。
- **remove**：寫 `{"stop": {"val": true, "now": !wait}}` → 等行程結束 → 收屍、整群補 SIGKILL → 從表拿掉；回覆帶最後一份 state.json。
- **收到 SIGTERM**：有 `save` 先存；對每個 loop 的 session 送 SIGTERM；等 daemon.json 的 `grace_ms`，沒走的整群 SIGKILL；收屍；結束。SIGINT 同樣收、不存。
- **save／load**：每筆 `{"loop": "/abs/x.loop.json", "ctl": {…當下 ctl.json 的內容…}}`；`runs` 不存，load 回來從 0 數（要接續就自己把 `times` 調小）。load 時某個 loop.json 不在＝NotFound、全有全無；state.json 裡的 `pid` 還活著＝Exists。
- **巢狀 grace**：只當慣例（使用者定，記在 NORMS 待定）——daemon 10000、loop 2000、inst 自定，外層宜大於內層。
- daemon 不再 import `aos_loop`。
- **daemon 被 pause** 就是字面：不掃資料夾、指令堆著、loop 照跑。「把表上每個 loop 都 pause」另開指令，等 kernel 要用再說。

## 5. 遷移步驟（跟 inst-json 那份一起做）

1. **拆 loop**：舊 `_Inst` 變成公開的 loop；`times` 改總數；狀態字 `removing`／`removed` → `stopping`／`stopped`；讀 ctl.json（stat 三元組判變、壞檔整份不採用、印一次）；寫 state.json（含 `pid`、`skipped`）；`aos-loop x.json` 命令列與 `run(path)`；接訊號、退出碼照 §3 的表。
2. **結束碼**：`aos_inst` 命令列與 `run()` 只說 inst 自己（正常 0／None，自己出錯非 0／`InstError`）；loop 每次跑完讀 `exit` 檔拿 `last_code`；**tasks：seq／if／not 跑完去讀該 inst 的 exit 檔來判斷，inst.json 沒寫 `exit` 的就當拿不到碼（印一行、算自己出錯）**；par 照參數順序讀各自的 exit 檔。
3. **daemon**：daemon.json 新欄位（`control_poll_ms`→`interval_ms`、拿掉 `stop_poll_ms`、加 `ctl`／`ctl_poll_ms`／`state`／`times`／`work_dir`／`grace_ms`）；自己是一個身體＝掃一次的 loop、自己讀 ctl.json；表上每筆是 `aos-loop` 子程序；包裝檔；控制＝改 ctl.json、看狀態＝讀 state.json、等停了才回＝等 state.json；SIGTERM 收尾；save／load 新格式；`add` 收 loop.json 路徑。
4. **文件**：`lib/README.md` 三段重寫；[CONCEPTS C-36](../CONCEPTS.md) 加「10-12 落實：loop＝一個 inst 的包裝、ctl 是一個宣告檔；daemon＝表＋資料夾指令＋自己也是 loop」；[NORMS](../NORMS.md)（ctl 規範 N-05～N-10 已寫、巢狀 grace 慣例）；[proto8-1 README](../../proto8-1/README.md) 把「節奏交給 daemon」改成「交給 loop，停＝ctl.json 的 paused」；code map 若有列 proto8 就同步。
5. **測試與 demo**：`LoopTest` 改成測 aos-loop 命令列（跑 3 次結束、SIGTERM、改 ctl.json 暫停再恢復、`now` 當場收掉、`times` 改小馬上 done、壞檔不影響、檔不見維持、state.json 有 `ctl_mtime`）；`Daemon` 那組照控制資料夾測，多測「改 daemon 的 ctl.json 暫停掃描再恢復」「`stop` 會 save 再走」「loop.json 沒寫 ctl 時 daemon 生包裝檔」；`test_returns_code`、`test_last_code`、tasks 11 個改讀 exit 檔；proto8-1 直接用 `aos_loop.Loop` 的 2 個測試改用新名字；測試與兩支 demo（`proto8/demo/run.py`、`proto8-1/demo/run.py`）的 inst 包一層 loop.json（或 `$ref`），改印出來的 `times`／`removed` 字樣，再加一段「不靠 daemon、直接 aos-loop 跑時鐘，改 ctl.json 停它」。

## 6. 未決

- loop 怎麼當場收掉 inst、清孫程式（舊 `run()` 的 `stop`、`new_session`）：看 [inst 進 json](2026-10-12-inst-json.md) 的 Q-A。
