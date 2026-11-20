# 使用者 11-20 晚瀏覽剛重建的 `~/aos-home` 時說的話（逐字，陸續追加）：問題與之後該改進的點，只記錄

← [2026-11-20](README.md)｜第一則另放在 [agent-fsm-py-收進子夾-1120](agent-fsm-py-收進子夾-1120.md)

使用者：「總之我接下來說的，都麻煩先記下來。」——這份照時間順序一則一段：原話逐字、頂層當場查到的現況、沒問的事。都沒派線、沒改程式。

## 第 2 則：範本的 .py 沒要覆蓋就從 AOS_HOME 取；hook_points.json 的 provider；description 與 _description；interfaces.json 的規範

### 原話

「總之我接下來說的，都麻煩先記下來。然後還有，這些範本的.py，感覺都是一些基礎的東西，感覺沒有要覆蓋的話，就應該可以從env:AOS_HOME裏面直接取，這樣ann底下會很乾淨。或許之後AOS_HOME那邊也要來做架構的重構，不然這些.py往後會難以維護。然後還有問題：hook_points.json這塊我看不懂，他的provider只能有一個嗎？我還以爲會是多個provider，比如"agent-fsm":{...}呢。然後ann/底下好多.json都有description，怎麽不是_description？這樣或許會比較符合aos體系的index那套？有原因嗎？interfaces.json有規範嗎？還是想到啥寫啥？」

### 他的想法（照原話整理）

- 範本的 .py 是基礎的東西：沒有要覆蓋，就從 `AOS_HOME` 直接取，`ann/` 底下才乾淨。
- 之後 `AOS_HOME` 那邊可能也要做架構重構，不然這些 .py 難維護。
- 三個疑問：`hook_points.json` 為什麼一份只有一個 provider（他以為是 `"agent-fsm": {...}` 多個並列）；為什麼是 `description` 不是 `_description`（想對上 index 那套）；`interfaces.json` 有沒有規範。

### 現況（頂層當場查的）

- **provider**：一份 `hook_points.json`＝一個提供者（發事件的那支程式）的全部點，格式是 `{"description", "provider": "agent-fsm", "points": {…}}`（[aos-hook-plan-1120/01-宣告格式](aos-hook-plan-1120/01-宣告格式.md)，程式 `py/aos/hook_point.py`）。多個提供者是在 `interfaces.json` 的 `aos-agent.hook_points` 清單裡並列：ann 那份是 `[{"provider": "aos-loop"}, "hook_points.json"]`——前一項指 aos 自己帶的 loop 那份，後一項指本夾這份。所以「多個」有，但拆成多份檔、由清單串起來，不是一份檔裡多個鍵。這是今天設計線定的，使用者沒被問過這一格。
- **description**：ann 夾裡有頂層 `description` 鍵的是 `hook_points.json`、`hooks.json`、`loop.json` 三份；其餘（`fsm.json`、`llm.json`、`tools.json`、`interfaces.json`、`_metainfo.json`、`body.json`、`subagents.json`）沒有。條文裡找不到「為什麼叫 `description`」的理由；規範只寫「`_` 開頭的 key 是普通 key，沒有附註慣例」（[命名（續）01](../../../docs/NORMS/命名-續-概念搬來的檔名/01-入口-metainfo-介面-血緣.md)）。index 那套的寫法是上層節點的 `_index`（或 `_metainfo` 的 `index`）裡一項 `{名: {"description": …}}`（N-69）；ann 夾沒有 `_index.json`，這三份的 `description` 是各檔自己寫給人看的一句，`index_view` 不讀它。
- **interfaces.json**：有規範但很薄。[命名（續）01「宣告介面」](../../../docs/NORMS/命名-續-概念搬來的檔名/01-入口-metainfo-介面-血緣.md)只定：這個檔名是固定名、資料夾用它宣告遵守哪些介面、其餘檔名由它指定、例 `{"aos-agent": {…}}`。每個介面底下能有哪些鍵沒有一張總表：`aos-agent` 那格的鍵是各線陸續加的（附錄 4 記著 11-10 加 `history`、`hooks`、`llm_keys`，11-20 加 `hook_points`），壞了怎樣寫在 [附錄4 持久檔](../../../docs/NORMS/附錄4-持久檔.json)。

### 沒問的

- 範本 .py 從 `AOS_HOME` 取：今天用 `std.fsm()` 編譯出來的定義與 reviewer 已經是「借 agent-fsm 的格程式」（設計稿 01 的表）；`cp -r` 抄出來的 ann 則整份帶著。他要的是不是把起手範本也改成借的，沒問。
- `description` 要不要改成走 `_index`／`_metainfo`、`hook_points.json` 要不要改成一份多個 provider、`interfaces.json` 要不要補一張鍵的總表：他是在問原因，還沒說要改。

## 第 3 則：聽完第 2 則的現況後的裁定

### 原話

「起手範本確實該改成要借的，之後做。interfaces.json就保持現在想加啥就加啥，我覺得很好，以後有需求再去定規矩，反正就一個"想看這個agent/kernel/...有提供啥界面，就去看interfaces.json，找自己想看的"。hook_points.json這塊，對於可hook點的宣告格式，之後要來討論一下，我要審過，並且會提出建議，比如直接拿json schema或許會更好。description這塊看起來就是放着，那OK，就這樣。然後是~/aos-home/llm，我也有些問題」

### 決定

- **起手範本改成借的**（格程式不整份帶進定義夾、從 `AOS_HOME` 取）：要做，「之後做」。
- **`interfaces.json`**：保持現在這樣，想加什麼就加什麼；以後有需求再定規矩。它的定位就是「想看這個 agent／kernel／…有提供什麼介面，就去看 interfaces.json，找自己想看的」。
- **`hook_points.json` 的宣告格式**：之後要討論，他要審過、會提建議（例：直接拿 json schema 或許更好）。在他審之前，現在的格式算暫定。
- **`description`**：放著，就這樣。

## 第 4 則：問 `~/aos-home/llm/kernel.json` 的格式

### 原話

「他的kernel.json的格式能說一下嗎」

### 現況（頂層照文件答的）

格式的出處是 [kernel_llm docs/01-用法](../../../py/tools/aos/kernel_llm/docs/01-用法.md)：頂層是整台 llm kernel 的設定（`slots`、`reserved`、`backends`、`timeout_ms`、`exec`、`endpoint`、選填 `budget`、`aging_cycles`），`endpoints` 是「代號 → 一個能力包」的表；包裡的鍵分兩種，kernel 自己看的（`exec`、`slots`、`budget`、`speed`、`backend`、`session_key`）與原樣交給端點函數的（`url`、`model`、`fixed`、`cost`、`context`、`summary`、`script`…）。只回答，他還沒說想法。
