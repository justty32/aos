# galtxt-a 第一輪規劃：由上而下拆資料夾樹（fable，2026-10-25）

← 題目與使用者原文：[thinking 2026-10-25-top-down](../../../thinking/2026-10-25-top-down.md)｜依據：[CONCEPTS](../../../CONCEPTS.md)（C-52 每層只管自己、C-56 KISS、C-61 工具是資料夾程式、C-65～C-67 stack 與工作區、C-68 資料夾＝程式）、[NORMS/10](../../../NORMS/10-基礎設施-定義與工作區.md)（N-50、N-53、N-57～N-61）、[CONVENTION](../../../CONVENTION.md)（P-05～P-41，特別是 P-17 小格、P-32 被叫者的工作區在呼叫方的小格裡、P-35 格可以是一整隻 agent、P-41 腦的工具呼叫）、[`_metainfo` M1～M10](../../../thinking/2026-10-24-metainfo.md)、[函數成長六級](../../../thinking/2026-10-24-fn-grow.md)、[工具＝函式庫](../../../lib/README.md)｜題目來源（只讀）：`~/repo/ai_core/sub_projs/galtxt/`

這份只規劃、不寫程式。每一節先講結論，理由放後面。文中 `galtxt/…` 一律指 `~/repo/ai_core/sub_projs/galtxt/…`（另一個 repo，只讀）。

---

## 1. 我對題目與範圍的理解

**題目**：給一組場景條件（地點、兩個人物、一個小事件、風格意圖），產出一小段 galgame 台詞（5～10 句），而且要能自動打分。另外要用 corpus 的「挖空一句台詞」benchmark 真跑 1～2 題。

**galtxt 那邊已經定好的方向，我照用**（`galtxt/corpus/固化/README.md` 與 idea 礦脈）：

- **overgenerate-and-rank**：生成端便宜地多產幾個候選，檢核端用規則砍、按分數排、取最高。所以管線不是「寫一句就交」，是「寫幾句 → 砍 → 排 → 挑一句」。
- **評分級聯**：Tier 0 確定性護欄（禁語、設定穿幫、格式、護欄關鍵詞）→ Tier 1 語域（稱謂階、句尾、長度）→ Tier 2 LLM judge（語意契合）→ Tier 3 人工抽查。**Tier 0、1 純程式，Tier 2 才用腦**。這正好對上使用者說的「護欄、評分、事實查證能用純程式的就用純程式」。
- **固化表＝規則的快取，真源是 corpus**：我們自己的 `data/` 是從 corpus 手抄出來的小表（兩張人物卡、一張地點卡、禁語表、稱謂階、評測題），每張標出處。

**極小版的一個固定場景**（跟 benchmark Q01 同一個定點，兩邊共用同一組資料表）：

- 地點：河鹿堂（老書店，木百葉窗、文庫本、梅花章）
- 人物：主角（佐伯悠，行首照 corpus 慣例寫「主角」）＋ 森下晴子（文靜文學少女、稱「主角同學」、愛宮澤賢治）
- 小事件：兩人同時伸手拿同一本《銀河鐵道之夜》，晴子決定把書讓給主角
- 風格意圖：靜（含蓄、留白）
- 稱謂階（`galtxt/corpus/固化/02_敬語與稱謂階.md`）：1（姓氏＋同學）

**挑的 benchmark**：

- **Q01「河鹿堂讓書：《銀河鐵道之夜》」**（必跑）——護欄型：護欄關鍵詞 `銀河鐵道之夜／宮澤賢治`＋`讓給／先看`，加分 `梅花章`；稱呼須是「主角同學」。護欄型的好處是純程式就能打出有意義的分數，離線假腦也能驗整條管線。而且它跟上面的固定場景是同一個定點、同兩個人，資料表只要做一套。
- **Q12「納涼祭的煙火（河堤）」**（有餘力才跑）——難度「中」、木下柚葉、要靠含蓄留白；這題拿來看 Tier 2 judge 有沒有用。多一張人物卡（木下柚葉）、一張地點卡（霞川河堤）。

**題目長什麼樣**（放工作區 `$AOS_WS/new/<題名>.json`，一題一檔；JSON 不是純文字，是這隻 agent 自己的說明定的形狀，P-11 是慣例、P-26 參數形狀由程式自己定）：

場景模式：
```json
{"mode": "scene",
 "place": "河鹿堂",
 "cast": ["佐伯悠", "森下晴子"],
 "event": "兩人同時伸手拿同一本《銀河鐵道之夜》，晴子決定把書讓給主角",
 "season": "四月", "time": "午後",
 "intent": "靜",
 "rank": 1,
 "lines": {"min": 5, "max": 10},
 "drafts": 3}
```

挖空模式（benchmark）：題目只指到評測題的編號，前後文、護欄關鍵詞、正解都在 `data/bench/Q01.json`；**正解只有最後打分的 `pick/` 會讀，寫手與評審碰不到**（靠資料夾隔離，見 § 4 的 `fs_needs`）：
```json
{"mode": "fill", "bench": "Q01", "drafts": 3}
```

**輸出長什麼樣**（P-13 的資料夾形：答案有附檔）：

```
$AOS_WS/out/<題名>/answer.txt     場景模式：5～10 行，格式照 corpus——旁白「（…）」一行、對白「角色：「台詞」」一行一句
                                   挖空模式：恰好一行「森下晴子：「…」」
$AOS_WS/out/<題名>/score.json     每個候選的 Tier 0／1／2 分數與理由、選了第幾個；挖空模式多一段跟正解的比對
$AOS_WS/done/<題名>.json          做完的題目從 cur/ 搬來
```

**怎麼評分**（照 `galtxt/corpus/評測/README.md` 的三層，權重先定死、之後再調）：

| 層 | 誰算 | 內容 | 分 |
|---|---|---|---|
| Tier 0 護欄 | 純程式 `lint` | 格式（行數、行首是旁白或「角色：「」」、說話者在卡司裡、挖空模式只能一行且說話者對）；禁語 A／B／C 類（`galtxt/corpus/固化/03_禁語與OOC護欄.md`）；D 類設定（連鎖書店、手機 App、真實品牌…）；護欄關鍵詞（benchmark 題才有，`required` 每組至少命中一個） | 過／不過；不過＝總分 0、標原因 |
| Tier 1 語域 | 純程式 `lint` | 稱謂對不對（階 1：晴子叫主角要用「主角同學」或「佐伯同學」，直呼「悠」就扣）、角色語言表的句尾／口癖有沒有出現、有沒有 NG 標記（驚嘆號連發、流行語）、每行長度 ≤ 60 字（含蓄） | 0～2 |
| Tier 2 語意 | agent `judge` | 承接前文、鋪墊後文、情緒對、不油膩、留白 | 0～3 |
| 加分 | 純程式 | benchmark 的 bonus 關鍵詞（梅花章） | 只記錄，不進總分 |

總分＝Tier 1＋Tier 2（0～5）；Tier 0 不過的候選總分 0。平手照 gen_v0 的做法：**嚴格比大小、先產生的贏**（候選編號小的贏），所以同樣的候選集合永遠挑同一個。benchmark 另記一個跟正解的「字元二元組重疊率」（0～1）當便宜的語料匹配訊號，**只記錄不計分**——真正的對照是人看 `score.json` 跟評分要點。

三個候選都沒過 Tier 0 時，`pick` 照樣挑「違規最少」的那個寫出答案、`score.json` 標 `pass: false`、結束碼 0（這是預料到的正常結果，不是 pick 的錯；N-43）。

---

## 2. 頂層拆法

### 2.1 切成哪幾塊

照目標切：**「備料 → 寫 → 砍 → 評 → 挑」**五步，加上 agent 範本原有的 idle。每步一個資料夾，頂層用一張 fsm 表黏起來。

```
galtxt-a/
  _entry        #!/bin/sh；exec aos-loop loop.json                （黏合）
  loop.json     {"exec": "fsm.json", "max": 40}
  fsm.json      idle → brief → write → check → judge → pick → idle  （黏合：整條管線就是這張表）
  idle/         new/ 或 cur/ 有題目退 0、沒有退 10                    （純程式，抄 agent-dan）
  brief/        認領題目、從 data/ 組出 brief.json 與 rules.json       （純程式）
  write/        把 brief 交給寫手 agent 跑 N 次、收回 N 份草稿          （黏合格）
  check/        每份草稿過一次 lint，寫 checks.json                    （純程式格）
  judge/        過了護欄的草稿逐份交給評審 agent 打語意分，寫 judge.json （黏合格）
  pick/         合分、挑最高、寫 out/、題目 cur/ → done/               （純程式）
  data/         固化表（人物卡、地點卡、禁語、稱謂階、評測題、範例句）  （資料，沒有 _entry）
```

**為什麼這樣切**：

1. **切在「要不要腦」的邊界上**。整條管線只有兩件事非腦不可：寫台詞、判語意。這兩件各自是一隻 agent（寫手、評審），其餘全是確定性程式。把腦關在兩個資料夾裡，之後優化（換模型、走 LLM kernel 排隊、算 token）只看這兩個節點；C-22 說的「能寫死的節點換成程式」就是這條線。
2. **切在資料的形狀變化處**。每一步的輸出是下一步的輸入，而且形狀都變：題目 JSON → brief／rules → 草稿文字 ×N → checks.json → judge.json → 答案。形狀一變就是一個邊界，邊界上的檔就落在 stack 裡，人隨時能看（C-34 求值＝空間狀態的變化、P-10 格之間傳的東西寫成檔）。
3. **一次一格、壞了停在原地**。fsm 一格一格跑，哪格失敗整隻停住、state 留在那格，人修好再 `aos-exec` 一次就從那格接著做，前面已經寫好的 brief、草稿都不用重算（P-20、N-53）。這比「一支 python 從頭跑到尾」好：一支 python 失敗在評審那步，重跑就得重付寫手的 token。
4. **寫手、評審是「格裡叫的整隻 agent」，不是格本身**（P-35）。一隻 agent 自己有 loop、fsm、state.txt，直接拿來當 fsm 的一格會跟頂層 fsm 搶同一份 state.txt（P-32 明寫的坑）。所以 `write/`、`judge/` 是薄薄的黏合格：開小格、備它的工作區、叫它、收答案。

**跟標準範本（agent-dan 三態）的差別**：範本是 idle／think／act 三態，腦在 think。這裡腦不在頂層的格裡，而是在兩隻子 agent 裡；頂層是五個確定性步驟的流水線。P-08 允許「要加狀態＝fsm.json 加一格」。頂層 fsm 完全不知道 `write/` 底下有一隻 agent（C-52）。

### 2.2 頂層黏合的小程式做什麼

`_entry`（照 agent-dan）：
```sh
#!/bin/sh
# _entry - 把 galtxt-a 的 loop 跑起來（loop 每次跑一格 fsm.json）
exec aos-loop loop.json
```

`loop.json`：`{"exec": "fsm.json", "max": 40}`——一題走 6 格（idle＋五步），40 次夠做 6 題；跑完 new/ 空了 idle 退 10、loop 以 0 結束。

`fsm.json`（每格都是「`aos-exec` 一個子資料夾」，包一張單子只為了給逾時——P-29、P-36 外層逾時 ≥ 內層總和）：
```json
{"_entry": ["aos-fsm", {"$env": "AOS_CF"}],
 "start": "idle",
 "states": {
   "idle":  {"exec": "idle", "next": "brief"},
   "brief": {"exec": {"argv": ["aos-exec", "brief"], "timeout_ms": 10000},  "next": "write"},
   "write": {"exec": {"argv": ["aos-exec", "write"], "timeout_ms": 900000}, "next": "check"},
   "check": {"exec": {"argv": ["aos-exec", "check"], "timeout_ms": 30000},  "next": "judge"},
   "judge": {"exec": {"argv": ["aos-exec", "judge"], "timeout_ms": 600000}, "next": "pick"},
   "pick":  {"exec": {"argv": ["aos-exec", "pick"], "timeout_ms": 10000},   "next": "idle"}}}
```

`argv[0]` 是 `aos-exec`（照 PATH 找，aos 自己的指令，N-50），目標是相對 cwd＝`galtxt-a/` 的子資料夾。不用 `sh -c`。

### 2.3 資料怎麼在塊之間流

**工作區 `$AOS_WS`**（使用者的東西）只有四個資料夾：`new/`（題目）、`cur/`（認領了）、`out/`（答案）、`done/`（做完的題目）。P-14：agent 只動這四個。

**頂層 stack `$AOS_STACK`**（預設 `$AOS_WS/.stack/`）＝五格共用的桌面（P-16），一題跑完長這樣：

```
.stack/
  state.txt            aos-fsm 的現在狀態
  trace.jsonl          每格一行（at、state、code、elapsed_ms）
  current.txt          正在做哪題（brief 寫）
  brief.json           給寫手看的：模式、卡司卡（精簡）、地點卡、事件、意圖、前後文（挖空模式）、兩句範例
  rules.json           給 lint 用的：禁語表、設定黑名單、稱謂規則、語域標記、必要關鍵詞、格式限制（行數、說話者集合）
  drafts/1.txt 2.txt 3.txt      write 收回來的草稿
  checks.json          check 寫：每份草稿的 Tier 0 過／不過＋原因、Tier 1 分＋命中
  judge.json           judge 寫：每份過了護欄的草稿的 Tier 2 分＋一個標籤理由
  writer/runs/001/     write 叫寫手第 1 次的小格（P-17；每次一格、不帶上一次的記憶）
    ws/{new,cur,out,done}/    寫手的工作區：題目＝brief（P-32 被叫者的工作區在呼叫方的小格裡）
    ws/rules.json             lint 工具要的規則（寫手的 lint 從自己的 $AOS_WS 讀）
    stack/{state.txt,trace.jsonl,current.txt,history.jsonl,lint/}   寫手自己的 stack；lint/ 是它叫 lint 的小格
  writer/runs/002/  writer/runs/003/
  judge/runs/001/ …    judge 叫評審的小格，同上形狀
```

**stack 樹＝呼叫樹**（P-38）：`.stack/writer/runs/002/stack/lint/` 一眼看出「頂層叫了寫手第 2 次、寫手叫了 lint」。

**流向一句話**：題目（ws:new）→ brief／rules（stack）→ 寫手小格的 ws:new ← brief；寫手 ws:out → drafts（stack）→ checks（stack）→ 評審小格的 ws:new ← 草稿＋前後文；評審 ws:out → judge（stack）→ 答案（ws:out）。**`data/` 只有 `brief` 與 `pick` 讀**：brief 讀人物卡、地點卡、固化表、評測題的前後文與關鍵詞；pick 只讀評測題的正解。寫手、評審、lint 只看 stack 裡 brief 幫它們算好的東西，不碰 data/。這樣每個節點讀什麼、寫什麼都數得出來，寫在各自的 `_metainfo.reads`／`writes`（§ 4）。

---

## 3. 往下一層

每塊寫：切成哪幾塊、理由、**刻意不拆的與理由**。

### 3.1 `idle/`（純程式，抄 agent-dan）

`idle/_entry` 原樣抄 agent-dan：`cur/` 或 `new/` 有東西退 0，沒有退 10。題目是 `.json` 檔不影響它（它只看有沒有檔，跳過 `.` 開頭）。

不拆，也不長。**之後收攏的第一個候選**：縮成 fsm.json 裡的內嵌單子（agent-ann 式 `idle.py`），這格沒有伴隨檔、沒有自己的狀態。

### 3.2 `brief/`（純程式：備料）

一支 `brief/_entry`（python3 標準庫），做五件事：
1. 認領題目（同 agent-dan 的 brain：`cur/` 有沒做完的先接著做，沒有就把 `new/` 排序第一個搬到 `cur/`，跳過 `.` 開頭），題名寫 `$AOS_STACK/current.txt`（N-05 先寫暫存再改名）。
2. 讀題目 JSON；`mode: fill` 就去 `data/bench/<編號>.json` 拿 `place`、`cast`、`season`、`speaker`、`rank`、`context`、`guard`——**不拿 `answer`**。
3. 從 `data/cast/<名>.json`、`data/places/<名>.json`、`data/samples/` 挑這場要的卡片，照 `rank` 查 `data/address.json` 得到該階的稱呼規則，從 `data/forbidden.json` 整份帶走。
4. 寫 `brief.json`（給腦看的、人話多）與 `rules.json`（給 lint 用的、全是可比對的字串與數字）。兩份分開是因為讀者不同：模型看的東西不該塞一堆黑名單搶注意力（同 M10「tool.json 與 _metainfo 分開」的理由）；lint 不該讀人話。
5. 退 0。題目壞（不是 JSON、缺欄位、卡片找不到）＝自己的錯，stderr 一行 `galtxt-a brief: 代號 原因`、退 1、state 不動（P-21、P-20）。代號：`TaskBad`、`CastMissing`、`PlaceMissing`、`BenchMissing`。

`brief.json` 大概長這樣（挖空模式）：
```json
{"mode": "fill", "name": "Q01",
 "place": {"name": "河鹿堂", "details": ["老書店", "木百葉窗把書架陰影拉得很長", "文庫本", "老闆蓋梅花章"]},
 "cast": [{"name": "森下晴子", "type": "文靜／書卷", "voice": ["輕聲", "句尾「…呢」「是嗎」", "長停頓「……」", "口頭禪「……這句，很好。」"],
           "calls_lead": "主角同學", "likes": ["宮澤賢治", "《銀河鐵道之夜》", "河鹿堂的梅花章"]},
          {"name": "主角", "type": "嘴硬心軟", "voice": ["拌嘴裡包著體貼", "不直白表達關心"]}],
 "season": "四月", "time": "午後", "intent": "靜", "rank": 1,
 "speaker": "森下晴子",
 "context": ["（河鹿堂深處。午後陽光穿過老木百葉窗。…）", "主角：「啊，抱歉，妳先請。」", "…", "森下晴子：【★ 空格 ★】", "主角：「這怎麼好意思，明明是妳先看上的。」", "…"],
 "must": [["銀河鐵道之夜", "宮澤賢治"], ["讓給", "先看"]],
 "samples": ["森下晴子：「《銀河鐵道之夜》…我每年春天都想再讀一次呢。你會覺得奇怪嗎？」"]}
```

**刻意不拆的**：
- 不把「認領題目」跟「組 brief」拆成兩格。認領只有六行、沒有自己的狀態，拆了多一格 trace 卻沒多出可觀察的東西。
- 不做成 agent。這一步是查表、選卡、拼 JSON，全部確定性；什麼時候該變成 agent？——當題目只給「一個合理的放學後地點」這種要推論的條件時，選地點那一小步才長成腦，而且是長在 brief 裡面，不是整個 brief 變腦。
- 不讀 corpus 原檔（markdown）。真源是 corpus，但執行期讀的是 `data/` 的手抄表（固化 README：真源＝規則、表＝快取）。從 markdown 自動抽表是另一支離線工具的事，不在這條管線裡。

### 3.3 `write/`（黏合格）＋ `write/tools/writer/`（agent：寫手）

**`write/_entry`**（python3，黏合）：讀 `brief.json`、`rules.json` 與題目的 `drafts`（預設 3）；對第 i 份（1…N）：
- 若 `$AOS_STACK/drafts/i.txt` 已經在了就跳過（**這格被殺掉重跑時不重付已經寫好的草稿**；P-20 接著做）。
- 開新小格 `$AOS_STACK/writer/runs/NNN/`（用 [lib/agent/agent_tool.py](../../../lib/agent/agent_tool.py) 的 `fresh_cell`＋`run_agent`，寫法同 lib/agent/pyfix；它會建 `ws/new/`、`stack/`，寫題目、`aos-exec --dotenv-override --ws ws tools/writer`，從 `ws/out/` 拿答案）。
- 題目內容＝`brief.json` 再加一行 `hint`（第 i 個角度，固定清單 `["借景", "動作", "留白"]` 輪著用，讓三份草稿不是同一句換字；確定性、不用亂數）。另外把 `rules.json` 複製到寫手的 `ws/rules.json`——寫手的 lint 工具從它自己的 `$AOS_WS/rules.json` 讀規則（見 3.4）。
- 答案寫到 `$AOS_STACK/drafts/i.txt`（先暫存再改名）。
- 任一次寫手退非 0 或沒答案＝這格失敗：stderr 一行 `galtxt-a write: AgentFailed 第 i 份（現場在 …）`、退 1；已寫好的草稿留著。

**`write/tools/writer/`**（agent，agent-dan 範本）：
```
writer/
  _entry  loop.json  fsm.json（idle 資料夾、think／act 內嵌單子）  .env  system.txt  brain.py  act.py
  idle/_entry                   抄 dan
  tools/lint -> ../../../../check/tools/lint    捷徑（lib 的「一條捷徑一個工具」做法；真身在 check/tools/lint）
```
- `system.txt`：你是日和町 galgame 的寫手；題目是一份 JSON，照 `mode` 寫整場（`lines.min`～`max` 行）或只寫挖空那一行；格式一行一句、對白「角色：「台詞」」、旁白「（…）」；守含蓄不油膩、只用卡片裡的設定；**交稿前先用 lint 工具檢查一次，lint 說不過就改**；最後只回台詞本身、不加解釋。
- `brain.py`、`act.py` 抄 agent-dan，錯誤訊息開頭改 `writer:`；**假腦改寫**（見 § 6）。
- `loop.json` `max: 12`（idle／think／act 一輪 3 次，最多 4 次問腦：寫 → lint → 改 → 交）；think `timeout_ms` 120000、act 60000。
- `.env`：`AOS_BRAIN_MODEL=chatgpt-gpt-6-luna-low`；`AOS_BRAIN_URL` 由外面給、沒給＝假腦。

**為什麼寫手要有 lint 工具**：讓腦在交稿前自己過一次護欄，Tier 0 的錯（用了禁語、叫錯稱呼）在寫手這層就被打回，省掉「寫三份全被砍」的空轉。這跟頂層的 `check/` 不重複——`check/` 是**不信任寫手**的硬閘門（出口保證，C-53 (b)），寫手的 lint 是**它自己的工具**（入口自檢）。兩處用的是同一個資料夾（捷徑），一份實作。

**為什麼寫手跑 N 次而不是一次要它寫 N 份**：一次要 N 份得讓腦回 JSON 陣列再解析，格式一壞整格失敗；跑 N 次每次一份純文字，每次一個獨立小格、獨立 history，彼此不互相汙染，而且 `parallel: true`——之後要省時間，黏合格把三次改成同時跑就好，寫手一個字不用改。

**刻意不拆的**：
- 不把寫手拆成「規劃 beat → 寫句子」兩隻 agent。5～10 句是一口氣的量，拆了多一次腦、多一份要對齊的中間格式；corpus 固化 README 的 L1～L3（場景規劃、beat 展開、句規劃）是整場戲幾十句才需要的層，等長到那時再拆、而且應該往確定性的方向長（gen_v0 已經證明那幾層能純程式）。
- 寫手不給 `read`／`ls` 之類的檔案工具去翻 corpus。brief 已經把它要的卡片算好了；給它翻書的自由就是給它跑題的自由（C-22 降低走進不可預測節點的機率）。要加「查人物卡細節」的工具，是下一圈的事。
- 不在這一輪做「全部不過就叫寫手重寫」的迴圈。fsm 不會分岔（N-36 只看 `next`），要迴圈得在 `write/` 裡面自己轉；而寫手已經有 lint 自檢。先看實跑數字：三份草稿有幾份過 Tier 0，再決定要不要迴圈。

### 3.4 `check/`（純程式格）＋ `check/tools/lint/`（純程式工具，被兩處掛）

**`check/_entry`**（python3）：對 `$AOS_STACK/drafts/*.txt` 每一份，`aos-exec --ws "$AOS_STACK" tools/lint`，stdin 給 `{"text": 草稿}`，stdout 收回 lint 的 JSON；全部收齊寫 `checks.json`。`--ws "$AOS_STACK"`＝告訴 lint「你的工作區是頂層 stack，規則在那裡的 `rules.json`」（C-66 指標＝`AOS_WS`、lib 規則 4「要動別的資料夾是叫它的人 `--ws`」）。lint 退非 0（規則檔壞、stdin 壞）＝check 自己停、退 1。

**`check/tools/lint/`**（工具契約照 [lib/README](../../../lib/README.md)：`_entry`、`tool.json`、`_metainfo` 三件）：
- stdin `{"text": "…"}`；規則一律從 `$AOS_WS/rules.json` 讀（一條規則，沒有「給了路徑就改讀別處」的暗門，C-56）。
- stdout 一行 JSON：`{"pass": true/false, "tier0": [{"code": "ForbiddenWord", "line": 3, "hit": "心跳漏了一拍"}, …], "tier1": 2, "tier1_notes": ["稱呼對", "有句尾「呢」"], "bonus": ["梅花章"], "lines": 7}`。給腦看時同一份 JSON 它也看得懂（tool.json 說明寫清楚 pass／tier0 的意思）。
- Tier 0 代號：`FormatBad`（行數、行首格式）、`SpeakerUnknown`（說話者不在卡司）、`SpeakerWrong`（挖空模式說話者不對）、`ForbiddenWord`（A／B／C 類）、`SettingBad`（D 類：連鎖書店、手機 App、真實品牌、天台鎖著…）、`KeywordMissing`（`must` 某組一個都沒命中）、`LineTooLong`。
- 錯（stdin 不是 JSON、`rules.json` 不在或壞）：stderr 與 stdout 各一行 `lint: ArgumentsBad／RulesMissing／RulesBad 原因`、退 1。
- 純函數：不寫檔、不用 stack；同一份 text＋rules 永遠同一個結果（`deterministic: true`）。

**為什麼真身放在 `check/tools/lint/`、寫手用捷徑掛**：`check` 是護欄的「主人」（硬閘門），寫手只是借用。P-33 說幾格共用一個工具就複製或捷徑；lib 已經選了捷徑、demo/agent-liv 證明 aos-exec 走進捷徑指到的真資料夾沒問題（cwd、`AOS_CD` 都是真身的位置；lint 不靠 `AOS_CD` 找東西，所以掛在哪都一樣）。

**刻意不拆的**：
- 不把 lint 拆成 `forbidden/`、`address/`、`format/` 三個工具。三個都是「拿規則表比對字串」，拆了寫手要叫三次、三個資料夾各一份十幾行開頭；規則本來就是 `rules.json` 裡的三個區段，拆在資料裡就夠了。什麼時候拆？——某一段要變成腦的時候（例如「同義改寫的油膩也要攔」要用語意判），那一段長成 agent、其餘留在 lint。
- 不讓 `check/` 自己 import lint 的程式碼「省一層 aos-exec」。那樣 lint 就有兩個入口（工具入口與 import 入口），兩邊的錯誤行為會慢慢分岔。多一層 aos-exec 對三份草稿是毫秒級的事。

### 3.5 `judge/`（黏合格）＋ `judge/tools/judge/`（agent：評審）

**`judge/_entry`**（python3）：讀 `checks.json`、`drafts/`、`brief.json`；對每份 **Tier 0 過了**的草稿，開小格 `$AOS_STACK/judge/runs/NNN/`，題目＝前後文（挖空模式）或場景條件（場景模式）＋這份草稿＋評分要點（含蓄、承接、不油膩）；跑評審 agent；答案要是「`分數：N`」開頭（N 是 0～3）加一行「`理由：<標籤>`」，解出數字寫進 `judge.json`；解不出＝`ReplyBad` 停、退 1（出口保證；重跑會開新小格、不帶上次的回答）。沒有任何草稿過 Tier 0 時什麼都不評、`judge.json` 是空表、退 0。

**`judge/tools/judge/`**（agent，agent-dan 範本，沒有工具）：`system.txt` 寫評分規則（0～3 的四級各一句話、含蓄基調紅線、只回兩行）；`.env` 同寫手（之後要換更強的模型只改這份 `.env`）；`loop.json` `max: 6`；think `timeout_ms` 90000。假腦見 § 6。

**為什麼評審跟寫手是兩隻 agent、不是一隻「寫完自評」**：自己評自己會偏；評審有獨立的 system prompt、沒有工具、可以換模型；兩隻的 `_metainfo` 也不同（評審 `llm_tokens` 小、`side_effect` 少）。這就是評分級聯裡「judge 是校準過的獨立儀器」。

**為什麼一份草稿評一次、不是三份一起排名**：各自獨立評才能平行、才能跟 Tier 1 的分數加總；排名式輸出又要解析陣列。代價是多兩次腦；三份草稿 3 次、一次約 2k token，便宜。

**刻意不拆的**：
- 評審不給 lint 工具、不給任何工具。它只要讀、只要回兩行。
- 不做 Tier 3 人工抽查的介面。答案與 `score.json` 落在工作區，人要看就看。idea 礦脈 4.2 的快速標籤工具是另一支離線工具。

### 3.6 `pick/`（純程式：取優、交卷）

`pick/_entry`（python3）：合分（規則見 § 1 表）、嚴格比大小、平手編號小的贏；挖空模式再讀 `data/bench/<編號>.json` 的 `answer` 算二元組重疊率、記 `bonus` 命中；寫 `$AOS_WS/out/<題名>/answer.txt` 與 `score.json`（先寫 `.` 開頭暫存資料夾再改名，N-05）；題目 `cur/` → `done/`；退 0。`checks.json` 或 `drafts/` 缺＝自己的錯 `StateBad`、退 1。

`score.json` 形狀：
```json
{"mode": "fill", "name": "Q01", "picked": 2, "pass": true,
 "drafts": [{"n": 1, "tier0": ["KeywordMissing"], "tier1": 1, "tier2": null, "total": 0},
            {"n": 2, "tier0": [], "tier1": 2, "tier2": 3, "total": 5, "bonus": ["梅花章"]},
            {"n": 3, "tier0": [], "tier1": 2, "tier2": 2, "total": 4}],
 "bench": {"bigram_overlap": 0.31, "guard_hit": true}}
```

**刻意不拆的**：不把「交卷搬檔」跟「合分」分成兩格；都是十幾行、沒有腦、沒有外部服務。

### 3.7 `data/`（資料：固化表的快取）

```
data/
  cast/森下晴子.json  cast/佐伯悠.json  （有餘力：木下柚葉.json）
  places/河鹿堂.json                     （有餘力：霞川河堤.json）
  address.json      稱謂階 0～5：女角叫主角的形、主角叫女角的形、各階語域（固化 02）
  forbidden.json    A 油膩／B 穿幫／C 語體 三類禁詞；D 類設定黑名單（固化 03）
  styles.json       角色類型 → 句尾、口癖、NG 標記（固化 01，只抄用到的兩型）
  bench/Q01.json    前後文、speaker、guard、answer、評分要點（抄評測 01）；有餘力 Q12.json
  samples/          兩三句從 corpus 場景抄的合格範例（不含評測題的正解）
```

每張表頂層帶 `"source": "corpus/固化/02_敬語與稱謂階.md"`——表是快取，真源在 corpus。

一張人物卡的樣子（給實作者對齊）：
```json
{"source": "corpus/人物/森下晴子.md",
 "name": "森下晴子", "display": "森下晴子", "type": "文靜／書卷",
 "voice": ["輕聲", "句尾「…呢」「是嗎」", "長停頓「……」"],
 "catchphrase": "……這句，很好。",
 "likes": ["宮澤賢治", "《銀河鐵道之夜》", "河鹿堂的梅花章", "焙茶"],
 "calls_lead": {"0": ["同學"], "1": ["主角同學", "佐伯同學"], "2": ["佐伯"], "3": ["悠同學"], "4": ["悠"]},
 "never": ["滔滔不絕", "流行語", "情緒炸出來"]}
```
（佐伯悠的卡 `display: "主角"`——corpus 的評測與場景行首都寫「主角」。）

**為什麼 `data/` 獨立一個資料夾而不是塞進 `brief/`**：① 兩個讀者（brief 讀卡片與規則、pick 讀正解）；② 這些表要被 git 單獨追蹤、人手改、diff 可審（固化 README：調品味＝改表＝可 review 的 diff）；③ `bench/` 的正解要能跟寫手、評審隔開——現在靠「brief 不複製 answer」這條程式紀律，之後要硬隔離就把 `data/bench/` 設成只有 pick 那層能讀的權限（C-64 借 Linux 權限做事）。這三條都是「需要檔案系統特性」，收攏時不縮回 JSON。

**刻意不拆的**：`cast/`、`places/`、`bench/`、`samples/` 四個子資料夾只是分類，裡面一檔一張卡；不再往下。`address.json`、`forbidden.json`、`styles.json` 各一檔，不拆成資料夾——都 < 8 KB。

### 3.8 深度到哪為止

最深的一條：`galtxt-a/write/tools/writer/tools/lint`（捷徑）→ 真身 `galtxt-a/check/tools/lint/`。資料夾程式四層（頂層 → 黏合格 → 寫手 agent → 工具）。再往下沒有要跑的東西，停。

---

## 4. 每個資料夾的 `_metainfo`

### 4.1 自己加的 key（通用 key 不夠描述這棵樹的地方）

通用 key（M3：`summary`、`time_ms`、`resource`、`llm_calls`、`llm_tokens`、`side_effect`、`idempotent`、`deterministic`、`interrupt`、`parallel`、`lock`）照寫。為了之後那一輪「看 `_metainfo` 做整棵樹的優化與收攏」，每個節點多六個 key（讀的人不認得就忽略，C-48；名字照 C-54 小寫底線）：

| key | 值 | 給收攏用什麼 |
|---|---|---|
| `kind` | `agent`／`program`／`glue`／`data` | 一眼分出腦節點、純程式、黏合層、資料。**`glue` 是收攏的首要對象**（太薄的中間層）；`agent` 一定是資料夾（第 5 級）；`data` 不是函數 |
| `grow_level` | 0～5（[函數成長六級](../../../thinking/2026-10-24-fn-grow.md)） | 現在在哪一級；收攏＝往低級退 |
| `reads`／`writes` | 字串陣列，前綴 `ws:`（工作區）、`stack:`（自己或共用的 stack）、`data:`（固化表）、`net:`（外部服務）、`cell:`（開給別人的小格） | 畫得出整棵樹的資料流；兩個相鄰節點 `writes` 跟 `reads` 只對上一個檔、又都沒有別的讀者，就是「可以併」的訊號 |
| `fs_needs` | 字串陣列，空＝沒有理由一定要是資料夾。值：`own_stack`（自己要有 state／history，是一隻 agent）、`tool_json`（腦要讀 `tool.json`，三件一套）、`mount`（是捷徑的掛點或目標）、`git_tracked`（要被 git 單獨追蹤、人手改）、`isolation`（要用權限擋別人讀）、`big_file`（大檔／二進位） | **這就是「需要檔案系統特性的不縮」的判據**：空的才准縮回 JSON |
| `callers` | 整數：被幾處叫 | 函數成長的「被 ≥ 2 處叫」門檻 |
| `llm_model`／`llm_endpoint` | 字串 | LLM 節點用哪個模型、哪個端點（`AOS_BRAIN_URL`，沒設＝假腦） |

數字全是**自報的估計**（10-13 § 3.1：`_metainfo` 是作者的契約，不是量出來的）；實跑後把實測寫到 `plan/round1-measure.md`，**不回寫 `_metainfo`**（M7）。估計的依據：gpt-6-luna-low 一次 chat 約 4～10 秒；brief 約 1.5k token；寫手一次問腦約 2.5k 進 300 出。

### 4.2 逐個節點

**`galtxt-a/_metainfo`**（頂層；叫 `aos-exec galtxt-a` 的人看到的就是這份，外層贏 M6）
```json
{"summary": "給一組場景條件（或評測的挖空題），寫幾份 galgame 台詞草稿、過護欄、評語意分、挑一份交卷",
 "kind": "agent", "grow_level": 5,
 "time_ms": {"val": 90000, "max": 1500000},
 "resource": ["llm", "cpu", "disk"],
 "llm_calls": {"val": 9, "max": 60},
 "llm_tokens": {"val": 24000, "max": 200000},
 "llm_model": "chatgpt-gpt-6-luna-low（寫手、評審各自的 .env）",
 "llm_endpoint": "AOS_BRAIN_URL（家機 LiteLLM http://localhost:4000/v1）；沒設＝假腦，離線可跑",
 "side_effect": true,
 "idempotent": false,
 "deterministic": false,
 "interrupt": "resumable",
 "parallel": true,
 "lock": [{"$env": "AOS_WS", "$prefix": "ws:"}],
 "reads": ["ws:new/*.json", "ws:cur/*.json", "data:*"],
 "writes": ["ws:out/<題名>/", "ws:done/<題名>.json", "stack:*"],
 "fs_needs": ["own_stack", "git_tracked"],
 "callers": 0}
```
`resumable`：每格之間狀態都在 stack（state.txt、drafts/、checks.json），殺掉再叫從同一格接著做；`llm_calls.val` 9＝寫手 3 次 × 2 問（寫、lint 後交）＋評審 3 次；`max` 60＝寫手 3 × 4（loop max 12）＋評審 3 × 2，再留一倍給 N 調大。`parallel: true` 但同一個工作區只能一份（`lock`）。

**`idle/_metainfo`**
```json
{"summary": "cur/ 或 new/ 有題目退 0，沒有退 10 請 loop 停",
 "kind": "program", "grow_level": 3,
 "time_ms": {"val": 5, "max": 1000}, "resource": "cpu",
 "side_effect": false, "idempotent": true, "deterministic": true, "interrupt": "safe", "parallel": true,
 "reads": ["ws:new/", "ws:cur/"], "writes": [],
 "fs_needs": [], "callers": 1}
```

**`brief/_metainfo`**
```json
{"summary": "認領一題，從 data/ 的人物卡、地點卡、固化表組出給寫手看的 brief.json 與給 lint 用的 rules.json",
 "kind": "program", "grow_level": 3,
 "time_ms": {"val": 50, "max": 10000}, "resource": ["cpu", "disk"],
 "side_effect": true, "idempotent": true, "deterministic": true, "interrupt": "safe", "parallel": false,
 "reads": ["ws:new/*.json", "ws:cur/*.json", "data:cast/*", "data:places/*", "data:address.json", "data:forbidden.json", "data:styles.json", "data:samples/*", "data:bench/<編號>.json（不讀 answer）"],
 "writes": ["ws:cur/<題名>.json", "stack:current.txt", "stack:brief.json", "stack:rules.json"],
 "fs_needs": [], "callers": 1}
```
`side_effect: true` 因為它搬題目（動了工作區）；`idempotent: true`：重跑同一題，cur/ 已有就接著做、brief 重寫一樣的內容。`parallel: false`：兩份同時認領會搶 new/ 第一題。

**`write/_metainfo`**（黏合格）
```json
{"summary": "把 brief 交給寫手 agent 跑 N 次（預設 3），每次一個新小格，答案收成 drafts/N.txt；已有的草稿不重寫",
 "kind": "glue", "grow_level": 3,
 "time_ms": {"val": 45000, "max": 900000},
 "resource": ["llm", "cpu"],
 "llm_calls": {"val": 6, "max": 36}, "llm_tokens": {"val": 18000, "max": 150000},
 "side_effect": false, "idempotent": true, "deterministic": false, "interrupt": "resumable", "parallel": true,
 "reads": ["stack:brief.json", "stack:rules.json", "stack:current.txt", "stack:drafts/"],
 "writes": ["stack:drafts/N.txt", "cell:writer/runs/NNN/{ws,stack}"],
 "fs_needs": ["mount"], "callers": 1}
```
`llm_*` 是三次寫手的加總（彙總法照 M6 推薦：加總）。`side_effect: false`：只寫自己的 stack 與小格，不碰工作區。`fs_needs: ["mount"]`：底下 `tools/writer/` 要放得下，而且寫手的 `tools/lint` 捷徑路徑是從這裡算的。`parallel: true`：三次可以同時跑（第一輪先串行）。

**`write/tools/writer/_metainfo`**（agent：寫手）
```json
{"summary": "寫手：照 brief 寫一份台詞（整場 5～10 行，或挖空的那一行），交稿前用 lint 自檢",
 "kind": "agent", "grow_level": 5,
 "time_ms": {"val": 15000, "max": 300000},
 "resource": ["llm", "cpu"],
 "llm_calls": {"val": 2, "max": 4}, "llm_tokens": {"val": 6000, "max": 50000},
 "llm_model": "chatgpt-gpt-6-luna-low（.env）", "llm_endpoint": "AOS_BRAIN_URL；沒設＝假腦（模板填槽）",
 "side_effect": true, "idempotent": false, "deterministic": false, "interrupt": "resumable", "parallel": true,
 "lock": [{"$env": "AOS_WS", "$prefix": "ws:"}],
 "reads": ["ws:new/*.json", "ws:rules.json（經 lint）"],
 "writes": ["ws:out/<題名>", "ws:done/<題名>.json", "stack:history.jsonl", "stack:state.txt", "stack:current.txt", "stack:trace.jsonl", "cell:lint/"],
 "fs_needs": ["own_stack", "mount"], "callers": 1}
```
`max 4`＝loop.json `max: 12` ÷ 3 格。`idempotent: false`：重跑會在 history 多接一則（範例 3 的理由）。

**寫手 `fsm.json` think 格的內嵌單子**（第三處，M1；kernel 第一版只看單子裡的）
```json
"think": {"exec": {"argv": ["python3", "brain.py"], "timeout_ms": 120000,
                   "_metainfo": {"summary": "問腦一次：帶 history 與 tools（lint）",
                                 "time_ms": {"val": 6000, "max": 120000},
                                 "resource": "llm", "llm_calls": 1,
                                 "llm_tokens": {"val": 3000, "max": 12000},
                                 "side_effect": false, "idempotent": false, "deterministic": false,
                                 "interrupt": "safe"}},
          "next": "act"}
```

**`write/tools/writer/idle/_metainfo`**：同 3.1 的 idle，`callers: 1`。

**`check/_metainfo`**（純程式格）
```json
{"summary": "每份草稿用 tools/lint 過一次 Tier 0 護欄與 Tier 1 語域，收成 checks.json",
 "kind": "program", "grow_level": 4,
 "time_ms": {"val": 300, "max": 30000}, "resource": "cpu",
 "side_effect": false, "idempotent": true, "deterministic": true, "interrupt": "safe", "parallel": true,
 "reads": ["stack:drafts/*.txt", "stack:rules.json（給 lint 當工作區）"],
 "writes": ["stack:checks.json"],
 "fs_needs": ["mount"], "callers": 1}
```
`grow_level: 4`：資料夾裡不只入口（有 `tools/`）。`fs_needs: ["mount"]`：它是 lint 真身的家、也是寫手捷徑的目標。

**`check/tools/lint/_metainfo`**（純程式工具；被 check 與寫手兩處用）
```json
{"summary": "台詞護欄：stdin 收 {text}，照 $AOS_WS/rules.json 驗格式、禁語、設定、稱謂、語域、必要關鍵詞，回一行 JSON（pass、tier0、tier1）",
 "kind": "program", "grow_level": 4,
 "time_ms": {"val": 40, "max": 5000}, "resource": "cpu",
 "side_effect": false, "idempotent": true, "deterministic": true, "interrupt": "safe", "parallel": true,
 "reads": ["ws:rules.json"], "writes": [],
 "fs_needs": ["tool_json", "mount"], "callers": 2}
```
`callers: 2`（check 直接叫、寫手經捷徑叫）＝函數成長「被 ≥ 2 處叫」成立，這個節點不會被縮。

**`judge/_metainfo`**（黏合格）
```json
{"summary": "過了護欄的草稿逐份交給評審 agent 打 0～3 的語意分，每份一個新小格，收成 judge.json",
 "kind": "glue", "grow_level": 3,
 "time_ms": {"val": 25000, "max": 600000},
 "resource": ["llm", "cpu"],
 "llm_calls": {"val": 3, "max": 12}, "llm_tokens": {"val": 6000, "max": 60000},
 "side_effect": false, "idempotent": true, "deterministic": false, "interrupt": "resumable", "parallel": true,
 "reads": ["stack:checks.json", "stack:drafts/*.txt", "stack:brief.json"],
 "writes": ["stack:judge.json", "cell:judge/runs/NNN/{ws,stack}"],
 "fs_needs": ["mount"], "callers": 1}
```
`idempotent: true` 指「重跑已評過的不重評」（跟 write 一樣，judge.json 裡已有的草稿跳過）。

**`judge/tools/judge/_metainfo`**（agent：評審）
```json
{"summary": "評審：讀前後文（或場景條件）與一份草稿，回「分數：N」「理由：標籤」兩行；沒有工具",
 "kind": "agent", "grow_level": 5,
 "time_ms": {"val": 7000, "max": 180000},
 "resource": ["llm", "cpu"],
 "llm_calls": {"val": 1, "max": 2}, "llm_tokens": {"val": 2000, "max": 10000},
 "llm_model": "chatgpt-gpt-6-luna-low（.env；要換更強的只改這份）", "llm_endpoint": "AOS_BRAIN_URL；沒設＝假腦（固定給 2 分）",
 "side_effect": true, "idempotent": false, "deterministic": false, "interrupt": "resumable", "parallel": true,
 "lock": [{"$env": "AOS_WS", "$prefix": "ws:"}],
 "reads": ["ws:new/*.txt"],
 "writes": ["ws:out/<題名>", "ws:done/<題名>.txt", "stack:history.jsonl", "stack:state.txt", "stack:trace.jsonl"],
 "fs_needs": ["own_stack"], "callers": 1}
```
評審的 think 格內嵌單子同寫手那份，`llm_tokens` 改 `{"val": 2000, "max": 10000}`、`time_ms` `{"val": 5000, "max": 90000}`。

**`pick/_metainfo`**
```json
{"summary": "合 Tier 1＋Tier 2 分、嚴格比大小、平手編號小的贏；寫 out/<題名>/{answer.txt,score.json}，題目 cur/ → done/；挖空模式再跟正解比",
 "kind": "program", "grow_level": 3,
 "time_ms": {"val": 30, "max": 10000}, "resource": ["cpu", "disk"],
 "side_effect": true, "idempotent": true, "deterministic": true, "interrupt": "safe", "parallel": false,
 "reads": ["stack:checks.json", "stack:judge.json", "stack:drafts/*.txt", "stack:current.txt", "data:bench/<編號>.json#/answer"],
 "writes": ["ws:out/<題名>/answer.txt", "ws:out/<題名>/score.json", "ws:done/<題名>.json"],
 "fs_needs": [], "callers": 1}
```

**`data/_metainfo`**（資料，不是函數；沒有 `_entry`）
```json
{"summary": "固化表的快取：人物卡、地點卡、稱謂階、禁語、語域標記、評測題、範例句；真源是 ~/repo/ai_core/sub_projs/galtxt/corpus，每張表頂層寫 source",
 "kind": "data", "grow_level": 4,
 "resource": "disk",
 "side_effect": false, "deterministic": true,
 "reads": [], "writes": [],
 "fs_needs": ["git_tracked", "isolation"], "callers": 2,
 "children": {"cast": "一人一張卡", "places": "一地一張卡", "bench": "一題一檔，含正解——只有 pick 讀", "samples": "合格範例句，不含評測正解"}}
```
`isolation`：`bench/` 的正解要能跟寫手、評審隔開（現在靠 brief 不複製 answer；之後可以用權限）。四個子資料夾各放一份極短的 `_metainfo`：`{"summary": "…", "kind": "data", "fs_needs": ["git_tracked"]}`，`bench/` 多 `"isolation"`。

---

## 5. 整棵樹（ASCII）

```
galtxt-a/                                  [黏合] agent 頂層：_entry → aos-loop → fsm.json 六格
├─ idle/                                   [純程式] 有題退 0、沒題退 10（抄 dan）
├─ brief/                                  [純程式] 認領題目、data/ → brief.json＋rules.json
├─ write/                                  [黏合格] 開小格 ×N、備 ws、叫寫手、收 drafts/N.txt
│  └─ tools/writer/                        [agent] 寫手（dan 範本：idle/ think act，system.txt，.env）
│     ├─ idle/                             [純程式]
│     └─ tools/lint ─捷徑─▶ ../../../../check/tools/lint
├─ check/                                  [純程式格] 每份草稿 aos-exec --ws $AOS_STACK tools/lint → checks.json
│  └─ tools/lint/                          [純程式工具] Tier 0 護欄＋Tier 1 語域；被 check 與寫手兩處叫
├─ judge/                                  [黏合格] 過了護欄的草稿逐份開小格叫評審 → judge.json
│  └─ tools/judge/                         [agent] 評審（dan 範本、沒有工具；回「分數：N」「理由：標籤」）
│     └─ idle/                             [純程式]
├─ pick/                                   [純程式] 合分、挑最高、寫 out/、cur/ → done/；挖空模式比正解
└─ data/                                   [資料] 固化表快取（真源 corpus）
   ├─ cast/  places/  samples/             [資料]
   ├─ bench/                               [資料；隔離] 評測題含正解，只有 pick 讀
   ├─ address.json  forbidden.json  styles.json
   └─ _metainfo

腦在哪：只有 write/tools/writer 與 judge/tools/judge 兩個節點 resource 含 llm。
```

跑起來的 stack 樹（一題、三份草稿）：
```
$AOS_WS/.stack/
├─ state.txt  trace.jsonl  current.txt  brief.json  rules.json  checks.json  judge.json
├─ drafts/1.txt 2.txt 3.txt
├─ writer/runs/001/{ws/{new,cur,out,done,rules.json}, stack/{state.txt,history.jsonl,trace.jsonl,current.txt,lint/}}
├─ writer/runs/002/…   writer/runs/003/…
└─ judge/runs/001/…    judge/runs/002/…   judge/runs/003/…
```

---

## 6. 給實作者的注意事項

### 6.1 哪些零件直接抄、哪些掛 lib

| 要做的 | 怎麼來 |
|---|---|
| 頂層 `_entry`、`loop.json`、`idle/_entry` | 抄 agent-dan，`loop.json` 的 `max` 改 40 |
| 寫手、評審兩隻 agent | 整隻抄 agent-dan（`_entry`、`loop.json`、`fsm.json`、`idle/`、`brain.py`、`act.py`、`.env`），只改：`system.txt`、錯誤訊息開頭（`writer:`／`judge:`）、`fake()`（見 6.2）、`loop.json` 的 `max`（12／6）、think 逾時（120／90 秒）。寫手 `tools/lint` 是相對捷徑 `../../../../check/tools/lint`（repo 在 Linux checkout，捷徑可以 commit；demo/agent-liv 已有先例）。評審沒有 `tools/`（brain.py 沒 `tools/` 資料夾就不帶 tools 陣列，agent-dan 已處理） |
| `write/_entry`、`judge/_entry` 的「開小格、備 ws、跑子 agent、拿答案」 | 用 `proto8/lib/agent/agent_tool.py` 的 `fresh_cell`、`run_agent`（寫法照 `lib/agent/pyfix/_entry`：`sys.path.insert(0, realpath(…/lib/agent))`）。`fresh_cell(stack)` 給它 `$AOS_STACK/writer`，小格就是 `$AOS_STACK/writer/runs/NNN/`；`run_agent(name, "tools/writer", task, cell, question="<題名>.json")` 會 `aos-exec --dotenv-override --ws cell/ws tools/writer`。多做一件：跑之前把 `rules.json` 複製到 `cell/ws/rules.json`。這是「掛 lib」裡唯一的一處；要完全自成一格就把那 40 行抄進來（lib 規則 9 的精神），兩者都行，先用 import |
| `check/tools/lint/` | 照 [lib/README 契約](../../../lib/README.md)寫（三件、stdin JSON、錯誤行 stderr＋stdout 同一行退 1、`+x`、第二行 `# lint - 一句話`）；可以直接拿 `test_lib.py` 的形狀檢查來驗它 |
| `brief`、`check`、`pick` 三支純程式 | python3 標準庫、`_entry` 帶 shebang；錯誤一行 `galtxt-a <格>: 代號 原因`、退 1；寫檔先 `.` 開頭暫存再 `os.replace`（N-05） |
| `data/` | 從 corpus 手抄；每張表 `source` 寫出處。只抄用到的：兩張人物卡（森下晴子、佐伯悠）、一張地點卡（河鹿堂）、稱謂階表、禁語表（A／B／C 類的禁詞各抄完整那幾列＋D 類設定）、文靜型與主角型的語域標記、Q01、兩三句範例 |
| 每個資料夾一份 `_metainfo`（§ 4 全文照放） | 內嵌單子的那份寫在寫手、評審 `fsm.json` 的 think 格裡 |

PATH：aos 的程式不動 PATH（N-59），跑的人自己把 `proto8/impls/{aos-exec,aos-loop,aos-fsm}/bin` 放進 PATH（測試用 `aos_bins.path_with()`）。

### 6.2 假腦要怎麼回，整條管線才能離線跑通

agent-dan 的假腦是「有 clock 就叫一次、然後回 FAKE ANSWER」。這裡的假腦要讓下游真的有東西可砍、可評、可挑，所以：

**寫手的假腦＝固化階梯第 3 級（模板＋槽填充），用 brief 裡的東西組一句合格台詞**：
1. 第一次被問（history 最後一則是 user）：先組一份草稿，回一則 `tool_calls` 叫 `lint`、`arguments` 是 `{"text": 草稿}`——這樣離線測試也走過「腦叫工具、act 跑 `aos-exec tools/lint`、小格 `lint/` 落在寫手的 stack」這條路。
2. 第二次被問（最後一則是 tool）：回那份草稿當答案（`content`）。
3. 草稿怎麼組（確定性、不用亂數）：
   - 挖空模式：`<speaker>：「<開頭><必要關鍵詞第一組第一個>…<必要關鍵詞第二組第一個>…<句尾>」`，例如 Q01 組出 `森下晴子：「既然這樣，這本《銀河鐵道之夜》就讓給主角同學吧。我下次再來呢。」`——稱呼從 `cast[].calls_lead`（brief 已照階選好）、句尾從 `voice`、關鍵詞從 `must`。`hint` 不同（借景／動作／留白）就在開頭換一個固定片語，三份草稿字面不同。
   - 場景模式：開場旁白一行（brief 的 place.details 挑一條）、對白輪流兩人各兩三句（模板：主角「啊，抱歉，妳先請。」／晴子「不，是我沒注意到……咦，主角同學？」…從 `samples` 與 `event` 拼）、收尾旁白一行；行數落在 `lines.min`～`max`。
   - 刻意讓**第 3 份草稿漏掉一組必要關鍵詞**（挖空模式），讓 check 真的砍掉一份、pick 真的在剩下兩份裡挑——測試才看得出 Tier 0 在工作。

**評審的假腦**：固定回 `分數：2\n理由：假腦`。要讓 pick 的平手規則被測到，兩份都 2 分、挑編號小的。

**真腦**：設 `AOS_BRAIN_URL=http://localhost:4000/v1`（LiteLLM，不用 key），模型由兩隻 agent 的 `.env` 給（預設 `chatgpt-gpt-6-luna-low`；外面已設 `AOS_BRAIN_MODEL` 就用外面的，`run_agent` 帶了 `--dotenv-override` 所以子 agent 的 `.env` 會蓋外層——跟 pyfix 一樣）。跑法：
```sh
mkdir -p ws/new && cp proto8/topdown/galtxt-a/plan/examples/Q01.json ws/new/   # 題目範例檔實作時放 plan/examples/
AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws ws proto8/topdown/galtxt-a
cat ws/out/Q01/answer.txt ws/out/Q01/score.json
```
真跑完把每個節點實際的 `elapsed_ms`（`trace.jsonl`、各小格的 `trace.jsonl`）與 token（LiteLLM 回的 `usage`；brain.py 經 LLM kernel 跑時才會寫回報檔，直接打 API 時先把 `usage.total_tokens` 多記一行到寫手 stack 的 `usage.jsonl`——這一行是 galtxt-a 自己的 brain.py 加的，範本不改）整理進 `plan/round1-measure.md`，跟 § 4 的宣告並排，給收攏那輪用。

### 6.3 自動測試 `proto8/tests/test_topdown_galtxt_a.py` 要驗哪幾件

全部離線（不設 `AOS_BRAIN_URL`＝假腦），照 `test_dan.py` 的寫法（`aos_bins`、`own_error.install()`、暫時工作區）：

1. **樹的形狀**：`galtxt-a/` 底下每個資料夾（含 `data/` 與其子資料夾，不含捷徑）都有 `_metainfo`、是 JSON、有 `summary` 與 `kind`；`kind: agent` 的一定有 `resource` 含 `llm`、有 `llm_calls`；每個 `tools/<名>/` 真身有 `tool.json`；每個 `_entry` 都 `+x` 帶 shebang；寫手的 `tools/lint` 是相對捷徑、指到 `check/tools/lint`。
2. **場景模式跑通**：放一題 scene JSON，`aos-exec --ws ws galtxt-a` 結束碼 0、stderr 空；`out/<題名>/answer.txt` 5～10 行、每行是旁白或「角色：「…」」、說話者 ⊆ {主角, 森下晴子}；`score.json` 有 `picked`、三份 `drafts` 各有 `tier0`／`tier1`／`total`；`done/<題名>.json` 在、`cur/` 空；頂層 `trace.jsonl` 有 idle、brief、write、check、judge、pick 六種 state 各至少一行，最後一行是 idle 的 10；stack 有 `brief.json`、`rules.json`、`drafts/1.txt..3.txt`、`checks.json`、`judge.json`；`writer/runs/001/stack/history.jsonl` 裡有一則 `tool_calls` 叫 `lint`、`writer/runs/001/stack/lint/` 這個小格存在；`judge/runs/` 有兩個或三個小格（過了護欄的份數）。
3. **挖空模式（Q01）**：`answer.txt` 恰好一行、以「森下晴子：「」開頭、命中 `must` 每一組至少一個；`score.json` 的 `bench` 有 `bigram_overlap` 與 `guard_hit`；第 3 份草稿 `tier0` 含 `KeywordMissing`、`total` 0、沒被挑；`picked` 是 1（兩份同 2 分、平手編號小的贏）；**所有 `writer/runs/*/stack/history.jsonl` 與 `judge/runs/*/…` 裡都找不到正解那句**（隔離）。
4. **lint 單元**（直接 `aos-exec --ws <有 rules.json 的資料夾> check/tools/lint`）：禁語「心跳漏了一拍」→ `ForbiddenWord`；階 1 直呼「悠」→ `tier1_notes` 含 `AddressBad`、`tier1` 只剩 1（稱呼是 Tier 1，不砍只扣）；說話者「柏木秋穗」不在卡司 → `SpeakerUnknown`；挖空模式兩行 → `FormatBad`；合格句 `pass: true`、`tier1` 2；stdin 不是 JSON → stderr 與 stdout 同一行 `lint: ArgumentsBad …`、退 1；沒 `rules.json` → `RulesMissing`。
5. **壞了停、修好接著做**：第一次跑時把 `AOS_BRAIN_URL` 指到一個關著的埠——寫手 `BrainFailed`，write 格退 1，loop 以 1 結束，`state.txt` 是 `write`，`brief.json` 已在、`drafts/` 空；第二次不設 URL 再跑一次：結束碼 0、`brief.json` 的 mtime 沒變（brief 沒重跑）、答案出來。再一個：手動把 `drafts/1.txt` 先放好再跑 write 格 → `writer/runs/` 只多兩個小格（已有的草稿不重寫）。
6. **`_metainfo` 自我一致**（給優化那輪一個基線）：頂層 `llm_calls.max` ≥ write 的 `llm_calls.max`＋judge 的 `llm_calls.max`；寫手 `llm_calls.max` ≥ 它 `loop.json` 的 `max` ÷ 3；每個 `kind: glue`／`program` 節點的 `fs_needs` 若為空，資料夾裡除了 `_entry` 與 `_metainfo` 沒有別的檔（不然該標 `mount` 或改級）。
7. **真腦**（`localhost:4000/v1/models` 連不上就 skip，同 `test_dan.test_real_model`）：Q01 跑通、`answer.txt` 一行、`guard_hit` 為真；不斷言分數。

跟使用者偏好對齊的幾件：不用 `sh -c`；腳本 python3 標準庫；錯誤一行帶代號、退 1；文件繁中白話。

---

## 7. 預期之後收攏時哪些會被併／縮（先猜，拿實跑數字對照）

照 § 4 的 `kind`、`fs_needs`、`callers` 與 `reads`／`writes` 看，從最可能到最不可能：

1. **`idle/`（三處：頂層、寫手、評審）→ 縮成 fsm.json 的內嵌單子**（第 3 級 → 第 0 級，agent-ann 的 `idle.py` 式）。`fs_needs` 空、沒有伴隨檔、`time_ms` 5。幾乎一定縮。
2. **`brief/`、`pick/` → 內嵌單子＋一支 `.py` 放頂層**（第 3 級 → 第 0 級）。都是單一腳本、`fs_needs` 空；`_metainfo` 跟著進單子（M1 第三處）。預期縮。代價：頂層資料夾多兩支 `.py`，fsm.json 變長；要看實跑後 fsm.json 有沒有超過 8 KB。
3. **`check/` 格 → 內嵌單子 `check.py`，`tools/lint/` 真身上移到 `galtxt-a/tools/lint/`**（P-33：內嵌單子格的工具放 agent 根的 `tools/`），寫手的捷徑改指 `../../../../tools/lint`。check 格本身很薄（跑三次 lint、合一份 JSON），但它的 `fs_needs: ["mount"]` 只是因為 lint 住在它底下；lint 搬走它就能縮。預期縮。
4. **`write/` 與 `judge/` 兩個黏合格**：兩支 `_entry` 做的事幾乎一樣（開小格、備 ws、跑子 agent 一遍、收答案），差別只在「跑誰、題目怎麼拼、答案收到哪」。兩個方向：(a) 併成一支共用的「跑子 agent N 次」黏合，吃一份 JSON 參數（agent、題目來源、答案去處）——那其實就是把 lib 的 `agent_tool.run_agent` 再往上包一層；(b) 各自縮成內嵌單子 `write.py`／`judge.py`，寫手、評審搬到頂層 `tools/`。**猜 (b)**：黏合格的 `fs_needs` 只有 `mount`，寫手一搬就空了。但要先看實跑：如果三次寫手改成平行、或加了「全不過就重寫」的迴圈，`write/` 就有自己的邏輯與狀態，那就留著。
5. **inst 單子的 `envs` key 能不能讓黏合格整個消失**：fsm 格的單子可以寫 `{"argv": ["aos-exec", "--ws", {"$env": "AOS_STACK", "$path": "writer/ws"}, "tools/writer"], "envs": {"AOS_STACK": {"$env": "AOS_STACK", "$path": "writer/"}}}`，一行就把子 agent 的 stack 與工作區都給對。少了的是「備題目、收答案、跑 N 次」——N＝1 時只剩備題目與收答案，可以搬進 brief（直接把 brief 寫進 `writer/ws/new/`）與 pick（直接去 `writer/ws/out/` 拿）；但那樣 brief 就得知道 write 的小格長相，跨格耦合，C-52 不喜歡。**猜不做**，除非實跑顯示 N＝1 就夠。
6. **寫手、評審、lint、data/ 不縮**：寫手與評審 `fs_needs: ["own_stack"]`（一隻 agent 一定是資料夾，第 5 級）；lint `tool_json`＋`mount`＋`callers: 2`；`data/` `git_tracked`＋`isolation`。
7. **反方向——會長的地方**：`judge/` 若實跑發現 judge 分數跟人工差太多，會長出「校準集」（人工打過分的草稿）當 few-shot，`data/` 多一個 `calibration/`；寫手若實跑發現三份草稿常常全同一句，`hint` 會長成一張「角度表」進 `data/`；Tier 2 若要走 LLM kernel 排隊（很多題同時跑），寫手與評審的 think 格 `exec` 改成 `aos-gate` 單子、`_metainfo` 寫在閘門寄出去的那張單子裡（M 02 § 5），資料夾樹不變。

一句話總結猜測：**六個格會剩兩個黏合格或零個；資料夾會從 11 個（不含 data 子夾）變成約 6 個——頂層、寫手、評審、lint、data、加寫手與評審各自的 idle 若也縮掉就更少。真正不能縮的是「有自己 stack 的」「要被兩處掛的」「要被 git 單獨追蹤或隔離的」三種，跟使用者說的「需要檔案系統特性的不縮」對上。**

---

## 附：跟既有原則對照（沒有硬衝突；擦邊的照原則選了）

- **P-11 題目是純文字**：我們的題目是 JSON。P 是慣例、不是規範；P-26 說參數形狀由程式自己的說明定。寫在 galtxt-a 的 README 就好。
- **P-08 標準三態**：頂層六態。P-08 自己說「要加狀態＝加一格」。
- **`_metainfo` 放在 `data/`（不是函數）**：M1 定義的是函數的屬性；使用者這次明說「每個資料夾都要有」，所以資料夾也放，`kind: data` 標明不是函數；kernel 不會去跑它，讀到也只是忽略多的 key（C-48）。
- **lint 從 `$AOS_WS/rules.json` 讀規則、check 用 `--ws $AOS_STACK` 叫它**：把頂層 stack 當 lint 的工作區。C-66「指標＝`AOS_WS`、呼叫者決定」、C-67「stack 放哪由呼叫方決定」都允許；lib 規則 4 正是這樣寫的。代價：lint 的說明要寫清楚「規則在工作區根的 `rules.json`」。
- **黏合格 import `lib/agent/agent_tool.py`**（realpath 找 `proto8/lib/agent`）：跟 lib/agent/pyfix 同一招；想完全自成一格就抄那 40 行。沒有原則擋，兩者都合規。
- **要帶給使用者的方向性問題**：沒有。範圍、benchmark、評分權重都是極小版先定死、拿實跑調的東西。
