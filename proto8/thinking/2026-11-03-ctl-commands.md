# 2026-11-03 loop 的 ctl.json 改成下指令（動作），不是寫期望狀態；不用信箱、誰能寫就能控制

← [thinking README](README.md)｜月份表 [2026-11](months/2026-11.md)｜出發點：[11-03 procs § 0 名詞表](2026-11-03-procs.md#0-名詞表代定)（動作 add／rm／start／stop／pause／resume）與頂層攤開的「宣告式（今天）vs 指令式」｜被本條改口的：[N-06、N-07、N-08、N-11、N-14](../docs/NORMS/05-基礎設施-窗.md)（loop 的 ctl 那半）、[C-54 命名方法 R4](../docs/CONCEPTS/01-設計理念/C-54-命名方法.md)（ctl 的 key 用狀態詞）、[11-02 state 窗](2026-11-02-state-window.md)（「ctl 有變才算變動」照舊、形狀換）｜不動的：[N-54](../docs/NORMS/04-基礎設施-loop與daemon.md) daemon 管別人的 `procs_ctl.json`（仍是宣告的名單）、[N-09](../docs/NORMS/05-基礎設施-窗.md) state 只有自己寫、[P-36](../docs/CONVENTION/06-巢狀.md)、[C-52](../docs/CONCEPTS/01-設計理念.md)｜程式：[aos-loop](../impls/aos-loop/README.md)（`src/engine/window.cpp` `read_ctl`、`loop.cpp` `serve`）、[aos-daemon](../impls/aos-daemon/README.md)、[aos-daemon-ctl](../bin/README.md)、[aos-eca](../extras/eca/README.md)、[ai_tools](../extras/ai_tools/README.md)、[aos_ws／aos-listen](../extras/human/README.md)｜場地 `~/code/playground/`（不在 git）

本檔只記使用者原文（逐字）、決定、查清的現況、fable 照原則定的規劃（可翻案）、原則沒講清楚要使用者一句話的衝突與方向題（[user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。**只規劃、沒實作。** 跟 [11-03 procs](2026-11-03-procs.md) 同一天、它的 § 2c（daemon 怎麼停／起子 loop）靠本檔。

## 使用者原文（11-03，逐字）

頂層攤開今天 loop 的 ctl.json 是「把我們希望它成為的狀態寫進去」（宣告式：`{"paused": true}` 整份就是期望、沒寫的回初始值），對照「下指令」：

> ctl這塊，我們目前是"把我們希望它成為的狀態寫進去"，我在想是否能改？改成就普通的下指令，用動作

頂層列了兩邊的得失（宣告式：寫幾次都一樣、不會漏；指令式：跟名詞表的動詞對上、人好懂，但要知道哪封是新的），使用者：

> 還是用指令吧，不然大家不好理解。但是loop就不要用mailbox那套，就是誰能寫ctl.json就能控制。

## 決定（11-03，使用者）

- **loop 的 ctl.json 改成下指令**：寫進去的是一個**動作**（名詞表的動詞 `pause`／`resume`／`stop`，加上今天 ctl 能做的節奏調整 `max`／`interval_ms` 與回音用的 `seq`），不是「我要它現在怎樣」。
- **不用信箱那套**（沒有 `new/`、`tmp/`、認領、一封一封）：ctl.json 仍是**一個檔、一扇窗**，**誰能寫這個檔就能控制它**；後寫的蓋前寫的，被蓋掉的指令就沒了——使用者接受（「誰能寫 ctl.json 就能控制」；要不漏用 daemon 那邊的信箱，不是 loop 的事）。
- **只有 loop 這一系控制自身的 ctl 改**；daemon 管別人的 `procs_ctl.json`（名單）照 [N-54](../docs/NORMS/04-基礎設施-loop與daemon.md) 仍是宣告的期望表（它要的是「表上有誰」，本來就不是動作；要動作有信箱）。
- 被改口的條文只加 11-03 註、不改寫（[規劃 § 6](#6-條文只加-11-03-註)）。

## 現況（查清的，不是規劃）

- **今天的 ctl**（`impls/aos-loop/src/engine/window.cpp` `read_ctl`、README「窗」）：每跑一次（睡著時每秒）讀一次；認 `paused`、`stopped`（布林）、`max`、`interval_ms`、`seq`（非負整數），其他 key 忽略；整份就是期望——**沒寫 `paused` 就等於不暫停**；讀到壞的整份不採用、原因進 state 的 `ctl_warning`、讀到好的清回 null；檔不在＝還沒人寫、維持上一份好的。`stopped` 壓過 `paused`：這次跑完退 0、phase `stopped`。`seq` 只拿來回音（state 的 `ctl_seq`）。
- **state**（`write_state`）：`{phase, counter_runs, max, interval_ms, paused, ctl_seq, ctl_warning, pid, started_at_ticks, boot_id, updated_at}`，有變才寫；`paused` 是 ctl 蓋過設定檔之後生效中的值。loop **起來時不讀自己的舊 state**（state 是窗不是存檔，N-09）；只有 daemon 的 adopt 讀自己上次的 `procs_state.json`（N-28「state 窗就是 save 檔」）。
- **誰在寫 loop 的 ctl**：人（`echo '{"paused": true}' > .stack/ctl.json`，demo／README 的例子都這樣寫）、ai_tools `daemon down`（daemon 的 ctl 寫 `stopped`）／`up`（**清掉殘留的 `stopped`**）、aos-eca `install`（**清掉子 loop 殘留的 `stopped`**）、常駐 bob `_entry` 的 `clear_stopped`、[procs 規劃 § 2c](2026-11-03-procs.md#2c-起停暫停代定)（daemon 替子 loop 寫 `stopped`、start 前清掉；aos-daemon-ctl `pause`／`resume` 寫 `paused`）。「殘留的 `stopped` 再起就馬上退」是今天宣告式最常踩的坑，三處都在手動清。
- **誰在讀 loop 的 state**：`aos_ws.loop_state`／aos-listen `--status`（`phase`、paused）、aos-eca（子 loop `phase` done／stopped、`code`）、ai_tools `running()`（`phase not in (done, stopped)`＋pid 判活）、quiet.py、daemon 的 adopt（自己的 `procs_state`，不是子項的）。
- **條文**：N-06「ctl.json 寫的是『我要它現在怎樣』，不是一條條指令；整份就是全部的期望，寫幾次都一樣；沒寫的欄位＝回初始值；讀的人只讀不寫；誰都可以寫，後寫的算」——前半被本條改口、後兩句照舊。N-07 兩個旗子 `paused`／`stopped`＋`max`／`interval_ms`。N-08 壞的不採用、`ctl_warning`。N-14 窗總則「判斷變化比內容或序號，不比 stat；回音以序號 seq 為準」。C-54 R4「ctl 的 key 是宣告狀態、一律用狀態詞」。N-11 ctl 只能蓋節奏類 key。

## 規劃（fable，照原則定的細節，可翻案）

### 1. 指令長什麼樣

ctl.json＝**一個 JSON 物件＝一道指令**（不是陣列、不是一行一封）：

```json
{"cmd": "pause", "seq": 7}
{"cmd": "resume"}
{"cmd": "stop"}
{"max": 20, "interval_ms": 500}
{"cmd": "resume", "max": null, "seq": 8}
```

- **`cmd`**（選填，字串）：`pause`／`resume`／`stop`——名詞表的三個動詞（[procs § 0](2026-11-03-procs.md#0-名詞表代定)；`add`／`rm`／`start` 不是 loop 自己做得到的事，不認）。不認得的值＝整份壞（N-08）。
- **`max`、`interval_ms`**（選填）：節奏調整，**跟指令一起或單獨都可以**；寫了就是「從現在起用這個值」、一直有效到下一道再改；寫 `null`＝回設定檔／旗標的值。沒寫＝不動（**跟今天不同**：今天沒寫就回初始值——指令式沒有「整份期望」可回）。
- **`seq`**（選填，非負整數）：回音用，state 回 `ctl_seq`（N-14「回音以序號 seq 為準」）。寫的人想確認「loop 看到我這道了沒」就帶 seq、等 `ctl_seq` 追上；不帶也行。
- 其他 key 忽略（C-48）；指示詞照 N-45 解（`cmd`、`max`、`interval_ms`、`seq` 四格）；型別不對、`cmd` 不認得、解不開＝整份不採用、`ctl_warning`、維持原狀（N-08 一字不改）。
- 只有 `{}` 或只有 `seq`＝一道「什麼都不做」的指令（回音仍更新）。

### 2. loop 怎麼知道這道是新的（沒有信箱）

- **比內容**（N-14「判斷變化比內容或序號」）：每次讀 ctl，把解完的那份跟**上一次讀到的**比，**不一樣＝新指令、照做一次**；一樣＝同一道、不再做（所以人不用急著刪檔，檔留著沒事）。不用 `seq` 當新舊判準：寫的人不必先讀 state 算下一號，「誰能寫就能控制」才真的成立；`seq` 純回音。
- **讀的人只讀不寫**照舊（N-06 後半）：loop 不刪、不改名、不清空 ctl.json——那三種都是「讀的人寫檔」，而且刪了之後第二個人寫進來的就跟第一道分不開。
- **兩個人先後寫、loop 還沒讀**：後寫的蓋掉前寫的，前一道**就沒了**（使用者「誰能寫 ctl.json 就能控制」；N-06「後寫的算」照舊）。要「每一道都算數」是信箱的事，loop 不做；daemon 管名單那邊有 `procs_ctl_mailbox`。
- **同一道寫兩次**（內容一樣）＝不是新的、不重做；三個動詞本來就冪等（§ 3），所以就算重做也沒差。
- **檔不在**＝沒有新指令，維持現狀（今天「檔不在＝還沒人寫」照舊）；寫的人寫完**可以**刪掉它，loop 不在意。
- **起來時的基準線**：loop 起來第一次讀 ctl，那份**當作「已經看過」、不執行**（基準線）；之後跟它不一樣的才是新指令。這一條把「殘留的 `stopped` 再起就馬上退」那個坑**整個拿掉**——舊的 `{"cmd": "stop"}` 留在檔裡，新起的 loop 看一眼就當舊的，不用誰去清。代價：**起來之前**寫好的指令不會被執行（想讓它一起來就暫停，見 § 4）。

### 3. 三個動詞各做什麼（冪等）

| 指令 | loop 在做什麼 | 效果 | 已經在那個狀態時 |
|---|---|---|---|
| `pause` | 跑著 | 這次跑完不起下一次，phase `paused`，每秒再讀 ctl | 已暫停＝不動（回音更新） |
| `resume` | 暫停中 | 起下一次，phase `running`／`waiting` | 沒暫停＝不動 |
| `stop` | 任何 | 這次跑完退 0，state 最後一份 phase `stopped`、`code 0`（同今天的 `stopped`） | 已在收尾＝不動 |
| `max`／`interval_ms` | 任何 | 從下一次起用新值；`max` 改到比 `counter_runs` 小＝這次跑完就 `done` | 同值＝不動 |

- `stop` 壓過同一道裡的其他東西（同 N-07「stopped 壓過 paused」）；`{"cmd": "stop", "max": 5}` 就是停。
- 要當場收掉正在跑的那次照舊送訊號（N-07 10-28 改口），ctl 沒有 `kill`。
- daemon 是 loop：它自己的 ctl.json 同一套——`pause`＝整圈暫停（10-29 § 四 2：不起 exec、不調表）、`stop`＝照 P-36 收掉活著的子項、寫好 state、退 0。

### 4. 「現在暫停中」記在哪、再起時怎麼辦（代定）

- ctl 不再是「暫停的真相」（它只是最後一道指令）。**暫停中這件事記在 loop 的記憶體與 state.json 的 `paused`／`phase`**——state 本來就有這兩格（11-02 state 窗），讀的人（aos-listen `--status`、aos-eca、ai_tools）**一個字都不用改**。
- **再起時要不要繼續暫停**：使用者四態原文「休眠但是可以隨時叫醒**繼續跑指令或繼續暫停**」——醒來要能接著暫停。指令式下 ctl 給不了這個（§ 2 基準線），所以**loop 起來時若開了 state 窗、而且 `$AOS_STACK` 裡已有一份自己的 state.json、它的 `paused` 是 true，就起來先暫停**（第一份 state 寫 `paused`、每秒讀 ctl 等 `resume`）；其他欄位不接（`counter_runs` 從 0、`max`／`interval_ms` 回設定檔——state 不是存檔，只借這一格）。這是 N-28「state 窗就是 save 檔」的精神縮到一格，代定；嫌多就改成「起來一律跑」（§ 要使用者看的 沒列，因為使用者原文偏向「繼續暫停」）。
- 連帶：想讓一支 loop「一起來就暫停」，寫一份只有 `{"paused": true}` 的 state.json 不是辦法（state 只有自己寫，N-09）——正路是起來後馬上寫 `{"cmd": "pause"}`；daemon 下的 proc 用 `aos-daemon-ctl pause`。

### 5. 跟 daemon 的關係（[procs 規劃 § 2c](2026-11-03-procs.md#2c-起停暫停代定) 照本檔改）

- **daemon 的 stop（loop 型）**＝往子 loop 的 ctl.json 寫 `{"cmd": "stop", "seq": N}`（`seq`＝它自己數的，回音用；寫法 N-05 暫存改名）→子 loop 跑完這次退 0→列留 `stopped`（procs § 2c 第 2 條照舊）。
- **daemon 的 start**＝用列上的 `stack` 再起；**不用先清 ctl**（基準線，§ 2）——procs § 2c 第 3、6 條「start 前清掉 `stopped`」那兩句**作廢**；舊的 `{"cmd": "stop"}` 留著沒事。起來是跑還是暫停照 § 4（它自己的 state.json）。
- **aos-daemon-ctl `pause`／`resume`**＝寫子 loop 的 ctl `{"cmd": "pause"}`／`{"cmd": "resume"}`（不帶 seq 也行；要回音就帶）。`CtlMissing`（exec 型沒有 ctl）照 procs § 2c 第 5 條。
- **daemon 自己的 ctl**：ai_tools `daemon down` 寫 `{"cmd": "stop"}`；`up` 不再清殘留；eca `install` 不再清子 loop 的殘留；常駐 bob `_entry` 的 `clear_stopped` 拿掉。
- **daemon 管別人的 `procs_ctl.json` 不變**（宣告的名單＋`procs_stopped`／`procs_started`，N-54）。`ctl_warning` 兩扇窗各回各的照舊。
- 繞過 daemon、自己往子 loop 的 ctl 寫 `stop`→子 loop 退 0→daemon 看到「退了」→照 11-02 從表上拿掉（procs 衝突 2 使用者「照舊拿掉」）。

### 6. 條文只加 11-03 註

- **N-06**：補「11-03 改口（使用者「還是用指令吧，不然大家不好理解。但是 loop 就不要用 mailbox 那套，就是誰能寫 ctl.json 就能控制」）：loop 這一系控制自身的 ctl.json 改成**一道指令**（`cmd`＝`pause`／`resume`／`stop`、`max`／`interval_ms`、`seq`），不是整份期望；新舊比內容；後寫的蓋前寫的、被蓋的就沒了；讀的人仍只讀不寫；daemon 管別人的 `procs_ctl.json` 照舊宣告（N-54）」。
- **N-07**：`paused`／`stopped` 兩個旗子→`cmd` 的 `pause`／`resume`／`stop`；`max`／`interval_ms` 改成「寫了才動、`null` 回初始、沒寫不動」；`stop` 壓過其他照舊；10-29 補的 daemon `pause` 照舊。
- **N-08**：不採用的清單多「`cmd` 不認得」；其餘一字不改。
- **N-11**「ctl 只能蓋節奏類 key」：照舊（`max`／`interval_ms`），加一句「ctl 的動作見 N-07 11-03」。
- **N-14**：補例子「loop 的 ctl 用『比內容』判新舊、`seq` 只回音」。
- **C-54 R4**（ctl 的 key 用狀態詞）：補「11-03：loop 的 ctl 改成指令，key 是 `cmd`、值是動詞（名詞表的動作欄）；daemon 的 `procs_ctl.json` 仍是狀態詞（`procs_stopped`、`procs_started`）」。
- **N-28**／**N-54**：daemon 停子 loop＝寫 `{"cmd": "stop"}`；「ctl／state 沒寫就自己放」照舊。
- [11-02 state 窗](2026-11-02-state-window.md)、[11-02 ctl-state-names](2026-11-02-ctl-state-names.md)（`echo '{"stopped": true}' > ctl.json` 的例子）、[11-02 resident-bob](2026-11-02-resident-bob.md)（`clear_stopped`）、[11-03 procs § 2c](2026-11-03-procs.md#2c-起停暫停代定)：各補一句「11-03 ctl 改指令，見本檔」。10 月紀錄照舊。

### 7. 改哪

| 哪裡 | 做什麼 |
|---|---|
| **aos-loop** `impls/aos-loop/src/engine/window.cpp` `read_ctl` | 認 `cmd`（三個動詞）、`max`、`interval_ms`（含 `null`）、`seq`；解完跟 `ctl_last_` 比，不同才回「新指令」；第一次讀＝基準線不執行；壞的照 N-08 |
| `loop.cpp` `serve` | 暫停旗子改成成員 `paused_`（`pause`／`resume` 改它、`stop` 設 `stopping_`）；`max_`／`interval_ms_` 由指令改、`null` 回設定；起來時 § 4 讀舊 state 的 `paused`；其餘流程（每秒再讀、`stopped` 退 0、`done`）不變 |
| `config.cpp`、`include/aos/loop.hpp`、README「窗」段、檔頭 | `resolve_keys` 的 ctl 格換成四個；文案 |
| `tests/test_cli.py`（aos-loop）、`tests/test_loop.py` | 今天寫 `{"paused": true}`／`{"stopped": true}` 的案改 `{"cmd": …}`；新案：同一道不重做、改內容才做、`stop` 殘留再起不退、基準線、起來讀舊 state `paused`、`max: null` 回設定、`cmd` 不認得＝`ctl_warning`、兩人覆寫後寫的算 |
| **aos-daemon** `src/daemon/daemon.cpp`、`child/child.cpp` | 自己的 ctl 走 Loop 同一套（零改動）；[procs § 2c](2026-11-03-procs.md#2c-起停暫停代定) 的 stop 改寫 `{"cmd": "stop"}`、start 不清；`check_ctl` 的 `ctl_note_`（10-29 過渡提醒）隨 procs 拿掉 |
| `impls/aos-daemon/tests/test_cli.py`、`tests/test_daemon.py` | 寫 daemon ctl 的案改 `{"cmd": …}` |
| `bin/aos-daemon-ctl`、`bin/README.md`、`tests/test_aos_daemon_ctl.py` | `pause`／`resume` 寫 `{"cmd": …}`（procs § 2c 第 4 條照改） |
| `extras/eca/bin/aos-eca`、README、`tests/test_eca*.py` | `install` 拿掉清 `stopped`；`stop`／`start` 走 daemon（procs 後續）；讀 state 的字不變 |
| `extras/ai_tools/bin/aos_ai_base.py`、`aos_ai_daemon.py`、README、`tests/test_ai_tools.py` | `write_ctl` 改寫一道指令（`{"cmd": "stop", "seq": n}`）；`up` 不清殘留；`running()` 不變 |
| `lib/aos/aos_ws.py`、`extras/human/bin/aos_human.py`、`tests/test_human.py` | **不改**（讀 state）；README 若有 `{"paused": true}` 例子換字 |
| demo README（`daemon-2`、`agent-*`）、`impls/aos-loop/README.md`、`impls/aos-daemon/README.md`、`extras/langs/lua`（若有 ctl 例子） | `echo '{"stopped": true}' > ctl.json` → `echo '{"cmd": "stop"}' > ctl.json` |
| 試驗場（不在 git） | `agents/resident_bob/_entry` 拿掉 `clear_stopped`；README 例子 |
| 條文、code map | § 6；`code-map/proto8/01-impls與舊lib.md`（aos-loop `window.cpp`／`loop.cpp` 那幾格）、`14-aos-daemon.md`、`02-tests*.md` |

順序：aos-loop 先（步驟 1）→ aos-daemon 自己的 ctl 自然跟上 → 周邊三支＋demo 文案 → 條文。可以跟 [procs](2026-11-03-procs.md) 一起做，也可以先做（它不依賴 procs；procs § 2c 依賴它）。

## 要使用者看的

**沒有新的衝突或方向題**。跟原則對過：N-06 被改口的是使用者自己這句話決定的；「讀的人只讀不寫」「誰都可以寫、後寫的算」照舊；新舊判準走 N-14 已有的「比內容」；壞的處置走 N-08；起來讀自己 state 的 `paused` 那一格是 N-28「state 窗就是 save 檔」的縮小版、為了使用者原文「繼續暫停」——不喜歡就改成「起來一律跑」，一句話的事，列在 § 4 代定。

## 實作時代定（11-03，實作者照原則定的，可翻案）

- **檔不見了**：讀到「檔不在」也記成「上一次讀到的」，之後再寫進來的一律算新指令（就算內容跟刪檔前那道一樣）。讀的人照樣不刪不改。
- **基準線那份是壞的**：當看過、不提醒（`ctl_warning` 不動）——它本來就不執行；之後寫進來的新的壞的才提醒。同一份壞的一直留著＝只提醒一次（比內容）。
- **`ctl_seq`**＝最後一道**照做**的指令的 `seq`；基準線那份不回音（起來時 `ctl_seq` 是 null），照做的那道沒帶 `seq`＝null。
- **`cmd` 寫 `null` 或三個字以外的值**＝整份不採用（不當沒寫），原因「cmd 要是 "pause"、"resume" 或 "stop"」。
- **ai_tools `daemon down`** 寫指令時保留檔裡原本的 `seq` 再加 1（其他 key 清掉），所以連下兩次 `stop` 內容也不同、都算新的；`up` 不再清殘留。
- 實作：`impls/aos-loop/src/engine/window.cpp`（`read_ctl`、`read_old_paused`）、`loop.cpp`；aos-daemon 的 `tend()` 改看 `paused_`／`stopping_`。
