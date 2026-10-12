← [thinking](README.md)｜Fable 排序器可由模型生成：實驗設計，2026-10-11

依據：[restart](2026-10-11-restart.md) §2.3（畫家）、§2.7（排序＝分配哪個任務先給哪個資源）、§2.10（排序程式可由模型生成）；[PLAN](../PLAN.md) §2～§4。方法借 [menu-ab](../../proto7-2/notes/play/2026-10-10-menu-ab/README.md)（判準跑之前寫死、同題跑 5 次看雜訊）與 [apprentice-5](../../proto7-2/notes/play/2026-10-09-real-ai/apprentice-5.md)（差距要大於雜訊才算），不搬它們的機制。

**一句話**：三個畫家世界、一份 7 行的 goal.md、一個只有兩個鍵的 order.json；手寫 30 行排序器先寫出標準答案，再讓 luna 照同一批 `ls`＋`cat` 寫一版，`diff` 三個場景的 order.json。全程離線、不起 tick、約 15 次呼叫、3～4 萬 token。

**跟 PLAN 不同的一處，要你拍板**：PLAN §2 把需求放在 `painter-a/in/` 裡；這裡把**每件需求也做成一個資料夾**（`req-01/task.json`）。理由：排序器只需要讀一種檔（`*/task.json`），介面最小；也剛好符合 §2.8「一切都是計算任務」——需求本身就是待排的計算任務，畫家是帶 `capacity` 的計算任務。

## 1. 排序器的介面

**執行**：在世界根目錄 `python3 scheduler/run.py`。根目錄取環境變數 `AOS_ROOT`，沒有就用目前目錄（這一行是日後接 tick 唯一要對的地方）。

**讀**：`<根>/*/task.json`，每個資料夾一份。只看這幾個鍵：

| 誰 | 怎麼認 | 鍵 |
|---|---|---|
| 資源（畫家） | 有 `capacity` | `serves`（字串）、`capacity`（整數）、`traits.good_at`（列表，可缺）、`traits.bad_at`（列表，可缺） |
| 任務（需求） | 有 `needs` | `needs`（字串）、`traits.want`（字串）、`traits.urgent`（布林，可缺） |
| 其他（scheduler 自己、`.aos/`） | 兩者都沒有／點開頭 | 不管 |

```json
// painter-a/task.json
{"serves": "paint", "capacity": 4, "traits": {"good_at": ["人物"], "bad_at": ["風景"]}}
// req-02/task.json
{"needs": "paint", "traits": {"want": "風景"}}
// req-03/task.json
{"needs": "paint", "traits": {"want": "人物", "urgent": true}}
```

**目標**：`scheduler/goal.md`，白話 7 行，手寫版和生成版都照它寫（這就是 §2.10「跟模型說幫我生成一個處理繪畫任務的排序」的那句話，寫成檔）：

```
# 這個世界的排序目標
把每件任務分給一個資源，這回合就開工。
1. 只配 needs 跟資源 serves 相同的。
2. 每個資源最多拿 capacity 件。
3. 任務的 want 在資源 good_at 裡 → 優先給它。在 bad_at 裡 → 不給。
   都不在 → 可以給，但要等所有能配到 good_at 的都配完之後。
4. 任務先後：urgent 的先，其餘照資料夾名字。有多個資源可選時照資源名字。
5. 配不到的放 wait。
```

**寫**：`<根>/.aos/order.json`，只有兩個鍵。`assign` 列出**每個**資源（沒拿到也列空陣列），陣列內是做的先後；`wait` 照名字排。

```json
{"assign": {"painter-a": ["req-03", "req-01"], "painter-b": ["req-05"]},
 "wait": ["req-02", "req-04"]}
```

**為什麼介面能這麼小**：第 4 條的「照名字」把平手全消掉，所以每個世界只有**唯一一個**正確的 order.json，判勝負就是 `diff`，不用人看半天。這是這份設計最重要的一招。

## 2. 試題（三個場景，答案先手算好、跑之前寫進 `expected.json`）

兩個畫家照 §2.3 設：painter-a 擅長人物、不擅風景、一週能畫三四張；painter-b 擅長風景、很忙、一週只接一單。

### S1「各歸其位」—— 最基本

- painter-a：`capacity 4`，good_at 人物，bad_at 風景
- painter-b：`capacity 1`，good_at 風景
- req-01 人物、req-02 風景、req-03 人物、req-04 人物、req-05 風景

```json
{"assign": {"painter-a": ["req-01", "req-03", "req-04"], "painter-b": ["req-02"]}, "wait": ["req-05"]}
```

一眼看得出：三張人物全給 a；b 只接一張，拿名字最前的風景；最後一張風景 b 滿了、a 不畫風景 → 等。**a 還剩一格卻空著**，這格是 §4 換目標的伏筆。

### S2「新人撿剩」—— 多一個沒標籤的資源（提示裡沒出現過）

- painter-a：`capacity 3`，good_at 人物，bad_at 風景
- painter-b：`capacity 1`，good_at 風景
- painter-c：`capacity 2`，沒有 traits（新人，什麼都不擅長也不排斥）
- req-01 人物、req-02 風景、req-03 人物、req-04 風景、req-05 人物、req-06 風景、req-07 人物

```json
{"assign": {"painter-a": ["req-01", "req-03", "req-05"], "painter-b": ["req-02"], "painter-c": ["req-04", "req-06"]}, "wait": ["req-07"]}
```

一眼看得出：a 填滿三張人物、b 一張風景；剩下 04 風、06 風、07 人，新人 c 照名字撿前兩件；07 沒人有空 → 等。測的是 goal 第 3 條「都不在 → 可以給但排後面」這個分支，S1 的檔案裡沒有這種資源。

### S3「急件」—— 順序開始有意義

- painter-a：`capacity 2`，good_at 人物，bad_at 風景
- painter-b：`capacity 1`，good_at 風景
- req-01 人物、req-02 人物、req-03 人物 **urgent**、req-04 風景、req-05 風景 **urgent**

```json
{"assign": {"painter-a": ["req-03", "req-01"], "painter-b": ["req-05"]}, "wait": ["req-02", "req-04"]}
```

一眼看得出：急件先，所以 a 的陣列是 `[03, 01]` 不是 `[01, 03]`；b 唯一一格給急的風景。S1 的檔案裡沒有 `urgent`，只有 goal.md 提到。

### 換目標（第四題，不是新場景）

把 goal.md 第 3 條的「在 bad_at 裡 → 不給」改成「在 bad_at 裡 → 最後才給（都不在的也配完之後）」，其他不動。重跑 S1：

```json
{"assign": {"painter-a": ["req-01", "req-03", "req-04", "req-05"], "painter-b": ["req-02"]}, "wait": []}
```

S2、S3 的答案不變（a 本來就滿）。這題直接測 §2.1「任意目標」：同一個世界、目標改一句、排序器該跟著變。

**手算答案要有第二個人**：三個場景的 `expected.json` 由我（AI）照 goal.md 獨立算一次、你再算一次，兩邊一致才開跑。不一致＝goal.md 有歧義，先改字，不開跑（這是 §6 第一個失敗點的事前防線）。

## 3. 給模型的輸入

**只給檔案夠不夠**：不夠，差兩樣——輸出長什麼樣（它猜不到 `assign`／`wait` 兩個鍵）、怎麼認資源和任務（不講的話它可能用資料夾名 `painter-` 判斷）。所以餵：S1 的 `ls`＋`cat`（包含 goal.md）＋ 6 行規矩 ＋ 1 個 order.json 樣本（用一個小到不是答案的示意）。**不給 S2、S3 的檔案**——它得照 goal.md 把 urgent 和無標籤資源寫對，這正是「換場景還對不對」要測的。

提示草稿（38 行，直接餵，不帶 system prompt）：

```
你要寫一個排序器。下面是一個資料夾（世界）的 ls 與 cat 結果。

$ ls
.aos  painter-a  painter-b  req-01  req-02  req-03  req-04  req-05  scheduler
$ cat painter-a/task.json
{"serves": "paint", "capacity": 4, "traits": {"good_at": ["人物"], "bad_at": ["風景"]}}
$ cat painter-b/task.json
{"serves": "paint", "capacity": 1, "traits": {"good_at": ["風景"]}}
$ cat req-01/task.json
{"needs": "paint", "traits": {"want": "人物"}}
$ cat req-02/task.json
{"needs": "paint", "traits": {"want": "風景"}}
$ cat req-03/task.json
{"needs": "paint", "traits": {"want": "人物"}}
$ cat req-04/task.json
{"needs": "paint", "traits": {"want": "人物"}}
$ cat req-05/task.json
{"needs": "paint", "traits": {"want": "風景"}}
$ cat scheduler/task.json
{"argv": ["python3", "run.py"]}
$ cat scheduler/goal.md
（goal.md 全文 7 行，照 §1 貼）

規矩：
- 有 capacity 的資料夾是資源，有 needs 的是任務，其他資料夾不管。
- 任務的 traits 可能有 "urgent": true；資源的 traits、good_at、bad_at 都可能缺。
- 寫 .aos/order.json，長這樣（只是示意格式，不是這個世界的答案）：
  {"assign": {"painter-a": ["req-01"], "painter-b": []}, "wait": ["req-02"]}
  assign 要列出每個資源（沒拿到也列空陣列），陣列內是做的先後；wait 照名字排。

請寫 scheduler/run.py：Python 3、只用標準庫、不超過 40 行。
根目錄取環境變數 AOS_ROOT，沒有就用目前目錄。
不要寫死任何資料夾名字或標籤值——換一個世界（別的畫家、別的標籤）也要能跑。
只回程式碼，不要解釋，不要 markdown 圍欄，第一行就是 import。
```

換目標那題：同一份提示，只換 goal.md 那 7 行，其他一字不改。

## 4. 判準（跑之前寫死）

每一份生成的 run.py 看四樣：

| 判準 | 怎麼量 | 過的門檻 |
|---|---|---|
| ① 順序對 | 在 S1、S2、S3 三個世界各跑一次，`python3 -m json.tool --sort-keys .aos/order.json` 和 `expected.json` 做 `diff` | 3/3 空 diff。一字不同就是錯；crash／沒寫檔／多鍵少鍵都算錯，但分開記類別 |
| ② 行數 | 去空行後 `wc -l` | 手寫版 ≤ 30；生成版 ≤ 手寫版 × 2 |
| ③ 人看得懂 | 你讀生成版 1 分鐘，指出「哪一行在做 bad_at 不給」；另外 `grep -c "painter-\|風景\|人物" run.py` | 指得出來；grep 為 0（沒把世界寫死） |
| ④ 換目標 | 用改過的 goal.md 再生成一版，跑 S1（新答案）、S2、S3（舊答案） | 3/3 空 diff |

**雜訊怎麼量**（照 menu-ab）：同一份提示對 luna 跑 **5 次**（temperature 預設，不調），記每次 ①的通過數（0～3）。5 次的分散就是雜訊；失敗的分三類記：crash／格式錯（鍵不對、陣列順序）／邏輯錯（配錯人）。

**結論怎麼下**：

- **成立**：5 次裡 ≥ 3 次 ① 3/3 **一次就過**（不重問），且這些通過版 ③ 都過，且 ④ 至少 1 次 3/3。意思是：給模型看檔案和 7 行目標，它多數時候能直接寫出對的排序器，而且目標改一句它跟著改。
- **半成立**：1～2 次 3/3，或 ① 過但 ③ 不過（寫死了世界）。意思是：可生成但不穩，第二輪得加「跑一次給它看 diff、重問一輪」的機制——那是另一個實驗，這輪不做。
- **不成立**：0/5。先看失敗類別——5 次**同一種**邏輯錯（例如全都把 bad_at 當成「排最後」）＝goal.md 寫得有歧義，是提示的錯不是模型的錯，改字重跑一輪；5 次錯法**各不相同**＝luna 寫不出來，拿 sol-low 再跑 5 次當對照：sol ≥ 3/5 → 「模型等級問題，luna 不夠」；sol 也 0/5 → 這個介面對模型不友善，回頭改介面。

**手寫版不是用來贏的**，它的用途有三：先產 `expected.json` 的對照（手算與手寫版輸出要一致）、給②一個基準行數、證明 30 行寫得完（介面夠小的證據）。真正的勝負是生成版對 `expected.json`。

## 5. 一輪要花多少

| 項 | 次數 | 每次約 token（進＋出） | 小計 |
|---|---|---|---|
| luna 原目標 | 5 | 1,500 ＋ 700 | 11k |
| luna 換目標 | 5 | 1,500 ＋ 700 | 11k |
| sol-low 對照（只在 luna 0/5 時） | 5 | 同上 | 11k |
| 合計 | 10～15 次 | | **2～3.5 萬** |

PLAN §4 的上限是每步 5 萬，夠。提示本身約 1,200 token（七個 task.json 很短、goal 7 行、規矩 6 行），回覆是 40 行 Python 約 600～800 token。沒有重問、沒有審查、沒有第二關——一次呼叫就是一份排序器。呼叫方式：直接 `curl` LiteLLM 一次拿 `usage`，不經任何 aos 的東西；menu-ab 一題要 20～30 次呼叫、每題 4～8 萬，這裡一份排序器只要 1 次、2k。

**luna 夠不夠**：應該夠，但這正是要量的。menu-ab 裡 luna 在有檢查器重問的情況下 4/5 寫得出幾十行工具；apprentice-5 顯示 luna 一次過的機率不高（第 1 題 0/6 一次過）但那題有藏起來的慣例、要猜。這裡沒有藏的東西，全在 goal.md 裡，所以我預期 luna 3～5/5；若低於 3，sol-low 那 5 次就是分辨「題目難」還是「模型弱」的對照。

## 6. 最可能失敗的三個地方

1. **goal.md 有兩種讀法**（例如「都不在 → 可以給」被讀成「跟 good_at 同等」）→ 兩個人各自照 goal.md 手算 `expected.json`，不一致就先改字；第 4 條的「照名字」平手規則一定要在，否則答案不唯一、`diff` 判不了。
2. **格式漂移**——模型把 order.json 寫成 `[["req-01","painter-a"], …]` 或少列空陣列的資源，邏輯全對卻 diff 不過 → 提示裡給一份示意樣本並明說「每個資源都要列、沒拿到也列空陣列」；判準把格式錯和邏輯錯分開記，格式錯多就是提示沒講清，不算模型寫不出排序。
3. **把 S1 寫死**——程式裡出現 `"painter-a"`、`"風景"`，或用資料夾名開頭判斷誰是資源 → 提示明說「不要寫死、換世界也要能跑」，判準③用 grep 擋，S2 的 painter-c 和 S3 的 urgent 都是 S1 檔案裡沒有的東西，寫死的版本一定在那兩題倒。

小的還有：模型回覆帶 markdown 圍欄或解釋文字（提示最後一行擋，判準容許剝圍欄一次、記一筆）；用了 Python 3.11 以上才有的語法（本機 Python 版本先寫在紀錄裡）。

## 7. 核心要先有什麼？

**什麼都不用。** 這個實驗完全離線：

```sh
$ cd world-S1 && python3 scheduler/run.py && cat .aos/order.json
$ diff <(python3 -m json.tool --sort-keys .aos/order.json) expected.json
```

不起 tick、不要 `llm/` 資源資料夾、不要 `procs.json`。模型那一次呼叫由人手動 `curl`，不經世界。排序器和 tick 的唯一接點是「`AOS_ROOT` 沒有就用目前目錄」那一行，日後 tick 以 `cwd=scheduler/`＋`AOS_ROOT=<根>` 起它，程式一字不改。

**由此建議 PLAN §4 的順序調一下**：第 4 步可以挪到第 2 步之前先做（或跟第 2 步同時）。它測的是 §2.10 這條最大膽的主張，又最便宜、最不依賴核心；tick（第 2 步）和 `llm/` 資源（第 3 步）做完之後，只是把這個已經驗過的 `scheduler/` 放進世界、`order.json` 從「人 cat 看」變成「tick 讀」。排序器本身的對錯不會因為 tick 存在而改變。

反過來，這個實驗會替 PLAN 先定下三件事（都還是提案、要你拍板）：需求是資料夾不是 `in/` 的檔；資源和任務靠 `capacity`／`needs` 認、不靠名字；`order.json` 是 `assign`＋`wait` 兩個鍵。第 2 步的 tick 讀 `order.json` 時就照這個形狀。

## 8. 做的順序（一個下午）

1. 手建三個世界資料夾＋goal.md（都是 JSON 小檔，用 `mkdir`／`echo` 就好）。
2. 我和你各自照 goal.md 手算三份 `expected.json`，對一次。
3. 我手寫 run.py（≤ 30 行），跑三個世界，輸出必須等於 `expected.json`——不等就是 goal.md 或 expected 錯，回第 2 步。
4. 提示定稿，`curl` luna 5 次，每次存回覆成 `gen-1.py`～`gen-5.py`，各跑三個世界、記表。
5. 改 goal.md 一句，再 5 次。
6. 照 §4 下結論，表和原始回覆存在這份旁邊的 `evidence/`（之後再開，這輪沒有）。

這輪**不做**：重問機制、審查模型、多個目標、多種資源、tick 接線、belief.json。做完結論只回答一句：「給模型看檔案和一段白話目標，它寫得出對的排序器嗎？」
