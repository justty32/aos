# `knowledge/aos/tools/goal.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/goal.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 goal

你的目標：一句話，你一直做到完成為止。當你自己停下來（你的回覆沒有呼叫任何工具）而且沒有信在等，aos 會在你的對話裡放一則訊息：

`[aos] goal: Fix the failing test in src/. (reminder 2 of 10. Keep working on it; ...)`

然後繼續做，或結束它。信永遠優先：只有佇列空了才會來提醒。

```json
{"op": "get"}
{"op": "set", "text": "Fix the failing test in src/.", "limit": 10}
{"op": "done", "reason": "the test passes now"}
{"op": "done", "status": "abandoned", "reason": "the file it needs is gone"}
{"op": "pause", "reason": "waiting for bob's answer"}
{"op": "resume"}
```

- `get` -> 幾行 `status TAB active`、`text TAB ...`、`reminded TAB 2 of 10`、`reason`、`set_by`、`updated`；或 `no goal`。
- `set` 取代你原本的目標，計數從 0 開始。人或你的上層 agent 也能設定、暫停、繼續或清除它（`aos-agent goal`、`aos/cli/goal.json`）。
- 計數什麼時候算數、什麼時候用 done 或 pause：`aos/tools/goal.json#/rules`。

錯誤：`aos/tools/goal.json#/errors`。

---

**`#/rules`**

# goal：提醒怎麼運作

- 以下全部成立時才會來提醒：你的佇列裡沒有信在等、你最後一則訊息是沒有呼叫工具的回覆（或你的對話還是空的：那目標就是你的第一則訊息），而且目標是 `active`。
- 每次提醒都是你對話歷史裡多一則訊息；目標文字要短。
- 進展：提醒之後只要你呼叫 `goal` 以外的任何工具，計數就重新從 0 開始。只是講話，或呼叫 `goal`（任何 op），不算。
- 上限：連續 `limit` 次提醒都沒有進展（預設 10）後，你會收到最後一則訊息 `[aos] goal: reminder limit 10 reached; goal paused ...`，目標變成 `paused`。`resume` 讓它從 0 再開始。
- `done`：只在目標真的完成（`status` done）或做不到（`status` abandoned）時用。給一句理由。之後就不再提醒；`set` 給一個新目標。
- `pause`：暫時沒辦法繼續時用：你在等回覆、等人或等另一個 agent。給一句理由。信不會讓它繼續：能繼續時自己呼叫 `resume`。在 agent-fsm 裡，如果你暫停自己的目標之後來了一則訊息，而你回覆時沒呼叫 goal，你會收到一則 "[aos] goal: paused ..." 提示；目標不會幫你繼續。
- 目標存在你的 stack（`goal.json`），不在你的對話歷史裡：對話歷史被摘要時它還在。

---

**`#/errors`**

# goal：錯誤

- `GoalMissing`：你沒有目標。先 `set` 一個，或什麼都不做。
- `GoalEnded`：目標已經 done 或 abandoned，所以不能暫停或繼續。還有事要做就 `set` 一個新的。
- `GoalBad`：你 stack 裡的目標檔壞了。`set` 會重新寫它。
- `WriteFailed`：目標檔寫不進去（磁碟、權限）。回報它。
- `CommandMissing`、`WsMissing`、`LaunchFailed`、`CommandFailed`、`DaemonFailed`：輔助程式不見了或起不來、沒有工作區、輔助程式失敗或超過 60 秒，或 daemon 沒在時間內回覆。這些是環境問題：回報它們（`aos/errors.json`）。
- `DaemonMissing`、`InstanceMissing`：你不是在 daemon 底下跑，所以工具找不到你。回報它。
- `ArgumentsBad`、`OpUnknown`：op 是 get、set、done、pause、resume 其中之一；set 需要 `text`；done 和 pause 需要 `reason`；`limit` 是 1 到 1000 的整數；目標文字最多 1000 個字元。見 `aos/errors/common.json#/input`。
