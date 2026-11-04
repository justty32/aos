← [入口](README.md)｜涵蓋：現況（查清的，不是規劃） › 「同一個 stack 裡有兩對 ctl／state」今天發生在哪；規劃（fable，照原則定的細節，可翻案）｜上一份 [02-每個窗現在叫什麼-誰定名-誰讀誰寫](02-每個窗現在叫什麼-誰定名-誰讀誰寫.md)｜下一份 [04-要使用者看的方向題-原則沒講清楚的](04-要使用者看的方向題-原則沒講清楚的.md)

### 「同一個 stack 裡有兩對 ctl／state」今天發生在哪

今天**沒有任何一處**真的在同一個 stack 裡放兩對格式不同的 ctl／state：

- daemon 的 stack：一對 `ctl`／`state`（loop 格式）＋一對 `loops_ctl`／`loops_state`（名字已經是主題在前，不是同名）。子項都在 `loops/<名>/` 自己的小格。
- 常駐 bob 控制器小格：aos-loop 一對；`relay` 只有 `relay_state.json`、沒有 ctl。
- agent 範本 stack：aos-loop 一對（多數沒開）；aos-fsm 的 `state.txt` 副檔名不同、沒有 ctl。
- eca 小格：只有子 aos-loop 一對。

所以「末端把 base 加前綴」這條例外**目前沒有現成的套用對象**，是給以後的（例如有人寫一支會「變成」aos-loop、又有自己另一種格式 ctl／state 的程式）。機制已經在：aos-loop 的 `ctl`／`state` key 與 `--ctl`／`--state` 旗標就能把 base 那份改名，**不用改 C++**。

## 規劃（fable，照原則定的細節，可翻案）

### 1. 改完每個元件的窗叫什麼

| 元件 | 改完 | 怎麼改 |
|---|---|---|
| aos-loop | `ctl.json`／`state.json`（**慣用名**；程式照 N-09 仍沒有預設名、沒寫不開） | 不動程式；README／C-54 例子照舊 |
| agent 範本、eca 範本、daemon 幫子 loop 補的 | `ctl.json`／`state.json` | **已經是**，不動（`child.cpp` 的補名與原則一致，留） |
| aos-daemon 自己（loop 面向） | **`ctl.json`／`state.json`**（推翻白天的 `daemon_*`） | demo 五份 daemon.json、`aos_ai_daemon.py:15`、`aos_ai_base.py:191`、`clocks.lua`、試驗場 `daemons/main/daemon.json`、README 範例、測試裡的 `"ctl": "daemon_ctl.json"`／`"state": "daemon_state.json"` 全改回；程式仍不加預設名 |
| aos-daemon 管轄 | `loops_ctl.json`／`loops_state.json`（**不動**；[方向題 1](04-要使用者看的方向題-原則沒講清楚的.md#方向題-1loops_ctljsonloops_statejson管別人的窗算不算控制自身)） | — |
| 常駐 bob 控制器 | **`ctl.json`／`state.json`**（推翻 resident-bob 規劃的 `loop_*`） | 試驗場 `agents/resident_bob/ctl/loop.json`、`_entry`（`clear_stopped` 的路徑）、兩份 README；`relay_state.json` 照舊（見下） |
| `relay`、aos-fsm 等「身體」自己的狀態檔 | `relay_state.json`、`state.txt`／`trace.jsonl` **照舊** | 它們沒有 ctl、不是「控制自身的 ctl／state 對」，是身體自己的紀錄檔（N-13 自訂名）；見[方向題 3](04-要使用者看的方向題-原則沒講清楚的.md#方向題-3末端把-base-加前綴的具體例子常駐-bob-的控制器小格誰是末端) |
| `aos_ws.loop_state`、aos-listen `--status` | **只認 `state.json`**，收回 `LOOP_STATE_NAMES` 的 `loop_state.json` 備案與 `--status` 那行的「（哪份）」註 | `lib/aos/aos_ws.py:117-121`、`extras/human/bin/aos_human.py:211-216`、`tests/test_human.py` 那 1 案改回、`lib/README.md`、`extras/human/README.md`、`extras/ai_tools/README.md`、`aos_ai_agents.py` 註 |

一句話：**loop 這一系在 stack 裡只有一對自己的 ctl／state，就叫 `ctl.json`／`state.json`；daemon 多的那對「管別人」的窗叫 `loops_ctl.json`／`loops_state.json`；身體自己的紀錄檔照 N-13 自己取名。**

### 2. 原則怎麼寫進條文（只補一句，不立新條）

- **N-13**（或 N-09）補 11-02 晚一句：「程式**控制自身**的 ctl／state 窗，慣用名 `ctl.json`／`state.json`、不加前綴（使用者 11-02 晚；loop 這一系全照此）。共用 stack 時末端（derived）的 ctl／state 跟 base 的格式不同，由末端把 base 那對改名加前綴（aos-loop 的 `ctl`／`state` key、`--ctl`／`--state` 旗標就是給這個用的），自己的用 `ctl.json`／`state.json`。」連回本檔。
- **N-28** 10-29／11-02 落實段與範例的 `daemon_ctl.json`／`daemon_state.json` 改回 `ctl.json`／`state.json`，標「11-02 晚改回」。`NORMS.md` 命名段、附錄 1、附錄 2 同步。
- [exec 像繼承 § 結論](../exec-inheritance.md#結論11-02跟使用者討論後) 補一句「11-02 晚：ctl／state 這一組例外——控制自身的不加前綴，見本檔」；其他固定名怎麼辦等[方向題 2](04-要使用者看的方向題-原則沒講清楚的.md#方向題-2exec-像繼承的前綴原則對-ctlstate-以外的固定名還適用嗎)。
- [state 窗](../state-window/README.md) 決定節的「方向題 1：daemon 的 ctl 也改 `daemon_ctl.json`（要）」與規劃 1 補「11-02 晚推翻，見本檔」；[常駐 bob](../resident-bob/README.md) 規劃 3／4 節與代定「aos-listen 認 `loop_state.json`」同樣補註。**不改寫原文**，只加註。

### 3. 代定的小事（實作者照做，可翻案）

1. **程式一律不加預設名**（aos-loop、aos-daemon 的 `ctl`／`state` 照 N-09 沒寫＝不開）：使用者定的是「叫什麼」，不是「一定要開」；`child.cpp` 幫子 loop 補名是 daemon 要看子項，另一回事、照舊。
2. `aos_ws.LOOP_STATE_NAMES` 整個收回成單一個名字（不留「先找 `state.json` 沒有再找 `loop_state.json`」）：那是 11-02 晚才為控制器加的、只有 test_human 1 案，留著就是兩套名字（C-54 一詞一義）。
3. 試驗場 `agents/resident_bob` 的改名由實作者在試驗場做（不在 git），順手 `rm` 控制器小格殘留的 `loop_ctl.json`／`loop_state.json`（舊名的檔會留在 `.stack/loops/bob_ctl/`，不會壞事但會誤導 `ls`）。
4. 分檔資料夾 `loops_state_loops/` 跟著 `loops_state` 的名字，本題不動。
5. 10 月的 thinking 與 `2026-11-02-daemon-env.md`、`2026-11-02-playground-daemon.md` 裡出現的 `daemon_state.json` 是當時的紀錄，照「舊紀錄照舊名」不改。
