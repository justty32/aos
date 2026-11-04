# 2026-11-02 晚 loop 這一系的窗檔名：控制自身的 ctl／state 就叫 `ctl.json`／`state.json`，不加前綴

← [thinking README](../../README.md)｜月份表 [2026-11](../README.md)｜出發點：頂層向使用者說明「eca 範本用 `ctl.json`／`state.json`，常駐 bob 用 `loop_ctl.json`／`loop_state.json`；全統一加 `loop_` 是大工程」｜被本條推翻的同日決定：[11-02 state 窗](state-window.md)（白天：daemon 窗慣用名 `daemon_ctl.json`／`daemon_state.json`）、[11-02 exec 像繼承 § 結論](exec-inheritance.md#結論11-02跟使用者討論後)（共用 stack 常見名字加前綴 `daemon_*`、`loop_*`）在 ctl／state 這件事上、[11-02 常駐 bob](resident-bob/README.md)（控制器窗 `loop_ctl.json`／`loop_state.json`、代定「aos-listen 也認 `loop_state.json`」）｜條文：[N-09、N-11、N-13、N-14、N-17](../../../docs/NORMS/05-基礎設施-窗.md)、[N-28、N-54](../../../docs/NORMS/04-基礎設施-loop與daemon.md)、[P-17](../../../docs/CONVENTION/02-題目stack停錯腦.md)、[C-54](../../../docs/CONCEPTS/01-設計理念/C-54-命名方法.md)｜程式：[aos-loop](../../../impls/aos-loop/README.md)、[aos-daemon](../../../impls/aos-daemon/README.md)、[aos-daemon-ctl](../../../bin/README.md)、[aos-eca-hub](../../../extras/eca/README.md)、[aos-say／listen](../../../extras/human/README.md)、[ai_tools](../../../extras/ai_tools/README.md)｜場地 `~/code/playground/`（不在 git）

本檔只記使用者原文（逐字）、決定、查清的現況、fable 照原則定的規劃（可翻案）、原則沒講清楚要使用者一句話的方向題（[user/03](../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。**只規劃、沒實作。**

> **11-03 補**：loop 的 ctl.json 11-03 改成一道指令（`{"cmd": "stop"}` 取代 `{"stopped": true}`；起來第一次讀到的那份當基準線，殘留的 stop 不用再清，常駐 bob `_entry` 的 `clear_stopped` 拿掉），見 [11-03 ctl-commands](../03/ctl-commands.md)。

## 使用者原文（11-02 晚，逐字）

> hmmm，就是說，eca本身繼承於daemon，daemon又繼承於loop，他們吃的都是同份ctl/state檔案，就是這份檔案內有額外的key，對於這種控制自己的ctl/state檔案，其實直接用ctl.json/state.json就好，沒必要費心用loop_*，所以改成統一用ctl/state吧，你懂得，就是loop這一系。就是說一個原則：控制自身的ctl/state檔案，那就是ctl/state，不加前綴。至於如果和base class的ctl/state分屬不同格式，那就是把base class的ctl/state增加前綴，畢竟你是末尾，你要負責處理。

頂層問「白天定的 `daemon_ctl.json`／`daemon_state.json` 怎麼辦」，使用者（11-02 晚，逐字）：

> 3.就用我這條，白天那個我還有記憶，晚上的我就是要推翻白天的我。

## 決定（11-02 晚，使用者）

- **原則**：**控制自身的 ctl／state 檔，一律叫 `ctl.json`／`state.json`，不加前綴**。loop 這一系（aos-loop、aos-daemon、eca 範本的子 loop、常駐 bob 的控制器……）全部統一。
- **例外的方向**：末端（derived）的 ctl／state 跟 base 的**格式不同**時，由**末端**負責——把 **base 那份加前綴**（例 `loop_ctl.json`／`loop_state.json`），自己的用 `ctl.json`／`state.json`。
- **被推翻（已定、不再是待裁衝突）**：
  - 11-02 白天 [state 窗](state-window.md) 的「daemon 窗慣用名 `daemon_ctl.json`／`daemon_state.json`」（含那份的方向題 1「ctl 一起改」）→ 改回 `ctl.json`／`state.json`。
  - 11-02 [exec 像繼承 § 結論](exec-inheritance.md#結論11-02跟使用者討論後)「共用 stack 的常見名字加自己前綴（`daemon_*`、`loop_*`）」**在 ctl／state 這件事上**由本條取代；其他固定名（信箱、紀錄檔、`relay_state.json` 這類）是不是也不管了見[方向題 2](#方向題-2exec-像繼承的前綴原則對-ctlstate-以外的固定名還適用嗎)。
  - 11-02 [常駐 bob](resident-bob/README.md) 規劃的控制器窗 `loop_ctl.json`／`loop_state.json`，與頂層代定「aos-listen `--status` 也認 `loop_state.json`」（`lib/aos/aos_ws.py` 的 `LOOP_STATE_NAMES`）→ 控制器改用 `ctl.json`／`state.json`，認兩個名字的程式收回（見規劃）。

### 方向題的答案（11-02 晚，使用者逐字）

- **方向題 1**（`loops_ctl`／`loops_state` 留不留名）：「hmmm，是這樣的，剛剛下班通勤的時候有個想法，就是說，exec和loops，其實都屬於proc，所以...改名？可是我又擔心和linux的proc撞名...不過好像撞名也沒差。就是說，exec是基石，loop是另一種基本形式，搞不好以後還會有更多形式。」→ 頂層判讀：使用者在想把 `execs`／`loops` 統稱 proc 並改名，**未定**；今晚 `loops_ctl`／`loops_state` 等**不動**，**待明天跟使用者談**。
  - **11-03 定案**（[11-03 procs](../03/procs.md)）：統稱 proc、名單合一成 `procs`；`loops_ctl`／`loops_state` 改 `procs_ctl`／`procs_state`（照本檔方向題 1 (a) 那句通則「管別人的窗＝`<被管的東西>_ctl`／`_state`」，N-13 的 11-03 補）。
  - **11-03 晚結案**（頂層列開著的事，使用者逐字）：「A2.解決了，以後相關的稱呼/慣例等也要變就是了。」→ 決定：本題已由 11-03 procs 合一解決；**以後相關的稱呼與慣例也跟著改成 proc 這一套**（說 exec／loop 是 proc 的兩種形式，名單、窗、說明一律用 proc 的叫法），遇到舊叫法順手改。
- **方向題 2**：「2.好。」→ 前綴原則對 ctl／state 以外的固定名照舊（選 a）。
- **方向題 3**：「3.對。」→ 只有帶 ctl 的才算 ctl／state 對；`relay_state.json` 照舊（選 a）。

## 現況（查清的，不是規劃）

### daemon 的 ctl／state 跟 loop 的格式一樣嗎（決定原則怎麼套）

**一樣，而且是同一段程式寫的、沒有多任何 key。** 使用者原文裡「同份 ctl/state 檔案，裡面有額外的 key」是 10-29 拆窗**以前**的樣子；現況：

- `Daemon` 繼承 `Loop`（`impls/aos-daemon/src/daemon/daemon.hpp`）。daemon 的 `ctl`／`state` 兩扇窗由 `Loop::read_ctl`／`Loop::write_state`（`impls/aos-loop/src/engine/window.cpp`）讀寫；daemon **沒有覆寫 `info()`**（grep 全 aos-daemon 沒有 `Daemon::info`；`Loop::info()` 回空物件），所以它的 state＝`{phase, counter_runs, max, interval_ms, paused, ctl_seq, ctl_warning, code(結束時), pid, started_at_ticks, boot_id, updated_at}`，跟 aos-loop 一字不差。
- daemon 的 `check_ctl`（`daemon.cpp:453`）只做一件事：ctl 裡出現 `loops`／`loops_added`／`loops_removed` 就**不採用、提醒搬到 `loops_ctl.json`**；不多認任何 key。所以 daemon 的 ctl 也只認 loop 那五個（`paused`、`stopped`、`max`、`interval_ms`、`seq`）。
- daemon **多出來的 key 全在另一對窗**：`loops_ctl.json`（`loops`、`loops_added`、`loops_removed`、`execs`、`execs_added`、`execs_removed`、`seq`）與 `loops_state.json`（`ctl_seq`、`ctl_warning`、`mailbox_warning`、`loops` 表、`execs` 表、`pid`、`started_at_ticks`、`boot_id`、`updated_at`），由 `windows.cpp` 的 `read_loops_ctl`／`write_more` 讀寫；10-29 使用者定的（[medium-plan § 四](../../2026-10/29/medium-plan/03-四-aos-daemon-的兩個手把-兩扇狀態窗.md)）。
- 結論：**daemon 對 loop 不是「同一份檔多幾個 key」，而是「同一份檔原樣（格式相同）＋另一對自己的窗」**。照使用者的原則，格式相同＝不必加前綴，daemon 的 `ctl`／`state` 直接叫 `ctl.json`／`state.json` 就對了；`loops_*` 那對不是「控制自身」而是「管別人」，原則沒講到，見[方向題 1](#方向題-1loops_ctljsonloops_statejson管別人的窗算不算控制自身)。

### 每個窗現在叫什麼、誰定名、誰讀誰寫

| 元件 | 窗 | 現在的名字 | 名字誰定 | 寫 | 讀 |
|---|---|---|---|---|---|
| aos-loop | ctl／state | 設定檔 `ctl`／`state` key 或旗標 `--ctl`／`--state`；**程式沒有預設名**，沒寫或 null＝不開（N-09） | 寫 loop.json 的人 | state：loop 自己 | ctl：人／aos-eca-hub／install 等 |
| ├ agent 範本（`demo/agent-*`） | 同上 | 多數**沒開**（`agent-bob`、`agent-fay`…只有 `exec`、`max`）；`agent-nia` 開 `ctl.json`／`state.json`（`agent-dan`、`agent-dan-q` 使用者剛定要刪，略） | 同上 | 同上；同一 stack 另有 aos-fsm 的 `state.txt`／`trace.jsonl`、agent queue 的 `letter_warning.txt` | `aos_ws.loop_state`（aos-listen `--status`、`aos_ai_agents.py` 的 `loop_phase`） |
| ├ eca 範本（`demo/eca-claude`、`demo/eca-codex`、試驗場 `agents/eca_bob`） | 同上 | `ctl.json`／`state.json`（10-30 eca 定；aos-eca-turn 自己不碰這兩個檔） | 範本作者 | state：aos-loop | aos-eca-hub（`loops/<名>/state.json` 判「收工了／出錯停了／停了」、寫 `ctl.json` 清殘留 `stopped`、`paused`）；`aos_ai_base.py:229`；`demo/talk/team/quiet.py` |
| ├ daemon 幫子 loop 補的 | 同上 | 子項設定沒寫就補 `"ctl": "ctl.json"`、`"state": "state.json"`（`impls/aos-daemon/src/child/child.cpp:147-151`）——**程式裡唯一寫死的 ctl／state 預設名**，已經是不加前綴 | aos-daemon | state：子 aos-loop | 同上一列 |
| aos-daemon 自己 | ctl／state（loop 面向） | **`daemon_ctl.json`／`daemon_state.json`**（11-02 白天慣用名；程式沒有預設名）——demo 五份 daemon.json（`daemon`、`daemon-2`、`daemon-3`、`llm-kernel`〔只開 state〕、`talk/team`）、`aos_ai_daemon.py:15` 生的 daemon.json、試驗場 `daemons/main/daemon.json`、`extras/langs/lua/examples/clocks.lua` | 寫 daemon.json 的人 | state：Loop（daemon 行程） | `aos_ai_base.py:191`（`Daemon.running()`、`stop` 寫 ctl）、`aos_ai_daemon.py status`、測試 |
| aos-daemon 管轄 | loops_ctl／loops_state | `loops_ctl.json`／`loops_state.json`：daemon.json `loops_ctl`／`loops_state` key，**沒寫＝這兩個預設名**、null＝不開；分檔資料夾 `loops_state_loops/`；信箱 `loops_ctl_mailbox/` | aos-daemon | loops_state：daemon | aos-daemon-ctl `ls`、aos-eca-hub（判 daemon 活著）、`aos_ai_base.py`、resident_bob 的 `relay`、daemon 自己 `adopt` |
| 常駐 bob 控制器（試驗場 `agents/resident_bob/ctl/`） | aos-loop 的 ctl／state | **`loop_ctl.json`／`loop_state.json`**（`ctl/loop.json`；11-02 resident-bob 規劃「共用 stack 加前綴」） | 範本作者 | state：aos-loop | `_entry`（install）`clear_stopped(loop_ctl.json)`；README；aos-listen `--status`（經 `aos_ws.LOOP_STATE_NAMES = ("state.json", "loop_state.json")`，先找到的算） |
| 常駐 bob 的身體 `relay` | 自己的狀態 | `relay_state.json`（`{bob, bob_pid, session_id, out_offset, sent, …}`；沒有 ctl） | relay 作者 | relay | relay 自己、install（讀 `session_id`） |
| aos-fsm（agent 範本的身體，跟 aos-loop 共用 stack） | state | `state.txt`（純文字一行）＋`trace.jsonl`；寫死在 `impls/aos-fsm/src/state/state.cpp`；沒有 ctl | aos-fsm | aos-fsm | aos-fsm（P-19 看 trace 行數） |

### 條文現在怎麼寫

- **N-09**：state 選填、沒給就不開、不提醒——沒規定檔名。**N-13**：外顯檔「名字與格式由程式自訂」。**N-14**：窗一族「名字由程式自訂（N-13）」。**N-11**：`ctl`、`state` 是位置類 key、不能從 ctl 改。**N-17**：心跳（11-02 白天已拿掉）。→ 這幾條都**沒把名字定死**，本題不改它們的本文，只在 N-13（或 N-09）補一句慣用名原則。
- **N-28**：daemon.json 是 loop.json 嚴格超集、「同名 key 同義（節奏、窗、收尾）」；它底下的 10-29／11-02 落實段與範例寫著 `daemon_ctl.json`／`daemon_state.json`（`04-基礎設施-loop與daemon.md`、`NORMS.md` 命名段、附錄 1、附錄 2 各一處）。**N-54**：名單走 daemon 的 ctl 窗（10-29 改口：搬到 `loops_ctl.json`）。
- **P-17**：叫**別的**資料夾程式給小格 `tools/<名>/`；11-02 補「呼叫方給的名字跟格自己的固定名分開命名空間」。跟本題的關係：給了小格就各有各的 stack、`ctl.json`／`state.json` 不會撞；會撞的只有「變成」（共用 stack）那一路。
- **C-54** R1 例子「`state.json - loop 自己回報的現況`」、R7「主題在前」（`loops_ctl`、`loops_state`、`ctl_seq` 都是這條來的）。`abbr.json` 有 `ctl`。

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
| aos-daemon 管轄 | `loops_ctl.json`／`loops_state.json`（**不動**；[方向題 1](#方向題-1loops_ctljsonloops_statejson管別人的窗算不算控制自身)） | — |
| 常駐 bob 控制器 | **`ctl.json`／`state.json`**（推翻 resident-bob 規劃的 `loop_*`） | 試驗場 `agents/resident_bob/ctl/loop.json`、`_entry`（`clear_stopped` 的路徑）、兩份 README；`relay_state.json` 照舊（見下） |
| `relay`、aos-fsm 等「身體」自己的狀態檔 | `relay_state.json`、`state.txt`／`trace.jsonl` **照舊** | 它們沒有 ctl、不是「控制自身的 ctl／state 對」，是身體自己的紀錄檔（N-13 自訂名）；見[方向題 3](#方向題-3末端把-base-加前綴的具體例子常駐-bob-的控制器小格誰是末端) |
| `aos_ws.loop_state`、aos-listen `--status` | **只認 `state.json`**，收回 `LOOP_STATE_NAMES` 的 `loop_state.json` 備案與 `--status` 那行的「（哪份）」註 | `lib/aos/aos_ws.py:117-121`、`extras/human/bin/aos_human.py:211-216`、`tests/test_human.py` 那 1 案改回、`lib/README.md`、`extras/human/README.md`、`extras/ai_tools/README.md`、`aos_ai_agents.py` 註 |

一句話：**loop 這一系在 stack 裡只有一對自己的 ctl／state，就叫 `ctl.json`／`state.json`；daemon 多的那對「管別人」的窗叫 `loops_ctl.json`／`loops_state.json`；身體自己的紀錄檔照 N-13 自己取名。**

### 2. 原則怎麼寫進條文（只補一句，不立新條）

- **N-13**（或 N-09）補 11-02 晚一句：「程式**控制自身**的 ctl／state 窗，慣用名 `ctl.json`／`state.json`、不加前綴（使用者 11-02 晚；loop 這一系全照此）。共用 stack 時末端（derived）的 ctl／state 跟 base 的格式不同，由末端把 base 那對改名加前綴（aos-loop 的 `ctl`／`state` key、`--ctl`／`--state` 旗標就是給這個用的），自己的用 `ctl.json`／`state.json`。」連回本檔。
- **N-28** 10-29／11-02 落實段與範例的 `daemon_ctl.json`／`daemon_state.json` 改回 `ctl.json`／`state.json`，標「11-02 晚改回」。`NORMS.md` 命名段、附錄 1、附錄 2 同步。
- [exec 像繼承 § 結論](exec-inheritance.md#結論11-02跟使用者討論後) 補一句「11-02 晚：ctl／state 這一組例外——控制自身的不加前綴，見本檔」；其他固定名怎麼辦等[方向題 2](#方向題-2exec-像繼承的前綴原則對-ctlstate-以外的固定名還適用嗎)。
- [state 窗](state-window.md) 決定節的「方向題 1：daemon 的 ctl 也改 `daemon_ctl.json`（要）」與規劃 1 補「11-02 晚推翻，見本檔」；[常駐 bob](resident-bob/README.md) 規劃 3／4 節與代定「aos-listen 認 `loop_state.json`」同樣補註。**不改寫原文**，只加註。

### 3. 代定的小事（實作者照做，可翻案）

1. **程式一律不加預設名**（aos-loop、aos-daemon 的 `ctl`／`state` 照 N-09 沒寫＝不開）：使用者定的是「叫什麼」，不是「一定要開」；`child.cpp` 幫子 loop 補名是 daemon 要看子項，另一回事、照舊。
2. `aos_ws.LOOP_STATE_NAMES` 整個收回成單一個名字（不留「先找 `state.json` 沒有再找 `loop_state.json`」）：那是 11-02 晚才為控制器加的、只有 test_human 1 案，留著就是兩套名字（C-54 一詞一義）。
3. 試驗場 `agents/resident_bob` 的改名由實作者在試驗場做（不在 git），順手 `rm` 控制器小格殘留的 `loop_ctl.json`／`loop_state.json`（舊名的檔會留在 `.stack/loops/bob_ctl/`，不會壞事但會誤導 `ls`）。
4. 分檔資料夾 `loops_state_loops/` 跟著 `loops_state` 的名字，本題不動。
5. 10 月的 thinking 與 `2026-11-02-daemon-env.md`、`2026-11-02-playground-daemon.md` 裡出現的 `daemon_state.json` 是當時的紀錄，照「舊紀錄照舊名」不改。

## 要使用者看的方向題（原則沒講清楚的）

### 方向題 1：`loops_ctl.json`／`loops_state.json`（管別人的窗）算不算「控制自身」

- **大白話**：daemon 有兩對窗。一對管它自己這支 loop（暫停、停、改節奏）——這對照原則叫 `ctl.json`／`state.json`，沒疑問。另一對是「表上要有誰」跟「表上現在有誰」，管的是**子項**，不是自己；名字 `loops_ctl`／`loops_state` 的 `loops_` 是**主題**（C-54 R7「主題在前」，跟 `ctl_seq` 一樣），不是為了跟 base 分開才加的防撞前綴。原則只講「控制自身的」，這對沒講到。
- **選項**：
  - (a) **照舊叫 `loops_ctl.json`／`loops_state.json`，不動**（fable 建議）。它們不是「控制自身」、也不是「base 的那對」，是另一種窗；10-29 拆窗是使用者定的、aos-daemon-ctl／aos-eca-hub／ai_tools／relay 全讀它、測試 22 檔提到。後果：零改動。
  - (b) 把管轄那對**併回** `ctl.json`／`state.json`（就是使用者原文裡「同一份檔多幾個 key」的樣子）。後果：翻掉 10-29 拆窗（`medium-plan § 四`，當時拆是為了「一份壞不影響另一份」、`ctl_seq` 各回各的、名單表 >100 列切檔不拖累 loop 面向），daemon C++ 三檔、aos-daemon-ctl、aos-eca-hub、ai_tools、relay、測試 20 多檔重寫，N-28／N-54 改口。**不建議**。
- 若選 (a)，順手定一句通則：「管別人的窗名字＝`<被管的東西>_ctl`／`<被管的東西>_state`」，以後 agent＋kernel 變體管別人時照這條，不用再問。

### 方向題 2：exec 像繼承的前綴原則對 ctl／state **以外**的固定名還適用嗎

- **大白話**：白天定「共用 stack 的常見名字加自己前綴（`daemon_*`、`loop_*`）或開資料夾」。晚上這條只把 ctl／state 挖成例外。stack 裡其他固定名——daemon 的 `loops_ctl_mailbox/`、`loops_state_loops/`、eca 的 `eca_archive/`、relay 的 `relay_state.json`、試驗場 clock 的 `clock.txt`、agent queue 的 `letter_warning.txt`——要不要照舊守白天的原則？
- **選項**：
  - (a) **照舊守**（fable 建議）：只有「控制自身的 ctl／state」是例外，理由是那對是 loop 這一系的**共同介面**（誰都知道 `ctl.json` 是手把、`state.json` 是窗，aos-eca-hub、aos-listen 才讀得到）；其他固定名不是介面、各自加前綴或開資料夾才不撞（P-17 的 11-02 改就是這個精神）。後果：現狀全部不動，只在 exec-inheritance 結論補一句例外。
  - (b) 全部不管，撞了再說。後果：以後 agent＋kernel 變體多了（使用者 11-02 自己說「.stack 底下就是會有一大堆東西」），`state.txt`、`history.jsonl` 這類名字真的會撞；到時才加契約更貴。

### 方向題 3：「末端把 base 加前綴」的具體例子——常駐 bob 的控制器小格，誰是末端

- **大白話**：控制器小格裡有兩支程式共用 stack：aos-loop（每 300 ms 起身體）跟 `relay`（身體）。aos-loop 有 `ctl.json`／`state.json`；`relay` 有自己的 `relay_state.json`、**沒有 ctl**。照原文「loop 這一系統一 ctl／state」，aos-loop 那對就叫 `ctl.json`／`state.json`（規劃第 1 節這樣定）。但如果把 `relay` 看成「繼承 aos-loop 的末端、它的 state 格式不同」，字面套原則就變成：`relay` 寫 `state.json`、aos-loop 的改 `loop_ctl.json`／`loop_state.json`——也就是**現狀**（只差 `relay_state.json` 改叫 `state.json`）。兩種讀法會得到相反的結果，要使用者一句話。
- **選項**：
  - (a) **「ctl／state 對」只算有 ctl 的那種；身體自己的紀錄檔不算**（fable 建議）：控制器小格裡只有 aos-loop 一對 → `ctl.json`／`state.json`；`relay_state.json` 照舊（它沒有手把，只是 relay 的工作紀錄，N-13 自訂名）。aos-fsm 的 `state.txt` 同理不動。後果：跟使用者原文「常駐 bob 改成 ctl/state」直接對上；aos-listen `--status` 只認一個名字；「末端加前綴」留給真的有第二對 ctl／state 的情況。
  - (b) 字面套：`relay` 是末端、它的狀態是另一種格式 → `relay_state.json` → `state.json`，aos-loop 的改 `loop_ctl.json`／`loop_state.json`（維持現狀）。後果：常駐 bob 等於不改、跟使用者「統一用 ctl/state」相反；aos-listen 要認兩個名字；以後每個有身體狀態檔的 loop 都要改 aos-loop 的窗名。
- 若選 (a)，順手補一個**真會用到例外的例子**寫進 N-13：「一支 `aos-foo` 自己認 `ctl.json`（`{"mode": …}`）又在同一個 stack 裡起 aos-loop → `aos-foo` 寫 loop.json 時給 `"ctl": "loop_ctl.json", "state": "loop_state.json"`，自己的照舊 `ctl.json`／`state.json`。」

## 實作步驟表（不實作；給隊長）

**前提**：另兩個 agent 正在改 aos-eca-hub（`extras/eca_hub/*`、`tests/test_eca_hub.py`、`bin/aos-eca-turn`、`thinking/2026-10-30-eca/*`、`thinking/2026-11-02-state-window.md`、`docs/NORMS/05-*`、`docs/CONVENTION/02-*`、`extras/human/*`、`lib/aos/`…）與 `letter_warning` 改名；**等那兩輪 commit 進 main、`git pull` 之後再開工**，否則步驟 2、4、6 會打架。demo `agent-dan`、`agent-dan-q` 正在被刪，略過。

| # | 改哪 | 做什麼 | 驗證 |
|---|---|---|---|
| 1 | demo：`demo/daemon/daemon.json`、`daemon-2/daemon.json`、`daemon-3/daemon.json`、`llm-kernel/daemon.json`、`talk/team/daemon.json`、`demo/README.md`、`daemon-2/README.md`、`daemon-3/README.md`；`extras/langs/lua/examples/clocks.lua` | `daemon_ctl.json`→`ctl.json`、`daemon_state.json`→`state.json`；README 的 `.stack/` 目錄樹同步 | `bash proto8/demo/run.sh`；`impls/aos-daemon/tests/test_demo.py` |
| 2 | `extras/ai_tools/bin/aos_ai_base.py:190-191`、`aos_ai_daemon.py:15`、`extras/ai_tools/bin/aos-ai` 檔頭、`extras/ai_tools/README.md`、`claude_skill/aos/concepts.md`、`aos_ai_agents.py` 註 | 讀寫路徑與生的 daemon.json 改回；`status` 文案 | `tests/test_ai_tools.py` |
| 3 | `lib/aos/aos_ws.py`（`LOOP_STATE_NAMES`→只剩 `state.json`、`loop_state` docstring）、`extras/human/bin/aos_human.py:206-216`、`lib/README.md`、`extras/human/README.md` | 收回 `loop_state.json` 備案與「（哪份）」註 | `tests/test_human.py`（那 1 案改回） |
| 4 | 測試：`tests/test_daemon.py`、`test_aos_daemon_ctl.py`、`test_eca_hub.py`、`test_exec_rules.py`、`test_talk.py`、`test_human.py`、`test_ai_tools.py`、`impls/aos-daemon/tests/test_demo.py`（白天 `daemon_*` 共 35 行、13 檔） | `"ctl": "daemon_ctl.json"`／`"state": "daemon_state.json"` 改回；`test_cli.py`（aos-daemon）本來就用 `ctl.json`／`state.json`，不動 | proto8 pytest 全套（11-02 基準 815 OK／8 skip）；`impls/aos-daemon` ctest |
| 5 | `impls/aos-daemon/README.md`（第 24、50、97、100、198 行一帶）、`src/daemon/daemon.hpp:18` 註解、`bin/README.md`（aos-daemon-ctl） | 「慣用名 `daemon_ctl.json`／`daemon_state.json`」改回、標 11-02 晚；**C++ 行為零改動**（只動註解） | `impls/aos-daemon` ctest；repo 根 `cmake --build --preset default && ctest --preset default` |
| 6 | 條文：`NORMS/05` N-13（或 N-09）補原則一句、`NORMS/04` N-28 範例與落實段、`NORMS.md` 命名段、附錄 1、附錄 2；`CONCEPTS/01-設計理念/C-54` R1 例子不動 | 照本檔「規劃 2」，連回本檔 | `/wf-lint` broken=0 |
| 7 | thinking 補註：[state 窗](state-window.md)（方向題 1 答案、規劃 1）、[exec 像繼承 § 結論](exec-inheritance.md#結論11-02跟使用者討論後)、[常駐 bob](resident-bob/README.md)（規劃 3／4 節、代定 aos-listen 那條、實跑段）；本檔「決定」補方向題 1～3 答案 | 只加「11-02 晚推翻，見 [ctl-state-names]」，不改原文 | `/wf-lint` |
| 8 | 試驗場（不在 git）：`~/code/playground/daemons/main/daemon.json`、`agents/resident_bob/ctl/loop.json`、`agents/resident_bob/_entry`（`clear_stopped` 路徑、檔頭說明）、`agents/resident_bob/README.md`、`~/code/playground/README.md:32`；`rm` 控制器小格的舊名窗 | 改回 `ctl.json`／`state.json` | 重跑 `aos-exec ../agents/resident_bob`：`aos-listen --stack $S --status` 印 `phase running（state.json）`→改成不印括號；`echo '{"stopped": true}' > $S/ctl.json` 收工；daemon 睡著時 `.stack/state.json` 不動 |
| 9 | code map：`wf/workflows/common/code-map/proto8.md`、`proto8/02-tests*.md`、`06-周邊工具-3.md`、`09-lib.md`、`13-demo.md`、`14-aos-daemon.md` | 檔名字串同步 | 跟程式對一遍 |
| 10 | `wf/WAIT_USER.md`（「aos-listen 認 `loop_state.json`」那條若還在就拿掉或改）、日誌一行、[months/2026-11](../README.md) 那列（頂層加） | — | `/wf-lint` |

## 影響面

- **程式行為**：C++ **零改動**（aos-loop、aos-daemon 本來就沒有 ctl／state 預設名；`child.cpp` 幫子 loop 補的已經是 `ctl.json`／`state.json`）。Python 四處：`aos_ws.py`、`aos_human.py`、`aos_ai_base.py`、`aos_ai_daemon.py`。
- **資料檔／設定**：demo 五份 daemon.json、`clocks.lua`、試驗場兩份設定＋install。
- **測試**：約 13 個測試檔、35 行字串改回（`daemon_*`）＋`test_human` 1 案；沒有新案要加（名字是設定給的，行為沒變）。
- **文件**：aos-daemon README、bin README、ai_tools 三份文件、lib／human README、demo 三份 README、NORMS 四處、三份 thinking 補註、code map 六處。
- **大小**：一個 commit 做得完（跟 11-02 白天把 `state.json`→`daemon_state.json` 那輪同量、方向相反）。

## 實作（11-02 晚，隊長派的 agent；時間到 22:55 硬期限，跟另一輪「刪 agent-dan」的未 commit 改動重疊的先不碰）

**做了**：步驟 1（demo 五份 daemon.json、daemon-2／3 README、`clocks.lua`）、步驟 4 的不重疊部分（`test_daemon`、`test_aos_daemon_ctl`、`test_eca_hub`、`test_exec_rules`、`test_talk`、`impls/aos-daemon/tests/test_demo.py`）、步驟 5（aos-daemon README、`daemon.hpp` 註解；C++ 行為零改動）、步驟 6（N-13 補一句含例子、N-28 改回、`NORMS.md` 命名段加一條、附錄 1；附錄 2 是當時出處照舊）、步驟 7（三份 thinking 補註、本檔「方向題的答案」）、步驟 8（試驗場 `daemons/main/daemon.json`、`agents/resident_bob` 的 `ctl/loop.json`／`_entry`／README、試驗場 README；沒有舊名殘檔；`daemon_ws` 沒碰、當時沒有 aos-daemon 在跑）。

**22:35 另一輪 commit（7dcc3dc6）後接著做**（第一批 25 檔被頂層的 HANDOFF commit 971811ce 一起帶進去了，其餘另開 commit）：步驟 2（ai_tools：`aos_ai_base.py`、`aos_ai_daemon.py`、`aos-ai` 檔頭、README、`concepts.md`；`test_ai_tools`）、步驟 3（`aos_ws.loop_state` 只認 `state.json`、`LOOP_STATE_NAMES` 拿掉、`aos-listen --status` 不再印「（哪份）」；`test_human` 那案改成 `test_status_reads_only_state_json`、另一案的 regex 跟上；human README）、`demo/README.md`、code map 02-tests／06-3／08-a／09-lib／13-demo、`WAIT_USER` 那行。

**還沒做**：
- 方向題 1（`loops_ctl`／`loops_state`、execs／loops 統稱 proc）待明天跟使用者談。（11-03 已定案、11-03 晚使用者說「解決了」，見上方「方向題的答案」）
  - 11-03 定案，見 [11-03 procs](../03/procs.md)。
