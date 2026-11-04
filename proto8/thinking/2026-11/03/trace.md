# 2026-11-03 trace.jsonl 整個拿掉

← [thinking README](../../README.md)｜月份表 [2026-11](../README.md)｜精神同 [11-02 state 窗有變才寫](../02/state-window.md)｜條文：[N-39](../../../docs/NORMS/07-基礎設施-組合子.md)（11-03 加註）、[P-07](../../../docs/CONVENTION/01-保證佈局入口.md)、[P-38](../../../docs/CONVENTION/06-巢狀.md)｜實作：[impls/aos-fsm](../../../impls/aos-fsm/README.md)、[bin/aos-eca-turn](../../../bin/aos-eca-turn)、[extras/human](../../../extras/human/README.md)、[extras/ai_tools](../../../extras/ai_tools/README.md)、extras/editors/nvim（11-03 封存，在 proto8/archive/）

本檔只記使用者原文（逐字）、決定、頂層照原則代定的細節（可翻案）、要使用者看的事（[user/03](../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

## 使用者原文（11-03，逐字）

> trace.jsonl會無限累加...老實說我覺得這個檔案沒啥必要。

> 整個拿掉。是這樣的，我一直在減輕負擔，好比說loop,daemon他們原本是每次exec都會更新一次state和其他東西，我們改成了只有必要的時候才更新。而像是這次的trace.jsonl，會需要用到它的這些指令，除了aos-listen之外我都沒聽過。而aos-listen --status其實也是沒必要的，要看他的狀態，應該是用aos-eca-ctl status。

## 決定（11-03，使用者）

1. **`trace.jsonl` 整個拿掉**：aos-fsm 與 aos-eca-turn 都不再寫。
2. **`aos-listen --status` 拿掉**；外部 coding agent 的狀態看 `aos-eca-ctl status`（同日加的 `state` 別名，[eca 17](../../2026-10/30/eca/17-11-03-批次-status.md)）。

## 頂層代定（11-03，可翻案）

1. **寫的人**：aos-fsm 拿掉 `append_trace` 與組那一行的程式，每次只動 `state.txt`；原本「先寫 trace 再寫 state」那條順序跟著沒了，state 寫不了照舊 `WriteFailed`、退 1。aos-eca-turn 不寫 trace：壞信的原因改記 `$AOS_STACK/mailbox_warning.txt` 一行、只留最後一封（跟 `lib/agent/queue` 同一套，N-16「壞信記 mailbox_warning」）；CLI 那層失敗只剩 stderr 一行，信照舊留在 `cur/`。
2. **條文只加註、不改寫**：N-39 加一條「11-03 加註：trace 拿掉」，N-39 本文、10-30 的 `next` 加註、N-38 與分檔開頭②③④講 trace 的地方照它讀；P-07、P-38 開頭各一句加註；其他提到 `trace.jsonl` 當例子的條文（N-13、N-28、N-30、N-43、P-16、P-19、P-43、C-65、名詞表）旁邊補「11-03 起沒有」。NORMS.md 表那列、條號表、各批出處各補一句。
3. **讀的人，拿掉的**：`aos-listen --status`、`--trace`、`LetterUnclaimed`（「信在 new/、trace 比信新＝沒人認領」那個判法靠 trace 的時間）；`aos-chat --trace`、`/trace`、`/status`（`/status` 印的就是同一份快照）；`aos-ai trace` 子命令與 `status` 的 `trace_tail`；nvim 的 `:AosTrace`（`:AosExec` 跑完改印 stack 的 `state.txt`，少一個 `,at` 鍵）；`lib/aos/aos_ws.py` 的 `last_jsonl`、`unit_of`、`failed`；`aos_human.py` 的 `last_trace`、`failure`、`unclaimed`、`Tail`、`status_lines`。給了拿掉的旗標＝`FlagUnknown`，不留別名或提示。
4. **「停在哪一格」的替代**：不另做。listen 沒人在跑時照樣提醒一次，改說「信在 queue 的 new/ 或 cur/、沒人在跑，錯誤一行在跑它的那個終端機」；chat 替你跑失敗時說「agent 停了（agent 結束碼 N）」，錯誤一行本來就印在上面（P-20、C-52：上層不替下層說原因）。aos agent 的 `phase` 直接看 stack 的 `state.json`，外部 coding agent 看 `aos-eca-ctl status`。
5. **測試怎麼看「跑了哪幾格」**：測試另放一支旁觀者 `proto8/tests/spy_bin/aos-fsm`（`aos_bins` 把它放在 PATH 最前面、`tool("aos-fsm")` 也給它）：跑真的 aos-fsm、跑前跑後看 `state.txt`，把 `{stack, state, code, next}` 記到 `$FSM_SPY_LOG`，`aos_bins.fsm_steps(stack)` 讀回來。`code` 是 aos-fsm 自己的結束碼（分岔接住＝0），所以 round／nia 那幾個序列裡原本記格的碼 10 的地方改成 0。fsm 本身的測試（impls 的 `test_cli.py`、`tests/test_fsm.py`）直接叫真的 fsm、改看結束碼與 state，另查 stack 裡不再出現 `trace.jsonl`。這是測試的工具，不是 aos 的程式。
6. **舊 stack 裡留著的 `trace.jsonl`**：沒人讀也沒人寫，留著不刪（使用者自己清）。

## 要使用者看的：topdown 兩個實驗靠 trace 量東西（未決，頂層沒動 topdown/）

topdown 的 galtxt-a、galtxt-b 是拿 fsm 的 `trace.jsonl` 當量尺的：

- **galtxt-a**：`train/common.py` 的 `run_cost` 把每次寫手／評審小格的 `trace.jsonl` 裡 `elapsed_ms` 加起來當 `time_ms`。trace 沒了，它不報錯、`time_ms` 一律變 0（評分表的時間欄就沒意義了）。
- **galtxt-b**：`deliver/_entry` 的 `measure.json` 用頂層 `trace.jsonl` 算每格花多久（`cells`）、圈數（`counter_cycles`＝brief 那格跑了幾次），用寫手小格的 trace 算寫手的牆上時間。trace 沒了，`cells` 只剩 deliver 自己、`counter_cycles` 變 0、寫手時間退回只算問腦的時間。`demo.sh` 結尾 `cat .stack/trace.jsonl`，檔不在、`set -e` 會讓 demo 以非 0 結束。
- **紅的測試（7 案，11-03 全套跑出來的；沒 skip、沒改）**：`test_topdown_galtxt_a` 的 `T.test_scene`、`CollapseT.test_inline_same_result`、`Round3T.test_train_whole`、`Round4OptT.test_train_selfopt`（都在讀 `trace.jsonl` 比格序，檔不在＝FileNotFoundError）；`test_topdown_galtxt_b` 的 `EndToEnd.test_q01`、`test_plan_bad_twice_then_resume`（同上）、`test_q08_redraft`（`counter_cycles` 0≠2）。`test_topdown_galtxt_b_fold` 沒紅（兩邊一樣少）。

可以怎麼辦（請挑一個，或另說）：

1. **topdown 自己記**：在它自己的格裡（或包一層小殼）把每格的開始時間、花多久寫到它自己的檔（例如 stack 裡的 `cells.jsonl`），deliver／train 改讀那個；stack 裡放什麼本來就是 agent 自訂（P-16）。量測回來，要動 topdown 的幾支程式與測試。
2. **不量時間了**：`time_ms`、`cells`、`counter_cycles` 這幾個欄拿掉（或圈數改從別處數，例如 `check.json` 的稿數），測試改看輸出與 `state.txt`、格序改用 `tests/spy_bin` 的旁觀者。改得最少，但失去時間數字。
3. **topdown 封存**：這兩個實驗當成過去的紀錄，測試標 skip 或搬走，不再跟著主線改。
4. **先只修測試**：測試的格序改用旁觀者（`aos_bins.fsm_steps`），量測欄位先放著變 0，等以後再決定 1 或 2。

## 瘦身候選（只列、沒動）

- **aos-chat**：拿掉 `/status`、`/trace` 後只剩「say＋等回答＋替你跑一次（`/run`）」，跟 `aos-say 話 && aos-listen` 加一行 `aos-exec` 差不多；以後 aos-agent 那套（[11-03 aos-agent](aos-agent.md)）出來時可以考慮收掉。
- **`lib/aos/aos_ws.py` 的 `loop_state`**：listen 不印快照之後，只剩 aos-ai `status` 的 `loop_phase` 在用。
- **nvim 外掛**：`:AosTrace` 拿掉後還有 `:AosExec`、`:AosGoto`、Lua 預覽；`:AosSay` 走舊協議（寫 `new/`、等 `out/`），範本都走 queue 之後幾乎用不到。
