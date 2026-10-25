# galtxt-b 第 2 輪：往下拆一層（只規劃、不實作；乙隊規劃者 fable，2026-10-25）

← [galtxt-b](../README.md)｜上一輪：[round1.md](round1.md)｜範圍不變：一地（河鹿堂）、兩人（主角、森下晴子）、一事、Q01＋Q08；假腦要能跑過，真腦 LiteLLM gpt。實作者照本檔建檔，有疑問回頭看 round1 的理由。

這輪的題目是：看第 1 輪跑出來的樣子，**在同一個範圍裡**讓樹長到合理深度。不是把範圍擴大。判準沿用 [函數成長六級](../../../thinking/2026-10-24-fn-grow.md) 的觸發點（被 ≥2 處叫、有伴隨檔、要自己保管東西、≥2 個步驟）與 C-22（能寫死的節點換成程式；把不可預測的大節點拆小，中間插可驗的程式節點）。

## 0. 第 1 輪 §6 四個方向的結論（一句話版，理由在 §1）

| 方向 | 結論 | 一句理由 |
|---|---|---|
| writer 長 `tools/lint`（自檢） | **做** | check 的檢核函數會被兩處叫（頂層 check 格、writer 的腦）→ 抽成 `lib/lint` 純函數，兩邊掛捷徑；writer 自檢少一圈打回 |
| writer 長 `tools/corpus_peek`（翻語料） | **不做** | 工具得讀 repo 外的路徑，撞 lib 契約「沙盒＝`$AOS_WS`」；極小版的語料錨改用 `brief/tables/samples.json`（Q01、Q08 的對白互為 few-shot、各自避開自己的正解） |
| brief 的 `distill/`（蒸餾表） | **不做** | 工廠期、要人審、沒有自動驗收；表只有兩人一地，手抄比蒸餾便宜；等 check 的礦（✗ 的理由）累積到有東西可回寫規則時再開 |
| brief 的 `opener/`（開場收尾升成搜尋） | **不做** | 一地兩題，查表夠；搜尋要成本函數，沒校準資料 |
| check 拆 `rules/` 子資料夾 | **不拆成資料夾，拆成函式庫** | 規則不到十條、共用同一個解析；拆成 `lib/lint` 一支純函數（規則表在程式裡），不開十個資料夾 |
| overgenerate-and-rank | **不做** | 排序要成本函數，沒有 Tier 3 的礦可校準；打回重寫＋自檢已經給了多次嘗試 |
| **新增：draft 長 `tools/director`（先出 beat 表再寫稿）** | **做** | 這是這輪唯一新增的 LLM 節點：把「寫稿」拆成「規劃節拍（LLM）→ 校驗節拍（純程式）→ 照節拍寫（LLM）」，中間插一個可驗的程式節點（C-22），而且 galtxt 自己的終點形態就是五層（L1 場景規劃→L2 beat 展開→…）；beat 文法在定點 01 已固化成可校驗的產生式 |

## 1. 往下拆哪幾塊、拆成什麼、為什麼

### 新樹（★＝這輪新增；→＝相對捷徑）

```
galtxt-b/                      頂層 fsm 不變：idle→brief→draft→check→judge→deliver→idle（六格）
  lib/                       ★ 這支程式自己的函式庫（純函數、stdin→stdout、照 proto8/lib 契約）：被 ≥2 處叫的才進來
    lint/                    ★ 純程式：稿子的確定性檢核（第 1 輪 check/_entry 的規則搬進來）{"text", "brief"|"brief_path"} → {"violations"}
    plan_lint/               ★ 純程式：beat 表的文法校驗 {"plan", "brief"|"brief_path"} → {"violations"}
  idle/                        不變
  brief/                       不變；tables/ 多兩份表（samples.json 語料錨、beats.json beat 文法），brief.json 多 samples、beats 兩格
  draft/                       黏合格改成兩步：沒 plan.json 先叫 director 出 beat 表、校驗；再叫 writer 照表寫稿
    tools/
      director/              ★ agent（agent-dan 形，無工具）：稿紙 → beat 表 JSON（B0…B7 每拍誰、做什麼、帶哪個關鍵詞）
      writer/                  agent（既有）；tools/lint → ../../../../lib/lint ★ 腦可自檢：交稿前先跑一次 lint、照違規改
  check/                       黏合格變薄：讀 stack、叫 tools/lint、算 pass／final、寫 check.json
    tools/lint → ../../lib/lint ★
  judge/ + tools/critic/       不變（critic 仍是 agent；收攏留第 3 輪，見 §5）
  deliver/                     多寫一份 out/<題名>/measure.json（實跑數字，§4）
```

深度：最深的路徑 `draft/tools/writer/tools/lint`（捷徑）→ 實體在 `lib/lint/`；資料夾實體最深是 `draft/tools/director/idle/`（4 層），跟第 1 輪一樣。agent 資料夾三隻（director、writer、critic），純函數兩個（lint、plan_lint），黏合格三個（draft、check、judge），純程式格三個（idle、brief、deliver）。

### 1a. `lib/lint/`（純程式；從 check 格抽出來）

- **為什麼**：第 1 輪 check 的規則寫在 `check/_entry` 裡，只有頂層一處用。這輪 writer 的腦要能「交稿前自己檢一次」——同一套規則被第二處叫，就是函數成長「被 ≥2 處叫」的觸發點；而且腦叫的工具要有 `tool.json`、stdin 收 arguments，跟格讀 stack 檔的介面不同，所以把規則抽成一支**只認 stdin→stdout 的純函數**，格與腦各自包一層。放 `galtxt-b/lib/`（不放 proto8/lib：規則是 galtxt 專用的；lib 的層名不建——只有兩個工具，「只建有東西的層」）。
- **入口**：`lib/lint/_entry`（python3，`+x`，第二行 `# lint - 稿子的確定性檢核：格式、護欄關鍵詞、禁語、地點穿幫、稱謂階、感嘆號、口頭禪、句長、旁白預算`）、`tool.json`、`_metainfo`——lib 契約的三個檔。
- **輸入**（stdin 一份 JSON）：`{"text": 稿子, "brief": 稿紙物件}` 或 `{"text": 稿子, "brief_path": "cur/1.json#/brief"}`（相對 `$AOS_WS`、`檔#/指標` 寫法——腦自檢時用這個，不用把整份稿紙再送一遍）。兩個都沒給＝`ArgumentsBad`；`brief_path` 指到的檔不在／指標指不到＝`BriefMissing`／`PointerMissing`，路徑跑出 `$AOS_WS`＝`PathBad`。
- **輸出**（stdout 一行 JSON）：`{"violations": [{"tier": 0|1, "rule", "line", "text", "reason"}], "counter_dialogue_lines": n, "counter_narration_lines": n}`。只報事實、不判 pass（pass／final 是 check 格的事：它知道 attempt 與 max_redrafts，lint 不知道）。
- **規則**（第 1 輪的九條照搬＋一條新的）：Tier 0 `format`、`speaker`、`line_count`、`must_mention`、`banned_A/B/C`、`place_canon`；Tier 1 `address`、`line_length`、`exclaim`、`catchphrase`、★`narration_max`（旁白行數 > `brief.lines.narration_max`（預設 4）＝太多旁白，定點 05 的旁白預算）。規則留在程式裡一張表（`RULES = [(名, tier, 函數)]`），不拆資料夾。
- **錯**：照 lib 契約，stderr 一行 `lint: 代號 原因`＋stdout 同一行、退 1。檢出違規**不是錯**（退 0）。

### 1b. `lib/plan_lint/`（純程式）

- **為什麼**：director 出的 beat 表要有人校驗，不然多一個 LLM 節點只是多一份不確定；定點 01 已把 beat 文法寫成產生式＋約束，正好是純程式能驗的東西（`B0 B1 B2 B3+ (B4) B5 (B6) B7`、c1 B5 在 B3 後、c2 B6 前要有買書／拿書事件、c4 B4 與 B5 可融合）。director 自己也能叫它自檢（同 lint 的理由：被兩處叫）。
- **輸入**：`{"plan": beat 表, "brief": …|"brief_path": …}`；**輸出**：`{"violations": [...], "counter_beats": n}`。
- **規則**：`grammar`（序列合產生式；用一個小狀態機，不用正則）、`beat_unknown`（名字不在 brief.beats 表）、`who_unknown`（`who` 不在 cast 或「旁白」）、`must_assigned`（brief.must_mention 每組至少被一拍的 `must` 認領）、`b5_after_b3`（c1）、`b6_needs_pickup`（c2：B6 之前有一拍 `event` 含「書」）、`beats_count`（拍數 5～10，跟台詞句數同量級）。
- **beat 表的形狀**（director 的答案、writer 的輸入，`$AOS_STACK/plan.json`）：

```json
{"beats": [
  {"beat": "B0", "who": "旁白", "do": "門鈴＋百葉窗的光，建立涼、靜、舊", "must": []},
  {"beat": "B1", "who": "旁白", "do": "兩人的手同時搭上同一本《銀河鐵道之夜》", "must": ["銀河鐵道之夜"]},
  {"beat": "B2", "who": "主角", "do": "先讓：妳先請", "must": []},
  {"beat": "B3", "who": "森下晴子", "do": "為什麼來這裡：安靜；你也喜歡宮澤賢治嗎", "must": []},
  {"beat": "B3", "who": "主角", "do": "只是想重溫、剛好是春天", "must": []},
  {"beat": "B4", "who": "森下晴子", "do": "讓書：這本讓給主角同學，下次再來", "must": ["讓給"]},
  {"beat": "B5", "who": "森下晴子", "do": "表面：沒關係的；洩底：想知道你讀完的想法", "must": []},
  {"beat": "B6", "who": "旁白", "do": "爺爺蓋梅花章", "must": []},
  {"beat": "B7", "who": "旁白", "do": "T9 定格：百葉窗的光退回去", "must": []}]}
```

### 1c. `draft/tools/director/`（agent，agent-dan 形）

- **為什麼**：第 1 輪 writer 一次問腦同時做兩件事——決定戲怎麼走、把每句寫出來。拆開後：director 只出「哪一拍誰做什麼、關鍵詞落在哪一拍」（短、結構化、**可用程式驗**），writer 照表填句（洞變小＝固化階梯往下一級）；打回重寫時只重寫句子、不重規劃（plan.json 留著），省 token 也更穩。這對應 galtxt 五層的 L1／L2（場景規劃、beat 展開）落成一個節點，realizer（L4）是 writer。代價：每題多一次問腦（典型 3 次），`_metainfo` 要反映。
- **檔**：照 agent-dan（`_entry`、`loop.json {"exec":"fsm.json","max":6}`、`fsm.json` 三態、`idle/`、`brain.py`、`act.py`、`system.txt`、`.env`、`_metainfo`）。`brain.py` 從 writer 的複製，只改 `render`（送稿紙的場景、事件、人物一句、beat 文法表 `brief.beats`、`must_mention`，要求只輸出 beat 表 JSON）與 `fake`（假腦：照 brief 拼一份合文法的表——B0、B1、B2、B3×2、B4、B5、B6、B7，`must_mention` 各組第一個詞分配到 B1／B4）。`act.py` 用 critic 的那份（無工具、`tool_calls`＝`ReplyBad`）。第 1 輪沒給 director 工具；要讓它自檢就掛 `tools/plan_lint`，這輪**先不掛**（它的輸出由 draft 黏合格驗，見 1e；避免一輪多兩個自檢迴圈，難看清楚效果）。
- **題目／答案**：`$AOS_STACK/director/ws/new/<n>.json`＝`{"attempt": n, "brief": …, "feedback": [plan_lint 的 violations]}`；答案 `out/<n>.txt`＝beat 表 JSON（可能包 ``` 圍欄，黏合格剝）。

### 1d. `draft/tools/writer/` 的變化

- 掛 `tools/lint → ../../../../lib/lint`（相對捷徑；aos-exec 走進實體，`AOS_CD` 是 lib 的位置，C-61「兩份一起搬也不斷」）。`brain.py`、`act.py` 一個字不改就能用工具（第 1 輪留著的 tool_calls 那段）；`system.txt` 加一段：「寫完先叫 `lint`（`text`＝整段稿子、`brief_path`＝`cur/<n>.json#/brief`）；有 Tier 0 違規一定改、Tier 1 盡量改；最多自檢兩次，然後交稿」；`render` 在稿紙尾巴補一行「你的題目檔是 `cur/<n>.json`」讓腦填得出 `brief_path`。
- `render` 多送 `plan`（beat 表）：「照這張表寫，每拍一到兩句，旁白拍寫（）」。
- `loop.json` 的 `max` 6 → **10**：一次自檢＝多一圈 idle→think→act（act 跑工具、退 0 回 idle、think 帶 tool 結果再問），兩次自檢＋交稿＝3 圈 think、最多 10 格含 idle。腦問幾次由這個 `max` 兜底，agent 自己不數（N-53）。
- 假腦：`GALTXT_FAKE_LINT=1` 時第 1 次回 `tool_calls` 叫 `lint`、第 2 次（最後一則是 tool）照 tool 結果交稿——把自檢那條路也跑一遍；預設假腦照第 1 輪直接交稿。

### 1e. `draft/_entry` 黏合格改成兩步

```
no-op 判準不變（check pass 或 final 就什麼都不做）
1. 沒有 $AOS_STACK/plan.json：
   小格 $AOS_STACK/director/（第 1 次清掉）、ws new/<k>.json={brief, feedback}
   aos-exec --ws … tools/director → 讀 out/<k>.txt、剝圍欄、json.loads（壞＝ReplyBad 退 1）
   aos-exec tools/plan_lint（stdin {plan, brief}；check 格那條捷徑同一個實體，draft 這裡也掛 tools/plan_lint → ../../lib/plan_lint）
   有違規 → feedback 寫回、再叫 director（最多 2 次；第 2 次仍壞＝PlanBad 退 1、等人，P-20）
   寫 $AOS_STACK/plan.json
2. 照第 1 輪叫 writer，題目多帶 plan；收 draft.json
```

plan 一題只做一次：打回重寫（attempt 2、3）沿用 plan.json；deliver 收尾時一起刪。**不**把「重規劃」做進去（check 的 `must_mention` 違規理論上可能是 plan 沒分配——但 plan_lint 的 `must_assigned` 已經擋了，剩下的是 writer 沒照表寫，重寫就好）。

### 1f. `check/_entry` 變薄

讀 `brief.json`、`draft.json`，`aos-exec tools/lint`（stdin `{"text", "brief"}`，整份 brief 內嵌，不用 `brief_path`），拿 violations 算 `pass`／`final`／`register_score`／`history`，寫 `check.json`——形狀跟第 1 輪一樣，`draft`、`judge`、`deliver`、測試都不用動。多記 `counter_violations_tier0`、`counter_violations_tier1`。lint 退非 0＝`LintFailed` 退 1（自己的錯）。

### 1g. `brief/` 的小改

- `tables/samples.json` ★：Q01 與 Q08 的對白各一段（抄自 corpus/評測 的「前後文」、**去掉挖空那句與正解**），形狀 `[{"benchmark": "q01", "text": …}, …]`。brief 挑 `benchmark != scene.benchmark` 的那幾段放進 `brief.samples`（語料錨當 few-shot，而且不漏自己的正解）。沒 benchmark 的場景全給。
- `tables/beats.json` ★：定點 01 的 beat 清單（B0～B7：名稱、內容、必要性）、產生式字串、約束 c1～c6 的白話——brief 原樣放進 `brief.beats`，director 與 plan_lint 都讀同一份。
- `brief.lines` 多 `narration_max`（預設 4）。
- `tables/_metainfo` 的 `summary` 加這兩份表。

### 看過之後決定不拆的（補第 1 輪 §3）

- **critic 不動**：第 1 輪就說它是收攏候選；這輪不往下也不先收（一輪只動一邊，使用者才看得出哪個改動造成哪個差）。
- **brief 不拆子格**：加兩份表、幾行程式，仍是幾十毫秒的純函數。
- **idle、deliver 不拆**：deliver 多寫 measure.json（§4）仍是純搬檔。
- **judge 不加「程式先過濾再問腦」**：定稿一定已過 Tier 0（或到了 max_redrafts），沒有可短路的。
- **lib 不分層**（`base/aos/agent`）：兩個工具，平放。
- **不給 director、writer 共用 brain.py**（三份近乎相同的 brain.py）：10-24 tool-lib 代定 9「第三份一樣的大段再抽」——這輪剛好第三份。但抽共用模組要 `import` 隔壁、撞 lib 契約「自成一格」，而且 aos-ai spawn 的範本複製法就是複製。**這輪照舊複製、把差異鎖在 `render`／`fake` 兩個函數**；要不要把「agent-dan 形的 brain」抽成 proto8 層級的範本（`aos-agent` 範本工具，10-23 使用者提過）是 proto8 的事，寫進 §6 衝突。

## 2. `_metainfo`

### 新資料夾（實作者照抄）

`lib/_metainfo`：

```json
{"summary": "galtxt-b 自己的函式庫：被兩處以上叫的純函數（stdin 一份 JSON → stdout 一行 JSON，照 proto8/lib 的契約）；格與 agent 用相對捷徑掛進自己的 tools/",
 "kind": "dir"}
```

`lib/lint/_metainfo`：

```json
{"summary": "稿子的確定性檢核：格式、護欄關鍵詞、禁語、地點穿幫（Tier 0）；稱謂階、感嘆號、口頭禪、句長、旁白預算（Tier 1）→ violations；只報事實不判 pass",
 "time_ms": {"val": 30, "max": 1000},
 "resource": "cpu",
 "side_effect": false,
 "idempotent": true,
 "deterministic": true,
 "interrupt": "safe",
 "parallel": true,
 "reads": ["stdin", "$AOS_WS/<brief_path>（給了才讀）"],
 "writes": ["stdout"],
 "grow_level": 4,
 "tier": "評分級聯 Tier 0＋Tier 1",
 "callers": ["check/（格，內嵌 brief）", "draft/tools/writer/（腦自檢，brief_path）"]}
```

`lib/lint/tool.json`（給 writer 的腦看，外部 API 欄位名照原名）：

```json
{"description": "檢查一段 galgame 稿子有沒有違反護欄與語域規則（格式、必提關鍵詞、禁語、地點、稱謂階、感嘆號、口頭禪、句長、旁白數）。回 {violations:[{tier,rule,line,text,reason}]}；tier 0 一定要改、tier 1 盡量改。",
 "parameters": {"type": "object",
                "properties": {"text": {"type": "string", "description": "整段稿子原文"},
                               "brief_path": {"type": "string", "description": "你的題目檔裡稿紙的位置，固定寫 cur/<n>.json#/brief（n 是題目檔名）"}},
                "required": ["text", "brief_path"]}}
```

`lib/plan_lint/_metainfo`：

```json
{"summary": "beat 表的文法校驗：序列合 B0 B1 B2 B3+ (B4) B5 (B6) B7、B5 在 B3 後、B6 前要有拿書、每組必提關鍵詞有一拍認領、拍數 5～10 → violations",
 "time_ms": {"val": 20, "max": 1000},
 "resource": "cpu",
 "side_effect": false,
 "idempotent": true,
 "deterministic": true,
 "interrupt": "safe",
 "parallel": true,
 "reads": ["stdin", "$AOS_WS/<brief_path>（給了才讀）"],
 "writes": ["stdout"],
 "grow_level": 4,
 "tier": "固化階梯第 2 級（規則分支）：定點 01 的 beat 文法",
 "callers": ["draft/（黏合格，驗 director 的表）"]}
```

`lib/plan_lint/tool.json`（這輪沒人的腦叫它，但照 lib 契約三個檔都要有；之後 director 自檢就能直接掛）：

```json
{"description": "檢查一張 beat 表合不合文法（B0 B1 B2 B3+ (B4) B5 (B6) B7、反差在話題後、蓋章前要拿書、必提關鍵詞都有拍認領）。回 {violations:[...]}。",
 "parameters": {"type": "object",
                "properties": {"plan": {"type": "object", "description": "{beats:[{beat,who,do,must}]}"},
                               "brief_path": {"type": "string", "description": "固定寫 cur/<n>.json#/brief"}},
                "required": ["plan", "brief_path"]}}
```

`draft/tools/director/_metainfo`：

```json
{"summary": "規劃節拍的 agent：工作區 new/<n>.json 是稿紙（第 2 次附 plan_lint 的理由），問腦一次，答案 out/<n>.txt 是 beat 表 JSON（每拍誰、做什麼、帶哪個關鍵詞）",
 "time_ms": {"val": 6000, "max": 150000},
 "resource": ["llm", "cpu"],
 "llm_calls": {"val": 1, "max": 1},
 "llm_tokens": {"val": 1800, "max": 4000},
 "llm_endpoint": "http://localhost:4000/v1",
 "llm_model": "chatgpt-gpt-6-luna-low",
 "side_effect": true,
 "idempotent": false,
 "deterministic": false,
 "interrupt": "resumable",
 "parallel": true,
 "reads": ["$AOS_WS/new/*.json", "$AOS_WS/cur/*.json", "$AOS_STACK/history.jsonl", "system.txt"],
 "writes": ["$AOS_WS/out/<n>.txt", "$AOS_WS/done/", "$AOS_STACK/{history.jsonl,current.txt,state.txt,trace.jsonl,llm.jsonl}"],
 "grow_level": 5,
 "shape": "demo/agent-dan（idle→think→act），沒有工具",
 "tier": "galtxt 五層的 L1／L2（場景規劃、beat 展開）"}
```

`draft/tools/director/idle/_metainfo`：同 writer 的 idle（照抄 [draft/tools/writer/idle/_metainfo](../draft/tools/writer/idle/_metainfo)）。

`draft/tools/director/fsm.json` 的 think／act 單子裡各帶 `_metainfo`（照 writer 的寫法）：think `{"summary": "問腦一次：稿紙→beat 表", "time_ms": {"val": 5000, "max": 120000}, "resource": "llm", "llm_calls": 1, "llm_tokens": {"val": 1800, "max": 4000}, "side_effect": false, "idempotent": false, "deterministic": false, "interrupt": "safe"}`；act 同 writer 的 act。

`check/tools/_metainfo`、`draft/tools/writer/tools/_metainfo`：`{"summary": "<誰> 叫的工具：lint（相對捷徑指 lib/lint）", "kind": "dir"}`。捷徑本身不放 `_metainfo`（它就是 lib 那份）。

### 舊資料夾的 `_metainfo` diff

| 檔 | 改什麼 |
|---|---|
| `galtxt-b/_metainfo` | `llm_calls` `{"val": 2, "max": 4}` → `{"val": 3, "max": 11}`（director 1～2＋writer 每稿 1～3（自檢）×3 稿＋critic 1）；`llm_tokens` `{"val": 4700, "max": 25000}` → `{"val": 7000, "max": 45000}`；`time_ms` `{"val": 18000, "max": 600000}` → `{"val": 26000, "max": 900000}`；`writes` 的 out 加 `measure.json`；`per_question` 加 `"counter_llm_calls": {"val": 3, "max": 11}` |
| `draft/_metainfo` | `summary` 改「兩步：沒 plan.json 先叫 tools/director 出 beat 表、tools/plan_lint 校驗；再叫 tools/writer 照表寫一稿」；`llm_calls` → `{"val": 2, "max": 5}`（第 1 稿：director 1～2＋writer 1～3；第 2、3 稿只有 writer）；`llm_tokens` → `{"val": 4300, "max": 15000}`；`time_ms` → `{"val": 16000, "max": 600000}`；`calls` 加 `tools/director`、`tools/plan_lint`；`writes` 加 `$AOS_STACK/plan.json`、`$AOS_STACK/director/` |
| `draft/tools/writer/_metainfo` | `summary` 加「可叫 lint 自檢（最多兩次）」；`llm_calls` `{"val": 1, "max": 1}` → `{"val": 1, "max": 3}`；`llm_tokens` → `{"val": 3000, "max": 11000}`；`time_ms` → `{"val": 10000, "max": 400000}`；`reads` 加 `cur/<n>.json#/brief（經 lint）`；`writes` 加 `$AOS_STACK/lint/（lint 的小格，空的）`、`llm.jsonl`；`calls: ["tools/lint"]` |
| `draft/tools/writer/fsm.json` think 單子 | `llm_tokens` max 7000 → 11000（帶 tool 結果再問） |
| `check/_metainfo` | `summary` 改「黏合格：叫 tools/lint 拿 violations，算 pass／final，寫 check.json」；加 `calls: ["tools/lint"]`；`time_ms` `{"val": 30, "max": 1000}` → `{"val": 80, "max": 2000}`（多一跳 aos-exec）；`grow_level` 3 → 4 |
| `brief/_metainfo` | `reads` 的 `tables/*.json` 不變；`summary` 加「few-shot 樣本、beat 文法」 |
| `brief/tables/_metainfo` | `summary` 加 `samples.json`、`beats.json` |
| `deliver/_metainfo` | `writes` 加 `out/<題名>/measure.json`；`reads` 加 `$AOS_STACK/trace.jsonl`、`$AOS_STACK/{writer,director,critic}/llm.jsonl`、`plan.json`（刪）；`summary` 加「彙整這題的實跑數字」 |
| `judge/`、`judge/tools/critic/` | `writes` 加 `llm.jsonl`（§4 的量測）；其餘不動 |

## 3. 給實作者的工作清單

**建**（照上面；入口 `+x`、第二行 NAME 一句）：

1. `lib/lint/{_entry,tool.json,_metainfo}`——規則從 `check/_entry` 搬過去（九條照搬＋`narration_max`），改成 stdin→stdout；`brief_path` 用 `檔#/指標` 解（自己切 `#`、`/` 一層層取，不用 aos-directive）。
2. `lib/plan_lint/{_entry,tool.json,_metainfo}`。
3. `draft/tools/director/`（整隻，照 writer 複製，改 `render`／`fake`／`system.txt`、act 用 critic 的）。
4. 捷徑：`check/tools/lint`、`draft/tools/plan_lint`、`draft/tools/writer/tools/lint`（`ln -s` 相對路徑；`git add` 捷徑本身）。對應的 `tools/_metainfo`。
5. `brief/tables/samples.json`、`brief/tables/beats.json`。

**改**：

6. `brief/_entry`：讀兩份新表，`brief.samples`（排除自己的 benchmark）、`brief.beats`、`brief.lines.narration_max`。
7. `draft/_entry`：兩步（§1e）；`plan.json`。
8. `draft/tools/writer/brain.py` `render`：加 plan、加「你的題目檔是 cur/<n>.json」、`GALTXT_FAKE_LINT`；`system.txt` 加自檢那段；`loop.json` max 10。
9. `check/_entry`：變薄（§1f）。
10. `deliver/_entry`：寫 `measure.json`、刪 `plan.json`。
11. 三隻 agent 的 `brain.py` `ask()`：寫 `llm.jsonl`（§4）。
12. 所有 `_metainfo` 照 §2；`README.md` 的樹與一句話；`demo.sh` 多一段 `GALTXT_FAKE_LINT=1` 跑 q01（看 writer 的 history 多出 tool_calls→tool→answer 三則）。

**驗收**（`proto8/tests/test_topdown_galtxt_b.py`；PATH 照 `tests/aos_bins.py`；全部用假腦，最後一組真腦）：

| 案例 | 怎麼做 | 綠的條件 |
|---|---|---|
| 端到端 q01 | 複製 examples/q01 到暫存 ws 的 new/，`aos-exec --ws ws galtxt-b` | 結束碼 0；`out/q01_…/{answer.txt,score.json,check.json,measure.json}` 在；`score.tier0.pass`；`.stack/plan.json` 不在（已刪）；頂層 trace 7 行、第 7 行 idle code 10 |
| 端到端 q08 打回重寫 | 同上，`GALTXT_FAKE_BAD_FIRST=1` | `check.json.history` 兩筆：第 1 稿含 `must_mention`、`banned_A`、`exclaim`，第 2 稿空；writer 的 `history.jsonl` 4 則；`.stack/director/` 只跑過一次（它的 trace 4 行） |
| 自檢那條路 | q01，`GALTXT_FAKE_LINT=1` | writer `history.jsonl` 裡依序有 assistant(tool_calls lint)、tool、assistant(稿)；`.stack/writer/lint/` 小格在；`measure.json.counter_lint_calls == 1` |
| **lint 每條規則各一個會紅的輸入**（直接 `aos-exec lib/lint`，stdin 餵 brief＋壞稿；brief 用跑過一次 q01 留下的 brief.json 或測試裡手組） | `format`：一行「主角 妳好」（沒「」）；`speaker`：「柏木秋穗：「…」」；`line_count`：只有 3 句；`must_mention`：沒有銀河鐵道之夜也沒宮澤賢治；`banned_A`：「心跳漏了一拍」；`banned_B`：「星巴克」；`banned_C`：「笑死」；`place_canon`：「連鎖書店」；`address`：森下晴子說「悠，…」／主角說「晴子，…」；`line_length`：一句 41 字；`exclaim`：森下晴子一個「！」；`catchphrase`：「……這句，很好。」兩次；`narration_max`：5 行旁白 | 每案 violations 裡**恰有**那條 rule（其他規則不誤中）；再餵第 1 輪假腦的好稿 → violations 空（證明雙向） |
| lint 自己的錯 | stdin 不是 JSON；沒 `text`；`brief_path` 指出 ws（`../x.json#/brief`）；指標指不到 | 退 1、stderr 與 stdout 同一行 `lint: ArgumentsBad／PathBad／PointerMissing …` |
| plan_lint 每條規則各一個會紅的 | `grammar`：缺 B0；`grammar`：B5 在 B3 前（也算 c1）；`beat_unknown`：B9；`who_unknown`：柏木秋穗；`must_assigned`：沒有拍認領「讓給／先看」；`b6_needs_pickup`：B6 前沒有含「書」的拍；`beats_count`：3 拍 | 同上恰有那條；餵 §1b 的範例表 → 空 |
| director 的表壞兩次 | 假腦開關 `GALTXT_FAKE_BAD_PLAN=2`（第 1、2 次都回缺 B0 的表） | `aos-exec galtxt-b` 退 1；stderr 有 `draft: PlanBad`；fsm `state.txt` 停在 `draft`；再跑一次（開關關掉）從 draft 格接著做、結束碼 0（P-20） |
| brief 的錯 | 場景 cast 寫「柏木秋穗」／place 寫「陽溜亭」／檔不是 JSON | 退 1、`brief: CastUnknown／PlaceUnknown／SceneBad`；`cur/` 裡題目還在 |
| check no-op | 跑完 q01 後手動把 `check.json` 留著、`draft.json` 同 attempt 再 `aos-exec check` | 退 0、`check.json` 內容不變（mtime 不變） |
| deliver 可重跑 | 跑到 deliver 之前（`score.json` 在），連跑兩次 `aos-exec deliver` | 第二次退 0、out 不變、`done/` 一份 |
| brief 的 samples 不漏正解 | 跑 q01 後看 `brief.json.samples` | 只有 q08 的段、不含「讓給主角同學」 |
| `_metainfo` 形狀 | 走訪 galtxt-b 底下每個資料夾 | 都有 `_metainfo`、是 JSON、有 `summary`；函數的有 `time_ms`；`resource` 含 `llm` 的一定有 `llm_calls`、`llm_tokens`、`llm_endpoint`、`llm_model`；數量類是數字或 `{val,max}` 且 `val ≤ max` |
| 捷徑 | `os.readlink` | 三條都是相對、指到的實體在 `lib/` 底下 |
| 真腦（`localhost:4000/v1/models` 連不上就 skip，同 test_dan） | `AOS_BRAIN_URL` 設好跑 q01 | 結束碼 0；`score.json.total ≥ 4`；`measure.json.counter_llm_calls` 在 3～11；`llm.jsonl` 每行有 `counter_tokens` |

「綠燈要證明能變紅」：每條規則的紅案例就是證明；另外拿掉 `lib/lint` 的 `narration_max` 那條，對應案例要紅。

## 4. 量測：實跑要記什麼、記在哪

目的：之後拿 `_metainfo` 表（宣告）對照實跑（量到的），找宣告失準、找貴的節點。全部照 stack／trace 慣例，不另開機制；計數欄位一律 `counter_*`。

| 要記的 | 誰記 | 記在哪 | 形狀 |
|---|---|---|---|
| 每格牆上時間 | aos-fsm（已有） | 每層 `$AOS_STACK/trace.jsonl` | `{"at","state","code","signal","elapsed_ms"}`——頂層一題一圈六行；writer／director／critic 各自的小格裡也有自己的 trace |
| 每次問腦的 token 與時間 | 三隻 agent 的 `brain.py` `ask()`（M7：實測寫自己的 stack，絕不回寫 `_metainfo`） | `$AOS_STACK/llm.jsonl`（agent 自己的 stack，一行一次） | `{"at": ISO 到毫秒, "model": 回覆的 model, "elapsed_ms": 請求到收到, "counter_tokens_prompt", "counter_tokens_completion", "counter_tokens", "usage": API 回的 usage 原物件（外部欄位名照原名）}`；假腦也寫一行（`counter_*` 全 0、`model: "fake"`），形狀才一致。`AOS_KERNEL_REPORT` 那段照舊另寫 |
| 問腦次數、重寫次數、自檢次數 | deliver 彙整（不另算：數 llm.jsonl 的行、check.json history 的筆數、writer history 裡 `tool_calls` 的則數） | `out/<題名>/measure.json` | 見下 |
| 一題總時間 | deliver：頂層 trace 從這題第一個 `brief` 行到 `deliver` 行的 `at` 差 | measure.json | `elapsed_ms` |

`measure.json`（deliver 在清 stack 之前寫；是「這一題」的數字，跟 `_metainfo` 的頂層與各格對照）：

```json
{"name": "q01_河鹿堂讓書", "benchmark": "q01",
 "elapsed_ms": 26120,
 "counter_cycles": 1, "counter_drafts": 1, "counter_plans": 1, "counter_lint_calls": 1,
 "counter_llm_calls": 4, "counter_tokens": 9800,
 "cells": {"brief": {"elapsed_ms": 19}, "draft": {"elapsed_ms": 15200}, "check": {"elapsed_ms": 80},
           "judge": {"elapsed_ms": 7100}, "deliver": {"elapsed_ms": 22}},
 "agents": {"director": {"counter_llm_calls": 1, "counter_tokens": 1700, "elapsed_ms": 5200},
            "writer":   {"counter_llm_calls": 2, "counter_tokens": 6000, "elapsed_ms": 9800},
            "critic":   {"counter_llm_calls": 1, "counter_tokens": 2100, "elapsed_ms": 6900}},
 "score": {"total": 6, "tier0": 1, "tier1": 2, "tier2": 3}}
```

`cells.*.elapsed_ms`：這題各格的 `elapsed_ms` 加總（打回那圈的 no-op 也算進去——那也是成本）。對照法（第 3 輪再寫工具，這輪先手看）：`measure.counter_llm_calls` 對頂層 `_metainfo.llm_calls.{val,max}`、`agents.writer.counter_tokens` 對 writer 的 `llm_tokens`、`cells.draft.elapsed_ms` 對 draft 的 `time_ms`；超過 `max` 的就是宣告失準。

## 5. 反向收攏的預期（更新）

- **會收**：`judge/tools/critic/` → judge 的一張 think 單子（不變）；`deliver/` → 併進 judge 尾巴（它現在多了 measure.json，但仍是純搬檔與加總）；`check/` 格本身——變薄後只剩「叫 lint、算 pass／final、寫檔」約 40 行，若 draft 黏合格在收稿時順手叫 lint 寫 check.json，check 格就能併掉（那會讓 draft 一格做兩件事，看第 3 輪 `_metainfo` 的 reads／writes 怎麼說：check 寫的 check.json 只有 draft、judge 讀）。
- **新長的、預期會留**：`lib/lint`、`lib/plan_lint`（被兩處叫、純函數——這是最不會被收的形）；`director`（如果真腦數字顯示 plan 讓打回率下降、token 沒多太多就留；反之就是第一個被收回 writer 的）。
- **可能縮回 JSON**：`brief/tables/` 五～七份 JSON → 一份 `tables.json`（除非要借檔案權限分「誰能寫表」）；director 與 writer 的 `fsm.json`／`loop.json`／`.env` 都是極小檔，但它們是範本的形、不縮。
- **中間層**：`tools/` 這層（每個黏合格底下）照 P-25／P-33 留著；第 1 輪 §7 第 6 條的方向性問題仍開著。

## 6. 跟原則有出入、要帶給使用者的（新增的；第 1 輪 §7 九條仍開著）

1. **三份幾乎一樣的 `brain.py`**（writer、director、critic）：10-24 tool-lib 代定 9「第三份一樣的大段再抽」到了，但 lib 契約「自成一格、不 import 隔壁」又說不要共用模組。這輪照複製；是不是該把「agent-dan 形的腦」做成 proto8 層級的範本或庫（使用者 10-23 提過 aos-agent 範本），由 proto8 定、不在 galtxt-b 裡解。
2. **lint 的 `brief_path` 用 `檔#/指標`**：N-62 說 `#/` 尋址只用在 aos-exec 的入口路徑、`$ref` 檔名、argv[0]；我拿同一寫法當工具參數的格式（相對 `$AOS_WS`）。寫法複用是好事，但不在規範列的那幾處——要不要允許「工具參數也可用 `檔#/指標`」。
3. **腦自檢的小格**：writer 叫 lint 時照 P-17 開小格 `$AOS_STACK/writer/lint/`，lint 是純函數、小格永遠是空的（lib 代定 10「base 層不用 stack」）；空資料夾會留在 stack 樹裡。接受（stack 樹＝呼叫樹的紀錄）或讓純函數工具不開小格（要改 act.py 範本），等使用者定。
4. **`llm.jsonl` 的欄位名**：自己的計數 `counter_tokens_*` 照新規，但 API 回的 `usage` 原物件照原名放在旁邊（C-54 例外「外部 API 參數名照原名」）——同一行裡兩套名字並存，接受還是只留一套。
5. **一題多一次問腦**：director 讓典型從 2 次變 3 次、token 約 +50%。這是用錢換可預測性（C-24 說要最佳化的是金錢、可預測性、人能不能理解——三者這裡互相拉扯）；真腦跑完 Q01／Q08 各幾次看 measure.json 再定留不留，這輪不拍板。
