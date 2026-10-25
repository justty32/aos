# galtxt-a 第四輪：收窄到一個性格×一個場景、樹中有樹、按子樹梯度一棵一棵固化（fable，2026-10-25）

← 上一輪 [round3.md](round3.md)（§ 12 步驟 1～6 已做完；7～9 由本輪改寫）｜實測 [round1-measure.md](round1-measure.md)｜收攏判準 [round2-collapse.md § 1](round2-collapse.md)｜經驗 [lessons.md](lessons.md)｜依據：[`_metainfo` 10-24](../../../thinking/2026-10-24-metainfo.md)（M1 `$ref`、M7）、[fn-grow 10-24](../../../thinking/2026-10-24-fn-grow.md)（六級）、[top-down 10-25](../../../thinking/2026-10-25-top-down.md)、[self-improve 10-24](../../../thinking/2026-10-24-self-improve.md)、[wf/STRUCTURE](../../../../wf/STRUCTURE.md)、C-55（值的雙形）、C-56（參數是表）、P-41（工具＝`tools/<名>/` 有 `tool.json`）、corpus 固化/04（槽填充模板）、06（開場收尾句庫）

給實作者照做。只寫規劃、不改程式。**以現在樹上的東西為準**（`train/` 四格、`train/optimize/`、`writer-sol/`、`human/`、`data/route.json`、`score.json` 的 `dims`、28 個綠測試）；round3 § 12 的步驟 7～9 作廢，換成本檔 § 11。

使用者 10-25 新方向（逐字；隊長中途轉來 6＋1 句）：
1. 「我這邊修改一下方向：把目標限縮到單一性格，單一場景。」
2. 「然後整棵樹的_metainfo收攏成一張表，不是一件好事，我想要的是一棵樹中有很多棵樹，嵌套再嵌套，這樣樹可以重複利用」
3. 「並且在進行改進時，_metainfo就是很好的依據。改進的時候可以只改進特定子樹。也就是根據各子樹的貢獻去做優化」
4. 「限縮角色設定，限縮故事背景。盡可能控制各種變量，然後我預期子樹會很深層...，因爲最終目標是讓整棵樹都不依靠LLM」
5. 「一個節點，一開始可能是agent，後來慢慢優化，不管是爲了token消耗量，還是可確定性或效能，他會逐漸變成普通程式」
6. 「遇到程式處理不了的輸入...，想想看，我們在做機器學習的時候是怎麽處理的？反正就是持續優化持續訓練」
7. 「從agent變成程式...一開始是agent，然後在優化過程中，agent會把一些功能或環節做成工具，這樣這個agent節點的確定性就會上升。之後持續積累，直到整個都變成程式。」
8. 「那當然，做出來的工具也可以是另一個agent。然後優化的時候，那個所謂的"梯度"，也就是確定性提升的幅度，可以分配給這些工具。」
9. 「梯度，我剛剛說是"確定性"。但這就跟metainfo一樣，可以是任意東西，甚至不一定要是數值。好比傲嬌方面的臺詞評級這類」
10. 「這個判斷用的，就是可以弄另一棵樹來做了。就像我先前說的那套一樣」
11. 「判斷器本身也可以被優化。優化器也是。所以，一大堆樹！」（頂層：不加新東西，照上面做最小示範；要回答「一大堆樹互相評、互相改，森林的錨在哪」→ § 5.6）

先前仍有效：結構化評分照 STRUCTURE 長、優化函數自己也是樹也有評級、塔停在第 2 層、人評 ≤ 6 筆只校正、腦只用 LiteLLM gpt 系列、控 token、**反向收攏不急（只併真空殼）**。

---

## 0. 一句話

只做**宮澤柚葉（精簡卡）× 教室・文化祭收攤（固定）**，題目只在兩個開關上變（小動作、fill／scene）。最終目標是**整棵樹不靠 LLM**：腦是鷹架，優化的主方向變成「把用腦的子樹一棵一棵換成純程式、分數不掉、token 往 0」。每棵有 `_metainfo` 的資料夾是一棵子樹，對外描述＝作者的 `_metainfo` ＋ 四種量出來的旁檔（`ratings.json` 評級、`stage.json` 固化到哪階、`grad.json` 梯度＝這棵對外描述的結構化 diff、`rollup.json` 直接子樹的彙總）；彙總由純程式 `meta/rollup` 沿被改那棵往上算、不看孫子。優化器每步只挑一棵、做一個動作（抽一個工具／換階／開關／蒸餾難例），diff 整筆算在那棵（或它抽出的那個工具）頭上；非數值的 diff 誰重誰輕由第三棵小樹 `train/weigh/` 判（它自己也從 agent 往規則表固化）。這圈實際走完：**寫手** agent → 半固化（抽 `beat`、`voice` 兩個工具）→ 純程式（0 token），收難例、蒸餾一次；**判斷器** agent → 規則表。

---

## 1. 收窄（控制變量）

### 1.1 一個角色、一個場景、兩個開關

| 固定的 | 內容 | 落在哪 |
|---|---|---|
| 角色（精簡卡） | 宮澤柚葉：傲嬌；特質三條（嘴硬心軟、先否認再讓步、被戳中音量翻倍）；口癖（哼／才不是／才沒／真是的／隨便你啦）；稱呼 rank 2（叫主角「你／喂」、被叫「宮澤」）；小動作三條（別過臉耳根紅、撥瀏海看窗外、踮腳）；NG（直白說喜歡、真的惡毒、冒煙／跺腳） | `data/cast.json` 柚葉（已有，照這份**刪到剩上面這些**，其他 likes／habits 留 corpus 不進卡） |
| 場景 | 教室、文化祭閉幕後的黃昏、十月、rank 2、intent 餘溫、主角＋柚葉、事件「文化祭收攤」 | `train/set.json.scope`（§ 1.2）；地點卡 `教室` 已有 |
| 評分尺 S | § 1.3 的傲嬌細項 | `data/dims.json` |

| 開關（題目只在這兩個上變） | 值 | 用途 |
|---|---|---|
| `mode` | `fill`（Q16，一行，有正解）／`scene`（5～10 行） | fill 量「那一句」、scene 量旁白洩底與多樣性 |
| 小動作 `detail` | `ribbon`（拆彩帶、捲一段塞書包）／`poster`（撕海報、嘴上丟手卻折好）／`lights`（關燈卻站窗邊） | ribbon、poster 訓練；**lights 永遠 held-out** 驗證 |

為什麼選教室收攤不選河鹿堂提書包：Q16 有正解與評分要點 (a)(b)(c)，純程式量法可以拿正解校對；fill 一行人評最便宜；地點卡已有。河鹿堂那題（`scene-yuzuha.json`）留著不刪、不再進訓練。

### 1.2 保留但不再用、要改的設定

| 東西 | 處理 |
|---|---|
| 晴子全套（cast／styles／samples／河鹿堂／Q01／`scene.json`／假腦文靜模板）、`scene-yuzuha.json` | **留、不刪、不改**：`test_scene`／`test_fill_q01`／`test_route` 照舊綠（round2 收攏證明靠它們）。 |
| `writer-sol/` | **留、凍結**（控制變量：模型固定 luna-low；變體是另一個變因）。`set.json.writers` 改成 `["writer"]`；`route` 動作從優化器動作表拿掉；`data/route.json` 形狀不變、`by_style` 空。 |
| `human/samples.json`（假腦 6 筆混晴子） | 刪掉讓 `rate.py` 重挑（程式產出，不是作者寫的）。 |
| `train/set.json` | `{"train": ["cls-ribbon.json", "cls-poster.json"], "verify": ["Q16.json", "cls-lights.json"], "measure": "Q16-fixed.json", "writers": ["writer"], "scope": {"style": "傲嬌", "place": "教室", "event": "文化祭收攤", "cast": ["佐伯悠", "宮澤柚葉"]}}`；`rate.py`／`verify.py` 讀到 `score.json.style ≠ scope.style` 就 `StateBad`（收窄用程式守，不靠人記得）。 |
| `train/budget.json` | § 7.4：`max_epochs 4`、`max_calls 180`、`max_tokens 500000`、`max_elapsed_ms 1500000`、`min_gain 0.25`、新 `min_loss 0.25`（固化後允許掉多少）。 |
| `train/optimize/policy.json` | `dims_to_action` 換成 § 5.3 的 `actions`（按子樹的動作表）；`min_gap` 留。 |
| `human/questions.json` | § 8.2。 |
| `score.json` 的 dims | § 1.3；`total` 對有 profile 的風格改加權（§ 1.4）。 |
| 新表 | `data/dims.json`（評分結構）、`data/hints.json`（寫手角度，從 `write.py` 的 `HINTS` 搬出）、`data/lint_switches.json`（lint 規則開關）、`data/templates.json`（固化用：收攤場景的句式／槽，從 corpus 固化/04、06 抄、只抄這個場景）。 |

### 1.3 傲嬌的評分細項（S；每個維度恰好一支程式或一行 rubric 量它）

從 corpus 抽：固化/01 § 1 傲嬌、固化/05「彆扭／傲嬌」段＋§ 三言行反差矩陣、人物/宮澤柚葉.md「性格表／裡」「口頭禪／小動作」、評測 Q16 評分要點 (a)(b)(c)。

| 維度 | 定義（出處） | 誰量 | 算法 | 值 |
|---|---|---|---|---|
| **反差** | 先否認（強）→ 讓步（弱）→ 補遮掩（01 § 1 節奏；Q16 (a)） | lint 純程式 | 柚葉對白：否認標記（才不是／才沒／哼／別誤會／又沒有）→ 0.5；讓步標記（不是不能／也不是不／還算／偶爾／隨便你／算了／沒說不行）在否認**之後** → 再 0.5；順序反只 0.5 | 0／0.5／1 |
| **洩底** | 旁白補真心（05 § 三；人物卡小動作） | lint 純程式，**scene 模式**（fill＝`null`） | 旁白行提柚葉＋洩底詞（別過／耳根／紅／瀏海／窗外／踮／描／偷瞄／手卻／沒走／小聲）→ 1；有旁白沒洩底 → 0.5；無旁白 → 0 | 0～1 |
| **語域** | 既有 Tier 1（稱呼階、口氣、NG 標記）＋ OOC 字面（冒煙／跺腳／////／喜歡你／我喜歡）扣 `OocMark` | lint | `tier1 ÷ 2` | 0～1 |
| **承接** | 接前文、鋪後文（既有 Tier 2 改名） | 評審腦 | `承接：N ÷ 3` | 0～1 |
| **像柚葉** | 嘴硬、節奏快、逞強是保護色；不坦率、不惡毒（Q16 (c)） | 評審腦（新行） | `÷ 3` | 0～1 |
| **文筆** | 句子漂亮、不油、留白、字數節制 | 評審腦（新行） | `÷ 3` | 0～1 |
| 護欄 | Tier 0 | lint | 沒過＝total 0 | 0／1 |
| 多樣性 | 三份兩兩二元組重疊（整題） | pick | 不變 | 0～1 |
| ★**一致** | 同輸入同角度跑 3 次的兩兩二元組相似（§ 4.2 的確定性） | pick（`hints_fixed` 的題才算） | `1 − 多樣性` | 0～1 |

純程式：反差、洩底、語域、護欄、多樣性、一致（字面標記＋順序，確定性）；腦：承接、像柚葉、文筆。評審 rubric（`grader/system.v2.txt`，`system.txt` 改捷徑指它；v1 留檔不進候選）：三個分各一行＋理由一行，`judge.py` 正則多兩條、缺行＝那維度 `null`（舊回覆、假評審相容）：

```
你是日和町 galgame 台詞的評審。題目給你場景條件（或挖空題的前後文）和一份草稿，格式、禁語、稱呼已有程式檢查過，你只評下面三項，各 0～3：
承接：3＝接前文、鋪後文、情緒對；2＝大致對但一處生硬；1＝勉強接上、情緒偏；0＝接不上或跑題。
像柚葉：這是宮澤柚葉（傲嬌、文藝社、嘴硬心軟、逞強是保護色）。3＝就是她會說的：嘴硬、節奏快、不坦率但藏不住；2＝像傲嬌但不特別像她；1＝口氣偏掉（太軟、太坦率、或真的惡毒）；0＝出戲。
文筆：3＝句子漂亮、留白、字數節制、不油；2＝通順但平；1＝囉嗦或說太滿；0＝油膩、賣萌符號、直球告白。
基調紅線：不油膩、含蓄、只用日和町的設定；碰紅線三項各最多 1 分。
只回四行，不要別的字：
承接：N
像柚葉：N
文筆：N
理由：一個短標籤
```

假評審三個分固定 2；假寫手技能表不變（luna 寫傲嬌加「～～」→ 語域 0.5）；假腦傲嬌模板的「留白」角度本來就漏否認標記 → 那份 `反差` 0.5——三份 dims 天生不同，離線驗得到「維度分得出差」。

### 1.4 `total` 怎麼算（`data/dims.json`）

```json
{"source": "評分結構（round4 § 1.3）：一維度一行——誰量（by）、權重、只在哪種模式有（modes）、改哪棵子樹才動得了它（moved_by）；pick 讀：風格在 profiles 裡＝total 是 5 × Σ(weight×值)/Σweight（null 的維度不進分母），不在＝舊公式 Tier 1＋Tier 2；權重只有人改、優化器不准碰（改了＝改損失函數）",
 "profiles": {"傲嬌": {"反差":   {"by": "tools/lint", "weight": 2, "moved_by": ["writer"]},
                      "像柚葉": {"by": "grader",     "weight": 2, "moved_by": ["writer"]},
                      "承接":   {"by": "grader",     "weight": 1, "moved_by": ["writer"]},
                      "文筆":   {"by": "grader",     "weight": 1, "moved_by": ["writer"]},
                      "語域":   {"by": "tools/lint", "weight": 1, "moved_by": ["writer", "tools/lint"]},
                      "洩底":   {"by": "tools/lint", "weight": 1, "modes": ["scene"], "moved_by": ["writer"]}}},
 "question_dims": {"多樣性": {"by": "pick", "moved_by": ["."]}, "一致": {"by": "pick", "only": "hints_fixed", "moved_by": ["writer"]}},
 "gate": "護欄（Tier 0）不是維度：沒過＝total 0"}
```

`total` 仍 0～5 → `rate.py` 門檻（4.0／3.0／3 份）與 `min_gain` 不動；文靜不在 `profiles` → 舊公式 → 既有測試的 `total` 一字不變。`pick.py`／`rate.py`／`verify.py` 對 dims 一律照表走、不寫死維度名。假腦下傲嬌 fill 三份 ≈ 3.7／3.7／3.0（平均 ≈ 3.45 ok）；round3 測試裡斷言 `good`／`ok` 字面的改成斷言關係。

---

## 2. 最終目標：整棵樹不靠 LLM——節點生命週期與固化進度

### 2.1 腦是鷹架：固化階梯套在「節點」上

corpus 固化/README 的階梯（腦寫 → 模板＋槽 → 規則）這裡變成**每個節點自己的生命週期**，同一資料夾、同一對外介面（呼叫方 `write.py` 一字不改，仍 `run_agent("writer", …)`，仍收 `ws:out/<題名>`）：

| 階 | `stage` | 長相（以寫手為例） | 腦做什麼決定 | token／題 | 確定性 |
|---|---|---|---|---|---|
| 0 | `agent` | agent-dan 範本：腦讀 brief、自己寫、叫 lint 自檢 | 全部（開場、節拍、口癖、收尾） | 3 份 × 7k ≈ 21k | 低（同輸入三次三樣） |
| 1 | `semi` | 腦還在，但**環節抽成 `tools/`**（`beat` 反差節拍、`voice` 口癖與句尾、`lint`）：腦叫工具、不自己想那段 | 只剩「選哪個節拍槽、填什麼遮掩句、要不要旁白」 | 腦叫工具多一來回：每份 +1 次、≈ +1.5k；**半固化階段 token 可能先升** | 中（工具那段固定） |
| 2 | `program` | `compose.py` 照固定順序叫 beat → voice → lint，殼拿掉；腦 0 次 | 無 | 0 | 1.0 |

**殼拿掉**＝`writer/_entry` 照 `stage.json.stage` 分流：`agent`／`semi` → `exec aos-loop loop.json`（原本）；`program` → `python3 compose.py`。兩套都留在資料夾裡（agent 的 `fsm.json`／`brain.py`／`act.py`／`system.txt`，program 的 `compose.py`），**前後版本都在，git 另有歷史**。回滾＝`stage.json` 改回。

一個該提的事實：**假腦已經是固化第 2 階**——`brain.py` 的 `compose()`（模板＋槽填充，固化階梯第 3 級）就是 `compose.py` 的第一版；真腦跑的是 agent、假腦跑的是 program。所以「寫手固化」的實作是把 `compose()` 搬出來、照 `data/templates.json` 走、加難例紀錄，不是從零寫。

### 2.2 `stage.json`（每棵用腦的子樹一份；`_metainfo` 用 `$ref` 併進）

```json
{"source": "train/optimize 改 stage／tools（動作 extract、stage），train/verify.py 補 history 的數字；人不手改；_metainfo 的 brain 指這份",
 "stage": "semi", "since_epoch": 1, "why": "determinism",
 "tools": ["lint", "beat"],
 "tools_share": 0.5, "decisions_left": ["選開場旁白", "填遮掩句", "要不要收尾旁白"],
 "history": [{"epoch": 0, "stage": "agent", "tools": ["lint"], "llm_tokens": 7000, "llm_calls": 2, "determinism": 0.3, "val": "ok", "total_avg": 3.45},
             {"epoch": 1, "stage": "semi",  "tools": ["lint", "beat"], "llm_tokens": 8500, "llm_calls": 3, "determinism": 0.55, "val": "ok", "total_avg": 3.5}]}
```

`tools_share`＝這棵的環節裡幾成已是工具（環節清單人寫在 `_metainfo.steps: ["開場旁白", "反差節拍", "口癖句尾", "遮掩句", "收尾旁白", "自檢"]`，`tools_share`＝有工具負責的 ÷ 總數）；`decisions_left`＝腦還在做的決定（`steps` 減掉有工具的）。`why` ∈ {`token`, `determinism`, `speed`}＝這次換階是為了哪個（優化器挑時最差的那個）。

### 2.3 整棵樹的腦用量（訓練成果除了分數也看它往 0 走）

根 `ratings.json.style:傲嬌` 多一格 `brain`、根 `rollup.json` 多一節：

```json
"brain": {"llm_calls_per_question": 9, "llm_tokens_per_question": 27000,
          "nodes": {"writer": "semi", "grader": "agent", "train/weigh": "agent", "tools/lint": "program", "tools/beat": "program"},
          "counter_on_brain": 3, "counter_program": 2}
```

verify 每個 epoch 印一行 `train: epoch 2 score 3.6 (Δ −0.1) tokens/題 27000 → 7200 on_brain 3 → 2`。**成功判準**（§ 4.4 判斷器用）：分數不掉超過 `min_loss`、token 往下、`counter_on_brain` 往下。

### 2.4 子樹會很深（草圖；這圈只長到 `writer/tools/*`）

```
writer/                              semi → program
├─ tools/lint → ../../tools/lint     program（已固化）
├─ tools/beat/                       反差節拍：{deny, yield, cover} 三槽 → 一行；program（這圈抽出）
│  └─（日後）tools/deny/ tools/yield/ tools/cover/   各自從句庫挑一句；可以先是小 agent（使用者 8：工具也可以是 agent）
├─ tools/voice/                      口癖插入＋句尾＋稱呼：一行 → 一行；program（這圈抽出）
└─（日後）tools/open/ tools/close/   開場／收尾旁白（固化/06 句庫）
grader/                              agent → （日後）semi：承接用 bigram 接前文、像柚葉用 lint 的反差＋語域、文筆用字數與留白規則
train/weigh/                         agent → rules（這圈走完）
```

**反向收攏不急**：round2 判準這圈只併「真空殼」（A-1 純容器、B-4 同內容葉片）；有旁檔的子樹不縮（N-4，§ 3.5）；`tools/beat/` 即使只有 `_entry`＋`tool.json`＋`_metainfo` 也留（P-41 工具要資料夾）。

---

## 3. 樹中有樹

### 3.1 什麼是子樹

**有自己 `_metainfo` 檔的資料夾**＝子樹（可 `cp -r`／捷徑／`$ref` 到別處的單位）。不是：內嵌單子的格（root 五格、train 的格；第 0 級，是上一層的身體）、純容器 `tools/`。這棵樹的子樹：根、`idle/`、`tools/lint/`、`writer/`（＋ `writer/tools/beat/`、`writer/tools/voice/`★）、`writer-sol/`（凍結）、`grader/`、`data/`（＋ `bench/`）、`human/`（＋ `import/`）、`train/`（＋ `optimize/`、`weigh/`★）、`meta/`（＋ `metatable/`、`collapse/`、`rollup/`★）。

### 3.2 對外描述＝`_metainfo` ＋ 四種旁檔

| 部分 | 檔 | 誰寫 | 內容 |
|---|---|---|---|
| 作者宣告 | `_metainfo` | 只有作者（M7） | 九軸＋ kind／grow_level／reads／writes／fs_needs／callers；`children`（只列直接子樹）；★`steps`（環節清單，用腦的子樹才有）；指旁檔的 `$ref` |
| 評級 | `ratings.json` | `train/rate.py`（寫手、評審）、`train/verify.py`（根） | `style:傲嬌`：`val`、`score_avg`、`score_min`、`counter_samples`、`dims`（§ 1.3 全部）、★`determinism`、★`cost {llm_calls, llm_tokens, time_ms}`（每跑一次實測）、★`tags`（評審 `理由` 標籤計數，非數值梯度的來源）、`rated_at`、`rated_by`；檔頂層 `scope` |
| 固化進度 | ★`stage.json` | `train/optimize`（stage／tools）、`train/verify.py`（history） | § 2.2 |
| 梯度 | ★`grad.json` | `train/verify.py`（每步）、`train/optimize`（分配給工具時拷） | § 4.1 |
| 人評 | `human.json` | `human/import` | round3 § 16.3；量的子樹多 `dim:<維度>` 格（§ 8.3） |
| 彙總 | ★`rollup.json` | `meta/rollup` | § 3.3 |

`_metainfo` 多的行（作者一次寫；檔要先在，不然 `$ref` 懸空）：`"ratings": {"$ref": "ratings.json"}, "brain": {"$ref": "stage.json"}, "grad": {"$ref": "grad.json"}, "human_ratings": {"$ref": "human.json"}, "rollup": {"$ref": "rollup.json"}`。哪棵有哪幾個：`writer/`、`grader/`、`train/weigh/` 五個全有；`tools/beat/`、`tools/voice/`、`tools/lint/` 有 `grad`、`rollup`（工具收分配來的梯度）；根有 `ratings`、`rollup`；`train/optimize/` 有既有 `ratings`＋`rollup`；其餘只有 `rollup`（rollup 跑過才加 `$ref`）。

**對外描述範例**（`writer/`，解開 `$ref` 後；數字是估）：

```json
{"summary": "寫手：照 brief 寫一份台詞…", "kind": "agent", "grow_level": 5, "steps": ["開場旁白", "反差節拍", "口癖句尾", "遮掩句", "收尾旁白", "自檢"], "…九軸…": "…",
 "ratings": {"scope": {"style": "傲嬌", "event": "文化祭收攤"},
             "style:傲嬌": {"val": "ok", "score_avg": 3.5, "score_min": 3.0, "counter_samples": 6, "determinism": 0.55,
                           "dims": {"反差": 0.83, "洩底": 0.5, "語域": 0.5, "承接": 0.67, "像柚葉": 0.67, "文筆": 0.67, "護欄": 1.0, "多樣性": 0.31},
                           "cost": {"llm_calls": 3, "llm_tokens": 8500, "time_ms": 6000},
                           "tags": {"承接自然": 4, "太直白": 1, "口氣不像": 1}, "rated_at": "…", "rated_by": "train/rate.py epoch 1 @ …"}},
 "brain": {"stage": "semi", "tools": ["lint", "beat"], "tools_share": 0.33, "decisions_left": ["選開場旁白", "填遮掩句", "口癖句尾", "收尾旁白"], "history": ["…"]},
 "grad": {"steps": [{"epoch": 1, "action": "extract", "target": "tools/beat", "diff": {"brain.stage": ["agent", "semi"], "determinism": 0.25, "cost.llm_tokens": 1500, "dims.反差": 0.17, "tags": {"+": ["嘴硬心軟"], "-": []}}, "accepted": true}]},
 "rollup": {"children": {"tools/beat": {"kind": "program", "grad_total": {"determinism": 0.25, "cost.llm_tokens": 1500}}, "tools/lint": {"kind": "捷徑"}},
            "val": "ok", "stage": "semi", "cost": {"per_run": {"llm_tokens": 8500}, "declared": {"llm_tokens": 6000}}, "rolled_at": "…"}}
```

### 3.3 彙總規則（誰算、看什麼、何時）

- **誰算**：`meta/rollup/_entry`（純程式、標準庫、~120 行）：`rollup [--up] [--dry-run] [--json] <子樹>`。讀那棵的 `_metainfo`（解一層 `$ref`）、它的旁檔、**每個直接子樹的 `rollup.json`**（沒有就退而讀那子樹的 `ratings.json`／`stage.json`／`grad.json`；再沒有只列 `kind`）→ 寫自己的 `rollup.json`。`--up` 一路做到沒有 `_metainfo` 的上一層（樹根）。`_metainfo` 一字不碰。錯：`RootMissing`／`MetainfoBad`／`RefBad` 退 1、不寫。
- **只看直接子樹**：根的 `children.train` 只有 `train/rollup.json` 給的一行（底下 optimize、weigh 已被 train 自己彙總）；根不打開 `train/optimize/`。
- **成本**：葉片 `cost.per_run` 來自 `ratings.json.cost`（rate.py 從小格 `usage.jsonl`／`trace.jsonl` 算）；根的 `per_question` 直接拿 `verify.json.usage ÷ 題數`（實測，rollup 不做乘法——每題叫幾次子樹從宣告算不出來）；`role: dev` 的子樹標 `excluded_from_cost`；`declared` 並排 `_metainfo` 的 `val`，差兩倍以上 stdout 印 `rollup: DeclaredOff writer llm_tokens 6000 vs 8500`（只印，M7）。
- **腦用量**（§ 2.3）：`brain.nodes` 從直接子樹的 `stage.json.stage`（沒有 `stage.json` 而 `resource` 含 `llm` ＝ `agent`；不含＝ `program`）收；上一層再把子樹 rollup 的 `brain.nodes` 攤平成 `子樹/孫` 的名字（這是唯一「看到孫子」的地方，但看的是子樹 rollup 給的摘要，不是孫子的檔）。
- **何時**：rate.py 寫完評級 → `rollup --up writer`、`--up grader`；verify.py 寫完根評級、被改子樹的 `grad.json` → `rollup --up <被改那棵>`；optimize 分配梯度給工具後 → `rollup --up writer/tools/beat`；人改 `_metainfo` 後自己跑。**沒被改的子樹 bytes 不變**（測試驗）。冪等：同輸入除 `rolled_at` 全同；git 追蹤，`git diff rollup.json` 就是對外數字的歷史。

### 3.4 搬去別棵樹／被多處引用時描述怎麼跟著走

| 情形 | 怎麼走 |
|---|---|
| `cp -r writer/ 別樹/` | 旁檔在資料夾裡，跟著走。`ratings.scope`、`grad.context.tree` 寫著「在 galtxt-a、傲嬌×教室收攤下量的」——**別樹的讀者看到 `context.tree ≠ 自己的樹根名` 就把 `grad` 當 `foreign`（列出、不拿來選）**；`ratings`、`stage` 照用（評級與固化進度是「它會什麼、到哪階」，可帶走；梯度是「它在這棵樹裡這一步值多少」，要重量）。`writer/tools/*` 是它的子樹，一起走；`writer-sol/` 要連 `writer/` 一起（相對捷徑，C-61）。 |
| 被多處捷徑指（`idle` 三處、`tools/lint` 兩處） | 真身一份旁檔；`callers` 合計；rollup 走到捷徑不進去，`children` 列 `捷徑 → ../idle`。 |
| `_metainfo` 用 `$ref` 陣列引用底稿（M1 § 5） | 底稿裡的相對 `$ref`（`"ratings.json"`）要從**底稿所在資料夾**算，不是最外那份——rollup／optimize 解 `$ref` 的那十行照這條做（先解底稿、把底稿裡的相對 `$ref` 接上底稿的資料夾、再合 key）。 |
| 整棵 galtxt-a 被放進更大的樹 | 根的 `rollup.json`＋`ratings.json` 就是上一層 `children.galtxt-a` 那行的來源；上一層不打開它。 |

### 3.5 跟六級成長／反向收攏怎麼接

- 旁檔是第 4 級的伴隨檔：有 `ratings`／`stage`／`grad`／`rollup` 的函數至少第 4 級——「被評過級、量過梯度的東西就是一個單位」。第 0～2 級沒旁檔，數字算在上一層那棵頭上。
- 往上長（格 → 資料夾；agent 抽工具＝`tools/<名>/` 從無到有）：`_metainfo` 從單子搬成檔、旁檔從無開始，下一次 rate／verify 自然長出來；上一層 rollup 下次重算多一行 `children`。
- 往回縮：round2 判準加 **N-4：有旁檔的不縮**；人硬要縮：把 `val`／`stage`／`grad_total` 寫進上一層 `rollup.json.children[<名>]` 加 `collapsed_from`、刪旁檔、再 collapse（人手）。`metatable --suggest` 候選表加「N-4」欄。
- 節點生命週期跟六級的關係：`agent → semi → program` 是**同一級（第 5 級資料夾）裡面的內容在換**，不是降級；固化完的 `writer/` 仍是資料夾（有 `compose.py`、`tools/`、旁檔）。只有工具也全成了純表（例：`beat` 退化成一張 `templates.json` 查表）才可能縮成 JSON（B-3），這圈不做。

---

## 4. 梯度＝對外描述的結構化 diff；確定性怎麼量；怎麼分配給工具；非數值怎麼比

### 4.1 `grad.json`

梯度不是一個數：**這一步改動前後，這棵子樹對外描述（`ratings`＋`stage`）的 diff，跟 `_metainfo` 同形**——數值鍵是差（`determinism +0.25`、`cost.llm_tokens −7000`）、非數值鍵是 `[舊, 新]`（`val ["ok", "good"]`、`stage ["semi", "program"]`）、集合是 `{"+": [...], "-": [...]}`（`tags`）。

```json
{"source": "train/verify.py 每步寫（優化器這步只改這棵，驗證前後的 ratings／stage diff 整筆算它的）；optimize 把 extract 那步的 diff 拷給被抽出的工具（assigned_from）；人不手改",
 "scope": "傲嬌×教室收攤", "context": {"tree": "galtxt-a", "verify": ["Q16.json", "cls-lights.json"], "S": "data/dims.json 傲嬌"},
 "steps": [
  {"epoch": 1, "action": "extract", "target": "tools/beat",
   "before": {"stage": "agent", "determinism": 0.3, "val": "ok", "total_avg": 3.45, "cost": {"llm_tokens": 7000, "llm_calls": 2}, "dims": {"反差": 0.67}, "tags": ["承接自然", "太直白"]},
   "after":  {"stage": "semi",  "determinism": 0.55, "val": "ok", "total_avg": 3.5,  "cost": {"llm_tokens": 8500, "llm_calls": 3}, "dims": {"反差": 0.83}, "tags": ["承接自然", "嘴硬心軟"]},
   "diff":   {"stage": ["agent", "semi"], "determinism": 0.25, "val": null, "total_avg": 0.05, "cost.llm_tokens": 1500, "cost.llm_calls": 1, "dims.反差": 0.17, "tags": {"+": ["嘴硬心軟"], "-": ["太直白"]}},
   "weigh": {"choice": "A", "reason": "確定性升、分沒掉；token 升是半固化的過渡", "by": "train/weigh epoch 1（agent）"},
   "accepted": true, "confidence": "ok", "measured_at": "…"}],
 "sum": {"determinism": 0.25, "cost.llm_tokens": 1500, "total_avg": 0.05}, "counter_steps": 1, "counter_accepted": 1, "counter_rolled_back": 0}
```

`confidence`：腦量的維度（承接／像柚葉／文筆／total）σ_Δ ≈ 0.3（round1-measure：評審 σ ≈ 0.5／份、6 份平均、兩次相減）；`|total_avg| < 0.3` 標 `low`。純程式的（反差、洩底、語域、確定性、token）沒雜訊、永遠 `ok`——**判斷器優先看這些**。

### 4.2 確定性怎麼量

`set.json.measure: "Q16-fixed.json"`＝`{"mode": "fill", "bench": "Q16", "drafts": 3, "hints_fixed": true}`：`write.py` 看到 `hints_fixed` 三份都用 `hints[0]`（同輸入、同角度跑 3 次）；pick 對這題多算 `dims.一致`＝1 − 多樣性（兩兩二元組 Jaccard 的平均）。verify 每個 epoch 跑它一次（agent 27k；program 0），`determinism` 寫進寫手 `ratings.json`、`stage.json.history`。`program` 階數學上 1.0（確定性程式）；`semi` 階介於中間（工具那段固定、腦那段還飄）。另記 `dims` 的三份標準差（`dims_std`）當第二個確定性指標，只記不比。

### 4.3 梯度怎麼分配給工具

- 一步只做一個動作，所以**那一步的 diff 整筆歸它**：`extract tools/beat` → 這筆 diff 同時寫進 `writer/grad.json.steps`（節點自己的）與 `writer/tools/beat/grad.json`（`assigned_from: "writer", step_epoch: 1`）——工具的「貢獻」＝它被抽出時讓上層確定性升多少、token 變多少、哪些標籤多了少了。
- `stage → program` 那步沒有新工具：diff 寫進 `writer/grad.json`，並**按各工具被叫次數分攤**給 `tools/*`（`assigned_share`；這步的 token 歸零大半是「殼拿掉」的功勞，分攤只是讓每個工具的 `grad_total` 能排序）。
- 上層（寫手）的 `rollup.children.tools/*.grad_total` 列每個工具累計的分配；**優化器下一步優先固化「梯度大（確定性升多、token 降多）、成本低（抽它只是查表、不多一次腦）」的那條**：排序鍵＝`(determinism_gain + tokens_saved/10000) ÷ max(cost_to_extract, 1)`，`cost_to_extract` 人填在候選工具表（§ 5.3）。
- **要實際量一次**（§ 7.3 的示範會量到）：epoch 0 agent 的 `determinism`；抽 `beat` 後；抽 `voice` 後；`program` 後——四個數＋三筆 diff；真腦數字記進 `round4-measure.md`。

### 4.4 非數值梯度怎麼比、誰判：第三棵樹 `train/weigh/`

同一步的 diff 裡會有 `determinism +0.25`、`cost.llm_tokens +1500`、`val ok→ok`、`tags +嘴硬心軟`——哪個重？使用者 10：「弄另一棵樹來做」。

`train/weigh/`（判斷器；agent-dan 範本、沒有工具；自己的 `_metainfo`、`stage.json`、`ratings.json`、`human.json`、`rules.json`、`log.jsonl`）：

- **介面**：題目＝兩份 diff（A＝這一步的 diff，B＝「不動」＝全零／全 null）＋ `rules.json`（優先序，人寫）；回兩行 `選：A|B`、`理由：短標籤`。被 `verify.py` 叫（取代現在 `delta ≥ min_gain` 那個純量規則）：選 A＝接受、選 B＝回滾。每次判斷一行追加 `weigh/log.jsonl {epoch, subtree, action, diff, choice, reason, by}`。
- **`rules.json`**（它的第一版固化目標；agent 階當 prompt 裡的指引，`rules` 階直接照表）：
  ```json
  {"source": "判斷兩份梯度 diff 誰好的優先序（人寫第一版；train/weigh 固化成 rules 階後只照這份）",
   "reject_if": [{"key": "dims.護欄", "lt": 0}, {"key": "bench.guard_hit", "drops": true}, {"key": "val", "drops": true, "unless": {"key": "cost.llm_tokens", "to_zero": true, "and": {"key": "total_avg", "ge": "-min_loss"}}}, {"key": "total_avg", "lt": "-min_loss"}],
   "prefer": [{"key": "val", "rises": true}, {"key": "cost.llm_tokens", "le": -0.3, "relative": true}, {"key": "determinism", "ge": 0.1, "only_if_before_lt": 1.0}, {"key": "total_avg", "ge": "min_gain"}, {"key": "tags.+", "contains_any": ["嘴硬心軟", "承接自然", "有留白"]}],
   "tie": "B"}
  ```
  意思：護欄掉、Q16 的 `guard_hit` 從中變沒中（外部錨，§ 5.6）、分掉超過 `min_loss` 一律回滾；評級掉一級只有「token 歸零且分沒掉太多」才准（固化的交換條件）；其餘照序：評級升 > token 省三成 > 確定性升 0.1（固化後恆 1.0 就不算這條）> 分升 `min_gain` > 好標籤多了；都沒有＝選 B（不動）。半固化階 token 升不在 `reject_if` 裡——**過渡期允許 token 升，條件是確定性升**（§ 2.1 說的）。diff 裡因此要帶 `bench.guard_hit`、`bench.bigram_overlap`（verify 從 Q16 的 `score.json.bench` 取）。
- **生命週期**：`stage.json` `agent`（真腦：讀兩份 diff 與 rules 回答；假腦：直接照 `rules.json` 算＝它的 program 階）→ `rules`（`_entry` 分流到 `rules.py`，0 token）。這是本圈**第二個實際走完 agent → 程式的節點**（小、便宜：一次 1 行輸入、≈ 1.5k token）。
- **它自己的成果／梯度**：不自評。`human/import` 拿人評的配對（§ 8.1 的 `pair-epoch`：人說前／後哪份好）對 `log.jsonl` 同一步的 `choice` 比 → `weigh/ratings.json` `judge:accept` 格 `{counter_judged, counter_confirmed, agreement, rated_by: "human/import"}`；下一個 epoch 的驗證分若跟它的判斷反向（它選 A、下一步分掉）也記一筆 `counter_contradicted`（verify 寫）。`agreement < 0.5` 且 ≥ 3 筆 → `calibration.json` 標它不可信、優化器退回純量規則（`min_gain`／`min_loss`）並印出來。
- **三棵樹的關係**：§ 5.1。

**結論（非數值怎麼比、怎麼挑方向）**：diff 自己不排序，排序是一張**人寫的優先序表**（`rules.json`）；表先當 agent 的指引、再固化成程式；表對不對由人評配對與下一步的分數回頭驗（判斷器有自己的評級）。所以「誰判斷 ok→good 比 token −300 重要」＝先是人（寫表）、執行是判斷器樹、校正是人評＋結果。

---

## 5. 三棵樹與按子樹優化

### 5.1 關係圖（誰讀誰的 `_metainfo`、誰改誰）

```
                 ┌──────────────────────────── 台詞樹 galtxt-a/（被優化的）────────────────────────────┐
                 │ 根 _metainfo + ratings.json(verify 寫) + rollup.json(rollup 寫)                      │
                 │ writer/ {_metainfo, ratings, stage, grad, rollup, tools/beat/{grad,rollup}, tools/voice/…}│
                 │ grader/ {…}   tools/lint/ {grad, rollup}   data/{dims,hints,lint_switches,templates}.json │
                 └───────▲───────────────────────────────┬────────────────────────────────────────────┘
      改（只改參數表、stage.json、tools 開關；│                                   │ 跑驗證題 → score.json
      先拷快照 params/changed.json）          │                                   ▼
┌────────────────────────────────────────────┴───┐          ┌─────────────────────────────────────────┐
│ 優化器 train/optimize/（第 2 層）                │          │ train/verify.py（第 1 層的驗證；不是樹）   │
│ 讀：根 rollup.json（→ 直接子樹的 val/stage/grad）│          │ 寫：根 ratings、<被改子樹>/grad.json、     │
│     data/dims.json(moved_by)、policy.json(actions)│          │     stage.json.history、optimize/ratings   │
│ 做：挑一棵子樹＋一個動作；分配 grad 給工具       │          │ 叫：rollup --up、weigh                     │
│ 自己的：_metainfo、ratings(verify 寫)、policy、rollup│       └───────────────┬─────────────────────────┘
└───────────────────────────────────────────────┘                          │ 兩份 diff（A 這步、B 不動）
                                                                           ▼
                                              ┌─────────────────────────────────────────────────────┐
                                              │ 判斷器 train/weigh/（第三棵；agent → rules）           │
                                              │ 讀：兩份 diff、自己的 rules.json；不讀任何 _metainfo     │
                                              │ 回：選 A/B＋理由 → log.jsonl；什麼都不改                │
                                              │ 自己的：_metainfo、stage、ratings(human/import 與 verify 寫)│
                                              └─────────────────────────────────────────────────────┘
人評 human/ → human/import 寫：writer/human.json（overall）、grader/ lint/ human.json（dim 一致度）、weigh/ratings.json（判得對不對）
```

讀寫邊界：優化器**只讀根的對外描述**（rollup）、**只改參數表與旁檔** `stage.json`（程式由人與 git 管）；判斷器**只讀兩份 diff**、**不改任何東西**；verify 是唯一寫梯度與評級的（成果由下層的驗證寫，不自評——round3 § 15 不變）；rollup 是唯一寫彙總的。

### 5.2 優化器每步只挑一棵（其餘凍結）

1. 讀根 `_metainfo`（解 `$ref`）→ `rollup.children`、`rollup.dims`、`rollup.brain`。
2. **目標排序**（固化是主方向）：先看 `brain.nodes` 裡還是 `agent`／`semi` 的子樹（候選＝它們）；每棵的順位＝`(tokens_per_question_share, 1 − determinism)` 大的先（最吃腦、最不確定的先固化）；平手看 `rollup.dims` 最差維度的 `moved_by`；`calibration.json` 標 `untrusted` 的維度不當依據。
3. 鑽下一層：挑中的子樹若有自己的 `rollup.children`（寫手有 `tools/*`），下一步的候選工具從它的 `children.*.grad_total` 與候選工具表排（§ 4.3 排序鍵）。
4. 動作：那棵的動作表（§ 5.3）第一個沒試過的（`params/` 快照記錄試過哪些）；全試過換下一棵。一步只改一個檔（或 `stage.json` 的一個 key）。
5. 寫：要改的檔拷到 `stack:epochs/NNN/params/<子樹>/<檔>`、寫 `params/changed.json {"subtree", "action", "target", "files", "from", "to"}`（通用回滾清單，取代現在只拷 `route.json`）；改檔；stdout `optimize: epoch 1 挑 writer（agent，tokens 21k/題，determinism 0.3）→ extract tools/beat（候選表：成本 0、預估確定性 +0.2）`。`--dry-run` 只印。
6. `optimize/ratings.json` 從 `action:route` 長成**每種動作一格**（`action:extract`、`action:stage`、`action:switch`、`action:distill`）；`min_gap` 規則不變。

### 5.3 動作表（`policy.json.actions`；一動作＝改一個檔；回滾＝從 `params/` 拷回）

| 子樹 | 動作 | 改哪個檔 | 怎麼改 | 回滾 |
|---|---|---|---|---|
| `writer`（任一用腦子樹） | `extract <工具>` | `<子樹>/stage.json.tools` | 候選工具表 `policy.tools[writer] = [{"name": "beat", "cost_to_extract": 0, "covers": ["反差節拍"]}, {"name": "voice", "cost_to_extract": 0, "covers": ["口癖句尾"]}]`（**工具程式人先寫好放 `tools/`**，動作只是「開給腦用」：`brain.py` 只列 `stage.tools` 裡的；`system.txt` 裡有一句「有 beat 工具時那一行用它組」）；`stage` 自動從 `agent` 變 `semi` | `stage.json` 拷回 |
| | `stage program` | `<子樹>/stage.json.stage` | `_entry` 改走 `compose.py`；只在 `tools_share ≥ 0.5` 時列為候選（殼拿掉前環節要先多半是工具） | 拷回 |
| | `distill` | `data/templates.json` | § 6：難例 → 腦示範 → 新模板條目 | 拷回 |
| `tools/lint` | `switch` | `data/lint_switches.json` | 對最差維度負責的規則開／關 | 拷回 |
| `.`（根） | `hints` | `data/hints.json` | `["借景","動作","留白"]` ↔ `["否認","讓步","洩底"]` | 拷回 |
| `grader` | （這圈不動；下一圈 `extract` 承接／像柚葉的規則工具） | — | — | — |
| （不准） | 改 `data/dims.json` 權重、改評審 rubric 的維度數、改 `optimize/_entry`／`weigh/rules.json` 本身 | — | 改損失函數＝自己給自己打分（round3 § 15.3 b／d） | — |

### 5.4 verify 的歸因、判斷、回滾

`verify.py`：跑驗證題與 `measure` 題 → 算 `after`（根與被改子樹的 ratings／stage 數字）→ 跟 `params/` 快照裡的 `before` 做 diff → 叫 `weigh`（A＝diff、B＝零）→ 選 B：照 `changed.json.files` 逐個拷回、stderr `train: Regressed epoch N 回滾 writer/extract beat（weigh: 確定性沒升）`、退 10；選 A：留。不論結果都寫 `<subtree>/grad.json.steps`（含 `weigh`、`accepted`）、`stage.json.history`、`optimize/ratings.json.action:<名>`、根 `ratings.json`；`extract` 那步再拷一份 diff 給 `tools/<工具>/grad.json`；最後 `rollup --up <子樹>`（根在路上）。只有被改那棵、它的工具、它到根的路上旁檔變，其他子樹 bytes 不變（測試驗）。

### 5.5 跟反向傳播哪裡像、哪裡不像

| | 反向傳播 | 這裡 |
|---|---|---|
| 責任往回分 | 一次 backward 得所有層的梯度 | 一次只動一棵，diff 整筆算它的（有限差分／座標下降）；N 棵要 N 步 |
| 鏈式法則 | 經中間層 activation 乘回去 | 沒有：只在「子樹」粒度歸因；抽工具那步的 diff 直接給那個工具（結構上誰被抽出誰負責），不經中間產物 |
| 梯度是什麼 | 一個向量 | **跟 `_metainfo` 同形的 diff**：有數（確定性、token）有非數（評級、標籤）；排序靠另一棵樹（判斷器）的規則表 |
| 可加性 | 線性 | 不可加：lint 的值隨寫手變；工具的梯度在「殼拿掉」後要重分攤 |
| 步長 | 連續 | 離散（抽一個工具、換一階、開一個關） |
| 雜訊 | batch 壓 | σ_Δ ≈ 0.3；純程式維度與確定性、token 沒雜訊，所以**固化方向的梯度比分數的梯度準** |
| 前向彙總 | activation 一層層算上 | `rollup` 一層層彙上（只看直接子樹）——這半邊貼 |

### 5.6 一大堆樹互相評、互相改：森林的錨在哪（頂層挖的邊緣狀況）

判斷器評優化器的每一步、優化器改台詞樹、人評校正判斷器、下一輪優化器也可以改判斷器的規則表——**三棵樹可能一起漂**：彼此說好（判斷器選 A、優化器照做、評級升）、實際變差（人看了覺得像套公式）。森林外的訊號只有兩種：**人評**（稀少、≤ 6 筆）與**外部可驗證的事實**（護欄、canon 專名、corpus benchmark 正解）。

| 我們的樹哪裡接到錨 | 接的是什麼錨 | 怎麼接 |
|---|---|---|
| lint 的 Tier 0（護欄、禁語、設定 D 類、稱呼階、必要關鍵詞） | corpus 固化/02、03（人寫、樹不改） | 純程式、規則表只有人改；任何一步讓 `dims.護欄` 掉 → 判斷器 `reject_if` 第一條，無條件回滾 |
| Q16 的正解 `bigram_overlap`、`guard_hit`、`bonus_hit` | corpus 評測 benchmark（樹看不到正解，只有 pick 讀） | 只記不比——**這圈起改成「只能掉不能升」的錨**：verify 每個 epoch 印 Q16 挑中那份的 `bigram_overlap`、`guard_hit`；`guard_hit` 從 true 變 false → 判斷器前的硬規則直接回滾（跟護欄同級，寫進 `rules.json.reject_if`）；`bigram_overlap` 連兩個 epoch 下降 → stderr `train: AnchorDrift Q16 bigram 0.13 → 0.08 → 0.05`（只警告） |
| 人評 `pair-stage`（固化前後哪份好）、`像套公式` 標籤 | 人 | `human/import` 寫 `weigh/ratings.json.judge:accept.agreement`、`writer/human.json.by_stage`；`agreement < 0.5` → 判斷器降級成純量規則；`像套公式 ≥ 2` → calibration 印「模板太死」 |
| `data/templates.json`、`cast.json` 精簡卡、`styles.json` 四個表 | corpus 固化/01、04、05、06（人抄、帶 `source`） | 蒸餾只**追加**條目、不改既有；追加的條目標 `distilled_epoch`、`teacher`，人看得出哪些是腦示範來的 |

| 哪裡沒接到錨（會漂的地方） | 為什麼 | 實跑時看什麼跡象 |
|---|---|---|
| 評審腦的三個維度（承接／像柚葉／文筆）與它產生的 `tags` | 尺本身是腦；寫手固化成模板後，評審可能照樣給 2 分（round1 它給三份同分） | **評審分辨力**（`grader/ratings.json.dims.分辨力`）掉到 0 且 `val` 不動；`tags` 全變成同一個標籤 |
| 確定性 `determinism` | 固化後數學上 1.0，再也不能分好壞；判斷器的 `prefer` 第三條從此永遠成立 | `determinism` 1.0 之後任何一步仍被判 A 的，理由裡只剩「確定性」→ 可疑（`rules.json` 要求確定性那條只在 `< 1` 時算） |
| 判斷器 `rules.json` 與優化器 `policy.json` | 都是人寫的表；這圈優化器**不改**判斷器、判斷器不改優化器（§ 5.1 的邊界）。使用者 11 說以後可以——到那時兩棵互改就沒錨 | 若日後開放：規則表的每次改動要有人評或 benchmark 跡象做依據（寫進 `grad.json.weigh.evidence`）；沒有外部證據的互改一律 `--dry-run` 印不做 |
| 訓練題 ribbon／poster 與 held-out lights 都是自造的（沒正解） | scene 模式沒有 benchmark | lights 的分數只能跟自己的過去比；它跟 Q16 的方向若反向（Q16 升、lights 掉）＝模板在背 Q16 的護欄詞 → `train: AnchorSplit` 警告 |
| 蒸餾的老師是寫手自己的 agent 階 | 自己教自己（腦的偏好被固化成規則） | 蒸餾條目進 `templates.json` 時標 `teacher: writer@agent`；人評樣本挑 `hard` 那題（§ 8.1 順位 4）讓人看一眼示範是不是像柚葉 |

**漂移的判準（verify 每個 epoch 印一行 `anchor:`，三個都看）**：(1) 自動評級升、Q16 的 `guard_hit`／`bigram_overlap` 掉；(2) 自動評級升、人評 `pair-stage` 選「前」或 `像套公式` 多；(3) 判斷器連三步選 A 而 `分辨力` → 0。任一成立＝停、回滾到上一個人評確認過的 epoch（`params/` 快照都在）、把 `rules.json` 拿給人看。**這圈的錨結論**：護欄與 Q16 正解是硬錨（寫進 `reject_if`）、人評是軟錨（校正判斷器）、三棵樹之間不互改規則表——「一大堆樹」要先有這條邊界，不然沒有一棵接地。

---

## 6. 難例與蒸餾（固化後接不住的輸入）

- **固化節點不退回問腦、不報錯停線**：`writer/compose.py` 收到 `brief` 時先查 `data/templates.json` 有沒有這個 `detail`（事件關鍵詞：彩帶／海報／關燈）的句式；**沒有就用場景通用模板（收攤泛用的否認／讓步／遮掩三槽＋通用旁白）照樣產出**（降級最佳猜測），並追加一行 `writer/hard.jsonl {"at", "question", "brief_key": {"mode", "detail"}, "why": "TemplateMissing", "output": "..."}`。lint、評審照跑；分數掉就掉（這就是梯度）。
- **下一輪拿難例當資料**：優化器動作 `distill`（§ 5.3；候選條件＝`hard.jsonl` 有未處理的行）：`train/distill.py`（內嵌單子，optimize 叫；或 optimize 直接做）對每個難例**以寫手的 agent 階當老師**（`stage` 暫走 agent、同一題跑一次、3 份）→ 挑 lint 過且 `反差 ≥ 0.5` 的那份 → 拆成模板條目（柚葉那句的否認／讓步／遮掩三段用 `beat` 的反函數切；旁白整句）→ 追加進 `data/templates.json[detail]`，`hard.jsonl` 那行標 `resolved_epoch`；下一個 epoch program 階就接得住。像蒸餾：腦示範一次、規則記住。token：一個難例 ≈ 21k（3 份），一個 epoch 最多蒸 2 個。
- **示範**：`cls-poster`（撕海報）故意不放進初始 `templates.json` → epoch 2 寫手變 program 後跑它 → 難例一筆 → epoch 3 `distill` → `templates.json` 多 `poster` 條目 → 再跑分回來。假腦下老師＝假腦的 `tsun()` 模板，整條離線可測。
- 其他節點（beat 查不到槽、voice 查不到稱呼）同一套：產出通用值＋記 `hard.jsonl`；這圈只有寫手實作完整的「收集 → 蒸餾」。

---

## 7. 訓練迴圈改寫

### 7.1 改什麼（盡量小改）

| 檔 | 改動 |
|---|---|
| `train/fsm.json` | 四格不變：`verify → train → rate → optimize → verify`；`loop.json` `max` 9 → 16（4 epoch × 4 ＋ 保險）。`distill` 不開格：是 optimize 的一種動作（它跑腦示範時用 `common.run_question`）。 |
| `train/common.py` | `run_question(cell, example, writer=None, env=None)` 多 `env`（distill 強制 `GALTXT_STAGE=agent`）；`rollup_up(subtree)`；`scope_check(score)`；`diff(before, after)`（§ 4.1 的三種鍵）；`usage_of` 不變 |
| `train/train.py` | 不變（題目換了） |
| `train/rate.py` | dims 照 `data/dims.json` 走；每格加 `determinism`（從 `measure` 題，verify 放的）、`cost`、`tags`；`grader/ratings.json` 寫 `role:grader`（`cost`、`dims.分辨力`＝同題三份承接／像柚葉的標準差 ÷ 1.5）；`scope_check`；人評樣本 § 8.1；完了 `rollup_up` |
| `train/verify.py` | 驗證題 2＋`measure` 1；寫根 `ratings.json`（含 `brain`）；§ 5.4 的 diff／weigh／回滾／歸因；印 § 2.3 那行 |
| `train/optimize/_entry` | § 5.2；`policy.json` 加 `actions`、`tools`；`distill` 動作 |
| `train/weigh/`★ | agent-dan 範本（`_entry`、`loop.json`、`fsm.json`、`brain.py`、`act.py`、`system.txt`、`.env` luna-low）＋ `rules.py`、`rules.json`、`stage.json`、`ratings.json`、`human.json`、`log.jsonl`、`_metainfo`（`kind agent`、`role dev`、`llm_calls 1／2`、`llm_tokens 1500／5000`、`steps: ["比較數值鍵", "比較非數值鍵", "套優先序"]`） |
| `writer/` | `stage.json`、`grad.json`、`compose.py`（從 `brain.py.compose()` 搬出、照 `templates.json`、叫 `tools/beat`／`voice`／`lint`、寫 `hard.jsonl`）、`_entry` 分流（`stage.json.stage == "program"` → `python3 compose.py`，否則原本的 `aos-loop`）；`tools/beat/`、`tools/voice/`（各 `_entry`＋`tool.json`＋`_metainfo`，純程式）；`brain.py` 只列 `stage.tools` 裡的工具；`system.txt` 多兩句「有 beat／voice 工具時用它」；`_metainfo` 加 `steps` 與 `$ref` 行 |
| `write.py` | `HINTS` 改讀 `data/hints.json`；`hints_fixed` |
| `brief.py` | `rules.json` 多 `switches`、否認／讓步／遮掩／洩底四個表（從 `styles.json.types.傲嬌` 新加的 `deny`／`yield`／`cover`／`reveal`）；`brief.json` 多 `detail`（題目 JSON 的 `detail`） |
| `tools/lint/_entry` | `反差`、`洩底`、`OocMark`；輸出 `dims` |
| `judge.py`、`grader/brain.py`、`pick.py` | 四行 rubric；加權 `total`；`一致` |
| `plan/examples/` | `cls-ribbon.json`、`cls-poster.json`、`cls-lights.json`（scene，`detail` 各一）、`Q16-fixed.json` |
| `data/templates.json`★ | `{"source": "corpus 固化/04 槽填充模板、06 開場收尾句庫，只抄教室收攤；distill 追加", "scene": "教室收攤", "generic": {"deny": [...], "yield": [...], "cover": [...], "open": [...], "close": [...], "reveal": [...]}, "by_detail": {"ribbon": {...}, "lights": {...}}}`（**故意沒有 `poster`**，§ 6） |

### 7.2 題目：同一場景怎麼分（兩個開關）

| 用途 | 題 | `mode` | `detail` |
|---|---|---|---|
| 驗證（固定；正解只有 pick 讀） | `Q16.json` | fill | （Q16 原文：收攤） |
| 驗證（固定、held-out） | `cls-lights.json` | scene | lights——**訓練、templates 都不放它的專屬句**（templates 只有 generic 接它） |
| 確定性量測 | `Q16-fixed.json` | fill、`hints_fixed` | — |
| 訓練 | `cls-ribbon.json` | scene | ribbon（templates 有） |
| 訓練 | `cls-poster.json` | scene | poster（templates **沒有** → 難例） |

**過擬合風險**：(a) 工具／模板對著 ribbon、poster 調，lights 分沒漲 → verify 抓（早停）；(b) 固化後整棵樹只會「文化祭收攤的傲嬌」——正是收窄要的，但 `ratings.scope` 要誠實寫場景，往外長時這格不能當通用 `style:傲嬌`（key 改 `style:傲嬌/scene:教室收攤`）；(c) Q16 的 `guard.must` 字面跟 lint `反差` 的標記同源 → Q16 的 `反差` 偏高，`cls-lights` 沒有 `must`、它的 `反差` 才乾淨——verify.json 分題記、判斷器看兩題平均但 stdout 分列；(d) **固化最大的過擬合**：program 階對 held-out 的 `承接`／`像柚葉` 可能明顯掉（模板不懂新小動作）——這就是 `min_loss` 存在的理由與難例機制要接的事；真腦實跑看掉多少。

### 7.3 一輪示範怎麼跑

```sh
export PATH=$PWD/proto8/impls/aos-exec/bin:$PWD/proto8/impls/aos-loop/bin:$PWD/proto8/impls/aos-fsm/bin:$PATH
G=proto8/topdown/galtxt-a
rm -f $G/human/samples.json
mkdir -p ~/code/try/galtxt-a/train4/ws
AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws ~/code/try/galtxt-a/train4/ws $G/train
```

| epoch | verify（含 measure） | train | rate | optimize（挑誰、做什麼） | 預期梯度 |
|---|---|---|---|---|---|
| 0 | Q16、lights、Q16-fixed 照 agent 寫手 → 根 ratings（基線 total ≈ 3.5、tokens/題 27k、determinism ≈ 0.3） | ribbon、poster × writer | 寫手評級；挑人評 4 筆 | 根 rollup：最吃腦＝writer（agent）→ `extract beat` | — |
| 1 | 同三題（semi）→ diff → weigh 選 A（確定性 +0.2、token +1.5k 過渡） | 同 | 同 | writer 仍 semi、`tools_share` 0.33 → `extract voice` | `beat/grad.json` 收到 step 1 |
| 2 | semi+voice → diff → weigh | 同 | 同；補人評到 6 | `tools_share` 0.67 ≥ 0.5 → `stage program` | `voice/grad.json` 收到 step 2 |
| 3 | program（0 token）：Q16 ≈ 持平、lights 掉 ≤ 0.25？→ weigh：token 歸零且分沒掉超過 `min_loss` → A；poster 在 train 跑出難例 1 筆 | poster → `hard.jsonl` | 同 | `hard.jsonl` 有未處理 → `distill`（腦示範 1 題 ≈ 21k）→ `templates.json.by_detail.poster` | step 3 分攤給 beat／voice；`max_epochs` 到 → 退 10 |

stdout 每步看得到：`optimize: epoch 0 挑 writer（agent，21k/題，determinism 0.30）→ extract tools/beat`、`train: epoch 1 verify total 3.55 (Δ +0.05) tokens/題 27000 → 31500 on_brain 3 → 3 determinism 0.30 → 0.55 weigh A（確定性升、分沒掉）`、`rollup: writer/tools/beat → writer → .`、`train: epoch 3 … tokens/題 27000 → 7200 on_brain 3 → 2`。

### 7.4 預算（round1-measure：agent 一題-次 ≈ 27k、9 次腦、≈ 20 s；寫手固化後一題-次 ≈ 7.2k（只剩評審 3 × 2.4k）、3 次）

| epoch | 題-次 | token | 腦呼叫 |
|---|---|---|---|
| 0（agent）：verify 2＋measure 1＋train 2 | 5 | 135k | 45 |
| 1（semi+beat，寫手每份 +1 次 ≈ +1.5k）：5 題-次 ×（27k＋4.5k） | 5 | 158k | 60 |
| 2（semi+voice，再 +1 次） | 5 | 180k | 75 |
| 3（program）：5 × 7.2k ＋ weigh 1.5k×3 ＋ distill 21k | 5＋1 | 62k | 25 |
| **合計 4 epoch** | 21 | ≈ 535k（≈ 8 min） | ≈ 205 |

半固化兩個 epoch 是最貴的（token 先升，§ 2.1 誠實寫出來）。`budget.json`：`{"max_epochs": 4, "max_calls": 250, "max_tokens": 650000, "max_elapsed_ms": 1500000, "min_gain": 0.25, "min_loss": 0.25}`（估計 ×1.2；格與格之間檢查，最多超一題 ≈ 32k）。假腦整條 0 token。要再省：`measure` 題只在 stage 變的 epoch 跑（省 2 × 27k）；這圈先每個 epoch 都跑，數字乾淨。

---

## 8. 人評（≤ 6 筆、只校正）

### 8.1 怎麼挑（`rate.py`；第一個 epoch 後 4 筆、之後追加到 6，不覆蓋）

全部傲嬌×教室收攤；候選＝驗證題小格（各 epoch）＋這個 epoch 訓練題，過護欄的草稿。**配對優先**（人最能分「兩份比一比」；配對也是判斷器的校正資料）：

| 順位 | 挑什麼 | `why_picked` | 筆數 |
|---|---|---|---|
| 1 | 同題（Q16）**固化前（epoch 0 agent）vs 固化後（program）**挑中的那兩份 | `pair-stage` | 2 |
| 2 | 同題（lights）agent vs program | `pair-stage` | 2 |
| 3 | 純程式說好、評審說不好（`|反差 − 像柚葉| ≥ 0.33` 最大） | `disagree` | 1 |
| 4 | 難例那題（poster）蒸餾前的降級產出 | `hard` | 1 |

每筆 `scene` 多 `epoch`、`stage`、`pair_id`（網頁並排用）。

### 8.2 `human/questions.json`

```json
{"source": "round4 § 8.2：tags 對應傲嬌細項（一半 lint 抓得到：先否認再讓步／旁白洩底／太油／稱呼不對；一半只有人知道：太坦率／真的惡毒／像柚葉／想看下去／像套公式）；dims 名字跟自動評分一樣才能逐維度比；pair 問『這兩份哪份好』",
 "tags": ["先否認再讓步", "旁白有洩底", "太坦率（直接說開心）", "真的惡毒／掃興", "太油（冒煙／跺腳）", "稱呼不對", "像柚葉", "想看下去", "像套公式"],
 "dims": ["反差", "像柚葉", "文筆"],
 "pair": "這兩份哪份比較好（A／B／差不多）"}
```

「像套公式」是固化專屬的人評標籤——模板化最常見的毛病，自動評分抓不到。

### 8.3 匯入（`human/import/`）

| 寫到 | 格 | 用途 |
|---|---|---|
| `writer/human.json` | `style:傲嬌`（val 多數決、tags 計數、dims 平均）；多 `by_stage: {agent: {...}, program: {...}}` | 固化前後人怎麼看；`program` 的 `像套公式` ≥ 2 → calibration 印「模板太死」 |
| `grader/human.json`、`tools/lint/human.json` | `dim:像柚葉`／`dim:文筆`、`dim:反差`／`dim:語域`：`agreement`＝1 − 平均絕對差、`bias` | `agreement < 0.5` 且 ≥ 3 筆 → `calibration.json` 標 `untrusted`，優化器不拿那維度當依據 |
| `weigh/ratings.json` | `judge:accept`：人評 `pair` 的答案 vs `log.jsonl` 同一步的 `choice` → `agreement` | 判斷器判得對不對（§ 4.4） |
| `human/calibration.json` | 並排＋判讀 | 給人看；門檻、權重、rules.json **不自動改** |

---

## 9. metatable 的新定位；rollup 介面

| 工具 | 定位 | 介面 |
|---|---|---|
| `meta/metatable/` | **除錯**：整棵樹壓平看一眼（壞 `_metainfo`、逾時不一致、收攏候選）；不是優化依據 | 既有不動；round3 § 4.3 的解一層 `$ref`、`ratings` 欄、`role` 欄照做（10 行）；多 `stage` 欄（`stage.json.stage`，沒有＝`—`）；`--suggest` 加「N-4 有旁檔」欄；彙總多「on_brain／program 節點數」一行 |
| `meta/rollup/`★ | **逐層彙總**（§ 3.3）；優化器讀的是它的產物 | `rollup [--up] [--dry-run] [--json] <子樹>`；只讀 `_metainfo`、旁檔、直接子樹的 `rollup.json`；寫 `<子樹>/rollup.json`；stdout 一行一層；錯 `RootMissing`／`MetainfoBad`／`RefBad` 退 1 不寫；`_metainfo`：`kind program`、`role dev`、`grow_level 3`、`deterministic true`、`idempotent true`、`reads` [`cwd:<子樹>/_metainfo`, `cwd:<子樹>/*.json`, `cwd:<子樹>/*/rollup.json`]、`writes` [`cwd:<子樹>/rollup.json`]、`fs_needs [mount]`、`callers 3` |

兩者標準庫 Python、離線、不叫 aos-directive。

---

## 10. 測試（`proto8/tests/test_topdown_galtxt_a.py` 新開 `Round4T`；全部假腦）

1. **評分結構**：`dims.json` 每維度 `by` 是存在的子樹或 `pick`；柚葉 fill 三份 `dims` 有全部 key（fill 的 `洩底` `null`）、`total`＝加權手算；晴子題 `total` 一字不變（既有斷言不動）。
2. **lint 細項**：「哼，才沒有。不過……也不是不能接受」→ `反差` 1.0；只「才沒有」→ 0.5；順序反 → 0.5；旁白「（宮澤柚葉別過臉，耳根有點紅。）」→ `洩底` 1.0、無旁白 0；「臉紅冒煙」→ `OocMark`；`switches.contrast_order: false` → `反差` `null`。
3. **judge 四行**：假評審四行 → 三個 dims；少「文筆：」→ `null` 不退 1；沒「承接：」→ `ReplyBad`。
4. **scope 守門**：`scope.style` 暫改文靜 → rate `StateBad`。
5. **寫手三階同介面**：`stage.json` 分別 `agent`／`program` 跑 Q16 → 都退 0、`answer.txt` 一行、以「宮澤柚葉：「」開頭、must 中；`program` 的 `stack/writer/runs/` **不存在**（沒開 agent 小格）、`usage.jsonl` 沒有、`counter_calls` 0；`semi` 且 `tools: ["lint","beat"]` → 假腦 history 多一筆 `beat` 的 tool_call；`tools: ["lint"]` 時 history 裡**沒有** `beat`。
6. **工具契約**：`writer/tools/beat`、`voice` 各有 `_entry`（+x）、`tool.json`（`description`、`parameters`）、`_metainfo`（`kind program`、`deterministic true`）；stdin `{"deny": "才沒有", "yield": "也不是不能接受", "cover": "真是的"}` → 一行、含三段、順序對；槽缺 → 回通用句＋stderr 一行、退 0（降級不報錯）。
7. **確定性**：`Q16-fixed.json` → 三份 `hint` 相同；`program` 階 `dims.一致` 1.0；`agent`（假腦同 hint 同輸出）也 1.0——用 `GALTXT_FAKE_JITTER=1`（假腦在第 n 份句尾加 n 個「…」）讓 agent 階 `一致` < 1，驗公式。
8. **難例**：`templates.json` 沒 `poster` → program 跑 `cls-poster` 退 0、`answer.txt` 在、`writer/hard.jsonl` 一行 `TemplateMissing`；再跑同題不重複記（同 `question` 同 `why`）。
9. **蒸餾**：手放 `hard.jsonl` 一行 → `optimize`（假腦老師）→ `templates.json.by_detail.poster` 有 `deny`／`yield`／`cover`／`open`、`hard.jsonl` 那行 `resolved_epoch`；`params/changed.json.files` 含 `data/templates.json`；再跑 program 不再記難例。
10. **diff**：`common.diff(before, after)` 數值差、非數值 `[舊,新]`、集合 `{+,-}`、沒變的鍵不出現；兩邊同＝`{}`。
11. **判斷器**：`rules.json` 既定 → 假腦（＝rules）對手寫的 diff：護欄掉 → B；token 歸零且 `total_avg` −0.2 → A；token 歸零且 −0.4 → B；確定性 +0.2、token +1.5k → A；全零 → B；`log.jsonl` 一行；`stage` `agent`／`rules` 兩階答案相同（假腦）。`weigh/_metainfo` bytes 不變。
12. **rollup 單元**（暫存三層樹）：中層 `children` 兩行對；孫子的 `ratings.json` 改了沒重算孫子 → 根不變；`--up 孫子` → 三份變、叔叔不變；`--dry-run` 不寫；兩次除 `rolled_at` 全同；懸空 `$ref` → `RefBad`；`brain.nodes` 收到 `子樹/孫` 名；每份 `_metainfo` bytes 不變。
13. **優化器照樹走**：手寫根 `rollup.json`（writer agent 21k、grader agent 7k、lint program）→ `--dry-run` 挑 writer、動作 `extract beat`；`tools_share` 0.67 → 挑 `stage program`；`hard.jsonl` 有未處理 → `distill`；全試過 → 換 grader（印「這圈沒動作」）；`params/changed.json.files` 都存在。
14. **梯度分配**：verify 在 `changed.action == extract` 後 → `writer/tools/beat/grad.json.steps[0].assigned_from == "writer"`、`writer/grad.json.steps[0]` 同一筆；`stage program` 那步 → beat、voice 各有 `assigned_share` 且和為 1；`tools/lint/grad.json` bytes 不變；`grader/*` bytes 不變。
15. **整條訓練**（假腦，`max_epochs 3`）：退 0；trace state 序列 `verify, train, rate, optimize` × 3 ＋ `verify`；`writer/stage.json.history` 四筆 stage 依序 `agent, semi, semi, program`；根 `ratings.json.style:傲嬌.brain.llm_tokens_per_question` 單調不升、最後 `counter_on_brain` 比第一筆少 1；根 `rollup.json.brain.nodes.writer == "program"`；`human/samples.json` ≤ 6、全 `style 傲嬌`、`place 教室`、`why_picked` 含 `pair-stage`；`optimize/ratings.json` 有 `action:extract`、`action:stage`；`weigh/log.jsonl` 3 行。
16. **回滾**：`weigh/rules.json` 暫改成「確定性升也拒絕」→ epoch 1 verify 退 10、`stage.json` 拷回 `agent`、`tools` 不含 `beat`、stderr `Regressed … writer/extract beat`、`grad.json.steps[0].accepted false`、`counter_rolled_back` 1。
17. **M7**：訓練前後所有 `_metainfo`、`fsm.json`、`dims.json`、`weigh/rules.json` bytes 一樣；變的只有旁檔（`ratings`／`stage`／`grad`／`rollup`／`human.json`／`hard.jsonl`／`log.jsonl`）、`templates.json`、`samples.json`、`route.json`、`policy.json`。
18. **預算**：`max_calls 3` → `BudgetSpent` 退 2。
19. **人評匯入**：手寫 `ratings.json` 5 筆（兩筆是 `pair`）→ `writer/human.json.by_stage` 兩格；`grader/human.json.dim:像柚葉.agreement` 手算對；`weigh/ratings.json.judge:accept.counter_confirmed` 對；`calibration.json` 列 `untrusted`；`SampleUnknown` 跳過；`RatingsBad` 退 1；重跑不變。
20. **搬得走**：`cp -r writer/` 到暫存假根 → `rollup --up` 不炸、`children.writer.grad_total` `null`、stdout `foreign grad（context.tree galtxt-a）`；`stage`、`ratings` 照列。
21. **metatable**：`--json` writer 列有 `ratings`、`stage`；`--suggest` 對有旁檔的印 N-4；彙總有 on_brain 行。
22. **真腦**（連不上 skip）：Q16 agent 階跑通、四行評審解得開；`semi` 階 history 有 `beat` 的 tool_call（腦真的叫了工具）；不斷言分數。

round3 的 `Round3T` 改：`test_tree` 加 `writer/stage.json`、`compose.py`；`test_fake_skill_table`／`test_rate`／`test_train_whole` 的 `total`／`val` 字面改關係斷言；`test_optimize` 改讀 rollup 形狀；`test_route` 不動（寫手列表只剩 writer 時 route 仍能題目級覆寫到 writer-sol）。

---

## 11. 做的順序（給實作者；每步可回頭：跑測試＋ `git add` 當快照）

1. **評分細項（S 先定，後面全靠它量）**：`data/dims.json`、`styles.json.types.傲嬌` 加 `deny`／`yield`／`cover`／`reveal`／`ooc`、`data/lint_switches.json`、`data/hints.json`、`cast.json` 柚葉刪成精簡卡；`brief.py` → `rules.json`（＋`detail`）；lint 的 `反差`／`洩底`／`OocMark`；`grader/system.v2.txt`＋捷徑；`judge.py`／假評審四行；`pick.py` 加權＋`一致`；`write.py` 讀 hints、`hints_fixed`。既有測試全綠＋測試 1～4、7。
2. **收窄題目與迴圈骨架**：`plan/examples/cls-*.json`、`Q16-fixed.json`；`set.json`（scope、measure、writers 只剩 writer）、`budget.json`；`rate.py`／`verify.py` 照表走、`scope_check`、`cost`／`tags`／`determinism`、根 `ratings.json`（含 `brain`）；刪 `human/samples.json`；round3 測試改關係斷言、綠。
3. **寫手三階（節點生命週期）**：`writer/tools/beat/`、`tools/voice/`（純程式＋`tool.json`＋`_metainfo`）；`data/templates.json`（故意沒 `poster`）；`writer/compose.py`（從 `brain.py.compose()` 搬、照 templates、叫三個工具、`hard.jsonl`）；`writer/stage.json`、`_entry` 分流、`brain.py` 只列 `stage.tools`、`system.txt` 兩句；`_metainfo` 加 `steps`、`$ref`。測試 5、6、8。
4. **rollup**：`meta/rollup/`；各子樹初始旁檔（只有 `source`）＋ `_metainfo` 的 `$ref` 行；rate／verify 叫 `rollup_up`。測試 12、17、20、21。
5. **梯度與判斷器**：`common.diff`；`train/weigh/`（agent-dan 範本＋`rules.json`／`rules.py`／`stage.json`）；`verify.py` 的 before／after／diff／weigh／通用回滾（`changed.json`）／寫 `grad.json`／`stage.history`／`action:<名>`；梯度分配給工具。測試 10、11、14、16。
6. **優化器照樹走**：`policy.json.actions`／`tools`；`optimize/_entry` 重寫（讀根 rollup、挑子樹、動作、快照）；`distill` 動作（腦老師＝`GALTXT_STAGE=agent` 跑一題、切模板、追加 templates）。整條假腦 `max_epochs 3`：測試 9、13、15、18。
7. **人評**：`questions.json`、`rate.py` 配對挑樣本、`human/import/`（寫手 by_stage、量者 dim 一致度、判斷器 agreement、calibration）；optimize 讀 `untrusted`。測試 19。
8. **工具收尾**：metatable 的 `$ref`／`ratings`／`stage`／`role`／N-4；`meta/table-round4.md`；README 的樹、「怎麼跑」補 train／weigh／rollup／固化三階；code map（鐵律 3）。
9. **真腦**：手跑一次 4 epoch → `plan/round4-measure.md`：四個 `determinism` 數與三筆 diff（§ 4.3 要實際量的）、每步判斷器選了什麼與理由、固化前後分數（Q16、lights 分開）、token 實花 vs 535k、`on_brain` 3 → 2、難例與蒸餾那筆、根 `rollup.json`。`human/samples.json` 換真腦 6 筆交頂層。

---

## 12. 結論草稿（給隊長寫進 thinking；只寫結論）

- **哪些子樹已固化（0 token）、哪些還靠腦與為什麼**：固化完的——`tools/lint`、`writer/tools/beat`、`writer/tools/voice`、`writer`（program 階，教室收攤這個場景）、`train/weigh`（rules 階）、`idle`、五格、train 的格；還靠腦——`grader`（承接／像柚葉／文筆三個「像不像」維度還沒有規則版；它是尺，尺換成程式之前先要人評校正過它）、`writer` 遇到 `templates.json` 沒有的小動作時降級（不問腦，記難例等蒸餾）、`train/weigh` 在 agent 階時（這圈走到 rules 就不用了）。固化前後分數：實跑才有（`round4-measure.md`）；預期 Q16 持平、held-out 的 lights 掉 ≤ `min_loss`、`像柚葉`／`承接` 掉最多。下一步最該固化：`grader`（最後一個每題必叫腦的節點，7.2k/題；先抽「承接＝前文 bigram 接得上」「像柚葉＝lint 的反差＋語域」兩個規則工具，`文筆` 留腦）。
- **節點生命週期**：同一資料夾、同一介面，`agent → semi → program` 是第 5 級資料夾裡的內容在換、不是降級；`stage.json` 記階、為什麼換、前後數字；`_entry` 照 `stage` 分流，兩套都留在資料夾裡（回滾＝改回 `stage`）。**假腦就是固化第 2 階的第一版**——真腦跑 agent、假腦跑 program，固化＝把假腦搬出來照表走。
- **半固化階 token 先升再歸零**：腦叫工具多一來回；判斷器的規則允許「確定性升換 token 暫升」，殼拿掉才歸零。
- **難例**：固化節點接不住就降級產出＋記 `hard.jsonl`，不退回問腦；下一輪 `distill` 以 agent 階當老師示範一次、切成模板條目——蒸餾；一題 ≈ 21k。
- **梯度＝對外描述的結構化 diff**（跟 `_metainfo` 同形：數值差、`[舊,新]`、`{+,-}`）；一步只動一棵，diff 整筆歸它；抽工具那步的 diff 直接給那個工具、殼拿掉那步按叫用次數分攤；確定性＝同輸入同角度三次的二元組相似。純程式鍵（確定性、token、反差）沒雜訊，固化方向的梯度比分數的梯度準。
- **非數值梯度誰判**：第三棵樹 `train/weigh/`——只讀兩份 diff＋一張人寫的優先序表（護欄不掉 > 分不掉超過 `min_loss` > 評級升 > token 省三成 > 確定性升 > 好標籤），agent 階照表當指引、rules 階照表執行；它自己的對錯由人評配對與下一步分數回頭記（不自評）。所以「ok→good 比 token −300 重要嗎」＝人先寫表、樹執行、人評校正。
- **三棵樹**：台詞樹被改（只改參數表與 `stage.json`）；優化器只讀根的 rollup（直接子樹的 val／stage／grad）、改一棵、分配梯度；判斷器只讀兩份 diff、不改任何東西；verify 是唯一寫評級與梯度的；rollup 是唯一寫彙總的。
- **跟反向傳播**：像在責任分層、誤差從損失往回記、前向一層層彙總；不像在沒有鏈式法則、不可加、離散步長、梯度不是向量而是 diff——每量一棵付一次前向。
- **塔與自我參照**（round3 § 15 不變，加）：判斷器是第三棵但不是第三層——它不優化優化器，只替優化器比大小；它能壞的地方是「規則表被它自己改」，所以表只有人改。成本每層 ×6～14 不變。
- **收窄的代價**：評級 key 是「傲嬌×教室收攤」不是「傲嬌」；固化出來的模板只會這個場景；往外長時 key 帶 scene、模板按 scene 分檔。
- **一大堆樹的錨**（§ 5.6）：森林外只有兩種訊號——人評（稀少）與外部可驗證的事實（護欄、canon 專名、benchmark 正解）。接到錨的：lint Tier 0（硬錨，掉就無條件回滾）、Q16 的 `guard_hit`／`bigram_overlap`（這圈起從「只記」改成「只能掉不能升」的硬錨）、人評配對與「像套公式」標籤（軟錨，校正判斷器）、corpus 抄來的表（蒸餾只追加、標 teacher）。沒接到的：評審腦的三個維度與 tags（尺本身是腦）、固化後恆為 1.0 的確定性、自己教自己的蒸餾、沒正解的 scene 題。漂移跡象三條（自動評級升但錨掉；自動評級升但人評選「前」；判斷器連選 A 而評審分辨力歸零），任一成立就停、回滾到上一個人評確認過的 epoch。邊界：這圈三棵樹**不互改規則表**（判斷器與優化器的表只有人改）——「一大堆樹」要先有這條，不然沒有一棵接地。

---

## 13. 未決、要使用者拍的

1. 場景選教室收攤（Q16）而不是河鹿堂提書包（有正解、可校對純程式量法）。
2. 傲嬌細項與權重（反差 2、像柚葉 2、承接／文筆／語域／洩底各 1）是我定的；人評一致度出來再調。
3. 這圈固化的是寫手（走到 program）與判斷器（走到 rules）；評審留在 agent——是否接受「尺先不固化」。
4. 判斷器 `rules.json` 的優先序（護欄 > 分不掉 > 評級 > token > 確定性 > 標籤）與「半固化期允許 token 升」。
5. 半固化兩個 epoch token 先升（535k 裡 ≈ 340k 花在那兩輪）——若要省，`measure` 題只在換階的 epoch 跑。
6. N-4「有旁檔的不縮」、`steps`／`brain`／`grad` 三個 `$ref` key 名要不要進通用表。
