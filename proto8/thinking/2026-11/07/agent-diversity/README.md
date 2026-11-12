# 不同質 agent 的頂層設計：同不同質只看工具、腦、記憶三樣，定義資料夾排成樹就是目錄，專精從帳上的訊號長出來，退休是搬進旁邊的 retired/ 樹
← [2026-11-07](../README.md)｜條文：[C-89](../../../../docs/CONCEPTS/05-agent/05-C-89-不同質與族譜.md)

使用者 11-07 傍晚五題方向題全選推薦（見「使用者裁定」）；隊長替他做的小決定在「代定」，每條可翻案。新條文的條號在 lift 時另編，避開 [lift-to-norms](../lift-to-norms/README.md) 暫編的 N-68、C-84。

## 使用者原文

- 想法 8（11-07 午後）：「我希望這輪增加一百個agent，並且每個都不要太同質化，不要只有prompt相似，要有獨特工具，獨特設定與記憶。」
- 一百個是方向：「方向，不湊數」（[kb-ideas](../kb-ideas/README.md)）。
- user-advice 的例子：「將需求丟給專管各人物的各agent」；「工具可以是開一個agent做事，或是將請求交給專精此道的kernel，所以才說會有成千上萬個agent。就好比LLM的神經元，不是每個區域都會被激活」。
- 工作區要乾淨（10-16，C-65）：「我不喜歡/ws底下出現一個work/，這太突兀了，工作區會變得不乾淨」。

## 結論

- 同不同質只看三軸：工具、腦、記憶（＝「獨特工具、獨特設定與記憶」）；差一軸就算不同（ad-2）；prompt 不算（「不要只有prompt相似」）。「誰叫它」不算。
- 撞鑰匙（三軸全同）不自動合併，建議其中一隻長出自己的記憶或工具；只有證明職責相同（同一份 case、同一道門）才合併。
- 專精 agent 從帳上的訊號長出來；生之前先查目錄有沒有三軸全同的現成貨，有就用。
- 目錄不另做表：定義資料夾排成樹就是目錄，搜尋用 `defs ls --match`。
- 退休＝搬進同深度的 `retired/` 樹，不刪、不改內容；復職就搬回來。
- 「一百個」是方向，設計裡沒有一步衝著數字去；改進迴圈本來就在把 agent 換成腳本，要等新類別（人物、勢力）才會長出新的重複角色。

## 設計

### 概念（五條，待入 CONCEPTS，條號 lift 時另編）

1. **定義就是身份**（C-46、C-79）。比對、目錄、族譜都以定義資料夾為單位。實例（daemon 表上的一列）、執行時的覆蓋層、呼叫方逐題指定的腦，都不算新 agent。定義實際用的腦要反映到定義上，走審視者的 `downgrade` 改副本 `llm.json` 再 `promote`（evolve-design），目錄本身不讀帳。
2. **三軸簽名，差一軸就是不同。** `tools`（工具表裡每支工具解析後的路徑集合，不看登記名）、`endpoint`（定義 `llm.json` 的 `endpoint`；空的記成 `"default"`）、`memory`（宣告的記憶根解析後的路徑；沒有記憶記 `null`，`null` 也是一個值）。`system.txt`、`agents.json`、fsm 形狀、成本都不進簽名。
3. **同質是缺陷，不是合併令。** 處理是請其中一隻長出自己的記憶或工具；「職責相同」的證明是同一個 case、同一道門都過（evolve-design 的 `metainfo_check`）。
4. **族譜＝資料夾樹＋出生時寫一次的 `lineage`。** 樹的層次是類別，`lineage.from` 是血緣，之後不回寫。版本歷史（同一路徑被 `promote` 換新版）交給 git 和 evolve 的 `.prev/`。
5. **狀態看所在位置。** 在 `defs/` 樹裡＝可用（叫到才起，躺著就是 sleep）；在 `retired/` 樹裡＝退休。`_metainfo.json` 不加 `status`、`count` 這類欄（evolve「實測不回寫」）。

族譜收全部定義（agent、腳本、kernel），不同質檢查只跑有腦的定義（`interfaces.json` 有 `aos-agent` 宣告的；ad-1）。

### 各層誰負責

| 層 | 做什麼 | 不做什麼 |
|---|---|---|
| aos-exec／loop／fsm | 無變動 | 不認 `lineage`、不認 defs 樹 |
| daemon、判官 | 無變動；daemon 表仍是唯一的實例清單；自動出生的實例照判官 `allowed: null`（不限）放行 | 不管定義；退休前「有沒有人在用」由隊長查表 |
| llm kernel | 無變動 | 誰先用腦、嵌套排程交給 kernel-nest |
| agent 範本 agent-fsm | `interfaces.json` 的 `aos-agent` 加 `memory`；`_metainfo.json`（evolve 格式）；README 第一行一句話 | 不加 `kind`／`status`／`role` 欄 |
| lib | `agents new` 寫 `lineage`（參數 `reason`、`review`）；工具 `lib/aos/defs/`（`ls`／`dup`／`refs`／`check`） | `defs` 不讀帳、不讀 `system.txt`、不查 daemon |
| 審視者（evolve-design 的 `templates/reviewer/`） | `suggest.specialize` 兩訊號＋`split` 出生記 lineage；`suggest.retire` 加兄弟條件；`suggest.differentiate` 列撞鑰匙的；生建議前用 `defs ls` 填 `existing` | 不動 defs 樹 |
| 隊長 | 一輪結束讀 `suggest`，做 `agents new` 與 `git mv`；維護類別 README | 不自己判三軸，交給 `defs` |
| 使用者 | 看 git log 與 `retired/` | — |

啟動步驟不多一步（C-78）：defs 樹就是工作區裡的資料夾，`defs` 是被叫才跑的工具。

### A. 簽名：三軸都從公開宣告讀

`interfaces.json` 的 `aos-agent` 多一鍵 `memory`：

```json
{"aos-agent": {"entry": "body.json", "tools": "tools.json", "llm": "llm.json", "memory": "tools/memory/_memory.json"}}
```

- 比對只讀這三個宣告指到的檔。
- 要被比對的 agent，記憶一律寫進 `_memory.json`、由 `interfaces.json` 宣告；`tools.json` 不用 env 指記憶（代定 6）。值裡有 `$env` 時照字面比 `{"$env","$path"}` 物件、不展開（N-67 ⑦）。
- 一隻 agent 有兩個記憶時，記憶軸只看宣告的那一個，多出來的捷徑顯在 `tools` 軸。
- 工具軸看解析後的路徑，不看登記名；工具的 env 不進簽名。

### B. `lib/aos/defs`：列、找重複、找引用、檢查

- `defs ls [--json] [--match 字] <defs 根>`：遞迴找有 `interfaces.json` 或 `_metainfo.json` 的資料夾，找到就不再往下。每個定義一行。`--match` 只比對路徑和 `summary`（不分大小寫）。
- `defs dup [--json] <defs 根>`：只取有 `aos-agent` 宣告的定義，鑰匙 `tools|endpoint|memory`（路徑相對 defs 根、排序後串起），同鑰匙同一格，列成員 ≥2 的格。O(n)。
- `defs refs [--json] <defs 根> <定義>`：列出宣告檔裡引用到這份定義的其他定義（`tools.json` 的 path、工具 env 的 `AOS_THOUGHT_FROM`）。退休前要查（代定 7）。
- `defs check <defs 根>`：README 第一行非空、`_metainfo.json` 有 `summary`、宣告的三個檔都在、定義資料夾名符合 `[a-z0-9_-]+`（代定 11）。不要求 `lineage.from` 指得到（代定 2）。退 0／1。
- 錯誤：`defs: error: <代號> <原因>`，代號至少有 `RootMissing`、`DefBad`。

`defs ls --json`（一行一個）：

```json
{"path": "kb/places/linker", "summary": "linker 只裁模稜提及並補原文中的表外人名。", "brain": true,
 "tools": ["../lib/base/read"], "endpoint": "terra", "memory": null,
 "lineage": {"from": "defs/kb/places/place_lead", "reason": "split"}}
{"path": "kb/places/kb_store", "summary": "kb_store 將原文逐字存成段落陣列，並產生固定標題。", "brain": false}
```

`defs dup --json`：

```json
{"groups": [{"key": "tools=|endpoint=luna|memory=null",
             "members": ["kb/places/namer", "kb/persons/title_translator"]}]}
```

### C. 出身 `lineage`（`agents new` 寫，只在出生時寫一次）

- `agents new` 參數：`reason`（`specialize`／`split`／`fix`／`manual`，預設 `manual`）；`review`（選填，指向促成它的 `review.json`）。寫完 `files` 後把 `{"lineage": {"from", "reason", "review"?}}` 併進新定義的 `_metainfo.json`，沒有就新建。
- `from` 照 agents 工具的路徑規則存：參數怎麼給就怎麼存（相對 `$AOS_WS` 或絕對）（代定 2）。
- `promote` 不寫 lineage（代定 1）。`_metainfo.json` 照 evolve 格式：`cost.time_ms`、`timeout_ms`（代定 3）。

```json
{"summary": "linker 只裁模稜提及並補原文中的表外人名。",
 "cost": {"time_ms": 12000},
 "timeout_ms": 120000,
 "resource": ["llm"],
 "lineage": {"from": "defs/kb/places/place_lead", "reason": "split", "review": "reviews/3/review.json"}}
```

### D. 生成訊號：審視者 `review.json` 的 `suggest`

每條 `specialize` 帶 `from`、`signal`、`evidence`、`proposal`（建議的三軸）、`existing`（`defs ls` 裡三軸全同的現成定義；有就改成「改用它」）。

1. `repeated_child`：連兩個 case 出現「同一個子定義＋同一組工具」的 thought／agents 子 agent（evolve 原條）。`proposal` 是那組子定義的三軸。
2. `context_too_big`：這份定義在這一輪 case 裡 think 行 `prompt_tokens` 中位數超過 `max_prompt_tokens_median`（預設 10000，ad-4）。`proposal` 留空，隊長裁拆法，只給 `evidence`。
3. `split` 出生的定義不另發訊號：審視者用 `split` 在副本生出新定義時 `lineage.reason` 寫 `split`，`promote` 時跟著換上（代定 5）。

「知識庫某子樹被反覆查」這類訊號等帳有內容摘要欄再補（交給 evolve-design）。

撞鑰匙另開 `suggest.differentiate`（代定 5）：

```json
{"suggest": {
  "specialize": [
    {"from": "defs/kb/persons/person_lead", "signal": "context_too_big",
     "evidence": {"prompt_tokens_median": 14200, "max_prompt_tokens_median": 10000},
     "proposal": null, "existing": null}],
  "differentiate": [
    {"key": "tools=|endpoint=luna|memory=null",
     "members": ["kb/places/namer", "kb/persons/title_translator"],
     "same_duty": null}],
  "retire": [
    {"def": "kb/places/writer_places", "signal": "unused_3_cases",
     "siblings_called": ["kb/places/linker", "kb/places/namer"],
     "callers": [], "refs": [], "merge_into": null}]}}
```

- `same_duty`：有同一份 case、同一道門的比較結果時才填；`true` 時才可以在 `retire` 寫 `merge_into`。
- `callers`（帳裡抄的「誰叫過它」）與 `refs`（`defs refs`）只寫在審視者自己的 `review.json`，不寫進被叫者的資料夾（晚審設計問題 17、evolve「他見不回寫進定義夾」）。試驗場 `defs/<名>/_observed.json` 的作法不進 aos。

審視者設定多兩個 key：`{"max_prompt_tokens_median": 10000, "retire_after_cases": 3}`。

### E. 退休

- **判準**：（a）連三個 case 沒在呼叫樹出現（evolve 原條）；**而且**（b）這三個 case 裡，同類別資料夾的其他定義至少有一隻被叫過。只有一隻的類別不退。
- **執行四步**（隊長按，永不自動）：
  1. `aos-agent ctl ls --json` 確認沒有一列的 `def` 指到它（有就不動，同 `promote` 的 `DefBusy`）。
  2. `callers` 與 `refs` 都清空：先改呼叫方。
  3. `git mv defs/<類別>/<名> retired/<類別>/<名>`（`retired/` 與 `defs/` 同層同深度）。
  4. 更新類別 README。
- 不刪檔；漏改的呼叫方照字面壞掉（路徑指不到就留 `stopped`，C-79），下一輪審視看得到。不做轉向、不留捷徑。
- defs 根要在 git 裡（隊長的工作區慣例；aos 工具不認 git）。

### F. 目錄怎麼讀

- 一個專案一棵 `defs/`（`$AOS_WS/defs/`，ad-5），第一層是類別（`kb/`、`kernel/`、`review/`……），再往下由隊長自訂。路徑就是唯一識別（C-68）。
- 每層資料夾有 `README.md`（第一行一句話；類別層列子項，用 `defs ls` 重生）。隊長只拿頂層一頁簡介加類別清單，要誰再往下翻（想法 7「只給他頂層簡介和目錄」）。
- 搜尋用 `defs ls --match`，memory 只拿來一層層 `read`／`ls`（代定 9）。
- tag 照 kb-scale／evolve 的 `_tags.json` 約定。
- 定義要能定期提取（ad-5 備註）：`defs/` 樹保持能整棵或按類別連 README、`lineage` 一起複製到別處；提取的時機與挑法交 evolve-design 的審視者或隊長，實作待排。

## 跟既有條文的讀法（結論）

1. C-52、C-46 vs 比對要讀別隻的定義：定義是磁碟上的原始碼，比對只讀 `interfaces.json` 宣告指到的檔（所以記憶根加進宣告）。
2. C-79、C-65 vs `agents new` 只准寫進工作區：defs 樹放 `$AOS_WS/defs/`（ad-5）；C-79 讀成「範本與 lib 不在 image 裡，演化出的定義在」。
3. `_metainfo` 實測不回寫：`lineage` 是出生時一次寫好的宣告，之後不回寫；狀態用所在資料夾表示；次數留在帳裡。
4. evolve 的 `suggest.retire`：加「同類別有兄弟被叫過」條件，不改 evolve 迴圈。
5. 11-04「放範本裡，每隻複製」vs 上千份複本：不重開；`lineage.from` 記著從哪個範本來，這一輪不加機制。範本修 bug 不會自動傳下去。
6. 判官 `allowed`：自動出生的實例照 `null` 放行；按定義路徑前綴放行歸判官遠期（N-42 (2)）。
7. 刪檔先問、不寫遷移 vs 退休：退休＝`git mv` 到 `retired/`，不刪、不留捷徑。
8. 試驗場 `agent_diversity` 的 `callers` 軸與 `active` 過濾不進 aos：`dup` 只量三軸、掃全部有腦的定義；「活不活」留給 `suggest.retire`。
9. C-46「沒有 `parent` 鏈」vs `lineage.from`：lineage 是原始碼的出處（像 git fork 紀錄），不是執行時的上層；aos-exec、fsm、agent 都不讀它，只有 `defs` 與審視者讀。條文要補這一句。
10. `_metainfo` 範本照 evolve 已裁格式（代定 3）。
11. 待定「self-improve 預設就關」vs 審視者自動 `agents new`（ad-3）：產出別的定義不算 self-improve（同 evolve 衝突 6 的讀法）；加拒生門：`existing` 非空就不生。

## 使用者裁定（11-07 傍晚，40 題選項框）

回覆原文全文在 [kb-ideas](../kb-ideas/README.md#11-07-傍晚-40-題裁定原文)；回覆後補一句「很多東西都可以靈活改進，所以後面我就不寫了」（[想法 15](../kb-ideas/README.md)）：各題的判準、標準、階段、門檻本身都可以再被改進。

- **ad-1**（數有多少隻不同 agent 時，要把腳本和 kernel 算進去嗎？）：選 A「只有有腦的定義進不同質檢查，「一百個」數的就是這些；腳本與 kernel 定義只在樹裡、有 README 與 lineage」。
- **ad-2**（工具、腦、記憶差幾樣，才算不同 agent？）：選 A「差一軸就算（fable）」。
- **ad-3**（專精 agent 的定義，要由誰建立和退休？）：選 B「前三個地點由隊長執行，之後審視者可以自動 agents new，跟 evolve 對 fix／split 的節奏一樣；退休永遠由隊長按」。加拒生門（讀法 11）。
- **ad-4**（上下文大到該拆工作，要用固定數字還是相對大小判斷？）：選 A「絕對數 max_prompt_tokens_median: 10000，寫在審視者設定裡」。
- **ad-5**（演化出來的定義樹，要放在工作區裡嗎？）：選 A「$AOS_WS/defs/（隊長的工作區裡）」。備註原話：「可以定期將定義提取出來。之後其他工作，比如我要拆另一個遊戲時，可以運用。」

晚審 [04 第 10 題](../../../../../wf/workflows/refactor/reports/2026-11-07-晚審/04b-要使用者裁定-續.md)問同一件事，使用者選 C「三項取二」但備註「以ad-2爲準」：判準照 ad-2，差一軸就算不同，「誰叫它」不算。

## 代定（隊長替使用者做的小決定，每條可翻案）

1. `lineage` 只在出生（新路徑）時寫；`reason` 只有 `specialize`／`split`／`fix`／`manual`；`promote` 不寫 lineage。
2. `lineage.from` 照 agents 工具的路徑規則存（相對 `$AOS_WS` 或絕對）；`defs check` 不要求它指得到。
3. `_metainfo.json` 的範例與範本照 evolve 已裁格式（`cost.time_ms`、`timeout_ms`）。
4. 工具名叫 `defs`、放 `lib/aos/defs/`（lib 工具名就是資料夾名）。
5. 撞鑰匙放 `suggest.differentiate`，只有 `same_duty: true` 才准 `merge_into`；不做 `downgrade_stuck` 訊號，改成 `split` 出生時記 lineage。
6. 要被比對的 agent，記憶一律寫在 `tools/memory/_memory.json`、由 `interfaces.json` 宣告；`tools.json` 不用 env 指 `AOS_MEMORY`。
7. 退休前除了帳裡的 `callers`，還要查 `defs refs` 的靜態引用。
8. 自動出生的實例照判官 `allowed: null` 放行；按定義路徑前綴放行留給判官的遠期（N-42 (2)）。
9. 搜尋用 `defs ls --match`，memory 只拿來一層層 `read`／`ls`。
10. 活躍 agent 只有 3 隻不當缺陷：要等新類別（人物、勢力）才長出新的重複角色。
11. 定義資料夾名照 memory 段名規則 `[a-z0-9_-]+`（`defs check` 查）。

## 落地

- 已做（[impl-plan](../impl-plan/README.md) 批 9 `f33595cf9`，[11-批9施工結果](../impl-plan/11-批9施工結果.md)）：範本 `interfaces.json` 加 `memory`、範本 `_metainfo.json`；`agents new` 寫 `lineage`；`lib/aos/defs/`（`ls`／`dup`／`refs`／`check`）；審視者 `suggest` 判準（`specialize`、`differentiate`、`retire` 兄弟條件、設定兩鍵）；處方頁在 `lib/aos/defs/README.md`。
- 未做：
  - `context_too_big` 真 round 端到端沒通：measure 收尾移除原 agent 帳、沒有公開通往 run 帳的邊，要補 measure 的保帳介面。
  - `split` 出生記 lineage（等 evolve 審視者放手寫副本）。
  - 試驗場驗證（三隻活躍 agent 記憶改由 `_memory.json`＋`interfaces.json` 宣告、跑 `defs dup`／`check`）交 arknights 線。
  - 條文：五條概念入 CONCEPTS；讀法 1、2、9、11 的改讀句。

## 同批其他題

- 改進迴圈、兩本帳、審視者、`promote`／watch、metainfo 評估：[evolve-design](../evolve-design/README.md)。專精 agent 的出生紀錄（`lineage`＋`review`）審視者的審視者可直接讀。
- 工具權限演進：[tool-evolve](../tool-evolve/README.md)（`extract`／`box`／`unshell` 改 `tools.json`，就是本題的工具軸）。
- 知識庫查詢、tag、`_tags.json`：[kb-scale](../kb-scale/README.md)。
- 誰先用腦、llm kernel 嵌套排程：[kernel-nest](../kernel-nest/README.md)。
