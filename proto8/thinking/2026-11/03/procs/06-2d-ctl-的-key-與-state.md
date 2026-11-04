← [入口](README.md)｜涵蓋：規劃（fable，照原則定的細節，可翻案） › 2d. ctl 的 key 與 state 的 `phase`：對過名詞表，不用換字（代定）、3. C++ 改哪（`impls/aos-daemon/src/`；aos-loop 零改動）｜上一份 [05-2c-起-停-暫停-代定](05-2c-起-停-暫停-代定.md)｜下一份 [07-4-舊名怎麼辦-遷移-當沒看到](07-4-舊名怎麼辦-遷移-當沒看到.md)

### 2d. ctl 的 key 與 state 的 `phase`：對過名詞表，不用換字（代定）

使用者「ctl 這塊可以的話也跟著這些名詞走，比如 stopped 改 paused」「state 也是」。對過 § 0 的表：aos-loop 的 ctl `paused`＝pause／resume 那態、`stopped`＝stop 那態（跑完這次退 0、stack 留著、再起 aos-loop 就接著）——**兩個字各管一態、今天就在表上**，使用者例子裡的「stopped 改 paused」會把兩態併成一個，不是他要的；`stopped` 不改。state 的 `phase` `running`／`waiting`／`paused`／`done`／`stopped` 五個字也都在表上（`waiting` 是 running 的細分、`done` 是「自己走完」、訊號與自己出錯併進 `stopped`——「同一種狀況挑一個字」）。所以 **aos-loop 的 C++ 不用為名詞改任何字**；要改的只有條文把這張表寫進去（N-06／N-07／N-09 加「11-03 名詞表」一句、C-54 R4 例子）。今天「ctl 的 `stopped` 會殘留、再起就馬上退」那個坑，由 [ctl-commands § 2](../ctl-commands/02-2-loop-怎麼知道這道是新的-沒有信.md#2-loop-怎麼知道這道是新的沒有信箱) 的基準線拿掉（起來第一次讀的 ctl 當已看過）；ctl 的 key 從 `paused`／`stopped` 改成 `cmd`＋動詞，state 的五個 `phase` 不動。

### 3. C++ 改哪（`impls/aos-daemon/src/`；aos-loop 零改動）

| 檔 | 做什麼 |
|---|---|
| `daemon/daemon.hpp` | 檔頭說明改統稱；`loops_`／`execs_`→`procs_`；`want_`／`want_execs_`→`want_`＋`stopped_`（名字集合）；`read_loops`／`read_execs`／`check_apart`→**`read_procs`**（解指示詞、`check_name`、照 § 2 判、`fix_ws` 擴成 `fix_paths` 處理 `ws`／`stack`）；`reconcile(want)` 一個參數；`ended_` 只記名字；`Child` 多 `stack`；預設名註解 |
| `daemon/daemon.cpp` | 建構子讀 `procs`（舊 key 不理）、預設名 `procs_ctl.json`／`procs_state.json`／`procs_state_procs/`；拿掉 `check_ctl` 的 `ctl_note_`；`adopt` 一張表、`stack` 從列上接、`stopped` 列接成 stopped；`log_line` 拿掉 `table`；`reconcile`：拿掉 `:568` 種類比對、小格＝`stack` 或 `procs/<名字>`、stopped 集合（寫子 loop ctl `stopped`、列 `stopping`→`stopped` 不拿掉、不起；拿掉集合→清子 loop ctl 的 `stopped` 再起）；子項自己退了照 11-02 從表上拿掉，只有在 stopped 集合裡的退了才留 `stopped`（衝突 2「照舊拿掉」）；`check_name` 訊息 |
| `daemon/windows.cpp` | `read_procs_ctl` 認 `procs`、`procs_added`、`procs_removed`、`procs_stopped`、`procs_started`、`seq`；`check_lists` 名單走 `read_procs`、三個名字陣列同 `procs_removed` 的檢查、`procs_stopped` 有 exec 型＝不採用；`write_more` 一張表、列多 `stack`、`phase` 三個字；`write_parts` 一張 |
| `daemon/mailbox.cpp` | `apply_letter` 認四個陣列 key＋`procs_added`；底多 `stopped_`；`procs_removed` 同時清集合；exec 型 stop＝壞信；「兩半同名」段刪 |
| `child/child.cpp`／`child.hpp` | 小格＝給的路徑（預設 `procs/<名字>/`）；指定 `stack` 時 `mkdir -p`；`spawn`／`spawn_exec` 形狀照 § 2；`ws`／`stack` 不灌進 `loop.json`；`row()` 多 `stack` |
| `README.md`、`bin/aos-daemon` 檔頭 | 名字同步；目錄樹；加「寫法決定怎麼起」「自己的 stack」「起停暫停」三段與 § 2 第 9 條那個坑 |
| `tests/test_cli.py`、`tests/test_demo.py` | 字串改名（約 400 行）；新案：字串／最小物件＝跑一次、多一個 key＝loop、同名改寫法不重起、舊 key 不理、`--json`；`stack`（落在 S、不在就建、相對從 cwd、`$env`、列上有、adopt 接回、同一 S 不擋、null／非字串）；起停（stop 寫子 ctl `stopped` 跑完退、列 `stopped`、不重起；start 清 ctl 再起同一 stack、ctl 有 `paused` 起來是暫停；ctl 拿掉名字＝起；add＋stop＝列 stopped 不起；exec 型 stop＝不採用／壞信；stopped 被 rm；`kill -9` daemon 再起 stopped 的不被起；daemon paused 時等解除；信來不叫起）；刪 `check_apart`／種類重起那幾案 |

行為上真正變的：名單一份、`loops` 裡的字串改跑一次、同名改寫法不重起、`ctl_note_` 拿掉、log 少 `table`、每項可指定 `stack`、多了 stop／start（stopped 的列）。期望表算法、信怎麼套、切檔、判活、log 開關不變。aos-loop、aos-exec、aos-fsm 零改動。
