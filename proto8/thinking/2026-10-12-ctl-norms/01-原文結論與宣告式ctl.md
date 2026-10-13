[← 回入口](../2026-10-12-ctl-norms.md)｜下一份：[02-指令式資料夾與未決](02-指令式資料夾與未決.md)

## 1. 使用者原文

- 「ctl 格式之後要定下規範。」「ctl 規範你可以開 agent 去定。」
- 看完第一版：「那應該是 `"stop": {"val": true, "now": true}` 吧。」
- 拍板：「沒寫的回初始值，其他都照建議。」（加上 inst-json 那邊定的「timeout、grace 都放 inst 內」）

## 2. 結論：兩種 ctl

| | 管什麼 | 長什麼樣 | 誰用 |
|---|---|---|---|
| **宣告式**：一個 `ctl.json` | 一個東西自己的狀態（loop、daemon 本身） | 一份檔寫「我要它現在怎樣」；讀的人定期看、照做；沒回覆 | loop；daemon 控制自己 |
| **指令式**：一個控制資料夾 | 一張表（daemon 底下有哪些 loop） | 一檔一指令，處理完變 `.done` 放回覆 | daemon 的 `control_dir` |

原則：規範盡量少，只保證「看得出成沒成、生效沒生效」；細分的代號、數字、間隔都算參考。「什麼時候用宣告式、什麼時候用指令式」**不寫成規範**。

## 3. 決定：宣告式 ctl.json

### 3.1 欄位

```jsonc
{
  "paused": {"val": false, "now": false},  // val true＝不再起新的一次；now true＝不等這次跑完，當場收掉（SIGTERM，過 grace 再 SIGKILL）
  "stop":   {"val": false, "now": false},  // val true＝不再起新的一次，這次結束後整個 loop 結束；now 同上
  "times": 5,              // 總共要跑幾次（含已跑過的）；null＝不限
  "interval_ms": 1000,     // 間隔
  "interval_mode": "after" // "after"＝跑完再隔；"fixed"＝固定週期
}
```

- **規範**：`paused`、`stop` 兩個旗子，各寫成 `{"val", "now"}`；`times`、`interval_ms`、`interval_mode` 能蓋過 loop.json 外層的執行方式 key（名字跟 loop.json 同一組，跟著 loop.json 的 key 表走）。
- **簡寫**：`"stop": true` ＝ `{"val": true, "now": false}`；`"stop": false` ＝ `{"val": false}`。
- **`stop` 壓過 `paused`**：`stop.val` 為 true 時 `paused` 整個不看，當不當場收掉只看 `stop.now`。`val` 為 false 時 `now` 沒意義，讀的人忽略。
- **不在 ctl.json 裡**：`ctl`、`ctl_poll_ms`、`state`（ctl 自己在哪、多久看、回報到哪）、`error_wait_ms`（收尾參數）、`timeout_ms`／`grace_ms`（單子的事，在 inst.json）。
- 每個欄位都選填。**沒寫的＝回起來時那份檔（loop.json／daemon.json）的初始值**，不是維持上一版 ctl.json。
- 型別錯（`times: "5"`）＝整份不採用。不認識的 key 照 N-04 忽略（例：daemon 替 loop 寫時多放 `"by": "daemon"`）。

### 3.2 語意（規範）

1. **期望狀態，不是指令**：整份檔就是全部的期望；沒有回覆、順序、歷史。
2. **冪等**：寫一次跟寫十次一樣。
3. **蓋過初始值**：有寫的欄位蓋過 loop.json／daemon.json，沒寫的回初始值。
4. **讀的人只讀不寫**：回報走 state.json。
5. **`stop` 是終點**：收尾完就結束，改回 false 不會復活；`paused` 才可逆。
6. **`now` 是 `paused`／`stop` 各自的子欄位**。

慣例：
- `times` 跑完 loop 就結束（`times` 改到比 `runs` 小＝馬上結束），要再跑就重新起。
- `paused` 期間 `times`、`interval_ms` 照樣可以改，解除暫停時生效。
- daemon 的 ctl.json 用同一組欄位：`paused`＝不掃資料夾（指令堆著、底下的 loop 照跑）；`stop`＝收工（config 有 `save` 先存、收掉全部 loop）；`stop.now`＝底下的 loop 也 `now`；`interval_ms`＝輪詢間隔；`times`＝掃幾圈就走。

### 3.3 寫的人

- **規範（N-05）**：先寫同資料夾 `.` 開頭的暫存檔，再改名蓋過去（`os.replace`）。ctl.json、state.json、`.done`、daemon 的 save 檔、aos-tick 的時鐘檔都照這條；這條就是 N-02「資料夾別亂弄」的細則之一。
- **誰都可以寫，後寫的算**，每次寫整份（規範）；慣例：daemon 是它管的 loop 的主要寫者，人臨時改也行。「讀、改一格、寫回」兩人同時做會互蓋，規範不解。
- 不 fsync（慣例）。

### 3.4 讀的人（規範：壞了就維持上一次）

- 定期看：每 `ctl_poll_ms`（慣例預設 1000）`stat` 一次，有變才重讀、驗、套用；跑的途中也看（`now` 要能當場收掉）。
- 判「有變」（慣例）：用 `(st_ino, st_mtime_ns, st_size)` 三元組，不能只比 mtime。
- 壞 JSON、不是物件、型別不對：整份不採用、維持上一次的好狀態、stderr 印一行（同一件事印一次，變了才再印）；不停、不退出。
- 檔不見：起來時就不在＝沒有控制；跑到一半不見＝維持上一次、印一次。**不當成回到初始值**。起來時就在但壞掉＝「上一次的好狀態」就是初始值。

### 3.5 state.json

- **規範**：要回報就寫到另一個檔、不碰 ctl.json，寫法照 N-05；選填；一個 state.json 只有被控制的那個東西自己寫。
- **格式（慣例）**：

```jsonc
{
  "id": "/abs/clock-loop.json",   // loop.json 的 realpath
  "state": "running",             // waiting／running／paused／done／stopping／stopped；daemon 底下剛起、還沒寫出來＝daemon 回 starting
  "pid": 12345,                   // loop 行程自己的 pid（daemon 用它判孤兒；load 前看它活不活）
  "times": 5, "runs": 2,
  "last_code": 0,                 // 上一次子程式的碼（讀 inst 的 exit 檔；沒寫 exit＝null）
  "last_error": null,             // inst 自己出錯的那一行；沒有＝null
  "ctl_mtime": 1760280000.123     // 上次套用的 ctl.json 的 mtime；沒有 ctl＝null
}
```

- 慣例：狀態物件有變就整份寫（起一次、跑完一次、paused 生效、stop 完），不定時寫；`interval_mode: "fixed"` 跳拍時多一個 `skipped` 計數。
- `ctl_mtime` 是宣告式唯一的回音（寫的人拿它比對「我那份被讀到了沒」）；**先當慣例，不進規範**。

### 3.6 放哪（慣例）

- daemon 自己的 ctl.json **不能放在 `control_dir` 裡**；config 驗到就拒絕。
- loop 的 ctl.json、state.json 不放進 node 的資料夾；daemon 替 loop 生的放 `work_dir/loops/<編號>/`。

### 3.7 三層通用慣例（10-12 夜定）

- 結論：**設定檔讀一次 → ctl 蓋過 → state 回報，三者節奏類的 key 同名**進 NORMS（N-11）；設定檔整份只在起來時讀一次，含 loop.json 的 `inst`。loop、daemon 共用一套七個狀態值（starting／waiting／running／paused／done／stopping／stopped），各取子集；daemon 也認 `interval_mode`；`last_error` 兩層共用，`last_code` 只在 loop；daemon state 的 `loops` 只寫個數（使用者：「一百台會很麻煩」），要細節用控制指令查；inst 的 state 就是 exit 檔。欄位表與狀態值當慣例，寫在 [lib README](../../lib/README.md#ctl-與-state-的慣例)。
