# 反向傳播式自我改進的頂層設計：每個函數留帳、帳隨呼叫樹往上走、一隻審視者照帳一次改一個函數
← [2026-11-07](../README.md)

以 fable 的 02 為底稿、opus 隊長補全。題目：arknights 知識庫那條線「聰明模型先摸索 → 固定成步驟工具 → 降級看哪裡錯 → 錯的再工具化、連帶優化被影響的子函數」（使用者稱「反向傳播」，「這種改進行爲我會特別關注」），aos 本體要怎麼支援，讓它變成系統的一部分而不是靠人。條文落點見 CONCEPTS C-84、NORMS N-68。

## 使用者裁定（11-07）

選項框裁定，原話逐字：

- 公式語言：「直接寫"lua":"...."或"py":"..."，然後呼叫相應lua.exe/python.exe(這臺是linux，沒有)。或是直接跑aos函數。初期可以用簡單的四則+min/max。其實沒啥規定，就是隨着複雜度增加，可以替換到所需技術棧。搞不好到後面，就是呼叫aos　agent」
- 審視者能不能自己寫程式：「按照推薦。但這就隨意。甚至這個過程本身也可以記錄下來，讓另一個agent進行改進流程。」
- 改好的版本誰換上：「自動換，退步自動退回。不過可以想想看神經網路這塊，有時候他的epoch會稍微退步，但下次又會進步補回來。」
- daemon 有信就醒：選推薦（不加）。
- 語意錯怎麼擋：「一開始先用人去看，但最近我比較忙，可以先用高階模型。這個也很自由，也可以先設計一套模式，後續慢慢優化。」
- `_metainfo` 的估時與逾時：選推薦（拆成 `cost.time_ms` 與 `timeout_ms`，工具檔用腳本一次改、不做相容）。

落成結論：公式以語言名當 key（`cal`／`lua`／`py`／`aos`），起步只做 `cal` 的四則＋`min`／`max`；審視者先開處方跑三個地點、之後放手，改進過程本身留帳、可被另一隻 agent 改進；自動換上、退步自動退回、容忍短暫退步；daemon 不加「有信就醒」（專精 agent 是定義，叫到才起，stack 留在磁碟就是 sleep）；語意錯先用高階模型當裁判（裁判是一支可替換的比對器），人抽查為輔、抽到的錯補進 `expect/`。

## 使用者裁定（11-07 傍晚，40 題選項框）

回覆原文全文在 [kb-ideas](../kb-ideas/README.md#11-07-傍晚-40-題裁定原文)；回覆後補一句「很多東西都可以靈活改進，所以後面我就不寫了」（[想法 15](../kb-ideas/README.md)）：各題的判準、標準、階段、門檻本身都可以再被改進。

- **evo-A**（函數自報的成本不準，要怎麼處理？）：選 C「平常只報告；但 kernel 或審視者要拿估值來排程、挑目標時，off 的定義改用他見的中位數」。備註原話：「hmmm，函數自報估值，老實說，應該是函數的設計者當初給函數寫下的估值，而agent作爲函數他確實會自報估值。兩者要分清。函數設計者給函數寫下的估值，這件事，hmmm，首先我要說，不是所有函數設計者都會寫這種估值，所以不能假定永遠都有metainfo，而且我們也不該強迫。一些比較笨的agent，你讓他報估值他也會報錯，那不如就只看他的說明就好。函數九軸是基礎特性，我們是建議不管多簡單或多笨的函數或agent都準備一份描述這個的metainfo啦，但不強迫。產出metainfo這件事，也是可以優化的一環，但我覺得除非是改進者之流，不然這屬於比較次要的要優化的東西。」
- **evo-B**（改進別人的審視者，什麼時候也要被改進？）：選 B「審視者自己的單位成本連續幾輪沒降、或 spent 比它省下來的還多時才跑」。備註原話：「如果審視者一直都做的不錯，那就沒必要改進他。這套判斷標準本身也是靈活的，可以被改進的。想想看，審視者，審視"審視者"的審視者，這樣一層層堆疊，每層之間的標準都可以靈活變換。」
- **evo-C**（拿來考審視者的好答案，要從哪裡找？）：選 A「從過去真實的 review.json 裡挑，被 watch 轉正（kept）的那幾輪當好答案」。備註原話：「兩者都可以。這套標準本身也可以靈活變換與改進。」

使用者 11-07 傍晚的兩條新想法（原話在 [kb-ideas](../kb-ideas/README.md) 第 11、12 條）：「下一輪規劃前，我這裏有些想法：弄了這麼多metainfo格式，那我們也要有一套相應的評估機制。」「還有，改進，我們現在是讓高智能agent去做，而這件事本身也可以記錄其過程，作爲一個函數進行成長。」緊接著補：「以及優化」。

## 設計（結論）

### 概念（五條）

1. **函數有兩本帳：自稱與他見。**自稱寫在定義裡的 `_metainfo.json`（估的、宣告，可寫公式）；他見是叫它的那層在自己 stack 記的實測（只記自己看得到的：秒、位元組、結束碼、自己這層的 token）。兩本不互寫，跑的時候誰都不改 `_metainfo.json`（守「實測不回寫」、C-46）；`deterministic` 是作者宣稱。
2. **成本是任意 JSON 值；aos 只定三個通用 key**：`token`（`in`／`out`／`cached`）、`counter_calls`、`time_ms`，其他 key 自由。每格純數或 `{"val", "unit"?, "max"?}`；依輸入變就寫公式 key：`{"cal": "4000 + in_bytes * 1.2"}`、`{"lua": ...}`、`{"py": ...}`、`{"aos": "<函數路徑>"}`，可帶 `vars`。這些是 metainfo 格式族的普通 key、不是指示詞，只有讀 metainfo 的人算；讀者沒有那種求值器＝這格沒有估值，不報錯。
3. **帳沿呼叫樹走，靠「帳裡寫明下一本在哪」連起來**：每行「我叫了誰」寫明對方的帳現在在哪（相對本 stack）；會生子 agent 的工具收掉子之前把子的帳抄進自己小格。從根往下翻，沒有帳的就是葉。觀測者只認公開介面 `aos-observed`。
4. **審視者是 agent，不是機制；它自己也是可被審視的函數。**aos 本體只保證：每層留帳、帳翻得到、定義寫得出來、改了之後量得到。審視者改整棵定義的副本，過門又變便宜就 `promote` 換上，之後盯著；`promote` 不准換掉正在跑的定義（含審視者自己）。正在跑的 agent 改自己仍只走 `self_tools`。
5. **門與目標分開**：門＝比對器說過（預設逐 byte，可換）；目標＝門內的成本；門沒過的不比。目標寫成 JSON 指標（例 `/token/in`），先留位置。

### 格式要點

- 命名：時間點 `*_at` 用 ISO 8601 UTC 到毫秒；計數 `counter_*`；時長 `*_ms`。
- `_metainfo.json`：`timeout_ms` 是行為（逾時就殺），`cost.time_ms` 是估時，頂層 `time_ms` 拿掉；`cal` 的變數只能是 `_tooldef.json` 的 `parameters` 名加 `in_bytes`；`cost_basis` 選填，由審視者發新版時填；不認得的 key 忽略（C-48）。
- `observed.jsonl`（每個 stack 一份、只追加；`interfaces.json` 宣告 `"aos-observed": {"file": "observed.jsonl"}`）：`self` 行（`def`、`ws`、`started_at`）、`think` 行（`endpoint`、`model`、`usage`、`elapsed_ms`）、`tool` 行（`name`、`def`、`stack`、`child`?、`code`、`elapsed_ms`、`in_bytes`、`out_bytes`）。時間是叫的那層量的牆鐘；`bash` 只記到 bash 那層。腳本用 `lib/observed.py` 的 `call(name, target, stdin)` 叫下游並記帳，不記就是葉。
- thought／agents 收子前把子 stack 底下所有 `observed.jsonl` 照相對路徑抄到 `observed/<子名>/`（跟 `children/<子名>/` 分開）；`agents` 在 `ask` 回來與 `rm` 前同步；同步不到就少算，不偷看。
- case 夾：`run.json`（`{"exec", "stdin"}` 或 `{"agent", "say"}`，路徑相對定義根）、`stdin.json`／`say.txt`、`ws/`、`expect/`、`check.json`（`compare`?、`min_score`）。比對器是普通 aos 函數：stdin `{"expect", "got", "input"}`，stdout `{"score", "diff", "why"?}`；沒寫 `compare`＝內建逐 byte。裁判是 agent 型比對器，帳記在 `check.cost`、進審視者 `spent`，不算產出成本。
- `measure`：stdin `{"case", "defs", "repeat"}`；產 `measure.json`（`check`、`size_bytes`、根 `cost` 取中位數、`tree`、`samples`、`measured_at`）。節點 `cost.token` 只算自己那本帳的 `think` 行；`kind` 看帳裡有沒有 `think` 行；同父同工具多次呼叫合成一個節點。
- `review.json`（`$AOS_WS/reviews/<輪>/`）：`round`、`case`、`before`、`target`、`tried`、`adopted`、`dirty`、`after`、`proposed`（整棵副本）、`spent`、`suggest`（`retire`／`specialize`，只建議）、`why`、`reviewed_at`。
- `ladder.json`：`{"ladder": ["sol","terra","luna","local"], "repeat": 3, "min_score": 0.9, "watch": {"window": 3, "tolerance": 0.10, "metric": "/token/in"}}`；每級三次都 ≥ `min_score` 才算過，取合格中最低級。
- `promote`：舊版搬到定義根的 `.prev/<目標>/<promoted_at>/`、副本複製上；`rollback` 換回最新一份；有 proc 正在用目標＝`DefBusy`。登記在誰的工具箱誰能按：審視者預設有（自動換上），隊長手上也有一份。
- watch（容忍短暫退步）：品質不容忍——換上後任一 case 門沒過立刻退回；成本容忍一段——拿單位成本（目標指標÷case 大小），換上前最近 3 個 case 平均當基準，換上後窗滿 3 個時平均貴超過 10% 才退，否則轉正；窗內不退。疊著換各算各的窗。紀錄在 `reviews/watch.json`，`state` 只有 `watching`／`kept`／`rolled_back`；3 與 10% 是代定、可改。
- 知識庫連結值＝`節點路徑#/JSON指標`（相對知識庫根），追連結＝`memory read`；tag 放節點 JSON 的 `tags` 或資料夾節點的 `_tags.json`，`memory find` 加選填 `tag` 逐字比對。要讓工具沿著走的才做連結；只是提到，寫名字就好。全庫規模交 [kb-scale](../kb-scale/)。
- 嵌套 kernel 只用一層轉交：`lib/aos/llm_forward/`＋範本 `kernel/llm-team/`；兩層各記各的帳，用量靠回信 `usage` 帶上來；本機模型一台 kernel 只放一包、`slots: 1`。更深的嵌套交 [kernel-nest](../kernel-nest/)。

### 審視者的一輪

1. **量**：`measure` 跑 case（之後順手叫 `metainfo_check`）。
2. **挑**：`kind: agent` 的節點按 `token.in` 占比取最大；沒有 agent 節點按 `time_ms`。
3. **試**：複製整棵定義根到 `reviews/<輪>/defs/`，依序試 `downgrade`（階梯下一級）→ `fix`（三份樣本逐 byte 一樣＝輸出由輸入決定，寫成腳本）→ `split`（腳本前處理＋更小的 LLM 步），一個成功就停，一輪只動一個目標。
4. **傳**：整個 case 用副本重量，門要全過，不過就退回、記進 `tried`。
5. **記**：寫 `review.json`；過門且單位成本更低就 `promote`，在 `watch.json` 開窗。
6. **盯**：每量一個新 case 先填進所有 `watching` 的窗。
7. **長**：填 `suggest`。

起步三個地點 `fix`／`split` 只開處方（施工交 gpt），第四個地點起放手；換模型從第一天全自動。

### metainfo 的評估

- 本節評的是**函數設計者**寫在 `_metainfo.json` 的估值；agent 跑的時候自報的估值是另一樣，分開記（代定：先不做）。`_metainfo.json` 不強迫、沒寫＝`unclaimed`、不算錯；笨 agent 不要它報估值。
- 工具 `lib/agent/metainfo_check`：每個成本 key 算落差比＝實測／估值，最近幾個 case 的中位數落在 0.8～1.25 算準（代定）；`verdict` 只有 `close`／`off`／`unclaimed`。只報公式係數偏或形狀錯，不自己改公式；連三個 case 都 `off` 的，審視者發下一版時改準。同職責多個定義：同 case、同門、都過門的照單位成本排。
- evo-A 已裁 (c)：平常只報告；kernel 或審視者拿估值排程、挑目標時，`off` 的改用他見中位數。

### 改進過程本身也是會成長的函數

- 審視者的自稱在 `templates/reviewer/_metainfo.json`，他見是它的 `observed.jsonl` 加 `review.json` 的 `spent`；考題是審視 case（`expect/` 放好答案，比對器看挑的目標與招式對不對）；成本是「改進一次要多少錢」。
- 第二隻審視者照同一套一輪七步，目標是 reviewer 這份定義；可以一層層往上疊，每層判準可不同、也能被改；某層一直做得不錯就不改它；換審視者的定義只能由上一層在它沒在跑時做。
- evo-B 已裁 (b)：判準起步寫死成「最近 3 輪的 `spent` 總和大於這 3 輪省下的成本總和」才審視審視者；判準本身也能改。
- evo-C 已裁 (a)、備註「兩者都可以」：起步從被 watch 轉正（`kept`）的真實 `review.json` 挑好答案，隊長或高階模型手寫的也可以用。

### 與既有條文的讀法（推薦讀法；條文落點見 C-84、N-68 與 [lift-to-norms](../lift-to-norms/README.md)）

1. N-62 鬆綁一句：`a/b#/c/1` 是全系統唯一的「指」法（RFC 6901、第一個 `#` 就切、`#` 後必 `/`），誰認由各讀者自己宣告；`$env` 仍不認 `#`。
2. 他見住在觀測者自己的 stack，定義資料夾只放自稱；試驗場的 `_observed.json` 不進 aos。
3. `cost.time_ms`＝估時、`timeout_ms`＝逾時、頂層 `time_ms` 拿掉，不寫相容。
4. 公式 key 不是指示詞；`py`／`lua` 由讀者自己決定在不在沙箱裡跑（交 tool-evolve）。
5. 帳（花了多少）跟拿掉的 trace（跑到哪格）不同；只准這一種帳，且要宣告成公開輸出 `aos-observed`。
6. 「self-improve 預設就關」管沙箱裡跑的函數改自己；審視者經 `promote` 換別人的定義不算 self-improve。
7. 成千上萬個 agent＝成千上萬個定義，叫到才起、用完即收。
8. 嵌套就是轉交，只用一層；兩種 kernel 照舊不併。
9. thought 的子 stack 照刪，刪前只抄帳。
10. 新格式照命名規則（`*_at` 日期字串、`counter_calls`）。
11. `promote` 先查 daemon 表，有 proc 在用就 `DefBusy`。

## 落地狀況

- aos 本體已做（impl-plan 批 1～6、8，見 [impl-plan 完成總結](../impl-plan/14-完成總結.md)）：`lib/metainfo.py`、`_metainfo` 改格式、`lib/observed.py`、收子前抄帳、`llm_forward` 與 `kernel/llm-team`、`measure` 與門、裁判比對器（叫 `judge-llm`）、`memory find` 認 tag、`promote`／`rollback`、審視者範本與 `review_round`、`watch`、`metainfo_check`。
- 未做：審視者自己寫 `fix`／`split` 副本（第四個地點起）、審視 case 與第二層審視（要先補「量審視者」的量測介面）；試驗場改接（`place_run` 改用 `lib/observed.py`、`meta_observe` 與 `_observed.json` 退役）交 arknights 線。
