← [入口](README.md)｜涵蓋：結論：改完每個元件的窗叫什麼、「末端加前綴」目前沒有套用對象；代定｜上一份 [02-每個窗現在叫什麼-誰定名-誰讀誰寫](02-每個窗現在叫什麼-誰定名-誰讀誰寫.md)｜下一份 [04-要使用者看的方向題-原則沒講清楚的](04-要使用者看的方向題-原則沒講清楚的.md)

## 結論（fable 照原則定的細節，11-02 晚已落地，可翻案）

### 每個元件的窗叫什麼

| 元件 | 窗 |
|---|---|
| aos-loop | `ctl.json`／`state.json` 是**慣用名**；程式照 N-09 沒有預設名、沒寫不開 |
| agent 範本、eca 範本、daemon 幫子 loop 補的（`child.cpp`） | `ctl.json`／`state.json` |
| aos-daemon 自己（loop 面向） | `ctl.json`／`state.json`；程式不加預設名 |
| aos-daemon 管轄 | `loops_ctl.json`／`loops_state.json`（11-03 起 `procs_ctl`／`procs_state`，方向題 1） |
| 常駐 bob 控制器 | `ctl.json`／`state.json` |
| `relay`、aos-fsm 等「身體」自己的狀態檔 | `relay_state.json`、`state.txt` 照舊（沒有 ctl，N-13 自訂名；方向題 3） |
| `aos_ws.loop_state`、aos-listen `--status` | 只認 `state.json` |

一句話：**loop 這一系在 stack 裡只有一對自己的 ctl／state，就叫 `ctl.json`／`state.json`；daemon 多的那對「管別人」的窗另外取名；身體自己的紀錄檔照 N-13 自己取名。**

### 「同一個 stack 裡有兩對 ctl／state」今天發生在哪

11-02 晚**沒有任何一處**在同一個 stack 裡放兩對格式不同的 ctl／state，所以「末端把 base 加前綴」目前沒有現成的套用對象，是給以後的。機制已經在：aos-loop 的 `ctl`／`state` key 與 `--ctl`／`--state` 旗標就能把 base 那份改名，**不用改 C++**。

### 代定（實作者照做，可翻案）

1. **程式一律不加預設名**（aos-loop、aos-daemon 的 `ctl`／`state` 照 N-09 沒寫＝不開）：使用者定的是「叫什麼」，不是「一定要開」；`child.cpp` 幫子 loop 補名是 daemon 要看子項，另一回事、照舊。
2. `aos_ws.LOOP_STATE_NAMES` 收回成單一個名字（不留「先找 `state.json` 沒有再找 `loop_state.json`」），免得兩套名字（C-54 一詞一義）。
3. 分檔資料夾 `loops_state_loops/` 跟著 `loops_state` 的名字，本題不動。
4. 舊紀錄（10 月的 thinking、`2026-11-02-daemon-env.md`、`2026-11-02-playground-daemon.md`）裡的 `daemon_state.json` 照「舊紀錄照舊名」不改。
