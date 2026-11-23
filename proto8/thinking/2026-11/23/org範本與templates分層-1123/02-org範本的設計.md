org 範本的設計：一副骨架、九個選擇題、幾樣選用件；不附現成的 agent 定義；初稿全文在 `draft/orgs/`（英文），之後由範本位子搬進 `proto8/templates/`。

# 02 org 範本的設計

← [入口](README.md)｜依據：[01 四個樣本的總結](01-四個樣本的總結.md)｜初稿：[draft/orgs/README.md](draft/orgs/README.md)

## 結論

1. **範本是一夾文件，不是 agent**：抄進專案的 `wf/org/` 就是那個專案的 org 入口與角色卡，改幾個佔位詞、答九個選擇題就能用。
2. **一副骨架加選擇題，不做「小型工作室版」「多部門版」兩套**。理由在 01：三個樣本的差別是九個各自獨立的選擇，paper_readings 兩邊都不是；做兩套要維護兩份「要一樣」的檔。這是推薦，[04](04-要問使用者的題目.md) 第 2 題請使用者定。
3. **不附現成的 agent 定義，只附一段「指向角色卡」的系統文字**。理由在下面「要不要附定義」。04 第 3 題。
4. **內容用英文**（依據在下面「語言」）；角色卡抄過去之後用使用者的語言填。04 第 4 題。

工作用的名字：`templates/orgs/basic/`。`orgs` 是使用者說的；`basic` 是我取的，可以換（例：`studio`、`team`）。

## 檔案樹

```
templates/orgs/
  README.md              這一類範本是什麼、怎麼抄、佔位詞表、跟別的範本的關係、不做什麼
  basic/                 ← cp -r 這一夾到 <專案>/wf/org
    README.md            org 入口：跟 workflows 的分別、使用者說了什麼、成員表、標準流程、通則、Done when
    CHOICES.md           九個選擇題：每題兩三個選項與各自適合的情況，答案寫在「Ours:」後面，留著當紀錄
    places.md            東西放哪的問答表、寫入範圍只是約定（三層：文字、工具檢查、OS）、開位子、定義指向角色卡、共用資源
    letters.md           六種狀態、開工信七欄、做工具時的故障清單、回信怎麼寫
    lead/README.md       負責人的角色卡（四段，已填通用的部分）
    seat/README.md       空白角色卡（四段）；每個位子 cp 一份
    extras/              選用件，拿了就搬到定位、整夾刪掉
      README.md          每樣什麼時候拿、搬到哪
      system.seat.txt    位子的系統文字：你是誰、先讀哪些檔、衝突照角色卡、信與 git 的規矩
      site.txt           配給包的站台層：向誰回報、語言、只讀只寫哪裡
      helper/README.md   打雜工的角色卡（寫給掛它的人看）
      improvements.md    改進紀錄的格式與規矩（觀察 → 提案 → 狀態）
      gates.md           品質閘門表（每道誰把關、證據是什麼、至多幾輪）
```

13 個檔、約 36 KB；最大的 `CHOICES.md` 4.9 KB。

## 哪些是骨架、哪些選用

| 檔 | 誰需要 | 出自哪個樣本 |
|---|---|---|
| `README.md`、`lead/`、`seat/` | 所有 org | 三個有 org 的都有（01「都有的」第 1～3 條） |
| `letters.md` | 所有 org | arena 的 `letters.md`；aos 與 paper 引用同一套；狀態照知識庫 `aos/mailbox.md` |
| `places.md` | 所有 org | arena 入口的「東西放哪裡」、aos 的 `places.md` |
| `CHOICES.md` | 所有 org（答一次） | 01「互相矛盾的」九列，一列一題 |
| `extras/system.seat.txt` | 位子有自己的定義時 | arena 五份 `system.txt` 的共同部分 |
| `extras/site.txt`、`extras/helper/` | 用配給包掛打雜工時（小型工作室） | aos 的 `chore` 卡與 wf 配給包的站台層 |
| `extras/improvements.md` | 成員可以空閒時改進自己（多部門） | arena |
| `extras/gates.md` | 每件工作過同一串檢查（管線型） | paper 的 G0～G6 |

**不放進範本的**：部門的 `assets/`、留言板、回顧。它們是做了才長出來的，各家長得不一樣（arena 的規矩也是「部門一開始只有角色卡，有了長期產出才建 `assets/`」）；`extras/README.md` 用一句話提到。

## 要不要附現成的 agent 定義

**推薦不附**，只附 `system.seat.txt`。理由：

1. **三個樣本的定義沒有共同的形**：身體不同（eca、agent-fsm）、腦不同、抄法不同（arena 動態連結、paper 整份抄、aos 直接用出廠範本）。真正一樣的只有系統文字那一段。
2. **做一份定義本來就只要一步**：`agent_def new`（或 `cp -r` eca-claude）之後蓋上系統文字、設腦。
3. **附了就多一組「要一樣」的抄本**：`start-api`、`start-eca` 裡的抄本要靠 `tests/test_start.py` 逐檔比對才不走樣；org 範本再抄一份 agent-fsm 與 eca-claude，範本位子每次改都要多同步兩處。
4. 打雜工已經有配給包（`templates/kits/`），不必再做一份。

代價：抄範本的人要自己做定義（`orgs/README.md` 第 6 步寫了指令）。

## 跟現有東西的關係

- **`start-api`、`start-eca`**（起手範本）：起一棵樹。先有樹，才談 org。org 範本不起任何行程。
- **`daemon-sub`**：給專案一台自己的子 daemon（arena 的 `mine_arena`、這個 repo 的 `repo-aos` 都是這樣），位子掛在它底下。org 範本只在 README 指過去。
- **`agent-fsm`、`eca-claude` 等**：位子的身體。
- **`kits`（配給包）**：一種打雜工的系統文字加工具。它的說明寫著站台層「optional, not shipped」（`proto8/templates/kits/README.md`「Layers」）；org 範本的 `extras/site.txt` 就是補這一層的起手稿。這個 repo 自己的站台層在 `wf/workflows/dispatch/kits/site.txt`，不動。
- **知識庫**：`proto8/knowledge/aos/` 現在沒有講 org 的頁（`_index.json` 24 項裡沒有）；`proto8/knowledge/wf/`（wf 怎麼組織）只講 workflows 與 knowledge 兩種，沒有 `wf/org` 這一層。範本落地後要補，見 [05](05-施工清單.md)。

## 抄過去之後要改哪幾處

1. 答 `CHOICES.md` 九題（各檔標 `CHOICE n` 的地方填答案）。
2. 填佔位詞：`<PROJECT>`、`<LEAD>`、`<SEAT>`、`<AGENT>`、`<PATHS>`、`<TEMP>`、`<ASK_USER>`、`<AOS_CONTACT>`、`<FEEDBACK_FILE>`、`<LANGUAGE>`、`<N>`；小寫的 `<…>` 是要寫一句話的空格。`grep -rn '<[^>]*>' wf/org` 列出還沒填的。
3. 入口的「What the user said」貼使用者的原話。
4. 每個位子 `cp -r seat <名>` 填四段、成員表加一列。
5. 專案的 `AGENTS.md` 加一行指到 `wf/org/README.md`。
6. 做定義、掛 agent（範本不代做）。

## 語言

我看到的慣例是混的：`proto8/templates/` 裡給 AI 讀、會被整夾抄走的是英文（`agent-fsm`、`agent-python`、`eca-claude`、`eca-pi`、`tool-python`、`kits`、`kernel/kernel-python` 的 README），講怎麼裝怎麼起的是繁中（頂層 README、`daemon-root`、`daemon-sub`、`start-api`、`start-eca`、`kernel`、`judge-llm`、`reviewer`）。兩條成文的規矩：頂層 README 說 kits「檔案一律英文、中立」；`proto8/knowledge/docs/02-寫入與節點怎麼寫.md` 說「內容語言英文（AI 讀）」（那條管的是 `knowledge/aos`）。org 範本是給 agent 讀、會被抄走的，所以初稿用英文。

但四個樣本的角色卡全是繁中。英文範本抄過去之後，使用者自己的專案要嘛邊填邊改成中文、要嘛留英文骨架填中文內容。這是 04 第 4 題。

## 初稿沒做到的

- 英文沒有請第二個人看過；範本位子搬的時候要再讀一遍。
- 沒有測試。建議範本位子加 `templates/tests/orgs/test_orgs.py`，學 `tests/kits/test_kits.py`：沒有中日韓字與站台專有名詞、每檔不超過 8 KB、骨架裡的相對連結都指得到、大寫佔位詞跟 `orgs/README.md` 那張表一致。
- 沒有拿一個真的專案抄一次試填（05 的驗收步驟有這一步）。
- 兩份 `.txt` 沒有第一行說明：照 kits 的做法，整份會送給模型，說明放在 `extras/README.md`。
