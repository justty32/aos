# galtxt-b 第 6 輪：節點生命週期、難例、結構化梯度、判斷器樹、錨（只規劃、精簡；fable，2026-10-25）

← [round5](round5.md)（五區 `_metainfo` §2、貢獻 §3、照樹走 §4、固化 §1b、預算 §6——本檔只寫新的，其餘引用）｜場景以 A 段已實作者為準（round5 §1、[round4 §11](round4.md)）｜使用者原文：thinking 乙隊一節最後七條（頂層轉述，本檔照它）

## 0. 一頁看懂

- **節點生命週期**：同一個資料夾、同一個對外介面，`agent → 半固化（腦叫越來越多工具）→ 純程式（連順序也固化、拿掉 agent 殼）`。「抽工具」是優化器的一種動作；抽出的工具可以是更小的 agent、再走同一條路（§1）。
- **接不住的輸入**：固化後的程式節點照樣給降級的最佳猜測、不退回問腦、不停線；記進難例；下一輪腦當老師示範、蒸餾進規則（§2）。
- **梯度**＝一步改動前後 `_metainfo` 的**結構化 diff**（形狀同 `_metainfo`），分攤給底下負責的工具；優先走「梯度大、成本低」的（§3）。確定性量一次。
- **判斷器樹**：讀兩份梯度 diff、答哪個較好＋理由；先問腦，有自己的 `_metainfo`、評級、被人評與結果回頭查，之後固化成「什麼比什麼重要」的規則表（§4）。三棵樹的關係圖在 §4。
- **錨**：森林外只有人評、可驗事實（lint 護欄／canon／benchmark）、雜訊 σ；標出哪裡接到錨、哪裡沒有、示範怎麼看漂移（§5）。
- **預算 ≤ 60 萬 token**，優先順序與砍法在 §6；工作清單 §7。

## 1. 節點生命週期：agent → 半固化 → 純程式

### 1a. 四階（`_metainfo.lifecycle`，record 寫；round5 §2a 的 `solid` 併進來改名，`solid.stage` 作廢）

| 階 | `stage` | 長相 | 腦還做什麼決定 |
|---|---|---|---|
| 0 | `agent` | agent-dan 形：腦讀題、自己寫全部 | 一切 |
| 1 | `tools` | 腦還在，但某些環節已是 `tools/<名>/`（lib 契約：stdin JSON→stdout；`tool.json` 給腦看）；腦改成「叫工具＋把結果拼起來」 | 叫哪個、什麼順序、工具沒給的那段內容 |
| 2 | `script` | 「叫哪個、什麼順序」也固化成 `_entry` 的純程式（一支 `run.py` 依序叫 tools/，不問腦）；agent 殼（loop／fsm／brain／system.txt）拿掉，但 `tools/` 裡可能還有小 agent | 只剩 tools/ 裡還是 agent 的那幾個 |
| 3 | `pure` | tools/ 全是純程式、整棵子樹 `rollup.llm_tokens.val == 0` | 無 |

**對外介面不變**：資料夾名不變、題目／答案的位置不變（`new/<n>.json`→`out/<n>.txt`）、呼叫方 `draft/_entry` 一個字不改（它只 `aos-exec tools/writer`，N-61 走進去跑什麼它不管——這就是 C-52 給生命週期的保證）。

`_metainfo.lifecycle`：

```json
"lifecycle": {"stage": "tools",
              "counter_steps": 2, "counter_steps_tooled": 2, "counter_steps_total": 5,          ← 幾成環節已是工具（2／5）
              "brain_decides": ["叫哪個工具、順序", "B3 話題那兩句的內容"],
              "tools": {"trim": {"since_round": 1, "why": "token −300／次、旁白與感嘆號的雜訊歸零（確定性 +0.3）", "stage": "pure"},
                        "hand_over": {"since_round": 2, "why": "反差拍句式枚舉得完（2×2）", "stage": "pure"}},
              "history": [{"round": 1, "from": "agent", "to": "tools", "move": "extract_tool:trim",
                           "before": {"llm_tokens": 10082, "deterministic_score": 0.55, "ratings.傲嬌.val": "ok"},
                           "after":  {"llm_tokens": 9700,  "deterministic_score": 0.85, "ratings.傲嬌.val": "ok"}}],
              "versions": "versions/"}                                                        ← 前後版本留在節點裡（§1c）
```

### 1b. 「抽工具」（優化器白名單新動作 `extract_tool`；round5 §1b-3 的 `solidify` 是它的特例＝把所有環節一次抽完）

```json
{"kind": "extract_tool", "node": "draft/tools/writer", "name": "trim",
 "step": "交稿前修剪：旁白 > narration_max 砍到上限、柚葉的感嘆號 > exclaim_max 換成句號、口癖 > 1 次的第二次換成「哼」",
 "impl": "pure|agent", "why": "noise.md：σ 0.58 全來自這兩條 lint 規則；腦每次寫法不同，交給程式就歸零"}
```

程式（`train/apply`）：① 在 `node/tools/<name>/` 建工具（`impl: pure`＝實作者預寫的殼＋腦給的規則表；`impl: agent`＝從 agent-dan 複製、system.txt 由提案給）；② `tool.json`、`_metainfo`（宣告區由程式生成，round5 §7-12）；③ `node/system.txt` 加一句「<step> 交給工具 `<name>`，不要自己做」；④ `lifecycle` 更新；⑤ 第 2 階 `script` 時另一種動作 `freeze_order`：把 history 裡腦叫工具的順序（過去 N 次一致 ≥ 90%）寫成 `run.py`、拿掉殼。抽出的工具若是 agent，它自己有 `lifecycle`，下一輪可以再被抽——這就是子樹會深的原因（使用者的預期）。

### 1c. 示範（B 段要實際走）

| 節點 | 走幾步 | 前後要量的 |
|---|---|---|
| **writer** | 兩步：抽 `trim`（純，見 1b）→ 抽 `hand_over`（反差拍「塞書那句」的句式表：2×2 開關 × 否認／讓步／遮掩三段，枚舉 ≤ 12 句，`impl: pure`） | 每步前後：`llm_tokens`、`deterministic_score`（§3c）、`ratings.傲嬌`（反差、含蓄）、lint 扣分次數 |
| **director** | 走完：`agent` → `script`（`plans.json` 2×2，`run.py` 查表＋plan_lint）→ `pure`；前後版本留 `director/versions/v0_agent/`、`v1_script/` | 分數不掉（round5 B0 驗收）、token −20%、`deterministic_score` → 1.0 |

**前後版本放哪**：節點內 `versions/<n>_<stage>/`（整個舊版資料夾複製進去，`kind: data`、不在 `subtrees`、runtime 不讀），搬走時跟著走；git 另有歷史但不當機制（使用者可翻）。

## 2. 接不住的輸入：降級猜測＋難例＋下一輪補上

照「持續優化持續訓練」：

1. **不退回問腦、不停線**：純程式節點遇到表上沒有的值（例 `prop: "舊車票"`、`first_speaker` 沒寫）→ 用**預設分支**（`plans.json#/default`、句式表的 `*` 列）產出，答案照交；`score.json` 多 `degraded: ["plan_template: prop 舊車票 不在表上，用 default"]`。
2. **記難例**：節點在**自己的小格**寫 `$AOS_STACK/<node>/hard_cases.jsonl`（一行：`{"recorded_at", "input": 縮過的題, "output", "reason", "round"}`）——runtime 不寫定義資料夾（P-15）；`train/record` 收集各小格的難例併進 `tree/<node>/hard_cases.jsonl`（訓練場的複本可以寫）。
3. **下一輪補上**（優化器動作 `teach`）：把難例交給該節點的 agent 版（`versions/v0_agent/` 還在；或同名的 agent 工具）示範一次 → 產出經 lint／plan_lint → 蒸餾進表（`plans.json` 多一列、句式表多一句）→ 難例標 `resolved`。
4. **示範**：B 段對 `plan_template` 餵一題 `prop: "舊車票"`（店誌有這道具、表上沒有）：第 1 輪降級＋記難例；第 2 輪 `teach` 後 `plans.json` 多一列、同題再跑 `degraded` 空、`反差`／`承接` 不低於其他四題。

`_metainfo` 加：`"hard_cases": {"counter_open": 1, "counter_resolved": 0, "file": "hard_cases.jsonl"}`（record 寫）。

## 3. 梯度＝結構化 diff

### 3a. 形狀同 `_metainfo`

`changes/<輪>.json.gradient`：對被改節點與它往上一路的每個 `_metainfo`，做改前／改後的 diff：

```json
"gradient": {"draft/tools/writer": {
   "rollup.llm_tokens.val": {"from": 10082, "to": 9700, "delta": -382},
   "rollup.measured.deterministic_score": {"from": 0.55, "to": 0.85, "delta": 0.30},
   "ratings.傲嬌.val": {"from": "ok", "to": "ok"},
   "ratings.傲嬌.反差": {"from": 0.70, "to": 0.75, "delta": 0.05},
   "ratings.human.傲嬌.tags": {"added": [], "removed": ["太長"]},
   "lifecycle.stage": {"from": "agent", "to": "tools"}},
 "draft": {"rollup.llm_tokens.val": {"delta": -382}}, ".": {"rollup.llm_tokens.val": {"delta": -382}}}
```

數值＝`delta`；非數值＝`from/to`（評級、stage）、集合＝`added/removed`（標籤）、文字＝原樣（人評評論，列在 `notes`）。

### 3b. 分攤到工具

上層節點的變化分給底下負責的工具：有貢獻（round5 §3）就按 `|contribution.dims[d]|` 比例分；沒有就按這一步「動了誰」——只動了 `trim` 就全給 `trim`。寫進各工具 `_metainfo.gradient_share[round]`。優先繼續的那條：`pick_rule` 多一項 `gain(S) = Σ 上一步 gradient 的好變化 ÷ 那一步的 token 成本`，「梯度大、成本低」的子樹加分（round5 §4a 的 score 多一項 `λ_gain × gain`）。

### 3c. 確定性怎麼量（定下來、量一次）

`deterministic_score`（0～1，`rollup.measured`）＝同一題、同一棵樹跑 N＝3 次：**台詞**用 1 − 兩兩（字元 3-gram Jaccard 距離）平均；**分數**用 1 − 總分樣本 σ ÷ 2。兩個都記（`text`、`score`），`val` 取 `score` 那個（優化看分數）。純程式節點 N＝3 一定 1.0，所以 director 走完前後就是 0.x → 1.0 的示範；writer 抽 `trim` 前後各量一次（3 次 × 1 題 ≈ 6 萬 token，§6）。

## 4. 判斷器樹（`train/arbiter/`）與三棵樹的關係

**最小試法**：`train/arbiter/`＝agent-dan 形的單發腦函數（round3 的 critic 形）：輸入兩份 `gradient`（同一節點的兩條候選改動、或兩輪），回 `{"better": "a|b", "why": [...], "weights_used": {"反差": 0.4, "token": 0.2, …}}`。優化器一步提 2 條候選（白名單內）時叫它挑一條；它有自己的 `_metainfo`（五區＋`lifecycle: agent`）、`ratings.judgments`（record 寫：它判「a 較好」的那幾次，下一輪 a 真的比較好的比率＝`accuracy`；人評對同一對樣本的偏好＝`human_agreement`）。固化路：判了 ≥ 8 次後，把它回答裡的 `weights_used` 平均成 `priority_rules.json`（「反差 > token > 文筆」那種表），`stage: script`，之後只在規則表平手時才問腦。

**三棵樹的關係圖**（誰讀誰的 `_metainfo`、誰改誰）：

```
                 讀 ratings／contribution／lifecycle            提 1～2 條改動（只提不改）
   台詞樹 tree/  ─────────────────────────────▶  優化器 train/optimize/tools/optimizer
      ▲                                                  │           ▲
      │ apply 只改被挑的子樹（程式動手）                    │ 兩條候選的 gradient │ tune 讀它的 ratings.moves
      │                                                  ▼           │   改它的 system.txt 經驗段／pick_rule
      │                                           判斷器 train/arbiter ◀── 人評 ratings.json（回頭查它判得對不對）
      │                                                  │ 回答「哪條較好」＋ weights_used
      │                                                  ▼
      │   record 寫 ratings／lifecycle／gradient    優化器照它挑的那條 → apply ─┘
      │
   錨：lint（護欄／canon／稱謂階）、人評、σ ───────────────────────────── 只進台詞樹的分數與判斷器的核對，不被任何樹改
```

- 台詞樹**被**優化器改、**被** record 寫五區；它不讀別人的。
- 優化器**讀**台詞樹的五區、**讀**自己的 `ratings.moves`；**被** tune 改（system.txt、pick_rule）；提案經判斷器。
- 判斷器**讀**兩份 gradient；**被** record 寫 `ratings.judgments`（用人評與下一輪結果回頭查）；**被**同一套固化（`priority_rules.json`）。它不改任何樹。
- 使用者「判斷器本身也可以被優化。優化器也是。一大堆樹」——這輪只做到：判斷器被查、被固化成表；不另開「優化判斷器的優化器」。

## 5. 錨：哪裡接到、哪裡沒有、怎麼看漂移

| 訊號 | 來自森林外？ | 接到哪棵樹的哪裡 |
|---|---|---|
| lint 的護欄、稱謂階、canon 專名、`must_mention` | 是（規則寫死、不被任何樹改；round5 §4a 凍結） | 台詞樹 `score.dims.護欄／語域`；間接進優化器的 effect 與判斷器的輸入 |
| 人評 `ratings.json`（6 筆／輪） | 是 | 台詞樹 `ratings.human`（校正 critic）；判斷器 `ratings.judgments.human_agreement`；**優化器沒有直接的人評**（只經由分數） |
| corpus benchmark 正解 | 是，但**這個場景沒有**（q01／q08 留作回歸：每輪跑一次、分數不掉） | 台詞樹的回歸分 |
| 雜訊 σ（noise.md） | 是（量出來的事實） | 判「改動有沒有效」的門檻（|Δ| ≥ 0.75 才算） |
| critic 的 含蓄／承接／文筆／角色味 | **否**（它是樹，會被校正、會漂） | 台詞樹分數的大半、優化器 effect 的大半、判斷器輸入的大半 ← **沒錨的那一塊** |
| 判斷器的 `weights_used` | 否 | 優化器挑哪條 ← 沒錨，只靠事後核對 |

**漂移怎麼觀察**（示範裡做）：① 凍結一份 `critic_v0`（round 0 的 critic 複本）與 `tree_v0`；每輪用**現在的 critic 評 tree_v0 的同一稿**（critic 漂多少）、用 **critic_v0 評現在的樹**（樹真的進步了多少）——兩條線在 `rounds/<輪>.json.drift`；② 判斷器每輪的 `accuracy`（它說較好的那條，下一輪分數真的較高的比率）與 `human_agreement` 連兩輪都掉＝判斷器漂；③ lint 維度（有錨）與 critic 維度（無錨）的相關：critic 維度升而 lint 維度沒升＝可疑。沒錨的那一塊的唯一真錨是人評，所以 6 筆裡固定 2 筆是「判斷器判過的對」（讓人也判一次）。

## 6. 預算（≤ 60 萬 token，luna-low；每次跑樹 ≈ 2 萬）

| 優先 | 項 | 次 | token | 不夠先砍 |
|---|---|---|---|---|
| 1 | director 走完 agent→script（round5 B0）＋前後 A/B：各 4 題 × 1 | 8 | 16 萬 | 不砍（主示範） |
| 2 | writer 抽 `trim`：抽後 4 題 × 1 ＋ 確定性 3 次 × 1 題（抽前的 3 次用 noise.md 既有） | 7 | 14 萬 | 確定性改用既有 noise 的 3 次＋抽後 3 次→ 省 2 萬 |
| 3 | 難例：降級一題（0 token，純程式）＋ `teach` 示範一次（director agent 版 1 次）＋ 補上後重跑 1 | 2 | 1 萬 | 不砍（便宜） |
| 4 | 判斷器：優化器一步提 2 條、判斷器判 1 次、兩條各跑 4 題×1 驗證誰真的較好 | 8＋2 腦 | 17 萬 | 砍成只跑判斷器選的那條（4 次、8 萬）；判斷器 `accuracy` 就沒得核對，改用人評 2 筆核 |
| 5 | writer 抽 `hand_over`＋抽後 4 題 | 4 | 8 萬 | **第一個砍**：只做 `trim` 一步也算「走幾步」的下限 |
| 6 | 漂移：critic_v0 評現在的樹 4 稿（只問 critic，每次 ≈ 0.4 萬） | 4 腦 | 1.6 萬 | 砍成 2 稿 |
| | **合計** | | **≈ 58 萬** | 砍 5→50 萬；再砍 4→41 萬 |

不算進去的：假腦跑的測試與 verify（0）；人評（人）。

## 7. 給實作者的有序工作清單、驗收、測試

1. **`lifecycle` 五區**（round5 §2a 加 `lifecycle`、`hard_cases`、`gradient_share`；`solid` 併進 `lifecycle`）：record 寫；`plan/metainfo_rollup.py` 印出來。驗收：形狀測試擴成含這三個 key；`counter_steps_tooled ≤ counter_steps_total`。
2. **director 走完**：`plans.json`（2×2＋`default`）、`run.py`（查表→plan_lint→輸出）、`versions/v0_agent/` 留全套、`lifecycle.history` 一筆、draft 照 ratings 選路（round5 §4 的 reroute）。驗收：4 題×1 A/B `val_delta ≥ −0.58`、`deterministic_score` 1.0、根 token −15% 以上；假腦：`run.py` 四題全過 plan_lint；`prop: 舊車票` → `default` 分支＋小格 `hard_cases.jsonl` 一行＋`score.degraded` 一條。
3. **writer 抽 `trim`**（`extract_tool`，`impl: pure`）：`writer/tools/trim/`（lib 契約；stdin `{text, brief_path}`→stdout 修剪後的稿）、system.txt 加一句、`lifecycle` 更新。驗收：抽後 4 題 lint 的 `narration_max`／`exclaim` 違規 0；`deterministic_score`（score 那個）抽前 noise.md 的 3 次（0.71）→ 抽後 3 次 ≥ 0.9；token 不增；假腦：`GALTXT_FAKE_LINT` 那條路改成腦叫 `trim`（history 有 `tool_calls: trim`）。
4. **難例→teach**：`train/record` 收小格的 `hard_cases.jsonl` 進 `tree/<node>/`；`train/apply` 的 `teach`：對 `counter_open > 0` 的節點，用 `versions/v0_agent/` 跑難例（1 次腦）→ plan_lint 過→寫進 `plans.json`→難例 `resolved`。驗收：第 2 輪同題 `degraded` 空、分數不低於四題平均 −0.58；假腦：teach 固定回一張合法表。
5. **梯度**：`train/record` 算 `gradient`（3a）與 `gradient_share`（3b）；`pick_rule` 加 `λ_gain`。驗收：手組前後兩份 `_metainfo`，diff 的數值／非數值／集合三類各一例；只動 trim 時 share 全給 trim；有貢獻時按比例。
6. **判斷器**：`train/arbiter/`（critic 形）＋ `train/optimize` 一步提 2 條、叫判斷器、採它選的；record 寫 `ratings.judgments`（accuracy、human_agreement）；≥ 8 次後 `priority_rules.json`＋`stage: script`。驗收：真腦一次判斷有 `better`、`why`、`weights_used`；假腦固定選 a、`accuracy` 可算；人評 samples 固定含 2 筆「判斷器判過的那對」（`why_picked: arbiter_check`）。
7. **漂移**：`train/init` 另存 `critic_v0/`、`tree_v0/`；`train/score` 每輪多跑 ②（critic_v0 評現在 2～4 稿、現在 critic 評 tree_v0 既有的 4 稿——後者 0 token，稿子已在 round0）→ `rounds/<輪>.json.drift`。驗收：兩條線各有數字；假腦 drift 全 0。
8. **writer 抽 `hand_over`**（預算夠才做）：2×2×三段句式表 ≤ 12 句、`impl: pure`；驗收同 3，`反差` 不掉。
9. **文件與留檔**：`plan/runs/round6/`（A/B、確定性、難例、判斷、漂移的數字）、README 加生命週期一段、`plan/lessons.md` 加這輪的經驗（使用者「留存經驗」）。

**測試檔** `proto8/tests/test_topdown_galtxt_b_lifecycle.py`（假腦）：lifecycle 形狀與 counter 不等式；director `run.py` 四題＋default；難例寫小格不寫定義（定義資料夾 hash 不變）；record 收難例、teach 後 resolved；trim 的三條修剪各一紅一綠（旁白 5 行→4、她的「！」3 個→2、口癖 2 次→第二次換「哼」）、修剪不改台詞句數；gradient 三類 diff、share 分攤；arbiter 假腦與 accuracy 計算；drift 全 0；`extract_tool` 提案指到凍結節點（lint／critic）→ rejected；`freeze_order` 只在順序一致 ≥ 90% 時允許。原 23＋train 測試照過、demo 三段照過、原樹 hash 不變。

## 8. 衝突、要使用者定的（接 round5 §7）

1. **難例寫哪**：runtime 寫小格（P-15 定義不被寫）、訓練場再併進 `tree/`——所以 repo 裡的 galtxt-b 永遠看不到難例，只有訓練場的複本有；要讓 repo 的樹也累積難例就得人把 `tree/` 畢業回去（round4 §9-4 同一題）。
2. **`versions/` 放節點裡**：搬走帶著走、但樹變大（每走一階多一份舊版）；git 已有歷史，兩份記錄。我選節點裡（使用者「你選」），可翻。
3. **判斷器只判「哪條較好」、不判「要不要改」**：「不改」永遠零風險（round4 §4e 的退化不動點），所以不給它「都不好」的選項；它一定選一條。要給就得定「都不好」的門檻。
4. **優化器一步提 2 條＝多跑一倍驗證**（§6 第 4 項 17 萬）：砍掉就只能靠人評核判斷器；要兩者取一。
5. **沒錨的那一塊佔分數大半**（§5）：critic 的四維＋判斷器的權重都沒外部錨。示範能「看見」漂移（drift 兩條線、accuracy、human_agreement），擋不住；真擋得靠更多人評或 benchmark 正解（這個場景沒有）。要不要為這個場景人手寫一句「正解」當 benchmark（一題一句、10 分鐘），我建議要——那是最便宜的新錨。
6. **`extract_tool` 由腦提「哪個環節、規則是什麼」**，殼是人預寫的：腦提的規則表可能跟 lint 打架（例如 trim 砍旁白砍到 `line_count` 不夠）；verify 跑 lint 擋得住，但「工具的實作品質」沒有人審——第一輪的 trim／hand_over 由實作者手寫、腦只提；之後要不要讓腦真的寫工具的程式（self-improve 那條路），列出。
