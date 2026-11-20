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

## 第 5 則：聽完 kernel.json 格式之後

### 原話

「這塊我之前好像也沒審過...不過這是kernel_llm自己規劃的，所以奇形怪狀也沒關係。就是說，之後等kernel種類多了，看能不能提取出一些通用的東西，我記得今天還是昨天有討論過的，反正就是這樣。不過llm kernel這塊挺重要的，之後找時間我來審審看。不過其實也還好，現在這樣也夠用了」

### 決定

- `kernel.json` 的格式是 kernel_llm 自己規劃的，長什麼樣都沒關係；現在這樣夠用，不改。
- 等 kernel 種類多了，再看能不能提取通用的東西（不現在規劃）。
- llm kernel 重要，他之後找時間審；沒排時間。

### 註（記錄者加，不是使用者的話）

- 他說「今天還是昨天有討論過的」，對得上的是 11-20 的 [aos-kres-1120](aos-kres-1120/README.md)（kernel 的資源基底與排程介面）與 [aos-kllm-round-1120](aos-kllm-round-1120.md)（llm kernel 的排序搬上共用骨架）、11-19 的 [aos-htop-1119](../19/aos-htop-1119/README.md)（自訂 kernel「先不定，讓它自然長」）。頂層列出這三份問他，他答：「對的，就是這些。」

## 第 6 則：`~/aos-home/perm` 怎麼這麼空

### 原話

「然後我在看aos-home/perm，他怎麽這麼空？」

### 現況（頂層當場查的）

- `perm/` 只有三個檔：`_entry`（`["aos-loop", "loop.json"]`）、`loop.json`（每 300 毫秒跑一次 `$AOS_HOME/lib/tools/aos/kernel`、把 `kernel.json` 交給它）、`kernel.json`（`{}`）。
- 空的原因有兩個：程式不在夾裡（借 `AOS_HOME` 的 `lib/tools/aos/kernel`，即掛 proc 的 kernel 的共用骨架）；設定是 `{}`（什麼都不管、全部原樣轉給根）。
- 出廠沒掛、沒人用（使用者 11-20「加一份選裝、預設不開」）；開法與可加的鍵（`allowed`、`max_running`、`queue`、`hooks`…）在 [start-api README「選裝：權限件」](../../../templates/start-api/README.md)。
- 對照第 1、2 則：這一夾已經是他要的「沒要覆蓋就從 AOS_HOME 取」的樣子，`llm/` 也是；`agents/ann/` 才是整份帶著程式。

## 第 7 則：perm 沒事了；回來看 root，問 `daemon.json#/procs` 底下那些的特性

### 原話

「那沒事了。然後回來看root，之前磨過一遍，所以還算熟，只是我忘記了，被寫在daemon.json#/procs底下的這些，他們的特性是？」

### 現況（頂層照 `cpp/aos-daemon/docs` 01～05、10 答的）

- `root/daemon.json` 的 `procs` 現在兩列：`_clock`（每 1000 ms 跑一次 `aos-clock`）、`_sweeper`（每 600000 ms 跑一次 `aos-sweeper --retention-days 7`），都帶 `auto_restart: true` 與 `stuck_after_ms`。
- 寫在這裡的是名單的「底」：daemon 一起來就自己起它們，不用 `add`；每次 daemon 起來都照 daemon.json 再讀一次（自己結束過的也再起）。
- 對照 `ctl add` 加的（`llm`、`ann`）：那是信改出來的，daemon 重起時靠 stack 接回，「只留名、設定記 null」，再起時照 proc 自己 stack 裡的 `loop.json`。
- 寫法決定怎麼跑：物件裡有 `interval_ms` 這類 loop 的 key＝一直跑的 loop；只有 `exec`＝跑一次。

## 第 8 則：叫頂層把兩件沒把握的查清楚

### 原話

「去查一下。」（指第 7 則回答裡頂層說沒把握的兩點：對寫在 `daemon.json#/procs` 的列下 `rm` 會怎樣、`_` 開頭的名字有沒有特別意義。）

### 結論（頂層查的）

- **`rm` 寫在 daemon.json 的列：當下拿掉，daemon 重起又回來。** 家機暫存樹 `~/.aos/scratch/root-rm-1120/` 實跑（`templates/daemon-root` 的抄本、清掉 `AOS_*`、裝的是 HEAD `6d37ccdc8` 那版）：起根，表上 `_clock`、`_sweeper`；`aos-daemon-ctl rm _sweeper` 退 0、表上只剩 `_clock`；`shutdown` 說「1 procs asleep」；再起，`_clock`、`_sweeper` 都在跑（新 pid）。收尾 `shutdown`，沒有留下行程；暫存樹沒刪。
- **`_` 開頭的名字程式不另眼相看。** `cpp/` 與 `py/aos`、`py/tools`（不含測試）裡找不到對 proc 名字第一個字是 `_` 的判斷，也沒有寫死 `_clock`、`_sweeper` 這兩個名字的地方；唯一的 `startswith("_")` 在 `py/aos/agent_spec_agent.py`，管的是 `defs.Agent` 的欄位名，跟 proc 名無關。所以只是命名慣例。

## 第 9 則：看 `.stack/procs_state.json`，問 `launch` 為什麼不直接用 aos inst 格式

### 原話

「def, launch這塊當初是爲何設計的？stuck_after_ms的意義？」

「launch當初爲何不設計成直接套用aos inst格式？」

### 現況（頂層當場查的）

- `def`：使用者 11-04 選的（「那就b。」，[aos-agent 05/03 第 2 條](../../2026-11/04/aos-agent/05-實作步驟/03-實作時改的設計.md)）——表上直接記定義夾，aos-agent 讀它找定義，不從 `exec` 推。
- `launch`：**不是使用者裁的，是 11-07 施工線代定的**（[arknights-kb 07](../07/arknights-kb/07-停不下與消失.md)「代定：…表上多 `launch`（可重放的入口與參數，好讓 adopt 不必猜型別）」、[08](../07/arknights-kb/08-daemon不分類實作結果.md)）。紀錄裡沒有「考慮過 inst 格式、為什麼不用」的字。
- `launch` 現在存的是 daemon 自己的「proc 寫法」（跟 `daemon.json#/procs` 一列、`procs_added` 一項同一種）：已起過的是 `{"exec": [入口, 參數…]}`，沒起過的存原設定（可帶 `ws`、`limits` 等 daemon 的鍵）。不是 inst（`{"argv": […], "cwd", …}`）。
- `stuck_after_ms`：照 [aos-daemon docs/04「判卡住」](../../../cpp/aos-daemon/docs/04-兩個手把-兩扇狀態窗.md) 答的，以前磨過，不另記。

### 決定

- 頂層問他是想知道原因還是要改成 inst 格式，他答：「這個先擱置，等以後遇到問題再說。」`launch` 的格式不動、不列待辦。

## 第 10 則：看 `.stack/procs`——stop_cause.json、aos-observed、letters.json、observed.jsonl、think/request.json

### 原話

「然後我開始來看.stack/procs，_clock/stop_cause.json來由是？ann/interfaces.json中宣告了aos-observed，這是啥？letters.json，這是agent的信箱對嗎？observed.jsonl又是啥？think中的request.json會被定期清理掉吧，一些重複的東西是否會用$override或$ref？」

### 現況（頂層當場查的，家機 `~/aos-home/.stack/procs/ann`，樹關著時讀檔）

- `think/request.json` 只有一份，每次問模型前整份覆寫（先寫暫存再改名），不是累積的，所以沒有「定期清理」這件事；答完那份留著，下一輪被蓋掉。
- 它是送給模型的請求原樣，**完全展開、沒有 `$ref`／`$override`**。這次那份 53 KB：`tools` 50.8 KB、`messages` 1.8 KB——九成六是工具說明，每一輪都整份重寫、整份送出去。
- `observed.jsonl` 最後兩筆：`prompt_tokens` 12626、12646（只問了幾句話），`cached_tokens` 都是 0。起手範本 `llm/kernel.json` 的 `sol` 那包沒寫 `session_key`；[kernel_llm docs/01](../../../py/tools/aos/kernel_llm/docs/01-用法.md) 記著 11-14 實測寫了 `"session_key": "litellm_session_id"` 快取命中 88%／82%、沒寫 18%／31%。這次家機沒有另外實測。
- `letters.json` 不是信箱：是「回答配對」的帳（`pending`＝收進對話、還沒答的信；`dropped`＝被丟的），信箱是同一夾的 `queue/`（`new/`、`cur/`、`tmp/`）。
- `observed.jsonl`＝每問一次模型記一行（哪封信、哪個端點與模型、token 用量、花幾毫秒）；自動 compact 的 35% 就是讀它。stack 的 `interfaces.json` 寫 `{"aos-observed": {"file": "observed.jsonl"}}` 是在宣告「我有這份觀測檔、檔名是這個」，由 `py/aos/observed.py` 寫。
- `stop_cause.json`：daemon 送 SIGTERM 之前先寫在那隻的 stack，內容是為什麼要它停（這次是 `shutdown`）；子 loop 收工時讀它，交給 `on_stop`（agent 的 `after_stop` 事件的 `cause`）。出處 [aos-daemon docs/03](../../../cpp/aos-daemon/docs/03-起-停-暫停.md)。

### 決定

- 頂層問要不要在暫存樹實測加 `session_key` 的差別，他答：「明天吧，這塊確實值得來處理。」（指每輪 1.2 萬 token、快取沒命中這一塊）
