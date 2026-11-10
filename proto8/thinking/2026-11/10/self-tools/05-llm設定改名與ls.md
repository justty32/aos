# 05 llm 設定：鍵改名 model、set 提醒、可調參數、ls／set／rm／reset

← [self-tools](README.md)

## 使用者原話

頂層列的題：1 set 什麼都收、鍵打錯或代號不存在不報錯；3 fsm 認 `endpoint`、eca-claude 認 `model`，鍵名不一；4 能調的只有換哪個腦；5 沒有單一鍵的 unset；6 show 看不出哪些是自己改的。

- 「不用管kernel」
- 「3.把fsm認的endpoint這個key，也改名爲model吧...麻煩的話就算了。1.跳warinig就好。4.基本上，model所指向的東西，他就是可以得到快取優勢的東西，然後agent能調的，就是一些與快取無關的。我是希望這樣啦。5.那就來個ls?」
- 頂層提案 `llm ls`（取代 show）、`ls -l`、`set`、`rm`、`reset`，問 show 換掉還是兩個都留：「換」

## 做了

- **鍵改名（題 3）**：agent-fsm 的腦設定鍵 `endpoint` 改叫 `model`，不留舊名。brain.py 組請求時照舊填進 kernel 請求信 body 的 `endpoint` 欄，kernel 一行沒動。跟著改的有：
  - wait.py（判斷要不要重組的那段）；
  - thought 的參數 `endpoint` 改名 `model`；
  - defs 分組讀 llm.json 的 `model`、review_round 降級梯子寫 llm.json 的 `model`（這兩支自己的輸出欄照舊叫 endpoint，指的是 kernel 包）；
  - reviewer 的 llm.json 說明、extras 兩支檢查腳本、測試、文件。
- **set 提醒（題 1）**：定義的 `interfaces.json` 在 `aos-agent` 裡多一格 `llm_keys`（身體認的鍵名）。`aos-agent llm set` 碰到不在單子上的鍵，照存，stderr 印一行 warning。self_llm 把這行也印進 stdout，因為腦只看得到 stdout。
- **可調參數（題 4）**：新檔 `templates/agent-fsm/llm_settings.py`。brain.py 把下表的鍵轉成型別後放進 `request`。kernel 原樣轉發 request，llm_http 再蓋上包的 `fixed`，所以 kernel 不用動。
- **ls／set／rm／reset（題 5、6）**：`aos-agent llm` 的 show 拿掉不留。
  - 沒給 ACTION＝`ls`，`ls -l` 多一欄來源（`definition`／`agent`，蓋掉定義值的再接 `definition: 原值`），`--json` 印陣列。
  - `rm KEY…` 只拿掉自己改的鍵，沒改過的＝`KeyMissing`，拿光了就刪檔。
  - self_llm 的 op 跟著改成 ls（可帶 `long`）、set、rm（`keys`）、reset。
- 測試：`cmd/aos-agent/tests/test_llm.py` 新增 3 支；self_llm 測試改新口徑並補 warning 那支；agent-fsm 的 test_cells 加一支（model、調整鍵、wait 重組）。
- 驗收隊員回報的兩件也順手改了：
  - self_llm 說「下一題起生效」不對，brain 每格都重讀，所以改成 `(takes effect from your next brain call)`；
  - 沒有任何設定時 stdout 會是空的，現在印 `(no settings: your body uses its defaults)`。

## 開給 agent 調的鍵（代定，可翻）

| 鍵 | 型別 | 為什麼算「與快取無關」 |
|---|---|---|
| temperature、top_p | 數 | 取樣參數，不動到前綴 |
| max_tokens | 整數 | 只限制輸出長度 |
| seed | 整數 | 取樣用 |
| presence_penalty、frequency_penalty | 數 | 取樣用 |
| stop | 字串（一個停止句），或 JSON 字串陣列 | 只影響輸出何時停 |

不開：system、tools、reasoning 類（reasoning_effort、thinking 等）、response_format、logit_bias。前三類會改前綴或讓快取失效；後兩個不是調答案品質的，先不放。

- 包的 `fixed` 照舊蓋過 agent 設的值。例如 kernel 範本的 `gemma` 包寫死 `temperature: 0.7`，agent 再怎麼設 temperature 都不會生效。
- **eca**：claude CLI 沒有 temperature 這類取樣旗標，所以只認 `model`，`llm_keys` 寫 `["model"]`。

## 其他代定（可翻）

- `llm_keys` 寫在定義的 `interfaces.json` 裡、跟 `llm` 放在一起。沒寫這格＝不知道身體認哪些鍵，就不提醒。
- `llm ls -l` 的形狀是 `鍵=值 TAB 來源[ TAB definition: 原值]`，預設 `ls` 照舊一行一個 `鍵=值`。
- `rm` 一個沒改過的鍵＝`KeyMissing` 報錯，不是 warning。理由同「那就報錯」：錯誤對小模型比較有用。
- thought 的子 agent 預設抄父的 `model`，但只在父與子的定義 `llm_keys` 一樣時才抄。不然像 eca 父的 `sonnet` 會被抄給 fsm 子，當成 kernel 包名，就叫不到了。
- `model` 寫成空字串或非字串＝CfgBad，調整鍵轉不了型別也＝CfgBad。wait 看到設定壞了就回 think，由 brain 報錯。

## 沒做

- agents 的 tooldef 例子 `{"endpoint": "fake"}`：agents 要被 agents-split 隊拆掉，這裡不動，留給它。
- knowledge/aos 裡還有舊寫法（`llm --target bob set endpoint=smart-high`、self_llm 的 show）：這裡歸 json-memory 隊，新節點內容在 [01](01-self_llm知識庫節點.md)。
- 試驗場 stack 裡 4 份舊鍵：改法寫在 [02](02-試驗場怎麼玩三個工具.md) 刷新段，只寫沒執行。
