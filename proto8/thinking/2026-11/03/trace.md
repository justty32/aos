# 2026-11-03 trace.jsonl 整個拿掉

← [thinking README](../../README.md)｜月份表 [2026-11](../README.md)｜精神同 [11-02 state 窗有變才寫](../02/state-window/README.md)｜條文：[N-39](../../../docs/NORMS/07-基礎設施-組合子.md)、[P-07](../../../docs/CONVENTION/01-保證佈局入口.md)、[P-38](../../../docs/CONVENTION/06-巢狀.md)｜實作：[impls/aos-fsm](../../../impls/aos-fsm/README.md)、[bin/aos-eca-turn](../../../bin/aos-eca-turn)（b3eebfa8）

本檔只記使用者原文（逐字）、決定、頂層照原則代定的細節（可翻案）（[user/03](../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

## 使用者原文（11-03，逐字）

> trace.jsonl會無限累加...老實說我覺得這個檔案沒啥必要。

> 整個拿掉。是這樣的，我一直在減輕負擔，好比說loop,daemon他們原本是每次exec都會更新一次state和其他東西，我們改成了只有必要的時候才更新。而像是這次的trace.jsonl，會需要用到它的這些指令，除了aos-listen之外我都沒聽過。而aos-listen --status其實也是沒必要的，要看他的狀態，應該是用aos-eca-ctl status。

## 決定（11-03，使用者）

1. **`trace.jsonl` 整個拿掉**：aos-fsm 與 aos-eca-turn 都不再寫。
2. **`aos-listen --status` 拿掉**；外部 coding agent 的狀態看 `aos-eca-ctl status`（同日加的 `state` 別名，[eca 17](../../2026-10/30/eca/17-11-03-批次-status.md)）。（11-04 已改：aos-eca 併進 `aos-agent`，看狀態用 `aos-agent state`／`status`，見 [11-04 aos-agent 子命令](../04/aos-agent/01-子命令.md)）
3. **topdown 兩個實驗**（galtxt-a、galtxt-b 拿 fsm 的 `trace.jsonl` 量時間與格序，trace 拿掉後 7 個測試紅）：使用者 11-03「封存 topdown」——整個搬進 `proto8/archive/topdown/`、測試不再跑（b8d75285）。（11-04 已改：使用者 11-04「topdown資料夾刪掉。」，archive/topdown 整個刪，c25fc582）

## 頂層代定（11-03，可翻案）

1. **寫的人**：aos-fsm 拿掉寫 trace 的程式，每次只動 `state.txt`；state 寫不了照舊 `WriteFailed`、退 1。（11-04 已改：`state.txt` 改名 `stage.txt`，見 [四元素 07 步 3](../04/four-elements/07-實作步驟.md#步-3fsm-的-statetxt-換同義詞題-10)）aos-eca-turn 不寫 trace：壞信的原因記 `$AOS_STACK/mailbox_warning.txt` 一行、只留最後一封（N-16）；CLI 那層失敗只剩 stderr 一行，信照舊留在 `cur/`。
2. **讀的人，拿掉的**：`aos-listen --status`、`--trace`、`LetterUnclaimed`；`aos-chat --trace`、`/trace`、`/status`；`aos-ai trace` 子命令與 `status` 的 `trace_tail`；nvim 的 `:AosTrace`；`lib/aos/aos_ws.py` 讀 trace 的函式；`aos_human.py` 讀 trace 的函式。給了拿掉的旗標＝`FlagUnknown`，不留別名或提示。
3. **「停在哪一格」的替代**：不另做。listen 沒人在跑時提醒「信在 queue 的 new/ 或 cur/、沒人在跑，錯誤一行在跑它的那個終端機」；chat 替你跑失敗時說「agent 停了（agent 結束碼 N）」（P-20、C-52：上層不替下層說原因）。aos agent 的 `phase` 直接看 stack 的 `state.json`。
4. **舊 stack 裡留著的 `trace.jsonl`**：沒人讀也沒人寫，留著不刪（使用者自己清）。
