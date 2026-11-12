# fable 規劃：不同質只量三軸（工具、腦、記憶），定義樹就是目錄，專精從帳上的訊號長出來、退休靠 git mv
← [README](README.md)

## 一、白話總結

這題在問三件事：怎麼判兩隻 agent 算不算「同一種」、什麼時候該多生一隻專精的、上千隻時怎麼找人與退休。下面每段講一個答案。

**判「同不同質」只看三樣東西：它有哪些工具、它用哪顆腦、它讀哪一塊記憶。** 這三樣正好是使用者原話點名的「獨特工具、獨特設定與記憶」。三樣全一樣就是同質，差一樣就算不同。prompt（`system.txt`）完全不算，因為使用者說「不要只有 prompt 相似」。像兩個只差「管哪個角色」的人物專員，工具與腦都一樣、只有記憶子樹不同，照這個規則算兩隻，這正是使用者 galgame 例子裡要的。

**三樣東西都從定義資料夾裡「公開宣告」的那幾個檔讀出來，不偷看別的。** 一隻 agent 的 `interfaces.json` 本來就寫著「我的工具表在哪、腦設定在哪」，這次只多宣告一行「我的記憶根在哪」。比對程式只讀這三個宣告指到的檔，像海關只看護照上的欄位，不翻行李。

**現行的 `agent_diversity` 檢查，方向對、量錯了兩樣。** 它多量了「誰叫它」（那是別人的行為，不是它自己的樣子，而且幾乎必然不同，等於白送一分）；它把 kernel 也算進腦（kernel 是環境，不是 agent 自己的）。它還是兩兩比對，一千隻要比五十萬對，而且一對失敗兩隻都不合格、不說該併誰。新做法是把三軸拼成一把鑰匙，鑰匙相同的放同一格，一格裡超過一隻就是重複，一次掃完。

**專精 agent 不是湊出來的，是帳上出現三種訊號才生。** 第一種：好幾個 case 裡都有人開了「同一份定義＋同一組工具」的臨時小幫手（這條 evolve-design 已經有了）。第二種：審視者想把一隻通才的腦降級，整隻卡在某一格過不了門——那一格就該拆出去給一隻窄工具的小 agent，其餘才降得下去。第三種：一隻 agent 每次問腦塞進去的字數中位數超過門檻，表示它背太多，該把記憶或職責切一塊出去。訊號只會變成「建議」寫在審視者的 `review.json` 裡，由隊長在一輪結束的審視時動手生；生之前先查目錄確認沒有三軸一樣的現成貨，有就直接用現成的。

**目錄不另外做一張表，定義資料夾本身排成樹就是目錄。** `defs/kb/places/linker/` 這種路徑，資料夾的層次就是分類，每個定義 README 第一行就是一句話說明，`_metainfo.json` 多一格 `lineage` 寫「我從誰拆出來、為什麼」。要找人，把現有的 `memory` 工具指到這棵樹，用它的 `find` 搜，不新造搜尋器。隊長只拿到頂層一頁簡介與類別清單，要誰再往下翻。新加一支小工具 `aos-defs`，只做兩件事：`ls`（列每個定義的路徑、一句話、三軸、出身）和 `dup`（列三軸全同的那幾格）。

**退休就是 `git mv` 搬進旁邊同樣深度的 `retired/` 樹，不刪、不改內容。** 要先確認 daemon 表上沒人正在用這份定義（跟 evolve 的 `promote` 同一個檢查）。搬走之後 `memory find` 自然搜不到它，但 git 記得它。合併＝同一格裡留被叫最多的那隻，其他退休。退休的判準在 evolve 原本「連三個 case 沒出現」之上補一句：同類別裡要有兄弟被叫過才算冷掉，否則只是這幾輪沒輪到它的領域，不該退——使用者說過不是每個神經元都會被激活。

**「一百個」是方向，這份設計裡沒有任何一步瞄準數字。** 數字只是 `aos-defs ls | wc -l` 的副產品。

## 二、設計

### 2.1 概念

- **定義＝身份**（C-46、C-79）。比對、目錄、族譜全部以定義資料夾為單位；實例（daemon 表上那列）和執行時改腦（覆蓋層、呼叫方逐題覆寫 endpoint）都不算新 agent。要讓「linker 其實都跑 terra」反映在目錄上，正途是審視者的 `downgrade` 改定義副本的 `llm.json` 再 `promote`，而不是目錄去看帳。
- **三軸簽名**：`tools`（工具表裡每支工具解析後的路徑集合，不看登記名）、`endpoint`（定義 `llm.json` 的 `endpoint`，空物件記成 `"default"`）、`memory`（記憶根解析後的路徑；沒有記憶工具就記 `null`，`null` 是一個值，跟有記憶算不同）。全部從 `interfaces.json` 的 `aos-agent` 宣告讀：既有的 `tools`、`llm`，加一個 `memory`。
- **同質＝三軸全同**。差任一軸即不同。`system.txt`、`agents.json`、fsm 形狀、成本都不進簽名：prompt 是使用者明說不算；成本是他見、隨輸入變；fsm 形狀每隻都是範本複本（11-04 使用者定的）。
- **族譜＝資料夾樹＋`lineage`**。樹的層次是類別，`lineage.from` 是血緣。兩者都是靜態、出生時定，之後不回寫。
- **狀態＝所在位置**。在 `defs/` 樹裡＝可用（叫到才起，躺著就是 sleep，交給 evolve-design）；在 `retired/` 樹裡＝退休。不在 `_metainfo.json` 加 `status` 欄。
- **族譜收所有定義，不同質檢查只跑有腦的**。有腦＝`interfaces.json` 有 `aos-agent`；腳本與 kernel 定義也在樹裡、有 README 與 `lineage`（從哪隻 agent 被 `fix` 成腳本），但不進 `dup`（方向題 1）。

### 2.2 機制

**A. 簽名與重複（`aos-defs`，新工具，放 `lib/aos/defs/`）**

- `aos-defs ls [--json] <defs 根>`：遞迴找有 `interfaces.json` 或 `_metainfo.json` 的資料夾（找到就不再往下，定義裡面的 `tools/memory/` 不算定義）。每個定義一行。
- `aos-defs dup [--json] <defs 根>`：只取有 `aos-agent` 宣告的定義，算三軸鑰匙 `tools|endpoint|memory`（路徑相對 defs 根、排序後串起），同鑰匙放一格，格內 ≥2 的列出。O(n)，不兩兩比。
- `aos-defs check <defs 根>`：lint——README 第一行非空、`_metainfo.json` 有 `summary`、宣告的三個檔都在、`lineage.from` 指得到。退 0／1。
- 不讀帳（`observed.jsonl`、ledger）、不讀 `system.txt`、不查 daemon 表。要「誰被叫幾次」找 evolve-design 的觀測工具。

**B. 目錄＝樹＋memory 工具**

- 一個專案一棵 `defs/`，第一層是類別（`kb/`、`kernel/`、`review/`……），再往下隊長自訂；定義資料夾名即定義名，路徑即唯一識別（C-68），不另訂「定義名唯一」規則。
- 每層資料夾有 `README.md`（第一行一句話；類別層列子項），這樣整棵樹就是 `memory` 工具認得的知識庫形狀。隊長範本多登記一支 `defs_memory`（就是 `lib/agent/memory` 的捷徑，`_memory.json` 的 `base` 指到 defs 根）；`read` 給頂層簡介＋類別目錄，`find` 搜一句話與 README。搜尋在上千筆後怎麼加 tag、怎麼縮範圍：交給 kb-scale。
- 類別層 README 的子項清單用 `aos-defs ls` 重生（gpt 可照做）。

**C. 出身（`lineage`）**

- `agents new` 寫新定義時，在新定義的 `_metainfo.json` 併入 `lineage`：`from`＝參數 `from`（相對新定義資料夾，照 C-50 續「定義內部路徑從自己資料夾算」）、`reason`＝新參數 `reason`（`specialize`／`split`／`fix`／`downgrade`／`manual`，預設 `manual`）、`review`＝新參數，選填，指到促成它的 `review.json`。`_metainfo.json` 不存在就新建只含 `lineage`。
- 審視者 `promote` 換上的副本同樣帶 `lineage`（`reason` 是它做的 move）；這在 evolve-design 的範圍內，這裡只定欄位。

**D. 生成訊號（寫進審視者 `review.json` 的 `suggest.specialize`）**

每一條建議都要帶：`from`（哪隻通才）、`signal`、`evidence`、`proposal`（建議的三軸）、`existing`（`aos-defs ls` 裡三軸全同的現成定義路徑，有就填、建議改成「改用它」）。三種訊號：

1. `repeated_child`：連兩個 case 出現「同一個子定義＋同一組工具」的 thought／agents 子 agent（evolve-design 原條，不改）。`proposal` 就是那組子定義的三軸。
2. `downgrade_stuck`：審視者對通才做 `downgrade` 時，整隻只因某一格（某一次工具呼叫前後的 think）過不了門而退回。`evidence` 記那格用了哪些工具；`proposal.tools`＝那格實際叫過的工具集合、`endpoint`＝原本的高階腦、`memory`＝通才的記憶根。意思是「把過不了的那格拆給一隻窄工具 agent，其餘降級」。
3. `context_too_big`：該定義在這一輪 case 裡 think 的 `prompt_tokens` 中位數 > 門檻（審視者設定 `max_prompt_tokens_median`，預設 10000，方向題 3）。`proposal` 留空由隊長裁拆法（拆記憶子樹或拆職責），只給 `evidence`。

訊號來源全部是 evolve-design 已定的兩本帳（`observed.jsonl` 的 think 用量、thought／agents 抄進父帳的子帳），不新增記錄點。「知識庫某子樹被反覆查」這類要看工具參數內容的訊號，帳裡只有位元組數、沒有內容，先不做，等帳有了內容摘要欄再補（寫明等什麼，照 C-52 例外門檻）。

**E. 退休與合併（`suggest.retire`）**

- 判準：（a）連三個 case 沒在呼叫樹出現（evolve 原條）；**且**（b）這三個 case 裡，它所在類別資料夾的其他定義至少有一隻被叫過。(b) 擋住「這幾輪根本沒做它的領域」被誤退。
- 合併：`aos-defs dup` 的同一格內，留他見 `count` 最高的那隻，其餘列進 `retire`，`merge_into` 填留下的那隻。
- 每條 `retire` 帶 `callers`（從帳裡抄：誰的 `from`／`def` 指到它），讓隊長先改呼叫方再搬。
- 執行：隊長 `aos-agent ctl ls --json` 確認沒有 `def` 指到它的列（有就不動，同 `promote` 的 `DefBusy`），然後 `git mv defs/<類別>/<名> retired/<類別>/<名>`。`retired/` 與 `defs/` 同層、同深度，定義裡的相對路徑（`../../lib/…`）搬過去仍指得到。不刪檔。復職＝搬回來。
- 沒改到的呼叫方照字面壞掉（路徑指不到→`stopped`，C-79），下一輪審視會看到；不做轉向、不留捷徑（C-56 寫什麼就做什麼、不寫遷移）。

**F. 誰按**

- 審視者只寫建議。
- 隊長在一輪結束的審視步讀 `suggest`，`specialize` 用 `agents new`（`from`＝範本或通才、`files`＝新 `system.txt`＋`tools.json`＋`llm.json`＋`tools/memory/_memory.json`、`reason`、`review`）；`retire` 照 E 的四步。前三個 case 隊長逐條做；之後 `specialize` 可改成審視者自動 `new`（方向題 2），`retire` 永遠是隊長按。
- 使用者看 git log 與 `retired/`。刪除永不自動。

### 2.3 JSON 範例

`interfaces.json`（agent-fsm 範本，加一鍵）：
```json
{"aos-agent": {"entry": "body.json", "tools": "tools.json", "llm": "llm.json", "memory": "tools/memory/_memory.json"}}
```

專精定義 `defs/kb/places/linker/_metainfo.json`：
```json
{"summary": "linker 只裁模稜提及並補原文中的表外人名。",
 "time_ms": {"val": 12000, "max": 120000},
 "resource": ["llm"],
 "lineage": {"from": "../place_lead", "reason": "split", "review": "../../../../reviews/2026-11-07T15/review.json"}}
```

`aos-defs ls --json`（每行一個）：
```json
{"path": "kb/places/linker", "summary": "linker 只裁模稜提及並補原文中的表外人名。", "brain": true,
 "tools": ["../lib/agent/read"], "endpoint": "terra", "memory": "../corpus/lore",
 "lineage": {"from": "kb/places/place_lead", "reason": "split"}}
{"path": "kb/places/kb_store", "summary": "kb_store 將原文逐字存成段落陣列，並產生固定標題。", "brain": false,
 "lineage": {"from": "kb/places/place_lead", "reason": "fix"}}
```
（`ls` 把 `lineage.from` 換算成相對 defs 根；腳本型定義沒有三軸欄。）

`aos-defs dup --json`：
```json
{"groups": [{"key": "tools=../lib/agent/read|endpoint=terra|memory=../corpus/lore",
             "members": ["kb/places/linker", "kb/persons/linker2"]}]}
```

`review.json` 的 `suggest`（延伸 evolve-design 的兩格，不另開格）：
```json
{"suggest": {
  "specialize": [
    {"from": "kb/places/place_lead", "signal": "downgrade_stuck",
     "evidence": {"stuck_step": 4, "tools_used": ["read"], "failed_endpoint": "terra"},
     "proposal": {"tools": ["../lib/agent/read"], "endpoint": "sol", "memory": "../corpus/lore"},
     "existing": "kb/places/linker"},
    {"from": "kb/persons/person_lead", "signal": "context_too_big",
     "evidence": {"prompt_tokens_median": 14200, "max_prompt_tokens_median": 10000},
     "proposal": null, "existing": null}],
  "retire": [
    {"def": "kb/places/writer_places", "signal": "unused_3_cases",
     "siblings_called": ["kb/places/linker", "kb/places/namer"], "callers": [], "merge_into": null},
    {"def": "kb/persons/linker2", "signal": "duplicate",
     "callers": ["kb/persons/person_run"], "merge_into": "kb/places/linker"}]}}
```

審視者設定多兩個 key：`{"max_prompt_tokens_median": 10000, "retire_after_cases": 3}`。

### 2.4 各層誰負責

| 層 | 做什麼 | 不做什麼 |
|---|---|---|
| aos-exec／loop／fsm | 無變動 | 不認 `lineage`、不認 defs 樹 |
| daemon | 無變動；表仍是唯一實例清單 | 不管定義；退休前「有沒有人在用」是隊長來查表，不是 daemon 去看定義 |
| llm kernel | 無變動 | 誰先用腦、嵌套排程：交給 kernel-nest |
| agent 範本（agent-fsm） | `interfaces.json` 加 `memory`；新增 `_metainfo.json` 範本（`summary`、`time_ms`、`resource`）；README 第一行一句話 | 不加 `kind`／`status`／`role` 欄 |
| lib 工具 | `agents new` 寫 `lineage`（新參數 `reason`、`review`）；新工具 `lib/aos/defs`（`ls`／`dup`／`check`）；`memory` 不改，只是多一個指向 defs 根的捷徑 | `aos-defs` 不讀帳、不讀 `system.txt`、不查 daemon |
| 審視者（evolve-design 的 `templates/reviewer/`） | `suggest.specialize` 三訊號、`suggest.retire` 加兄弟條件與合併、生建議前用 `aos-defs ls` 填 `existing`／`merge_into` | 不動 defs 樹、不 `new`（方向題 2 裁定前） |
| 隊長 | 一輪結束讀 `suggest`，執行 `agents new` 與 `git mv`；維護類別 README | 不自己判三軸，交給 `aos-defs` |
| 使用者 | 看 git log、`retired/`；裁方向題 | — |

啟動步驟（C-78）不多一步：defs 樹是工作區裡的資料夾，`aos-defs` 是被叫才跑的工具。

## 三、與既有條文的衝突

1. **C-52 只認公開介面 vs 比對要讀別隻的定義檔。** 衝突：判同質要讀 `tools.json`、`llm.json`、記憶根，而 C-46 說 agent 只看到自己的工具清單。後果：照字面讀 C-52 就沒法做任何跨定義比對；放寬成「隨便讀定義資料夾」又會讓程式認內部檔名分支。**推薦**：定義是磁碟上的原始碼，不是正在跑的下層；只讀 `interfaces.json` 宣告指到的檔，所以把記憶根加進宣告（一鍵 `memory`），`system.txt` 沒宣告就不讀——正好也符合「prompt 不算」。這是「B 宣告、A 照宣告」的標準型。
2. **C-79「定義是原始碼，不在 image 裡」、C-65「工作區只放交辦與成果」vs `agents new` 只准寫進工作區。** 衝突：審視與隊長生出的新定義必然落在 `$AOS_WS`，所以 defs 樹放在 ws 裡最順；但這讓 image 帶著定義。後果：放 ws 裡→image 搬到另一台就帶著整套定義，可遷移（C-83）但 image 變大；放 ws 外→每次 `new` 後要多一步搬，且 `agents new` 要放寬 PathBad。**推薦**：defs 樹放 `$AOS_WS/defs/`（方向題 4），把演化出的定義當成「成果」看待；C-79 那句改讀成「範本與 lib 不在 image 裡，演化出的定義在」。
3. **`_metainfo` 待定稿「實測不回寫」、evolve「他見不回寫進定義夾」vs 族譜要記出身與狀態。** 衝突：若把 `status`、`count` 寫進 `_metainfo.json` 就違反。後果：寫了→定義跑一次就變、簽名漂移；不寫→族譜少資料。**推薦**：`lineage` 是出生時一次性宣告（不是實測），之後不回寫；狀態用所在資料夾表示；次數留在帳裡由審視者讀。
4. **evolve 的 `suggest.retire`「連三個 case 沒出現」vs 使用者「不是每個神經元都會被激活」。** 衝突：按領域分化的專精 agent 本來就該長時間不被叫。後果：照原條→人物專員在連做三個地點後被建議退休，隊長要一條條否決；不設退休→死定義堆著。**推薦**：加「同類別有兄弟被叫過」的條件（§2.2 E）。這是對 evolve 兩格判準的補充，不改它的迴圈。
5. **11-04 使用者「格程式放範本裡，每隻複製」vs 上千份複本。** 衝突：`idle.py` 修一行要改一千份；名詞表與待定「工具＝函式庫」都是引用不複製。後果：維持複製→每隻獨立、可單獨演化，但範本修 bug 不會傳下去；改引用→與使用者裁定相反。**推薦**：不重開。`lineage.from` 已經記了每份從哪個範本來，將來要「重鑄」有線索可追；此輪不加機制。
6. **判官 `allowed` 逐一列實例名 vs 自動出生的大量實例。** 推薦方向是按定義路徑前綴放行；機制交給 kernel-nest。
7. **使用者「刪檔一定先問」、proto8 不寫遷移 vs 退休要把定義拿掉。** 衝突：刪不得、又不留轉向。後果：留捷徑→等於遷移層；直接刪→違反使用者偏好。**推薦**：退休＝`git mv` 到同深度 `retired/`，不刪；建議單先列 `callers` 讓隊長改呼叫方；漏改的照字面壞掉、下一輪審視看見。
8. **現行 `agent_diversity` 的 `callers` 軸與 `active` 過濾 vs C-46 定義＝身份。** 衝突：誰叫它、有沒被叫是他見，不是定義的樣子。後果：留著→白送一項差異、沒被叫過的定義永遠沒法檢查。**推薦**：`dup` 只量三軸、掃全部有腦定義；「活不活」留給 `suggest.retire`。

## 四、方向題（未裁，暫照推薦）

1. **族譜裡「算 agent」的範圍。** 選項 a：只有有腦的定義（`aos-agent` 宣告）進不同質檢查，「一百個」數的是這個；腳本與 kernel 定義只在樹裡有 README 與 `lineage`。選項 b：所有定義都算，三軸對腳本改量「輸入輸出形狀」。後果：a 簡單、數字會偏小（改進迴圈一直在把 agent 變腳本）；b 數字好看但要替腳本另定判準，多一套格式。**推薦 a**——使用者說過「方向，不湊數」，數字小不是問題；族譜照樣看得到整個神經網。
2. **專精定義誰按。** 選項 a：永遠只建議，隊長執行。選項 b：前三個 case 隊長執行，之後審視者可自動 `agents new`（照 evolve 對 `fix`／`split` 的同一節奏），退休永遠隊長按。選項 c：全自動。後果：a 最穩、隊長每輪多幾分鐘；b 與 evolve 一致，自動生出的定義可能冷門（有 retire 兜底）；c 退休牽涉搬檔，不該自動。**推薦 b**。
3. **「上下文過大」的門檻。** 選項 a：絕對數 `max_prompt_tokens_median: 10000`，審視者設定檔裡一個數。選項 b：相對全樹中位數的倍數（×2）。後果：a 一眼懂、要隨模型換代調；b 自適應、但全樹都胖時一隻都不會被點名。**推薦 a**。
4. **defs 樹放哪。** 選項 a：`$AOS_WS/defs/`（隊長工作區裡）。選項 b：工作區外另一棵，`agents new` 放寬 PathBad 或每次手搬。後果：a 零改動、image 帶定義；b 工作區乾淨、多一步、多一條例外。**推薦 a**（見衝突 2）。

## 五、落地小步（gpt 照圖施工）

每步一句完成條件；順序可照做，1～4 彼此獨立可並行。

1. **範本加記憶宣告**：`templates/agent-fsm/interfaces.json` 的 `aos-agent` 加 `"memory": "tools/memory/_memory.json"`；`templates/docs/02-agent-fsm.md` 補一句。完成：`aos-agent ctl add` 範本複本照常掛上，既有 tests 全過。
2. **範本加 `_metainfo.json`**：`templates/agent-fsm/_metainfo.json` 內容 `{"summary": "<一句話，與 README 第一行同>", "time_ms": {"val": 30000}, "resource": ["llm"]}`；README 第一行改成一句話說明。完成：`aos-exec` 範本資料夾行為不變，`python -c 'import json;json.load(open(...))'` 讀得過。
3. **`agents new` 寫 `lineage`**：`lib/agent/agents/_entry` 的 `new` 加選填參數 `reason`（enum 五值，預設 `manual`）、`review`（字串）；寫完 `files` 後把 `lineage: {from, reason, review?}` 併進新定義的 `_metainfo.json`（沒有就建）；`from` 寫成相對新定義資料夾的路徑；`_tooldef.json` 同步加參數說明。完成：用 `new` 從範本生一隻，新定義 `_metainfo.json#/lineage/from` 解析後等於範本路徑。
4. **新工具 `lib/aos/defs/`**：`_entry`（python）、`_tooldef.json`、`_metainfo.json`；子命令 `ls`／`dup`／`check`，照 §2.2 A 與 §2.3 的輸出格式；路徑一律印成相對 defs 根；錯誤格式 `aos-defs: error: 代號 原因`，代號至少 `RootMissing`、`DefBad`。完成：在 `tests/` 擺一棵三個定義（兩個三軸全同）的小樹，`ls` 印三行、`dup` 印一格兩個成員、`check` 對缺 README 的定義退 1。
5. **defs 樹接上 memory**：隊長範本（arknights 的 `place_lead` 或新開 `lead`）的 `tools.json` 多登記 `defs_memory`，捷徑同 `tools/memory/` 的做法，`_memory.json` 的 `base` 指 `../../defs`；defs 根與每個類別層放 `README.md`。完成：隊長叫 `defs_memory {"op":"find","query":"連結"}` 回到含 `linker` 的路徑；`{"op":"read"}` 只回頂層簡介與類別清單。
6. **審視者 `suggest` 判準**（在 evolve-design 的 `templates/reviewer/` 裡改）：設定檔加 `max_prompt_tokens_median: 10000`、`retire_after_cases: 3`；產 `suggest.specialize` 時實作 `repeated_child`（已有）、`downgrade_stuck`、`context_too_big` 三訊號，每條用 `aos-defs ls --json` 填 `existing`；產 `suggest.retire` 時加兄弟條件、加 `dup` 合併、填 `callers`。欄位照 §2.3。完成：拿 arknights 三個地點的帳跑一次，`review.json` 的 `retire` 列出 `writer_places` 且 `siblings_called` 非空，`specialize` 的每條都有 `existing` 欄（可為 null）。
7. **隊長的處方頁**：在隊長讀得到的知識庫寫一節 `defs/README.md#執行建議`：specialize 四步（讀 `proposal`→查 `existing`→`agents new` 帶 `reason`／`review`→更新類別 README）、retire 四步（`ctl ls --json` 查 `def`→改 `callers`→`git mv` 到 `retired/<同路徑>`→更新類別 README），逐條寫出確切指令。完成：gpt 照頁面對一條假建議走完兩套步驟，不需判斷設計。
8. **驗證並封存舊檢查**：在試驗場 `defs/` 上跑 `aos-defs dup` 與 `aos-defs check`，把結果與 `runs/2/diversity.json` 的差異寫成一段放進本資料夾 README 的「驗證」節；試驗場的 `agent_diversity` 不改、不刪（試驗場是唯讀）。完成：README 有該節，列出三隻 agent 的三軸與 `dup` 為空的事實。
