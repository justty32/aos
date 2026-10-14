[← 回入口](../2026-10-12-loop-daemon.md)｜下一份：[02-loop與daemon](02-loop與daemon.md)

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

同夜順帶講了代理人＝一個 loop 跑「切狀態機一步」的 inst，原話在 [inst 進 json §5](../2026-10-12-inst-json.md#5-使用者順帶講的代理人)。

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
| inst.json | `aos-inst x.json` | `argv`、`cwd`、`envs`、`stdin`／`stdout`／`stderr`、`exit`＋布林、`timeout_ms`、`grace_ms`（見 [inst 進 json](../2026-10-12-inst-json.md)） | — |
| loop.json | `aos-loop x.json` | `times`、`interval_ms`、`interval_mode`、`grace_ms`、`ctl`、`ctl_poll_ms`、`state`、`error_wait_ms` | `inst`：一份 inst.json 格式，或 `{"$ref": …}` |
| daemon.json | `aos-daemon x.json` | loop 那一組（`times`、`interval_ms`、`ctl`、`ctl_poll_ms`、`state`、`grace_ms`）＋ `control_dir`、`load`、`save`、`work_dir` | `inst`＝daemon 自己每拍跑一次的身體（選填；10-14 夜使用者拍板候選 g，daemon.json＝loop.json 的超集，見 [NORMS N-28](../../NORMS/05-命令列與daemon-N21至N28.md)）；表上每個 loop 是一支 `aos-loop` 子程序 |

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
- **誰蓋過誰**：loop.json 外層是初始值；ctl.json 有寫的欄位蓋過，沒寫的回初始值（ctl.json 的格式見 [ctl 規範](../2026-10-12-ctl-norms.md)、NORMS N-06～N-08）。
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
- `inst` 格＝daemon 每拍的身體（選填），每拍＝收屍 → 掃資料夾 → 跑 inst（10-14 夜候選 g 拍板，N-28）。
- daemon 自己的退出碼 0／1 不動；SIGINT 收、不存，SIGTERM 先存再收。
