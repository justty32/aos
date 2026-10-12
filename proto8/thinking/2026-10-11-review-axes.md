← [thinking](README.md)｜Fable 九軸與可預測性落地，2026-10-11

# 九軸、人隨意加的標籤（traits）、可預測性、S 表示式——放進「一切都是資料夾」會長什麼樣

全篇是 AI（Fable）的提案，一條都沒定。依據順序：[10-11 討論 §2](2026-10-11-restart.md)（最高）→ [PLAN §2](../PLAN.md) → 九軸原文（repo 外 `~/repo/ai_core/docs/kb/kb-ss/doc_05_axes_metadata.md`）→ proto7 的 [axes-astra](../../proto7/notes/thinking/2026-10-04-axes-astra.md) 與 [r5](../../proto7/notes/thinking/2026-10-04-r5-synthesis.md)／[r6 綜合](../../proto7/notes/thinking/2026-10-04-r6-synthesis.md)（舊脈絡是 proto7-2，只借概念：「沒宣告＝未知、任務照跑」「第 9 軸拆成幾率性＋可預測性，後者只留定義」）→ 使用者 [9/19 草稿](../../thinking/2026-09-19.md)（「inst.json 應該加 `_meta`」——本篇的 `axes` 段就是那個 `_meta`）。

**一句話結論**：核心的 tick **一軸都不必認**（第一版連 `life` 都可以先當所有任務都是「每回合跑一次」）。九軸裡只有「需要什麼資源」真的有程式（排序器）在讀；其餘是給人和模型看的標籤，有兩軸（組合、環境）被這個世界直接填死了值，不必有鍵。可預測性不進 `task.json`，住在**觀察者自己的** `belief.json`。agent 的 S 表示式用一份 `steps.json`，節點可以指向資料夾。

## 0. 先把世界的規則擺出來（每一題都靠它）

- 計算任務＝一個有 `task.json` 的資料夾；tick 照 `.aos/order.json`（沒有就 ls 順序）起 `argv`，cwd＝該資料夾。
- 任務之間只靠「寫檔到對方 `in/`」講話，回覆落在對方 `out/`。
- 資源＝有 `capacity` 的任務；它**自己**一回合只處理 capacity 件，核心不管。
- 排序器＝一個任務，輸出 `.aos/order.json`。
- 這幾條把九軸裡好幾軸的「值」寫死了：通道一定是檔案、環境一定是自己的資料夾、組合一定是資料夾樹。**軸沒有消失，是世界替你填了值**——所以有些軸不需要鍵。

## 1. 九軸逐軸：誰讀

### 1.1 一張表

| # | 軸（原文） | 鍵 | 可能的值（白話） | 誰讀 | 沒寫時當作 |
|---|---|---|---|---|---|
| 2 | 生命週期 | `life` | `round`＝每回合起一次、回合內就退出；`long`＝一跑好幾回合才結束；`service`＝常駐不結束 | **tick**（tock 等不等它退出）、排序器（service 不算排隊） | `round` |
| 4 | 資源（需求側） | `needs` | `[]`＝不用 aos 層的資源；`["llm"]`；`["llm","human"]`。值是**資源種類名**，對應某個資源資料夾 `provides` 的值 | **排序器** | `[]` |
| 4 | 資源（供給側） | `provides`、`capacity` | `provides: "llm"`；`capacity: 1`＝一回合只處理一件。**有 `capacity` 的任務就是資源**——這正是 §2.7 的定義「有限的處理能力」 | **排序器** | 不是資源 |
| 9 | 確定性 | `determinism` | `fixed`＝同輸入同輸出；`random`＝有亂數或有模型；`external`＝看外面的東西（時鐘、網路），結果跟什麼時候跑有關 | 數節點的工具、人、模型；排序器之後才讀（重跑有沒有意義） | `unknown` |
| 6 | 執行保證 | `rerun` | `same`＝重跑結果一樣（冪等）；`adds`＝每跑一次多一份效果；`all_or_nothing`＝要嘛全做要嘛沒做 | 想重試的人（v1 沒人） | `unknown` |
| 5 | 可中斷性 | `kill` | `safe`＝隨便殺，重跑就好；`resume`＝殺了下次接得上；`unsafe`＝殺了會留半成品 | 想殺行程的人（v1 沒人；之後是排序器自己照 `procs.json` 的 pid 送 TERM，不經核心） | `unknown` |
| 3 | 跨呼叫狀態 | `state` | `none`＝每次從頭；`own_folder`＝記在自己資料夾（zip 帶得走、`cp -r` 會連著複製）；`outside`＝記在世界外（DB、別的服務；zip 帶不走） | 打包／複製的人 | `own_folder` |
| 1 | I/O 型態 | `io` | `files`＝只碰 in/ out/；`network`＝還會上網；`stream`＝邊跑邊寫 out/（通常跟 service 一起出現） | 人、模型 | `files` |
| 8 | 環境 | `reach` | `self`＝只看自己資料夾；`world`＝會讀別人的資料夾；`outside`＝碰世界外（家目錄、網路） | 人、模型 | `self` |
| 7 | 組合 | （無鍵） | 值就是資料夾樹＋`steps.json`：有 `steps.json` 的任務是 S 表示式，沒有的是葉子 | 數節點的工具 | 葉子 |

值用英文是為了跟 `argv` 等鍵同一種字；核心不解析任何一個值，寫中文（`"每回合"`）一樣能跑，純屬口味。

兩軸的註解：
- **1 與 8 在這個世界幾乎重疊**（都是「它伸手摸到多遠」）。原文 1 問「水管接哪」、8 問「跑在哪」；這裡水管一定接 in/ out/、一定跑在自己資料夾，剩下的差別只有「有沒有往外伸」。留兩個鍵是為了跟原文對得上；嫌多就只留 `reach`。
- **原文的 1b「互動式（中途停下來問人）」在這個世界變成了 batch**：agent 要問人＝寫檔到 `human/in/`、退出、下回合再讀——每一次 run 都是一次性的。所以 `io` 幾乎永遠是 `files`。這是世界替你消掉的一個麻煩。
- **`rerun` 對 `life: round` 的任務其實是必然的**：tick 每回合都會再起它，不能重跑的任務在這世界活不下去。所以這一軸對 round 任務是文件、對 long／service 才是資訊。

### 1.2 tick 真的要讀幾軸

比你猜的還少：**一軸（`life`），而且第一版零軸。**

- `life` 是 tick 唯一有理由讀的：tock 要等「這回合會結束的」退出，就得知道誰會結束。但 PLAN 第 2～4 步裡所有任務——echo、painter、llm、scheduler——全是 `round`。沒有 service 之前，「等所有起過的行程退出、或到期限」跟「全部當 round」是同一件事。等第一個 service 出現再讓 tick 讀這一軸。
- **`needs` 不必 tick 讀**。資源自己限流（llm/ 一回合處理一件，多的留在 `llm/in/` 排隊），排序器決定先後；tick 就算照 ls 順序全部起，也只是慢，不會壞。tick 不分配資源，就不需要知道誰要什麼。這跟 PLAN §8 第三點「資源的 capacity 誰管：資源自己」一致。
- 其他七軸 tick 都不碰。tick 也**不殺行程**（到期限只在 `procs.json` 記「還在跑」，下回合 skip），所以 `kill` 軸不是它的事。要殺是排序器的規則，它拿 pid 自己殺。

### 1.3 排序器讀幾軸

v1（PLAN 第 4 步手寫 30 行）讀：`needs`、`provides`、`capacity`，再加上兩個**事實**——`ls */in/ | wc -l`（誰的隊列長）與 `.aos/procs.json`（誰還在跑）。`life` 用來把 service 排除在「排隊」之外。`determinism`／`rerun`／`kill` 等排序器開始做「重跑」「殺卡住的」才讀。

一個縫，先記著：`needs` 是**預告**，`llm/in/` 裡的檔案數是**事實**。agent 若自己直接寫到 `llm/in/`，排序器就沒機會把它導去便宜的 `llm-local/`。日記裡「兩個 llm 資源，便宜的優先」要成立，寫請求那一步得由排序器決定目的地（例如 agent 寫 `{"to": "llm"}` 到自己 `out/`，排序器搬）。這題第 3 步真跑時再定，不影響本篇。

### 1.4 樣本

agent 的 `task.json`：

```json
{
  "argv": ["python3", "run.py"],
  "axes": {
    "life": "round",
    "needs": ["llm"],
    "determinism": "random",
    "rerun": "same",
    "kill": "safe",
    "state": "own_folder",
    "io": "files",
    "reach": "world"
  },
  "traits": {"good_at": ["人物"], "bad_at": ["風景"]}
}
```

資源的 `task.json`（`provides`／`capacity` 也放 `axes`：它們就是第 4 軸的供給側）：

```json
{
  "argv": ["python3", "serve.py"],
  "axes": {
    "life": "round",
    "provides": "llm",
    "capacity": 1,
    "determinism": "random",
    "io": "network",
    "reach": "outside"
  },
  "traits": {"model": "luna", "cost": "便宜"}
}
```

### 1.5 結論

| 讀者 | 讀哪幾軸 |
|---|---|
| tick | `life`（v1 零軸） |
| 排序器 | `needs`、`provides`、`capacity`；`life` 排除 service；之後 `determinism`／`rerun`／`kill` |
| 打包／複製的人 | `state` |
| 人、模型 | 全部，尤其 `io`、`reach`、`determinism` |
| 沒有人 | 第 7 軸——它是資料夾樹本身 |

## 2. traits：要不要結構

結論：**純自由 JSON，零結構，核心永遠不讀。** traits 就是「人隨意加的標籤」（§2.9 原話「可以隨意定義」），不是要刻意經營的東西，所以也不該為它設計格式。 分界線一句話：**程式驗得出來的是軸（白名單裡那幾個鍵），只能靠判斷的是 trait。**「這個任務在繪畫上偏現代性」沒有程式驗得出來，所以它是 trait；「一回合內會退出」驗得出來，所以是軸。

排序器怎麼用它而不知道鍵名？三種，由笨到聰明：

1. **字包比對**：把 traits 攤平成一袋字（鍵、值、列表元素都當字），請求檔（`{"want":"風景","style":"現代"}`）也攤成一袋字，交集多的優先。不用知道任何鍵名。缺點：`bad_at: ["風景"]` 跟 `want: "風景"` 也會交集——字包看不懂「不擅長」。
2. **排序器自己認極少數鍵**：手寫排序器若想認 `bad_at` 是減分，寫在**排序器的 README**，不寫在核心、不叫 traits 的結構。這是排序器的規則。
3. **問模型**：把 `task.json` 的 traits 和請求檔原樣貼給模型，問「這件派給誰」。這就是 §2.9 說的「之後會有一大堆東西，所以才需要大語言模型」。PLAN 第 4 步第二版（模型生成的排序器）天然走這條。

兩個約定（不算結構，是讓 1 攤得開）：
- traits 的值用字串或字串列表，不巢狀。
- traits 裡不放核心或排序器要拿去「計算」的數字。`priority` 若要有，它是排序器自己認的鍵（做法 2）；PLAN 樣本把它塞進 traits 可以，但要記得那是排序器的約定，不是任務的屬性——「重要」是別人對它的看法，跟 §3 的可預測性一樣有主體性。

請求檔也是自由 JSON，兩邊都自由，**配對是觀察者的判斷**。這跟 §3 是同一件事的兩面。

## 3. 可預測性：住哪、長怎樣、誰寫、怎麼更新

### 3.1 住哪

住在**觀察者自己的資料夾**，檔名 `belief.json`：

- 排序器 → `scheduler/belief.json`
- 使用者 → `human/belief.json`（`human/` 本來就是你在這個世界裡的座位——日記裡它整天沒出場，這就是它的一個用途）
- 另一個 agent → `painter-b/belief.json`

不進 `task.json`：`task.json` 是任務自己（作者）的宣稱，`belief.json` 是別人對它的認識。同一個任務在三份 belief.json 裡可以有三種分數——這就是 §2.14 的主體性，用檔案位置表達，不用欄位表達。

### 3.2 長怎樣

```json
{
  "painter-a": {
    "expect": {"rounds": 3, "llm_calls": 1, "quality": "人物好、風景差"},
    "seen": 12,
    "hit": 9,
    "since_version": "a1b2c3d",
    "last_round": 1990,
    "note": "10-12 把第一步換成程式後變準了"
  },
  "llm": {
    "expect": {"rounds": 1},
    "seen": 40,
    "hit": 40,
    "since_version": "9f8e7d6",
    "last_round": 1990
  }
}
```

- 鍵＝任務資料夾名（資源也是任務，所以 `llm` 也在裡面）。
- `expect`：我預期它會怎樣——**自由 JSON，用觀察者自己的話**。排序器寫數字，你寫形容詞，agent 寫什麼都行。
- `seen`／`hit`：看了幾次、幾次跟預期一樣。**可預測性＝`hit/seen`，算出來的，不存**。存兩個計數而不存比率，是為了能繼續累加。
- `since_version`：這些經驗是對哪一版任務累積的（`task.json`＋`steps.json` 的 sha 前七碼）。
- **沒有條目＝不知道**。不預設 0、不預設 1。

### 3.3 誰寫

只有觀察者寫自己的 belief.json。排序器的 run.py 每回合寫；你用 vim 寫；agent 在它 steps.json 裡的某一步寫。核心不讀不寫。

### 3.4 更新規則（三行）

1. **每次看到結果**：把上次寫的 `expect` 跟實際比（out/ 的檔、用了幾回合、`llm/out/usage.json` 裡幾次呼叫）。像 → `hit+1, seen+1`；不像 → 只 `seen+1`，並把 `expect` 改成這次看到的。
2. **任務換版**（sha 跟 `since_version` 不同）→ `seen`、`hit` 歸零，`expect` 留著當第一個猜測。
3. **「像不像」怎麼判是觀察者自己的事**：排序器比數字、你用眼睛、agent 問模型。格式不規定這一步——這一步正是主體性所在，規定了就不是「認識」而是「屬性」了。

沒經驗時的第一個 `expect` 可以從 §4 數出來的「幾個節點是模型」來：三節點一模型 → 預期「大致可預測」；三節點三模型 → 預期「別信」。那是客觀數字給主觀信念的**種子**，不是信念本身。

### 3.5 同一套格式三個觀察者都能用嗎

**能。** 格式裡沒有任何觀察者專屬的欄位；差別只在 `expect` 的用語和「像不像」怎麼判，而這兩樣本來就該各自不同。副產品：三份 belief.json 可以互相 `cat`——排序器可以把你的 `human/belief.json` 當一條規則讀（「使用者說它風景差，就別派風景」）。那是排序器**讀別人的信念**，格式不用為它多做什麼。

兩個邊緣：
- 它**不會長成垃圾**：每個任務一條、就地覆寫，不累積歷史（你 10-04 的要求）。要歷史的人自己做 module。
- `task.json` 說 `determinism: fixed` 但其實偷看時鐘 → belief.json 的 hit 率會掉。宣稱和經驗分兩個檔，就是為了這種時候兩邊對得起來、看得出誰說謊。

## 4. S 表示式在磁碟上

### 4.1 `steps.json`（提案）

```json
[
  {"id": "understand", "argv": ["python3", "understand.py"]},
  {"id": "draw",       "call": "llm", "prompt": "prompts/draw.md"},
  {"id": "save",       "argv": ["python3", "save.py"]}
]
```

兩種節點：
- **`argv`**：程式節點。run.py 當下 spawn 它、等它退出，同一回合內完成。它是一個 POSIX 子行程，只是不在 tick 的名單上。
- **`call`**：交給世界裡另一個資料夾處理。寫一個請求到 `<call>/in/`、退出；下回合回覆到了才往前走。`call: "llm"` 就是模型節點；`call: "./tools/ocr"` 可以是一個子資料夾裡的程式任務，甚至另一個 agent。

**一句話執行規則**：run.py 每回合讀 `state.json` 的 `pc`，該步是 `argv` 就跑完、`pc+1`、接著下一步；是 `call` 就寫請求到那個資料夾的 `in/` 然後退出，下回合看到回覆才 `pc+1`；走到底把結果寫 `out/`、`pc` 歸零。步與步之間傳資料全靠 `state.json`（程式讀寫它，提示詞把它貼進去）。

三個要求怎麼達到：
- **每個節點是一個計算任務**：`call` 節點字面成立（目標是有 task.json 的資料夾）；`argv` 節點是子行程，是 POSIX 行程、不是世界裡的資料夾任務——差這一點，見 §6。
- **模型節點與程式節點可互換**：把 `{"call":"llm","prompt":"prompts/understand.md"}` 換成 `{"argv":["python3","understand.py"]}`，其他步不動、`state.json` 欄位不變。反過來也行。日記裡「我把第一步換掉」就是這一行。
- **能數出幾個是模型**：`grep -c '"call": *"llm"' steps.json`。一般化的定義：節點的目標資料夾 `task.json` 寫 `determinism: random` 就算模型節點。v1 用 grep。

### 4.2 更簡單的表示：節點就是子資料夾

```
painter-a/
├── task.json
├── state.json
└── steps/
    ├── 1-understand/task.json     {"argv": [...]}
    ├── 2-draw/task.json           {"call": "llm", "prompt": "..."}   ← 換成 argv 就是程式節點
    └── 3-save/task.json
```

run.py 每回合看哪個 step 的 `out/` 有結果，起下一個。

| | `steps.json` | 節點＝子資料夾 |
|---|---|---|
| 「每個節點是一個計算任務」 | `argv` 節點是子行程，不是世界裡的任務；`call` 節點才是 | 字面成立：每個節點都是有 task.json 的資料夾 |
| 一眼看完 | `cat steps.json` 一屏 | `ls steps/` 看順序，再 cat 三份 |
| 換節點 | 改一行 | 改那個資料夾的 task.json，別處不動 |
| 數模型節點 | 一行 grep | `grep -l llm steps/*/task.json \| wc -l` |
| 巢狀（一步本身是個 agent） | 用 `call: "./sub"` 指到子資料夾——其實就變成右邊 | 天然 |
| 每步有自己的 in/ out/ 歷史 | 沒有（混在 state.json） | 有；代價是**檔案多三倍**（你 10-04：垃圾要清） |
| 插一步 | 列表中間插一筆 | 改編號 |
| tick 要不要認它 | 不用 | 不用（run.py 自己起子任務）；但會很誘人想讓 tick 遞迴掃子資料夾——忍住，那是核心加功能 |

**結論：v1 用 `steps.json`**，理由是檔案少、一屏看完、PLAN 第 5 步只要數節點。把 `call` 設計成「指向資料夾」就留了後門：哪一步大到要自己的 in/ out/、或本身是個 agent，就把它搬成子資料夾、寫 `call: "./steps/draw"`。**兩種表示其實是同一種**——`steps.json` 寫順序，重的節點才落地成資料夾。

### 4.3 兩個數字，不只一個

§2.16 說的是「進入可預測性不高的節點的**可能性**降低」。真正拉低可預測性的是**模型節點有沒有決定下一步走哪**。
- 數字一：模型節點數／總節點數。v1 做這個。
- 數字二：能改 `pc` 的模型節點數（它的輸出決定分支）。v1 的 steps.json 是直線、沒分支，數字二恆為 0。之後若允許某步往 `state.json` 寫 `next` 跳步，就要分開數——一個會選路的模型節點，比三個只會填空的更難預測。

## 5. 第一版完全不做、只留鍵名佔位

| 題 | v1 做 | v1 不做、只留鍵 |
|---|---|---|
| 1 九軸 | tick：**零軸**（全部當 `round`）。排序器：`needs`、`provides`、`capacity`＋`ls */in/`＋`procs.json` | `life` 等第一個 service 出現才讀；`determinism`、`rerun`、`kill`、`state`、`io`、`reach` 寫在 task.json 裡沒程式讀；第 7 軸連鍵都不給 |
| 2 traits | 自由 JSON；排序器第一版頂多認 `bad_at` 一個鍵（寫在它的 README） | 字包比對、問模型（第二版排序器才做） |
| 3 belief.json | **不寫程式**。你想寫就手寫 `human/belief.json`，零程式 | 排序器自動更新、`since_version` 校驗、觀察者互讀 |
| 4 steps.json | PLAN 第 5 步：`argv`＋`call: "llm"` 兩種節點、直線、`grep -c` 數 | `call` 指子資料夾、分支、數字二、節點＝子資料夾 |

佔位的規矩：鍵寫出來、值照預設填或寫 `"unknown"`，**不寫程式讀它**。等某支程式真的要讀某個鍵，去 thinking/ 補一句為什麼再動。這樣做符合「沒宣告＝未知、任務照跑」，也符合煞車第 3 條（第三句寫不出來就不做）。

## 6. 我不確定的

1. **`needs` 預告 vs `in/` 事實**（§1.3 的縫）。若 agent 永遠自己挑資源資料夾寫，`needs` 可能一直只是標籤，排序器看隊列就夠。真跑第 3 步才知道。
2. **`argv` 節點不在 tick 名單上**，跟「一切都是計算任務」差一點。我認為可以（它是子行程、是 POSIX）；若你覺得字面要成立，走 §4.2 子資料夾，代價是檔案數。
3. **belief.json 的「像不像」留給觀察者**，意思是排序器第一版還是得手寫一個比法——比回合數最簡單；比品質只能問模型或問你。所以 v1 不寫它是對的，但第二版排序器一碰到「誰畫得好」就會回來要這個檔。
