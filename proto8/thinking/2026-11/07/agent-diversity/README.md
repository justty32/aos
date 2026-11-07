# 不同質 agent 的頂層設計：同不同質只看工具、腦、記憶三樣，定義資料夾排成樹就是目錄，專精從帳上的訊號長出來，退休是搬進旁邊的 retired/ 樹
← [2026-11-07](../README.md)｜簡報 [01-簡報](01-簡報.md)｜fable 原始輸出 [02-fable規劃](02-fable規劃.md)

本檔是 opus 隊長的補全：以 fable 的 02 為底稿，核對了條文引用，補上 fable 漏掉的衝突，修掉幾處跟同批已裁設計對不上的地方，並跟同批的 [evolve-design](../evolve-design/README.md)、[tool-evolve](../tool-evolve/README.md)、[kb-scale](../kb-scale/README.md)、[kernel-nest](../kernel-nest/README.md) 對齊。使用者出門到 16:30，說不要問他，方向題當時寫「未裁，暫照推薦」，11-07 傍晚使用者已全部裁定（見「使用者裁定」節）；隊長替他做的小決定另列在「代定」一節，每條都可以翻案。新條文的條號在 lift 時另編，避開 [lift-to-norms](../lift-to-norms/README.md) 暫編的 N-68、C-84。

## 白話總結

這題問三件事：兩隻 agent 怎樣算「同一種」、什麼時候該多生一隻專精的、將來上千隻時怎麼找人、怎麼讓用不到的退休。下面一段講一件事。

**判斷同不同質，只看三樣東西：手上有哪些工具、用哪顆腦、讀哪一塊記憶。** 這三樣正好是你原話點名的「獨特工具、獨特設定與記憶」。三樣全一樣，就算同一種；差一樣，就算不同。寫給它的那段開場白（prompt）完全不算，因為你說「不要只有prompt相似」。舉例來說，兩隻人物專員工具和腦都一樣，只是一隻讀「夕」的資料、一隻讀「年」的資料，照這個規則就是兩隻不同的 agent。這跟你在 user-advice 裡說的「專管各人物的各agent」是同一個意思。

**試驗場現在那支檢查，方向對，但量錯兩樣。** 第一，它多量了一項「誰叫它」。那是別人的行為，不是它自己的樣子；而且每隻 agent 都由自己專屬的腳本叫，這一項幾乎一定不同，等於白送一分。晚審也剛好指出「把誰叫我寫進被叫者的資料夾，就是下層知道了上層」，所以這一項拿掉，兩邊說的是同一件事。第二，它比的是兩兩配對，一千隻就要比五十萬對，而且一對沒過就兩隻都不合格，也不說哪隻該怎麼辦。新做法是把三樣東西拼成一把鑰匙，鑰匙一樣的放進同一格，掃一遍就知道哪幾隻重複。

**重複了不自動合併，而是請它長出自己的特色。** 兩隻鑰匙一樣、只有開場白不同的 agent，做的多半是兩件不同的事（例如一隻取英文名、一隻翻譯），直接併掉就會把其中一件事弄壞。所以撞鑰匙只會寫成「這兩隻太像了」，建議給其中一隻配上自己的記憶或工具。真要合併，得先證明兩隻做的是同一件事：拿同一份考題、過同一道門，這是 evolve-design 已經有的比法。

**專精 agent 不是湊數湊出來的，是帳上出現訊號才生。** 有兩種訊號。第一種是好幾個地點都有人臨時開了「同一份定義、同一組工具」的小幫手，表示這件事一再出現（evolve-design 已經有這條）。第二種是某隻 agent 每次問腦時塞進去的字太多，表示它背的東西太雜，該把一塊記憶或一塊職責切出去。另外，審視者在改進時把一步拆成「腳本先處理、模型只做一小塊」，拆出來的那一小塊本來就是一隻新的專精 agent，它出生時會記下自己是怎麼來的。要生之前，先查目錄有沒有鑰匙一樣的現成貨，有就直接用。

**目錄不另外做一張表：定義資料夾本身排成樹，就是目錄。** 例如 `defs/kb/places/linker/`，資料夾的層次就是分類，每個定義的 README 第一行就是一句話說明。每個定義再多記一格「出身」：我是從誰拆出來的、為什麼。找人時先一層一層往下看，要搜尋就用一支小工具 `defs`，把一句話說明和路徑拿來比對。這支工具還能列出重複的那幾格，以及「有誰引用了這份定義」。

**退休就是搬進旁邊的 `retired/` 樹，不刪檔、不改內容。** 搬之前先確認兩件事：daemon 上沒有人正在用它，也沒有其他定義引用它。搬走後就搜不到它了，但 git 記得它，要復職就搬回來。「多久沒被叫就退休」，在 evolve-design 原本「連三個地點沒出現」之外再加一個條件：同類別的兄弟這三輪要有被叫過，才算它冷掉了。不然只是這幾輪剛好沒做到它的領域，不該退。這呼應你說的「不是每個區域都會被激活」。

**「一百個」是方向，這份設計裡沒有任何一步是衝著數字去的。** 數字只是把目錄數一數的副產品。要先說清楚的是：改進迴圈的方向本來就是把模型做的事換成腳本，所以第二輪三個地點下來，活躍的 agent 還是三隻，這是預期中的事。要往上長，得等做到人物、勢力這些新類別，任務的形狀變了，才會冒出新的重複角色。

**有五題原則推不出答案，都先照推薦做。** 分別是：「算 agent」只算有腦的定義、差幾樣才算不同、專精定義誰來按、「字太多」的門檻怎麼定、定義樹放在哪。跟既有條文的衝突共有十一條，最要緊的三條是：比對時要讀別隻 agent 的定義（只讀它公開宣告的那幾個檔）、「出身」那一格看起來像 C-46 說的「沒有 parent 鏈」、定義樹放進工作區會讓你 10-16 說過「工作區要乾淨」的那個顧慮又冒出來。

## 設計

### 概念（五條，待入 CONCEPTS，條號 lift 時另編）

1. **定義就是身份**（C-46、C-79）。比對、目錄、族譜都以定義資料夾為單位。實例（daemon 表上的一列）、執行時的覆蓋層、呼叫方逐題指定的腦，都不算新 agent。試驗場 B3 報告「沒有把模型代號算新定義」就是這個意思。linker「其實都跑 terra」要反映到定義上，正途是審視者的 `downgrade` 改副本的 `llm.json` 再 `promote`（交給 evolve-design），目錄本身不去讀帳。
2. **三軸簽名，差一軸就是不同。** 三軸是：`tools`（工具表裡每支工具解析後的路徑集合，不看登記名）、`endpoint`（定義 `llm.json` 的 `endpoint`；空的記成 `"default"`）、`memory`（宣告的記憶根解析後的路徑；沒有記憶就記 `null`，`null` 也是一個值）。`system.txt`、`agents.json`、fsm 形狀、成本都不進簽名：prompt 是你明說不算的；成本是他見，會隨輸入變；fsm 每隻都是範本複本（11-04 你定的「每隻複製」）。
3. **同質是缺陷，不是合併令。** 三軸全同表示「只有 prompt 不同」，正是你說不要的那種。處理方法是請其中一隻長出自己的記憶或工具；只有證明兩隻職責相同時才合併。「職責相同」的證明是同一個 case、同一道門都過（evolve-design 的 `metainfo_check`「同職責多個定義誰划算」）。
4. **族譜＝資料夾樹＋出生時寫一次的 `lineage`。** 樹的層次是類別，`lineage.from` 是血緣。兩樣都在出生時定好，之後不回寫。版本歷史（同一路徑被 `promote` 換新版）交給 git 和 evolve 的 `.prev/`，不是 lineage。
5. **狀態看所在位置。** 在 `defs/` 樹裡就是可用的（叫到才起，躺著就是 sleep，已裁，交給 evolve-design）；在 `retired/` 樹裡就是退休。`_metainfo.json` 不加 `status`、`count` 這類欄（守 evolve 已定的「實測不回寫」）。

族譜收全部定義（agent、腳本、kernel），不同質檢查只跑有腦的定義（`interfaces.json` 有 `aos-agent` 宣告的；方向題 1）。

### 各層誰負責

| 層 | 做什麼 | 不做什麼 |
|---|---|---|
| aos-exec／loop／fsm | 無變動 | 不認 `lineage`、不認 defs 樹 |
| daemon、判官 | 無變動；daemon 表仍是唯一的實例清單；自動出生的實例照判官現行 `allowed: null`（不限）放行 | 不管定義；退休前「有沒有人在用」由隊長查表 |
| llm kernel | 無變動 | 誰先用腦、嵌套排程交給 kernel-nest |
| agent 範本 agent-fsm | `interfaces.json` 的 `aos-agent` 加 `memory`；新增 `_metainfo.json`（照 evolve 已裁格式）；README 第一行一句話 | 不加 `kind`／`status`／`role` 欄 |
| lib | `agents new` 寫 `lineage`（新參數 `reason`、`review`）；新工具 `lib/aos/defs/`（`ls`／`dup`／`refs`／`check`） | `defs` 不讀帳、不讀 `system.txt`、不查 daemon |
| 審視者（evolve-design 的 `templates/reviewer/`） | `suggest.specialize` 兩訊號＋`split` 出生記 lineage；`suggest.retire` 加兄弟條件；`suggest.differentiate` 列撞鑰匙的；生建議前用 `defs ls` 填 `existing` | 不動 defs 樹；方向題 3 裁定前不自己 `new` |
| 隊長 | 一輪結束讀 `suggest`，做 `agents new` 與 `git mv`；維護類別 README | 不自己判三軸，交給 `defs` |
| 使用者 | 看 git log 與 `retired/`；裁方向題 | — |

啟動步驟不多一步（C-78）：defs 樹就是工作區裡的資料夾，`defs` 是被叫才跑的工具。

### 機制與資料格式

#### A. 簽名：三軸都從公開宣告讀

一隻 agent 的 `interfaces.json` 本來就宣告了「工具表在哪、腦設定在哪」（範本現況 `{"aos-agent": {"entry": "body.json", "tools": "tools.json", "llm": "llm.json"}}`），這次只多一鍵 `memory`：

```json
{"aos-agent": {"entry": "body.json", "tools": "tools.json", "llm": "llm.json", "memory": "tools/memory/_memory.json"}}
```

比對程式只讀這三個宣告指到的檔。就像海關只看護照上的欄位，不翻行李。

- **記憶的宣告只認一個地方。** 範本的記憶根本來就寫在 `tools/memory/_memory.json` 的 `base`；試驗場卻是在 `tools.json` 裡用 env 指 `AOS_MEMORY`（例 place_lead 的 `{"$env": "AOS_WS", "$path": "kb-ak2"}`）。C-norms 原文是「用 `AOS_MEMORY` 指，定義裡的 `_memory.json` 蓋過它」。所以施工時，凡是要被比對的 agent，記憶一律寫進 `_memory.json`、由 `interfaces.json` 宣告；`tools.json` 不再用 env 指記憶（代定 6）。值裡有 `$env` 時，就照字面比 `{"$env","$path"}` 物件、不展開（N-67 ⑦：環境變數的值不落檔）。
- **一隻 agent 有兩個記憶**（例如隊長多了一個指向 defs 樹的捷徑）：記憶軸只看宣告的那一個，多出來的捷徑因為路徑不同，會在 `tools` 軸上顯出差別，不必另訂規則。
- **工具軸看解析後的路徑**，不看登記名，所以兩隻把 `lib/base/read` 登記成不同名字仍算同一支。工具的 env（例 linker 的 `read` 帶 `AOS_WS` 指語料）不進簽名：那是工具的參數，不是工具本身。

#### B. `lib/aos/defs`：列、找重複、找引用、檢查

工具名照 lib 的慣例就是資料夾名 `defs`（fable 寫成 `aos-defs`；`aos-` 前綴是 `cmd/` 的指令，代定 4）。

- `defs ls [--json] [--match 字] <defs 根>`：遞迴找有 `interfaces.json` 或 `_metainfo.json` 的資料夾，找到就不再往下（定義裡面的 `tools/memory/` 不算定義）。每個定義一行。`--match` 只比對路徑和 `summary`（不分大小寫），給上千個時搜尋用（代定 9）。
- `defs dup [--json] <defs 根>`：只取有 `aos-agent` 宣告的定義，算鑰匙 `tools|endpoint|memory`（路徑相對 defs 根、排序後串起），同鑰匙的放同一格，列出成員 ≥2 的格。O(n)，不兩兩比。
- `defs refs [--json] <defs 根> <定義>`：列出宣告檔裡引用到這份定義的其他定義，看的是 `tools.json` 的 path，以及工具 env 的 `AOS_THOUGHT_FROM`。這是「靜態引用」，退休前要查（代定 7）。
- `defs check <defs 根>`：README 第一行非空、`_metainfo.json` 有 `summary`、宣告的三個檔都在、定義資料夾名符合 memory 段名規則 `[a-z0-9_-]+`（代定 11）。**不要求 `lineage.from` 指得到**，因為親代可能已經退休（代定 2）。退 0／1。
- 錯誤照 lib 慣例：`defs: error: <代號> <原因>`，代號至少有 `RootMissing`、`DefBad`。

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

注意這一格的例子：沒有工具、沒有記憶、只靠腦的小 agent 最容易撞鑰匙（namer 就是這一型）。撞了，正是使用者那句話要的提醒：給它一個自己的記憶。以 namer 為例，可以讓它讀凍結名字表，看到既有的命名風格。

#### C. 出身 `lineage`（`agents new` 寫，只在出生時寫一次）

- `agents new` 的新參數：`reason`，可以是 `specialize`、`split`、`fix` 或 `manual`，預設 `manual`；`review`，選填，指向促成它的 `review.json`。寫完 `files` 後，把 `{"lineage": {"from", "reason", "review"?}}` 併進新定義的 `_metainfo.json`，沒有這個檔就新建。
- `from` **照 agents 工具自己的路徑規則存**：參數怎麼給就怎麼存，相對 `$AOS_WS` 或是絕對路徑。fable 原稿寫成「相對新定義資料夾」，但那樣親代一退休或搬類別，路徑就斷了，`check` 也會跟著紅（代定 2）。
- fable 原稿的 `reason` 有 `downgrade`，這裡拿掉。`downgrade` 是同一個路徑換新版，不是出生；版本歷史交給 git 與 evolve 的 `.prev/`（代定 1）。`promote` 不寫 lineage。
- `_metainfo.json` 照 evolve-design 已裁的格式寫：估時放 `cost.time_ms`、逾時放 `timeout_ms`，頂層不再有 `time_ms`。fable 的範例還在用舊的 `time_ms.{val,max}`，這裡改掉（代定 3）。

```json
{"summary": "linker 只裁模稜提及並補原文中的表外人名。",
 "cost": {"time_ms": 12000},
 "timeout_ms": 120000,
 "resource": ["llm"],
 "lineage": {"from": "defs/kb/places/place_lead", "reason": "split", "review": "reviews/3/review.json"}}
```

#### D. 生成訊號：寫進審視者 `review.json` 的 `suggest`

每條 `specialize` 建議帶這幾欄：`from`（哪隻通才）、`signal`、`evidence`、`proposal`（建議的三軸）、`existing`（`defs ls` 裡三軸全同的現成定義；有就填，建議改成「改用它」）。

1. `repeated_child`：連兩個 case 出現「同一個子定義＋同一組工具」的 thought／agents 子 agent。這是 evolve 原條，不改。`proposal` 就是那組子定義的三軸。
2. `context_too_big`：這份定義在這一輪 case 裡，think 行 `prompt_tokens` 的中位數超過門檻（審視者設定 `max_prompt_tokens_median`，預設 10000，方向題 4）。`proposal` 留空，由隊長裁定拆法（拆記憶子樹或拆職責），只給 `evidence`。用第二輪的數字對照：place_lead 中位 8,940、linker 約 4,210，現在都不會觸發。
3. **`split` 出生的定義不必另發訊號。** fable 原稿多一種 `downgrade_stuck`（通才降級時「整隻只因某一格過不了門」）。可是 evolve 的門是看整個 case 的產出，帳裡只有位元組數、沒有內容，算不出是哪一格錯的，所以這個訊號量不到。而且「降級失敗之後拆成『腳本＋更小的 LLM 步』」本來就是 evolve 的 `split` 招，拆出來的小 LLM 步就是新的專精 agent。所以這裡改成：`split` 在副本裡生出新定義時，`lineage.reason` 寫 `split`，`promote` 時跟著換上。這樣專精 agent 也會在改進迴圈裡自然長出來，不必另外再建議一次（代定 5）。

「知識庫某子樹被反覆查」這類訊號要看工具參數的內容，現在的帳只有位元組數，先不做；等帳有了內容摘要欄再補（交給 evolve-design）。

**撞鑰匙另開一格 `suggest.differentiate`**（fable 原稿是在同一格裡留被叫最多的那隻、其他退休；理由見概念 3，代定 5）：

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

- `same_duty`：有同一份 case、同一道門的比較結果時才填（`true`／`false`）；`true` 時才可以在 `retire` 裡寫 `merge_into`。
- `callers` 是從帳裡抄出來的「誰叫過它」，`refs` 是 `defs refs` 查到的「誰引用它」。這兩樣都寫在審視者自己的 `review.json` 裡，不寫進被叫者的資料夾。這正是晚審設計問題 17「他者觀測寫回被叫者的資料夾，下層因此知道上層」的建議做法（彙整結果出到樹外的報告），也和 evolve 已定的「他見不回寫進定義夾」一致。試驗場那份寫在 `defs/<名>/_observed.json` 的作法不進 aos。

審視者的設定多兩個 key：`{"max_prompt_tokens_median": 10000, "retire_after_cases": 3}`。

#### E. 退休

- **判準**：（a）連三個 case 沒在呼叫樹出現（evolve 原條）；**而且**（b）這三個 case 裡，它所在類別資料夾的其他定義至少有一隻被叫過。只有一隻的類別就不會被退，這是刻意的：沒有兄弟可比，就看不出它是冷掉了還是沒輪到。
- **執行四步**（隊長按，永不自動）：
  1. `aos-agent ctl ls --json` 確認沒有一列的 `def` 指到它（有就不動，同 `promote` 的 `DefBusy`）。
  2. `callers` 與 `refs` 都清空：先改呼叫方。
  3. `git mv defs/<類別>/<名> retired/<類別>/<名>`。`retired/` 與 `defs/` 同層同深度，定義裡的相對路徑搬過去照樣指得到。
  4. 更新類別 README。
- 不刪檔；復職就是搬回來。漏改的呼叫方照字面壞掉（路徑指不到就留 `stopped`，C-79），下一輪審視會看到。不做轉向、不留捷徑（不寫遷移）。
- defs 根要在 git 裡。這是隊長的工作區慣例，aos 工具不認 git（tool-evolve 已寫明「`promote` 不碰 git」）。

#### F. 目錄怎麼「讀」

- 一個專案一棵 `defs/`，第一層是類別（`kb/`、`kernel/`、`review/`……），再往下由隊長自訂。定義資料夾名就是定義名，路徑就是唯一識別（C-68），不另訂「定義名唯一」的規則。
- 每層資料夾都有 `README.md`（第一行一句話；類別層列出子項，用 `defs ls` 重生），所以整棵樹也是 memory 認得的形狀。隊長只拿到頂層一頁簡介加類別清單，要誰再往下翻（想法 7「只給他頂層簡介和目錄」）。
- **搜尋用 `defs ls --match`，不用 memory 的 `find`**（代定 9）。fable 原稿要用 memory `find`，但 memory 會把定義資料夾裡的 `.json` 檔都當成子節點（`memory_fs.py` 的 `children` 只略過 `_`、`.` 開頭與 README），`find` 又是在全文 grep、最多回 20 筆。搜「read」會先撈到上千份 `tools.json`，20 格立刻被雜訊塞滿。memory 只拿來 `read`、`ls`，一層一層翻。
- defs 要加 tag 的話，照 kb-scale／evolve 已定的 `_tags.json` 約定，不另訂格式（交給 kb-scale）。

## 與既有 CONCEPTS／NORMS 的衝突

fable 列了八條，這裡核對過條文。第 6 條改了歸屬，另外補上三條（9～11）。

1. **C-52「只認公開介面」、C-46「agent 只看到自己的工具清單」 vs 比對要讀別隻 agent 的定義檔。** 照字面讀，任何跨定義比對都做不了；放寬成「隨便讀定義資料夾」，又會讓程式依賴內部檔名。推薦：定義是磁碟上的原始碼，不是正在跑的下層；比對只讀 `interfaces.json` 宣告指到的檔，所以把記憶根加進宣告。`system.txt` 沒宣告，就不讀，這正好也符合「prompt 不算」。後果：範本多一鍵；不加的話記憶軸只能猜檔名。（晚審設計問題 18「改進者要看穿下層」是同一類張力；那邊是看帳，這邊是看宣告，都走「B 宣告、A 照宣告」。）
2. **C-79「定義是原始碼，不在 image 裡」、C-65「工作區是使用者的檔與成品」 vs `agents new` 只准寫進工作區。** 新定義必然落在 `$AOS_WS`，所以 defs 樹放在 ws 裡最順，但 image 就帶著定義。fable 漏了 C-65 的原話：你 10-16 說「我不喜歡/ws底下出現一個work/，這太突兀了，工作區會變得不乾淨」，`defs/`、`retired/`、`reviews/` 三個資料夾會讓這個顧慮又冒出來。另外，試驗場現在其實是 b 型：`defs/` 在試驗場根、工作區是 `ws/kb-ak2`，定義由施工者寫，不經 `agents new`。推薦仍是放 ws 裡（方向題 5），理由是隊長這類 agent 的「成品」本來就是定義；C-79 改讀成「範本與 lib 不在 image 裡，演化出的定義在」。後果：放外面的話，要放寬 `agents new` 的 `PathBad`，或每次手動搬，審視者自動生定義就做不了。
3. **待定稿「`_metainfo` 實測不回寫」、evolve「他見不回寫進定義夾」 vs 族譜要記出身與狀態。** 推薦：`lineage` 是出生時一次寫好的宣告（作者在寫，不是跑的時候寫），之後不回寫；狀態用所在資料夾表示；次數留在帳裡，由審視者讀。後果：不這樣做，定義跑一次就會變，簽名跟著漂移。
4. **evolve 的 `suggest.retire`「連三個 case 沒出現」 vs 你說「不是每個區域都會被激活」。** 照原條，人物專員在連做三個地點之後就會被建議退休，隊長得一條條否決。推薦加上「同類別有兄弟被叫過」這個條件。這是補充 evolve 的判準，不改它的迴圈。
5. **11-04 你定的「放範本裡，每隻複製」 vs 名詞表「引用、不複製」、待定「工具＝函式庫」與上千份複本。** 試驗場已經看得到：4 份 `idle.py` 全同，act.py／brain.py 3 同 1 異。推薦不重開：`lineage.from` 已經記下每份從哪個範本來，將來真要「重鑄」有線索可追；這一輪不加機制。後果：範本修 bug 不會自動傳下去，要靠審視者或隊長逐份換。
6. **判官 `allowed` 逐一列實例名 vs 自動出生的大量實例。** fable 寫「交給 kernel-nest」，核對後不對：kernel-nest 已寫明問腦鏈不經判官，判官名單不在它的範圍。實際上判官的 `allowed` 可以是 `null`（不限，`lib/aos/judge` 原文「null 或沒寫＝不限」），所以現在不衝突，自動出生的實例照 `null` 放行。將來要「按定義路徑前綴放行」，是 N-42 (2)「判官往後長成誰能對誰做什麼」那條遠期方向的事，留在判官那裡。
7. **你的偏好「刪檔一定先問」、proto8 不寫遷移 vs 退休要把定義拿掉。** 推薦：退休就是 `git mv` 到同深度的 `retired/`，不刪；先清 `callers`、`refs`；漏改的照字面壞掉，下一輪審視看得到。後果：留捷徑等於多一層遷移；直接刪違反偏好。
8. **試驗場 `agent_diversity` 的 `callers` 軸與 `active` 過濾 vs C-46「定義就是身份」、C-74 單向分層。** 誰叫它、有沒有被叫過都是他見，不是定義本身的樣子。晚審設計問題 17 從另一頭指出同一件事。推薦：`dup` 只量三軸、掃全部有腦的定義；「活不活」留給 `suggest.retire`，而且寫在審視者自己的報告裡。後果：留著的話，白送一項差異，從沒被叫過的定義也永遠檢查不到。
9. **（補）C-46「子 agent 只看自己的 stack，沒有 `parent` 鏈」 vs `lineage.from` 寫著「我從誰來」。** 看起來像在定義裡加了一條 parent 鏈。推薦讀成兩件不同的事：C-46 講的是執行時「誰生了我這個實例」，lineage 講的是原始碼「這份定義是從哪份分出來的」，像 git 的 fork 紀錄；aos-exec、fsm、agent 本身都不讀它，只有 `defs` 與審視者讀。後果：條文要補一句「lineage 是作者的出處，不是執行時的上層」；不補的話，有人會拿它去做執行時往上找。
10. **（補）evolve 已裁的 `_metainfo` 格式（`cost.time_ms`／`timeout_ms`、頂層 `time_ms` 拿掉）與 lift-to-norms 草稿 C09 vs fable 範本 `_metainfo.json` 仍寫 `time_ms.{val,max}`。** 這不是跟原則衝突，是跟同批已裁的格式對不上。已照 evolve 改（代定 3）。
11. **（補）待定之二「self-improve 預設就關」 vs 方向題 3 選 b（審視者第四個地點起自動 `agents new`）。** evolve 衝突 6 已經把「審視者經 `promote` 換別人的定義」讀成不算 self-improve；自動 `new` 是同一類（產出別的定義，不是改正在跑的自己）。推薦沿用那句改讀，並加一道門：要生的定義三軸若已有現成貨，就拒生（`existing` 非空就不生）。後果：不加這道門的話，自動出生會先長出一堆重複。

## 方向題（11-07 傍晚已裁，五題都選推薦）

1. **「算 agent」的範圍。** (a) 只有有腦的定義進不同質檢查，「一百個」數的就是這些；腳本與 kernel 定義只在樹裡、有 README 與 `lineage`。(b) 所有定義都算，三軸對腳本改量「輸入輸出形狀」。後果：a 簡單，但數字會偏小，因為改進迴圈一直在把 agent 變成腳本；b 數字好看，但要替腳本另訂判準，多一套格式。**推薦 a**：你說過「方向，不湊數」，數字小不是問題；族譜裡照樣看得到整張神經網，包括 kernel 與工具那些「不是每個區域都會被激活」的部分。**已裁（11-07 傍晚）。**
2. **（補）差幾軸才算不同。** 你的原話是「要有獨特工具，獨特設定與記憶」，可以讀成三樣都要獨特，也可以讀成至少要有一樣。(a) 差一軸就算（fable）。(b) 差兩軸（試驗場現行，但它有一軸是白送的 callers）。(c) 三軸都要不同。後果：c 最嚴，但「專管各人物的各agent」通常工具和腦相同、只差記憶，會全部不過；b 也會擋掉這一型；a 讓「只差記憶」的專員成立，但上千個專員可能只是同一個模子換一塊記憶。**推薦 a**：user-advice 的例子要的正是這一型，而且這一型最能把職責縮窄、換成便宜的腦。**已裁（11-07 傍晚）。**
3. **專精定義誰按。** (a) 永遠只建議，隊長執行。(b) 前三個地點由隊長執行，之後審視者可以自動 `agents new`，跟 evolve 對 `fix`／`split` 的節奏一樣；退休永遠由隊長按。(c) 全自動。後果：a 最穩，隊長每輪多花幾分鐘；b 跟 evolve 一致，自動生出的定義可能冷門，但有退休規則兜底；c 退休牽涉搬檔，不該自動。**推薦 b，加上衝突 11 的拒生門。**`split` 出生（代定 5）本來就跟著 evolve 的節奏走。**已裁（11-07 傍晚）。**
4. **「上下文過大」的門檻。** (a) 絕對數 `max_prompt_tokens_median: 10000`，寫在審視者設定裡。(b) 全樹中位數的倍數（×2）。後果：a 一眼看得懂，但要隨模型換代調整；b 會自己調整，但全樹都胖的時候一隻也不會被點名。**推薦 a。****已裁（11-07 傍晚）。**
5. **defs 樹放哪。** (a) `$AOS_WS/defs/`（隊長的工作區裡）。(b) 工作區外另一棵（試驗場現況）。後果：a 程式零改動，image 帶著定義，但工作區多三個資料夾，碰到你 10-16「工作區要乾淨」的顧慮；b 工作區乾淨，但 `agents new` 要放寬 `PathBad`，否則審視者沒辦法自動生定義。**推薦 a**（衝突 2）。**已裁（11-07 傍晚）。**使用者備註：定義要能定期提取出來，之後別的工作（例如拆另一個遊戲）可以拿去用——所以 `defs/` 樹要保持能整棵或按類別複製出去（代定：提取＝把 `$AOS_WS/defs/` 的某幾個類別連 README、`lineage` 一起複製到別處，提取的時機與挑法交 evolve-design 的審視者或隊長，實作待排）。

## 使用者裁定（11-07 傍晚，40 題選項框）

使用者 11-07 傍晚在 40 題選項框裡裁定（回覆原文全文在 [kb-ideas](../kb-ideas/README.md#11-07-傍晚-40-題裁定原文)）；除特別註明，選的都是推薦。回覆後補一句「很多東西都可以靈活改進，所以後面我就不寫了」（[想法 15](../kb-ideas/README.md)）：各題的判準、標準、階段、門檻本身都可以再被改進，沒逐題寫備註的也一樣。

- **ad-1**（數有多少隻不同 agent 時，要把腳本和 kernel 算進去嗎？）：選 A「只有有腦的定義進不同質檢查，「一百個」數的就是這些；腳本與 kernel 定義只在樹裡、有 README 與 lineage」。
- **ad-2**（工具、腦、記憶差幾樣，才算不同 agent？）：選 A「差一軸就算（fable）」。
- **ad-3**（專精 agent 的定義，要由誰建立和退休？）：選 B「前三個地點由隊長執行，之後審視者可以自動 agents new，跟 evolve 對 fix／split 的節奏一樣；退休永遠由隊長按」。
- **ad-4**（上下文大到該拆工作，要用固定數字還是相對大小判斷？）：選 A「絕對數 max_prompt_tokens_median: 10000，寫在審視者設定裡」。
- **ad-5**（演化出來的定義樹，要放在工作區裡嗎？）：選 A「$AOS_WS/defs/（隊長的工作區裡）」。備註原話：「可以定期將定義提取出來。之後其他工作，比如我要拆另一個遊戲時，可以運用。」

晚審 [04 第 10 題](../../../../../wf/workflows/refactor/reports/2026-11-07-晚審/04b-要使用者裁定-續.md) 問的是同一件事，使用者選 C「三項取二」但備註「以ad-2爲準」，所以判準照 ad-2：工具、腦、記憶差一軸就算不同，「誰叫它」不算。

## 代定（隊長替使用者做的小決定，每條可翻案）

1. `lineage` 只在出生（新路徑）時寫；`reason` 只有 `specialize`／`split`／`fix`／`manual`，拿掉 fable 的 `downgrade`；`promote` 不寫 lineage。為什麼：同一路徑換新版是版本歷史，git 與 `.prev/` 已經在管。翻案：要記版本血緣，就讓 `promote` 也寫一格 `lineage.prev`。
2. `lineage.from` 照 agents 工具的路徑規則存（相對 `$AOS_WS` 或絕對），不存「相對定義資料夾」；`defs check` 不要求它指得到。為什麼：親代退休或搬類別時，不會連帶讓子代的 check 變紅。翻案：改回相對定義資料夾，同時讓 check 也去 `retired/` 找。
3. `_metainfo.json` 的範例與範本照 evolve 已裁格式（`cost.time_ms`、`timeout_ms`）。翻案：跟著 evolve 那題一起翻。
4. 工具名叫 `defs`、放 `lib/aos/defs/`，不叫 `aos-defs`。為什麼：lib 工具名就是資料夾名，`aos-` 前綴是 `cmd/` 的指令。翻案：要給人在殼裡直接打，就另包一支 `cmd/aos-defs`。
5. 撞鑰匙改成 `suggest.differentiate`，只有 `same_duty: true` 才准 `merge_into`；`downgrade_stuck` 拿掉，改成 `split` 出生時記 lineage。為什麼：前者避免把做不同事的兩隻硬併；後者是因為帳裡算不出是哪一格錯，而且跟 evolve 的 `split` 重複。翻案：帳有了逐格內容摘要後，再把 `downgrade_stuck` 加回來。
6. 要被比對的 agent，記憶一律寫在 `tools/memory/_memory.json`、由 `interfaces.json` 宣告；`tools.json` 不再用 env 指 `AOS_MEMORY`。為什麼：一個地方宣告，比對才不必猜。翻案：讓 `defs` 也去讀 `tools.json` 的 env（要多認一種寫法）。
7. 退休前除了看帳裡的 `callers`，還要查 `defs refs` 的靜態引用。為什麼：帳只記得三輪內真的叫過的；有人在 `tools.json` 登記了它、只是這三輪沒叫到，搬走一樣會壞。翻案：只看帳，壞了靠下一輪審視發現。
8. 自動出生的實例照判官 `allowed: null` 放行；按定義路徑前綴放行留給判官的遠期（N-42 (2)），不交給 kernel-nest。翻案：要逐一列名的話，隊長在每次出生後補名單。
9. 搜尋用 `defs ls --match`，memory 只拿來一層層 `read`／`ls`。為什麼：memory 的 `find` 在定義樹裡會被 `.json` 雜訊塞滿 20 格。翻案：等 kb-scale 的 tag `find` 做好後，改用 `_tags.json`＋`find --tag`。
10. 「為什麼只有 3 隻」不當成缺陷處理：改進迴圈本來就在把 agent 變成腳本，要等新類別（人物、勢力）才會長出新的重複角色。翻案：你若要這一輪就看到更多隻，就在下一批先做人物類別，並照方向題 2 的 a 讓專員按記憶分化。
11. 定義資料夾名照 memory 段名規則 `[a-z0-9_-]+`（`defs check` 查）。為什麼：不照的話，memory 一層層往下翻時會看不到它（`children` 不列定址不到的名字）。翻案：memory 放寬段名（不足 #4 那題）。

## 落地順序（交 gpt 照圖施工，每步一句完成條件）

1～4 彼此獨立，可以並行。

1. **範本加記憶宣告**：`templates/agent-fsm/interfaces.json` 的 `aos-agent` 加 `"memory": "tools/memory/_memory.json"`；`templates/docs/02-agent-fsm.md` 補一句。完成條件：用 `aos-agent ctl add` 掛範本複本照常掛得上，範本既有 tests 全過。
2. **範本加 `_metainfo.json`**：內容 `{"summary": "<與 README 第一行同>", "cost": {"time_ms": 30000}, "resource": ["llm"]}`；README 第一行改成一句話說明。完成條件：`aos-exec` 跑範本的行為不變，`python3 -c 'import json;json.load(open("templates/agent-fsm/_metainfo.json"))'` 讀得過。
3. **`agents new` 寫 `lineage`**：`lib/agent/agents/_entry` 的 `new` 加選填參數 `reason`（`specialize`／`split`／`fix`／`manual`，預設 `manual`）與 `review`（字串）；寫完 `files` 後，把 `lineage: {from, reason, review?}` 併進新定義的 `_metainfo.json`（沒有就建），`from` 照參數原樣存；`_tooldef.json` 同步加參數說明。完成條件：用 `new` 從範本生一隻，新定義的 `_metainfo.json#/lineage/from` 等於傳入的 `from` 字串，`reason` 為 `manual`。
4. **新工具 `lib/aos/defs/`**：`_entry`（python）、`_tooldef.json`、`_metainfo.json`、README；子命令 `ls`（含 `--match`）／`dup`／`refs`／`check`，照「機制與資料格式 B」的輸出格式；路徑一律印成相對 defs 根；錯誤格式 `defs: error: <代號> <原因>`。完成條件：在 `tests/` 擺一棵四個定義的小樹（兩個三軸全同、一個在 `tools.json` 引用另一個、一個資料夾名有大寫），`ls` 印四行、`dup` 印一格兩個成員、`refs` 印出那個引用者、`check` 對大寫那個退 1。
5. **審視者 `suggest` 判準**（在 evolve-design 的 `templates/reviewer/` 裡改，排在 evolve 落地第 12 步之後）：設定加 `max_prompt_tokens_median: 10000`、`retire_after_cases: 3`；`specialize` 做 `repeated_child`、`context_too_big` 兩訊號，每條用 `defs ls --json` 填 `existing`；新增 `differentiate`（取 `defs dup`）；`retire` 加兄弟條件，填 `callers`、`refs`；`merge_into` 只在 `same_duty: true` 時填。完成條件：拿 arknights 三個地點的帳跑一次，`retire` 列出 `writer_places` 且 `siblings_called` 非空，`specialize` 每條都有 `existing` 欄（可為 null），`differentiate` 為空。
6. **`split` 出生記 lineage**（evolve 落地第 15 步放手之後）：審視者用 `split` 在副本生出新 LLM 步的定義時，帶 `reason: "split"` 與 `review`。完成條件：給一個可拆的假步驟，副本裡的新定義 `_metainfo.json#/lineage/reason` 是 `split`。
7. **隊長的處方頁**：在隊長讀得到的知識庫寫 `defs/README.md`，裡面一節「執行建議」：specialize 四步（讀 `proposal` → 查 `existing` → `agents new` 帶 `reason`／`review` → 更新類別 README）、retire 四步（照「機制與資料格式 E」），逐條寫出確切指令。完成條件：gpt 照這頁對一條假建議走完兩套步驟，過程中不需要判斷設計。
8. **試驗場驗證**（試驗場交 gpt，本夾不改試驗場）：把試驗場三隻活躍 agent 的記憶改由 `_memory.json`＋`interfaces.json` 宣告（代定 6），在試驗場 `defs/` 上跑 `defs dup` 與 `defs check`，把結果與 `runs/2/diversity.json` 的差別寫成一段，放進本 README 的「驗證」節。完成條件：README 有這一節，列出四隻有腦定義的三軸，`dup` 為空（opus 依現有檔手算：place_lead、linker、namer、writer_places 四隻的工具集各不相同，預期為空）。
9. **條文**（opus，不交 gpt）：五條概念待入 CONCEPTS；衝突 1、2、9、11 的改讀句；條號在 lift 時另編、避開 N-68／C-84。完成條件：wf-lint 綠。

## 同批其他題

- 改進迴圈、兩本帳、審視者、`promote`／watch、metainfo 評估、「改進過程本身也記錄、可被另一個 agent 改進」：交給 [evolve-design](../evolve-design/README.md)。本題只在它的 `suggest` 格裡補判準、多開 `differentiate` 一格，並讓 `split` 出生時記 lineage。專精 agent 的出生紀錄（`lineage`＋`review`）也是「改進過程」的一部分，審視者的審視者要算「哪些出生後來活下來」時，可以直接讀，怎麼用交給 evolve-design。
- 工具權限演進：交給 [tool-evolve](../tool-evolve/README.md)。它的 `extract`／`box`／`unshell` 會改定義的 `tools.json`，等於直接改了本題的工具軸：專精 agent 被抽出專屬工具後，自然就跟別隻不同質，這正是「獨特工具」最常見的來源。協調型 agent 停在開放期、專精 agent 走到全專屬工具，兩題的結論一致。
- 知識庫查詢、tag、`_tags.json`：交給 [kb-scale](../kb-scale/README.md)。
- 誰先用腦、llm kernel 嵌套排程：交給 [kernel-nest](../kernel-nest/README.md)。判官名單不在它的範圍（衝突 6）。

## opus 註

- fable 的條文引用都核對過了：C-46、C-52、C-56、C-65、C-68、C-78、C-79、C-83 的位置與意思都對。C-65 fable 轉述成「工作區只放交辦與成果」，原文是「工作區＝使用者的檔、成品要留的地方」，意思相同。兩處需要修正：一是判官名單錯交給 kernel-nest（衝突 6），二是 `_metainfo` 還用舊格式（衝突 10）。
- 試驗場 `agent_diversity` 的評語（量了 callers、model 量的是定義檔而非實際用的腦、從沒讀 prompt、兩兩比對、一對失敗兩隻都出局）見[簡報 §2.3](01-簡報.md)；fable 照單接受，設計已逐條處理。
