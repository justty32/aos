# galtxt-b 第 4 輪：評級進 `_metainfo`、結構化分數、訓練迴圈、人評（只規劃；fable，2026-10-25）

← [galtxt-b](../README.md)｜前情：[round1](round1.md)、[round2](round2.md)、[optimize](optimize.md)、[round3-collapse](round3-collapse.md)（假設已照它收完：director／critic 是單發腦函數、plan_lint 在 draft/tools/、有 `plan/aos-fold`）｜使用者原文：[thinking 2026-10-25 top-down 乙隊一節](../../../thinking/2026-10-25-top-down.md)｜參考（不改）：[demo/self-improve](../../../demo/README.md)、[thinking 2026-10-24 self-improve](../../../thinking/2026-10-24-self-improve.md)、[aos-kernel-llm](../../../impls/aos-kernel-llm/README.md)、[aos-daemon](../../../impls/aos-daemon/README.md)、[wf/STRUCTURE 四級成長](../../../../wf/STRUCTURE.md)、[C-55 布局成長](../../../docs/CONCEPTS/01-設計理念.md)、[`_metainfo` M1～M10](../../../thinking/2026-10-24-metainfo.md)

使用者這段話的骨幹：① `_metainfo` 除了九軸也存任意資訊，例如「這個資料夾函數在傲嬌方面的台詞生成有 good 評級」；② 分數要結構化、而且結構照 STRUCTURE 的「膨脹即拆、四級成長」長；③ 訓練迴圈＝跑幾次→記成果→交給優化函數改樹→再跑；④ 優化函數也是一棵會被優化的樹，可以一直疊；⑤ kernel／daemon 需要就做；⑥ 人評是稀缺資源，拿來校正自動評分。極小範圍不擴：一地（河鹿堂）、同兩個事件（讓書、進新書日），**為了有「風格評級」多兩位本來就屬那型的角色**（§1）。

## 0. 一頁看懂

```
galtxt-b/                         被訓練的樹（第 3 輪收攏後；不變）
  _metainfo                       多一個 ratings 子物件：跑出來的評級（記錄者寫，作者不碰；§3）
  draft/tools/writer/_metainfo    同上（風格評級記在產出台詞的那個節點）
  human/                        ★ 人評契約：samples.json／ratings.json／questions.json 的形狀，與匯入程式 import/
  train/                        ★ 訓練迴圈（第 1 層優化器＋第 2 層調整器）——一棵獨立的資料夾程式，工作區是「訓練場」
    idle/ run/ score/ record/ pick/ optimize/ apply/ verify/ tune/
    optimize/tools/optimizer/     agent：讀 _metainfo 表＋本輪成果，提出改動清單（不直接改檔）
```

訓練場（`aos-exec --ws 訓練場 galtxt-b/train`）：`set/`（6 題）、`tree/`（galtxt-b 的工作複本，優化器只能改這裡）、`runs/<輪>/<題>/<次>/`（每次跑的工作區）、`rounds/<輪>.json`（結構化成果）、`changes/<輪>.json`（改動與效果）、`human/`（給使用者勾的樣本與回來的評級）。一輪＝6 題×2 次＝12 次跑樹＋優化器問腦 1 次 ≈ **21 萬 token**（§7）。

## 1. 範圍：三種風格、同一地點、同兩個事件

不讓晴子「演」傲嬌（角色語言表：一個角色可混兩型但主軸要穩；叫她演別的型＝我們自己製造 OOC，check 的稱謂與感嘆號預算也會全亂），改用 dossier 裡本來就屬那型、而且跟河鹿堂有關係的角色：

| 風格（評級的 key） | 角色（`corpus/人物/`） | 跟河鹿堂的關係（店誌／dossier） | 稱謂階 | benchmark |
|---|---|---|---|---|
| 文靜／書卷 | 森下晴子 | 常客、梅花章信仰 | 1 | q01、q08（有正解） |
| 傲嬌 | 宮澤柚葉 | 文藝社買參考書來這；《城鎮的傍晚》有主角在河鹿堂門口遇柚葉 | 1 | 無正解（critic 只照稿紙與總則打） |
| 害羞／內向 | 木下柚葉 | 常客、挑沒人的午後去、集梅花章很慢很珍惜 | 1 | 無正解 |

題集 `train/set/`（6 題＝3 角 × 2 事件）：`q01_讓書_晴子`、`q08_新書_晴子`（＝現在的兩題）、`讓書_宮澤`、`新書_宮澤`、`讓書_木下`、`新書_木下`——後四題是同一份場景 JSON 換 `cast` 與 `intent`（傲嬌配「鉤」、害羞配「靜」），`must_mention` 照事件不變。每題 JSON 多一格 **`"style": "傲嬌"`**（評級的 key；沒寫＝取女角卡上的主軸類型）。要補的表：`brief/tables/cast.json` 加兩張卡（從 dossier 與 01 表蒸餾，照晴子那張的格），`address.json` 不用動，`samples.json` 多兩段（宮澤：Q16 的對白去掉正解；木下：Q02 的）。

為什麼兩位都叫柚葉也沒關係：display 一個寫「宮澤柚葉」一個寫「木下柚葉」，labels 不含裸的「柚葉」（lint 的 speaker 認 labels）。

## 2. 結構化分數：三處同一套、照四級長

### 2a. 長法（C-55＋STRUCTURE 四級，套到「分數」上）

| 級 | 長相 | 什麼時候升 | 例 |
|---|---|---|---|
| 1 單值 | `"傲嬌": "good"` | 一開始 | good／ok／bad 三檔 |
| 2 物件 | `"傲嬌": {"val": "good", "多樣性": 0.7, "文筆": 0.9, "counter_samples": 4, "rated_at": …}` | 同一個 key 底下有兩種以上不同的「為什麼」（critic 的 reasons 或人評的 tags 分出 ≥ 2 類、各 ≥ 3 筆） | 原值進 `val`（C-55），維度當同層 key，值 0～1 |
| 3 維度再長成物件 | `"文筆": {"val": 0.9, "含蓄": 1.0, "句長": 0.8}` | 同上規則套在一個維度上 | 維度的原值進它的 `val` |
| 4 拆檔 | `"傲嬌": {"$ref": "ratings/傲嬌.json"}` | 這個 key 的物件 > 1 KB（STRUCTURE 條列門檻），或要讓別的程式單獨讀寫它 | `_metainfo` 可用 `$ref`（M 01 §5） |

**降級也成立**：子維度在所有樣本上都跟 `val` 同向、沒提供新資訊（相關 > 0.95、連續兩輪）→ 併回上一級。長與縮都**只在 `train/record` 做**（一個寫者），人不手改。

### 2b. 三處怎麼用

| 處 | 誰寫 | 現在（第 4 輪起點） | 允許長到 |
|---|---|---|---|
| **評分節點**：`out/<題名>/score.json` | judge（每次跑） | 第 2 級：`{"val": "good", "total": 6, "max_total": 6, "dims": {"護欄": 1.0, "語域": 1.0, "語意": 1.0}, "tiers": {…現在的 tier0/1/2…}, "reasons": [...]}`；`val` 由 total 映射（≥5 good、3～4 ok、≤2 bad） | 第 3 級：critic 的 `semantic` 拆 `{"val", "承接", "含蓄", "角色味"}`（critic 的 system.txt 多要三個 0～1；拆不出就留 val） |
| **`_metainfo.ratings`**（§3） | `train/record`、`human/import` | 第 1～2 級：`"ratings": {"文靜": {"val": "good", "多樣性": 0.8, "語意": 0.9, "counter_samples": 4}, "傲嬌": "ok"}` | 第 3～4 級照 2a |
| **優化函數的成果**：`train/optimize/tools/optimizer/_metainfo.ratings.moves` | `train/tune` | 第 2 級：`"moves": {"edit_prompt": {"val": "good", "delta_mean": 0.6, "counter_samples": 3}, "fold": {"val": "bad", "delta_mean": -0.8, "counter_samples": 2}}` | 第 3 級：按「改哪個節點」再分 |

`多樣性` 是**純程式算的**：同一題跑 k 次，k 份稿子兩兩的字元 3-gram 重疊率，1 − 平均重疊＝多樣性（gen_v0「歷史入條件」那套的量尺；只有 k ≥ 2 才有這個維度）。其他維度從 score.json 的 tiers 正規化到 0～1。

## 3. `_metainfo` 的評級欄位：寫法、誰寫、怎麼更新、跟 M7 怎麼辦

### 3a. 寫法——一個 key、自由長、幾個固定格

`_metainfo` 多一個 **`ratings`** 子物件（評級＝rating；裝多個用複數，C-54）。裡面：

```json
"ratings": {
  "文靜": {"val": "good", "語意": 0.92, "語域": 1.0, "護欄": 1.0, "多樣性": 0.71,
          "counter_samples": 4, "rated_at": "2026-10-26T03:12:00.000Z", "round": 2,
          "source": "train/record（自動：score.json＋多樣性）"},
  "傲嬌": "ok",
  "害羞": {"val": "ok", "語意": 0.55, "語域": 0.75, "counter_samples": 4, "rated_at": "…", "round": 2},
  "human": {"傲嬌": {"val": "bad", "tags": ["太直球", "稱呼錯"], "含蓄": 0.2, "counter_samples": 2, "rated_at": "…"}}
}
```

- **通用 key（固定格）**：`val`（C-55 原值，good／ok／bad）、`counter_samples`（幾筆樣本算出來的）、`rated_at`（最近一次更新）、`round`（第幾輪）、`source`（誰算的、怎麼算）。其餘 key（風格名、維度名）**自由**——這就是使用者說的「任意資訊」；讀的人不認得就忽略（C-48）。
- **`human` 是獨立子物件**：人類觀感跟自動評分分開放、各自照 2a 長；不混算（人評是校正器不是訊號，§6）。
- 風格 key 用中文（跟 corpus 的類型名一致，一詞一義）；維度名也中文。它們不是程式的 key、不受「全小寫底線」限制——這一點列進 §9 衝突。

### 3b. 誰寫、怎麼更新

- **只有兩個寫者**：`train/record`（自動評級）與 `human/import`（人評）。被評的函數自己不寫、kernel 不寫、優化器不寫（它只能改 `ratings` 以外的東西——而且是改 `tree/` 複本裡的）。
- **寫法**：讀整份 `_metainfo` → 只動 `ratings` 這個 key（merge：同風格同維度覆寫、新的加）→ N-05 暫存改名。`ratings` 以外的任何 key 一個字元都不動（測試要證明：先改壞一個宣告 key 再 record，record 後那個 key 原樣）。
- **更新規則**：`val` 由該風格的 `語意`×0.5＋`語域`×0.3＋`護欄`×0.2（≥0.8 good、≥0.5 ok、否則 bad）算，權重寫在 `train/score/weights.json`（可被優化器調，§4）；`counter_samples` 累計、數值取**最近兩輪的平均**（不是全史，樹改過就該忘舊的）。
- **寫到哪個資料夾**：`produced_by` 那個節點（產出台詞的 `draft/tools/writer`）＋頂層 `galtxt-b/_metainfo`（整棵樹的評級）。director 不記風格評級（它的產出是表，不是台詞）；critic 記的是**它自己被人評校正的準度**（`ratings.calibration`，§6）。

### 3c. 跟 M7「實測絕不回寫 `_metainfo`」的衝突怎麼處理

M7（10-24）：kernel 量到的 `time_ms`、token **不回寫**使用者的 `_metainfo`，因為那是作者的契約、改了分不出誰說的。使用者 10-25 現在要「跑出來的評級寫進 `_metainfo`」。兩句話都要守，分法是：

| | 宣告（作者寫） | 實測（kernel／deliver 量） | 評級（訓練記） |
|---|---|---|---|
| 放哪 | `_metainfo` 既有 key | kernel 的 `served.jsonl`、deliver 的 `measure.json`（**不進 `_metainfo`**，M7 不變） | `_metainfo.ratings`（**新的、獨立的 key**） |
| 誰寫 | 人／生成樹的程式 | kernel、deliver | 只有 `train/record`、`human/import` |
| 分得出誰說的嗎 | — | 不在同一份檔 | 在同一份檔但不同 key，而且每筆帶 `source`、`rated_at`、`counter_samples` |

所以 M7 從「實測不回寫 `_metainfo`」**收窄成**「實測不回寫**宣告的那些 key**；跑出來的評級寫在 `ratings` 子物件、由專責的記錄者寫」。這是對 10-24 代定的修正，要使用者點頭（§9 第 1 條）。附帶：`time_ms`／`llm_tokens` 的 val 要不要也讓 record 回填（optimize.md §4 說憑空估的 val 都偏 2～3 倍）——**不**，仍照 M7；但 record 可以在 `ratings` 旁寫一個 `measured`（`{"time_ms": {"p50": …, "max": …}, "llm_tokens": {…}, "counter_samples"}`），讓看表的人並排看。這條也列 §9。

## 4. 訓練迴圈：`galtxt-b/train/`

一棵獨立的資料夾程式（照 self-improve 的形：外層 loop、一圈幾格、每一版落檔、原版永遠不動），**由上而下拆、每格有 `_metainfo`**，優化器是它的一個工具 agent。

### 4a. 樹

```
train/                       _entry（exec aos-loop loop.json）、loop.json {"exec": "fsm.json", "max": 40}、fsm.json 一圈九格、_metainfo
  idle/                      純程式：round.json 的 round < max_rounds 且預算沒到頂 → 0；否則 10
  init/                      純程式：第 0 輪才做——複製 galtxt-b（排除 train/、plan/、human/ 的資料檔）到 tree/、寫 round.json；之後 no-op
  run/                       純程式：對 set/ 每題跑 k 次：runs/<輪>/<題>/<次>/ 各一個工作區，aos-exec --ws 它 tree/（可選：寫 daemon.json 交 aos-daemon 並行，§5）
  score/                     純程式：收 runs/<輪>/**/out/*/{score,measure}.json → rounds/<輪>.json（每題每次的 dims、每風格平均、多樣性、token、失敗數、跟上一輪的差）
  record/                    純程式：把 rounds/<輪>.json 的評級寫進 tree/_metainfo 與 tree/draft/tools/writer/_metainfo 的 ratings；把上一輪改動的效果寫進 changes/<輪-1>.json 的 effect
  pick/                      純程式：主動學習挑 ≤ 6 筆 → human/samples.json（§6）
  optimize/                  黏合：把 tree 的 _metainfo 表（metainfo_table.py 跑出來的 json）、rounds/<輪>.json、允許的改動清單交給 tools/optimizer，收 changes/<輪>.json
    tools/optimizer/         agent（agent-dan 形，有工具 read／json_read 指 proto8/lib/base，只讀）：提出 1～3 條改動，不直接改檔
  apply/                     純程式：驗 changes/<輪>.json（白名單：哪些檔、哪種改法）→ 改 tree/、寫 diff；不合白名單的那條標 rejected
  verify/                    純程式：改完的 tree 形狀還對（fsm.json 可解、_metainfo 形狀測試那段、lint 自測綠、假腦 demo 一題跑通）；壞了就把 tree/ 退回上一版快照、這輪的改動標 reverted
  tune/                      純程式（第 2 層）：讀 changes/*.json 的 effect，更新 optimizer/_metainfo.ratings.moves；某類改動 counter_samples ≥ 3 且 delta_mean < 0 → 在 optimizer 的 system.txt「不要做」清單加一行（§4d）
```

`fsm.json`：`idle → init → run → score → record → pick → optimize → apply → verify → tune → idle`；每格「不是我的回合就退 0」（第 0 輪 optimize／apply／verify／tune 都 no-op——先有基準再改）。`round.json`：`{"round": n, "max_rounds": 2, "k": 2}`。loop `max` 40 兜底。

### 4b. 一輪在做什麼（白話）

1. **跑**：6 題各跑 2 次＝12 份稿、12 份 score.json、12 份 measure.json（約 20 萬 token、並行 6 個約 40 秒、串行約 4 分鐘）。
2. **算**：每題兩次的 dims 平均、兩稿的多樣性；每風格（3 個）跨兩題平均→這一輪的風格評級；token 加總；失敗（退非 0、PlanBad、ToolFailed…）計數。跟上一輪比 → `delta`。
3. **記**：評級進 `tree/` 兩個 `_metainfo` 的 `ratings`；上一輪的改動＋這輪的 delta 合起來＝那次改動的效果，寫回 `changes/<上一輪>.json.effect`。
4. **挑**：6 筆給人看（§6）。
5. **改**：優化器讀 `_metainfo` 表（它看到的就是 optimize.md 看的那張表＋`ratings`）、本輪成果、上一輪改動的效果、改動白名單，提 1～3 條改動（JSON）；apply 照白名單改 `tree/`；verify 確認樹沒壞。
6. 回 idle；round＋1；第 2 輪再跑一次就知道改動有沒有用。使用者說一兩輪就好：**`max_rounds` 預設 2**（基準＋改一次＋驗一次＝跑樹 3 輪）。

### 4c. 優化器（第 1 層）能改什麼——白名單，程式動手、腦只決定

| 改動種類（`kind`） | 能動的路徑（`tree/` 內） | 怎麼寫 | 風險 |
|---|---|---|---|
| `edit_prompt` | `draft/tools/{writer,director}/system.txt`、`judge/tools/critic/system.txt` | `{"kind": "edit_prompt", "path", "old", "new", "why"}`（old 必須唯一命中） | 低；最常用 |
| `edit_table` | `brief/tables/*.json` 的某個指標 | `{"kind": "edit_table", "path": "brief/tables/cast.json#/宮澤柚葉/voice/ng/-", "op": "set|append|del", "value", "why"}` | 中；稱謂 regex 壞了 lint 會 BriefBad → verify 擋 |
| `set_param` | 場景預設（`lines`、`max_redrafts`）、單子的 `timeout_ms`、`train/score/weights.json`、think 單子的 `llm_model`（限 gpt 系列名單） | `{"kind": "set_param", "path": "檔#/指標", "value", "why"}` | 低 |
| `fold`／`unfold` | 任一節點 | `{"kind": "fold", "target": "judge/tools/critic", "to": 4}`——交給 `plan/aos-fold`（round3） | 高；verify 一定跑假腦 demo |
| `reroute` | `draft/_entry` 要叫哪個 writer（只有長出第二個 writer 變體後才有意義） | `{"kind": "reroute", "style": "傲嬌", "to": "tools/writer_tsundere"}` | 中；第 4 輪先列在白名單、預期用不到 |
| `fork_node` | 複製 writer 成 `writer_<風格>`（只改 system.txt）、draft 照 `style` 選路 | `{"kind": "fork_node", "from": "draft/tools/writer", "name": "writer_傲嬌", "edit_prompt": {…}}` | 高；是 reroute 的前提 |

不在白名單：改 `lib/`（lint 規則＝判準，改了分數不可比——self-improve 的「改進者看不到判準」同理，lint 與 critic 的 system.txt 列為**可改但 verify 要跑校準集**，見 §6）、改 `train/`、改 `ratings`、刪檔、跑 shell。優化器的工具只有唯讀的 read／json_read（proto8/lib/base，沙盒＝訓練場 `$AOS_WS`）；它輸出 changes JSON，**apply 用程式改**——C-22 能寫死的動作不交給腦，也讓每條改動可審、可退。

優化器一次問腦：輸入＝`_metainfo` 表（約 3k token）＋本輪成果（1k）＋上一輪效果（0.5k）＋白名單與格式（1k）→ 輸出 ≤ 1k。約 7k。

### 4d. 第 2 層：`train/tune`（純程式、不問腦）

成果是「每一類改動帶來的分數變化」：`changes/<輪>.json`＝`{"round", "moves": [{kind, path, why, applied|rejected|reverted}], "effect": {"delta_total_mean": +0.5, "delta_by_style": {…}, "delta_tokens": -1200}}`。tune 把它累進 `optimizer/_metainfo.ratings.moves.<kind>`（第 2 級：`val`、`delta_mean`、`counter_samples`），再做一件事：某類 `counter_samples ≥ 3` 且 `delta_mean ≤ 0` → 在 optimizer 的 `system.txt` 末尾「經驗」段加一行「`<kind>` 在本樹上平均 −x 分，先不要用」；`delta_mean ≥ +0.5` 加一行「`<kind>` 有效，優先考慮」。這就是「用更簡單的東西讀紀錄調整優化器一次」——規則式，不問腦，零 token。

**第 2 層的成果什麼時候才有一筆**：一次 `fork`／`edit_prompt` 的效果要「改前一輪、改後一輪」兩個完整評估才量得到＝24 次跑樹（6 題×2 次×2）。兩輪訓練只給第 2 層 1～2 筆樣本，`counter_samples ≥ 3` 的門檻碰不到——第 4 輪 tune 多半只記不改，這是誠實的預期。

### 4e. 第 N 層：推論（不做）

| 層 | 它優化的對象 | 它的「成果」是什麼 | 一筆成果要跑幾次下層 | 成本（6 題×2 次、每次 1.7 萬 token） |
|---|---|---|---|---|
| 1（galtxt-b 樹） | 台詞 | 一次跑的結構化分數 | 1 次 | 1.7 萬 |
| 2（optimizer） | 第 1 層的樹 | 一條改動造成的分數變化 Δ | 改前改後各一輪＝24 次 | 41 萬 |
| 3（tune 或優化 optimizer 的腦） | optimizer 的提案策略 | **Δ 的變化**：換了策略之後，每條改動的平均 Δ 升了多少（ΔΔ） | 要比較「舊策略下的 m 條改動」與「新策略下的 m 條」，m ≥ 3 才壓得住雜訊 ＝ 2×3×24＝144 次 | 245 萬 |
| 4 | 第 3 層的規則 | ΔΔ 的變化 | 再乘 2×3 ＝ 864 次 | 1 470 萬 |

**成本每層約 ×6（2 個對照 × 3 筆樣本）、效果量每層變小、雜訊不變**：第 1 層同一題同一樹跑兩次總分可以差 2（q01 6 分、q08 4 分，而且還是不同題；同題重跑的 σ 要先量——§8 工作清單第 0 項），σ≈1 時 12 次的平均標準誤≈0.3，第 2 層能辨認 |Δ| ≥ 0.6 的改動；第 3 層的 ΔΔ 多半 < 0.3，要 144 次才勉強有訊號、而且是在假設第 2 層的改動效果穩定（它不穩定：樹每輪在變）。**結論：塔在第 2 層停、第 3 層只做規則式 tune（零成本、不求訊號），不值得往上疊**；要往上疊的判準寫成一條：下一層預期帶來的分數增益 × 它成功的機率 < 它要燒的 token 換算成「直接多跑第 1 層幾次」的增益時，不疊。

**同一棵優化樹優化自己（自我參照）能不能收住塔**：機械上可以（optimizer 的 `tree/` 包含它自己、白名單加上它自己的 system.txt），但會壞在三處：① **判準洩漏**——它改得到 score／record／critic 就能把分數改好看（self-improve 的教訓「改進者看不到判準」、C-64 要用權限隔開：判準那幾個資料夾另一個 Linux 使用者或唯讀）；② **非定態**——它一邊改自己一邊產生第 2 層樣本，樣本不再是同一個策略的，`delta_mean` 沒有意義；③ **退化的不動點**——「什麼都不改」永遠零風險，自我參照的優化器很容易收斂到不作為。所以不做自我參照；第 2 層用純程式 tune，它沒有腦、改不壞判準、也不會為了保護自己什麼都不改。

## 5. 要不要自己做 kernel／daemon

| 需求 | 現成的夠不夠 | 結論 |
|---|---|---|
| 一輪 12 次跑樹要並行 | **aos-daemon 剛好**：`train/run` 寫一份 `daemon.json`，`loops` 每項＝`{"exec": ["aos-exec", "--ws", "runs/<輪>/<題>/<次>", "tree"], "max": 1}`，`aos-exec daemon.json`；全部 `done` 就收工。每個小格各自的 stack（P-17） | 用 daemon，不做新的 |
| 控 token 額度 | aos-kernel-llm 有 `budget.max_tokens`／`max_calls` 每窗額度，但要腦經 aos-gate 寄信才算得到；現在三隻腦函數直接打 API | **這輪不經 kernel**：train 自己算（每次跑的 `measure.json.counter_tokens` 加總，`train/budget.json` 的 `max_tokens`／`max_rounds`，到頂 idle 退 10、stderr 一行 `train: BudgetSpent`——照 self-improve 代定 6）。要改成經 gate 只要把 think 單子的 `argv` 前面插 `aos-gate`，樹不用動；等多隊共用一個 LiteLLM 要分配額度時再接 |
| 按 `_metainfo.ratings` 選路（傲嬌題交給評級 good 的 writer 變體） | kernel-llm 排隊只看 priority／time_ms，不看風格；而且選路是「叫哪個函數」不是「哪封信先跑」 | 不是 kernel 的事：`draft/_entry` 讀 `tree/draft/tools/writer*/_metainfo.ratings[style].val`，挑最好的（同分取名字最短＝原版）——純程式 20 行，等 `fork_node` 長出第二個變體才啟用。寫在 draft 黏合格裡，不另立 `route/` |
| 排隊叫腦（LiteLLM 同時太多連線） | daemon 並行 6 個小格＝同時 6 路問腦；LiteLLM 單機應該吃得下；吃不下就 daemon 的 `loops` 分兩批 | 不需要 |

結論：**不做新的 kernel／daemon**；用 aos-daemon 並行、train 自己記帳。

## 6. 人評：樣本、問題、匯入、校正

### 6a. 契約（照隊長給的，補細節）

`human/samples.json`（`train/pick` 寫；陣列、≤ 6 筆、台詞短）：

```json
[{"id": "b-r1-讓書-宮澤-2", "team": "b", "round": 1,
  "scene": {"cast": ["主角", "宮澤柚葉"], "place": "河鹿堂", "event": "同時伸手拿同一本書、她讓書", "intent": "鉤", "style": "傲嬌"},
  "lines": ["主角：「啊，抱歉，妳先請。」", "宮澤柚葉：「才、才不是要讓你……只是我拿不動而已。」", "…（≤ 10 句）"],
  "produced_by": "draft/tools/writer",
  "auto_scores": {"val": "ok", "dims": {"護欄": 1.0, "語域": 0.5, "語意": 0.67, "多樣性": 0.6}, "register_agree": false},
  "why_picked": "程式語域 1 分、critic 語域 2 分：兩個評分器不合"}]
```

`human/questions.json`（這份是**設計**，網頁照它出題；頂層做網頁）：

```json
{"overall": ["good", "ok", "bad"],
 "tags": ["油膩", "太直球", "OOC（不像這個角色）", "稱呼不對階", "世界穿幫", "沒承接前文", "太長／囉嗦", "太短／沒戲", "旁白說明腔", "像真的 galgame"],
 "dims": ["含蓄", "角色味", "承接", "文筆", "多樣性"],
 "note": "每筆最多兩下：overall 一鍵，叉的話再點一個 tag；dims 選填（滑桿 0～1）；comment 選填。"}
```

`human/ratings.json`（網頁寫回；每筆 `{"id", "overall", "tags", "dims", "comment", "rated_at"}`）。

### 6b. 怎麼挑 6 筆（`train/pick`，主動學習、純程式）

依序填滿、每風格至少 1 筆：
1. **兩個評分器不合的**：`register_agree: false`（程式算的語域 vs critic 給的）——這是「自動評分最拿不準」的直接證據，1～3 筆。
2. **critic 中間分的**：`semantic` 1 或 2（0、3 它很確定），各風格挑 1。
3. **校正錨**：自動 `val` 最高的一筆與最低的一筆各 1——人同不同意兩端，是校正最便宜的訊號。
4. 補到 6：同一風格多樣性最低的（看人覺不覺得「都一樣」）。

台詞短的優先（≤ 8 句）；同一題同一次只挑一筆。

### 6c. 匯入 `human/import/`（資料夾程式、純程式）

`aos-exec --ws 訓練場 galtxt-b/human/import`：讀 `$AOS_WS/human/ratings.json` 與 `samples.json`，對 `id` → 找 `produced_by`、`style` → 寫進 `tree/<produced_by>/_metainfo.ratings.human.<style>`（第 2 級：`val`＝多數票、`tags` 計數前三、`dims` 平均、`counter_samples`）與頂層；另寫 `human/calibration.json`：

```json
{"counter_rated": 6,
 "agreement": {"overall": 0.67, "by_style": {"文靜": 1.0, "傲嬌": 0.5, "害羞": 0.5}},
 "confusion": [{"auto": "good", "human": "bad", "ids": ["b-r1-讓書-宮澤-2"], "tags": ["太直球"]}],
 "suggest": ["傲嬌：人說太直球、自動沒抓到 → critic 對傲嬌的「含蓄」要更嚴；或 lint 加規則「傲嬌句尾要有否認／讓步」"]}
```

`train/score` 下一輪讀 `calibration.json`：某風格 agreement < 0.5 → 該風格的自動 `val` 加註 `"calibrated": false`（記錄者標、不改分）；優化器看得到這個標記與 `suggest`——**人評透過校正表影響優化器，不直接進分數**。critic 的 `_metainfo.ratings.calibration` 記 agreement（它被評的是「準不準」）。

### 6d. 多少人評才夠、怎麼挑（結論）

- **每輪 6 筆、兩輪 12 筆**（約 10 分鐘）。目的是抓**系統性**不合（某風格自動一直說 good、人一直說 bad），12 筆分 3 風格各 4 筆，夠看出「某風格的評分器偏了」，不夠估細維度的權重。
- 停的條件：連續兩輪 `agreement.overall ≥ 5/6` → 之後每輪只給 2 筆（兩端錨）。
- 挑法見 6b；不挑「自動很確定」的（人力花在最拿不準處）。
- 使用者說「最好少用」：預設 `pick` 只在 `round.json.human: true` 時寫 samples；關掉就不產生。

## 7. token 預算

| 項 | 數 | 依據 |
|---|---|---|
| 一次跑樹 | ≈ 1.7 萬 token、15～18 秒 | round2 實測 17115／17379（optimize.md 前三名做了會降到約 1.1 萬） |
| 一輪 | 6 題 × 2 次 ＝ 12 次 → **≈ 20.5 萬**；優化器 1 次 ≈ 0.7 萬；critic 已含在跑樹裡 → **≈ 21 萬／輪** | k＝2 是「多樣性」維度與壓雜訊的最低值 |
| 一次完整訓練（基準輪＋改 1 次＋驗 1 次） | 3 × 20.5 萬 ＋ 2 × 0.7 萬 ≈ **63 萬**；時間並行約 2 分鐘、串行約 12 分鐘 | `max_rounds: 2` |
| 省錢版 | k＝1、4 題（兩風格）→ 一輪 6.8 萬、全程 21 萬；代價：沒有多樣性維度、σ 更大 | 要先量 σ 再決定 k |
| 預算檔 `train/budget.json` | `{"max_rounds": 2, "max_tokens": 800000, "max_elapsed_ms": 3600000}`，到頂 idle 退 10 | 照 self-improve 代定 6 的形（10-25 已改 `max_*`） |

腦只用 gpt 系列（`.env` 的 `chatgpt-gpt-6-luna-low`；優化器用同一個，`llm_model` 進 set_param 白名單時只能選 `chatgpt-gpt-6-*`）。

## 8. 給實作者的工作清單與驗收

0. **先量雜訊**（半小時、約 10 萬 token）：現有 tree 用真腦把 q01、q08 各跑 3 次，記總分與 dims 的 σ，寫進 `plan/runs/round4/noise.md`。σ 決定 k（σ ≤ 0.7 → k＝2 夠；σ > 1 → k＝3 或先修評分器）。
1. **範圍**：`brief/tables/cast.json` 加宮澤柚葉、木下柚葉兩張卡（照晴子那張的格；資料從 `corpus/人物/` 與 `固化/01` 蒸餾，1 表的傲嬌／害羞兩節有現成的句尾、口癖、NG）；`samples.json` 加兩段；`train/set/` 六題 JSON（多 `style`）；brief 把 `style` 放進 brief.json、沒寫就取女角卡的第一個 type。
2. **結構化分數**：judge 的 `score.json` 加 `val`、`dims`（2b）；critic system.txt 多要 `dims: {含蓄, 承接, 角色味}`（0～1，拆不出就不給）；`tests` 加 score 形狀案例。
3. **`human/`**：`questions.json`（照 6a）、`import/{_entry,_metainfo}`（6c）、`README.md` 一頁寫契約；測試：假 ratings.json 6 筆 → `_metainfo.ratings.human` 正確、`ratings` 以外 key 一字不變、calibration.json 的 agreement 算對、壞 id＝`SampleUnknown` 跳過不擋。
4. **`train/`**：九格照 4a；`_metainfo` 照 §10；`optimizer/` 從 agent-dan 複製（工具 read／json_read 捷徑到 `../../../../../lib/base/…`——路徑太長就寫絕對；注意 proto8/lib 在 repo 裡、訓練場在外）；`apply` 的白名單與 `fold` 接 `plan/aos-fold`；`verify` 跑：`fsm.json` 可解、`_metainfo` 形狀（抄測試的 `meta_problems`）、`lib/lint` 自測、假腦跑 set 第一題。
5. **假腦**：optimizer 的假腦固定回一條 `edit_prompt`（在 writer 的 system.txt 末尾加「（假腦加的一行）」）；critic 假腦固定 dims；這樣假腦端到端能走完兩輪、`changes/1.json` 有 effect（假腦分數不變＝delta 0）。
6. **測試** `proto8/tests/test_topdown_galtxt_b_train.py`：假腦兩輪端到端（`max_rounds: 2`、k＝1、set 兩題）結束碼 0、`rounds/{0,1,2}.json`、`changes/1.json.effect` 在、`tree/_metainfo.ratings` 有三風格（或兩）、原 galtxt-b 樹一字未動（hash）；白名單：一條 `edit_prompt` 指到 `lib/lint` → rejected；一條壞 old → rejected；verify 退回：故意把 changes 寫成把 fsm.json 弄壞 → tree 回上一版、標 reverted；budget 到頂 → idle 退 10、`train: BudgetSpent`；pick 挑法：構造 12 筆假 score，斷言挑出的 6 筆符合 6b 的順序與「每風格至少 1」；ratings 四級成長：餵 reasons 分兩類各 3 筆 → 該風格長成第 2 級；全同向兩輪 → 併回；真腦案例（連不上 skip）：`max_rounds: 1`、k＝1、2 題，看 changes/1.json 有優化器真提的改動且 apply 成功。
7. **文件**：README 加 train／human 一段；`plan/runs/round4/` 放真腦一次完整訓練的 `rounds/*.json`、`changes/*.json`、`human/samples.json`。

驗收：上面測試全綠；原 23 條照過；`sh demo.sh` 照過；真腦一次完整訓練（§7 的 63 萬）跑完，`changes/1.json.effect.delta_total_mean` 有數字（正負都算成功——目的是流程走通、訊號能量到）；`human/samples.json` 6 筆交給頂層做網頁。

## 9. 跟原則衝突、要使用者定的

1. **M7 vs 評級進 `_metainfo`**（§3c）：建議把 M7 收窄成「實測不回寫宣告 key；評級由 record／import 寫進 `ratings`」。要使用者點頭，然後落條文。附帶一題：`time_ms`／`llm_tokens` 的 val 要不要讓 record 在 `ratings.measured` 旁寫一份實測（不改宣告）。
2. **`ratings` 裡的 key 用中文**（風格名「傲嬌」、維度「多樣性」）：C-54 說 JSON key 全小寫底線，但這些是資料值當 key（跟 corpus 一詞一義），不是程式認的格。要嘛接受「自由區的 key 不受命名規則管」，要嘛轉成拼音／英文（`tsundere`、`diversity`）——我建議前者，寫進 C-48「不認得的 key 一律忽略」旁邊當註。
3. **評分結構三處同一套的「長」由 record 自動做**：C-55 說的成長是人整理時做的；這裡讓程式照門檻自動升級／降級。自動長會讓 `_metainfo` 的形狀隨時間變、讀者要兩形都收（C-48 雙形本來就要求）。要不要讓程式自動長、還是只建議人來長，方向性問題。
4. **優化器改的是 `tree/` 複本、不是 repo 裡的樹**：好的改動怎麼「畢業」回 repo（人看 diff 後 `cp`？自動 commit？）沒定；我建議人看。跟 self-improve「原版永遠不動」一致，但使用者說的「改樹」若指 repo 裡那棵，就是另一種做法。
5. **判準能不能被優化器改**（critic 的 system.txt、lint 規則、score 權重）：改了分數就不可比，但「校正評分器」又正是人評的目的。我的切法：lint 不可改；critic 的 system.txt 與 weights 可改**但只能由人評的 `calibration.suggest` 觸發**（優化器只有在 calibration.json 說某風格偏了才准動 critic）。這是我代定的，列出來。
6. **`train/` 放在 galtxt-b 裡還是旁邊**：放裡面（`galtxt-b/train/`）符合「一個題目一棵樹」，但複製 `tree/` 時要排除自己、而且 `_metainfo` 形狀測試會把 train 底下的資料夾也算進去（是好事）。放旁邊（`galtxt-b-train/`）乾淨但多一個頂層資料夾。我選裡面，可翻。
7. **並行跑用 aos-daemon**：daemon 的子項名字＝小格名，12 個名字要不撞、不能帶 `#`；6 個同時打 LiteLLM 的連線數使用者那邊吃不吃得下不知道。
8. **人評的 `human` 子物件要不要進總分**：我定不進（只校正）。使用者說「使用者觀感也可以納入考量」可以讀成要進；兩種後果：進＝人評變主訊號、6 筆就能左右一輪；不進＝人評只改評分器、慢一輪才生效。
9. **第 3 層以上不做**（§4e 的判準）：使用者說「可以繼續疊加」，我的結論是第 2 層用規則、第 3 層不值得；這是方向性判斷，要他看過成本表再定。
10. **經驗留存與 MCP（使用者的支線）**：經驗留在 `plan/lessons.md`（每輪一節：這次拆法哪裡對、哪裡錯、`_metainfo` 哪些 key 真的被用到）——不進 thinking（那裡只留使用者原文與結論）。MCP：這棵樹對外只有一個入口（`aos-exec --ws ws galtxt-b`、題目放 `new/`、答案在 `out/`），包成 MCP 只是一個 tool `galtxt.generate(scene) → {lines, score}`：起暫存工作區、寫 `new/`、跑、讀 `out/`；訓練迴圈也能包成 `galtxt.train(set, rounds)`。資料夾程式天生就是「一個工具一個入口」，MCP server 只是薄殼，不改樹。寫一段放 lessons.md 即可，不另開檔。

## 10. 新資料夾的 `_metainfo`（實作者照抄）

`human/_metainfo`：

```json
{"summary": "人評契約與匯入：samples.json（挑給人看的 ≤ 6 筆）、ratings.json（網頁寫回）、questions.json（網頁問什麼）、import/ 把評級併進 _metainfo.ratings.human 並算校正表",
 "kind": "dir"}
```

`human/import/_metainfo`：

```json
{"summary": "把 human/ratings.json 併進 produced_by 資料夾與頂層 _metainfo 的 ratings.human（只動 ratings 這個 key），並寫 human/calibration.json（自動 vs 人的一致率、混淆、建議）",
 "time_ms": {"val": 50, "max": 2000}, "resource": ["cpu", "disk"],
 "side_effect": true, "idempotent": true, "deterministic": true, "interrupt": "safe", "parallel": false,
 "reads": ["$AOS_WS/human/ratings.json", "$AOS_WS/human/samples.json", "$AOS_WS/tree/**/_metainfo"],
 "writes": ["$AOS_WS/tree/<produced_by>/_metainfo#/ratings/human", "$AOS_WS/tree/_metainfo#/ratings/human", "$AOS_WS/human/calibration.json"],
 "grow_level": 3, "writer_of": ["ratings.human"]}
```

`train/_metainfo`：

```json
{"summary": "訓練迴圈：對 set/ 的題把 tree/（galtxt-b 的複本）跑 k 次、算結構化成果、記進 tree 的 _metainfo.ratings、挑人評樣本、讓 optimizer 提改動、程式套用並驗證，再跑下一輪；第 2 層 tune 用規則調 optimizer",
 "time_ms": {"val": 180000, "max": 3600000}, "resource": ["llm", "cpu", "disk"],
 "llm_calls": {"val": 49, "max": 140}, "llm_tokens": {"val": 210000, "max": 800000},
 "llm_endpoint": "http://localhost:4000/v1", "llm_model": "chatgpt-gpt-6-luna-low",
 "side_effect": true, "idempotent": false, "deterministic": false, "interrupt": "resumable", "parallel": false,
 "lock": [{"$env": "AOS_WS", "$prefix": "ws:"}],
 "reads": ["$AOS_WS/set/*.json", "$AOS_WS/tree/", "$AOS_WS/human/ratings.json", "budget.json"],
 "writes": ["$AOS_WS/tree/（改動與 ratings）", "$AOS_WS/runs/", "$AOS_WS/rounds/", "$AOS_WS/changes/", "$AOS_WS/human/samples.json", "$AOS_STACK/round.json"],
 "grow_level": 5, "unit": "round",
 "per_round": {"counter_runs": 12, "counter_llm_calls": {"val": 49, "max": 70}, "llm_tokens": {"val": 210000, "max": 300000}}}
```

`train/idle/_metainfo`：`{"summary": "round.json 的 round < max_rounds 且預算沒到頂就 0，否則 10（BudgetSpent 時 stderr 一行）", "time_ms": {"val": 5, "max": 100}, "resource": "cpu", "side_effect": false, "idempotent": true, "deterministic": true, "interrupt": "safe", "parallel": true, "reads": ["$AOS_STACK/round.json", "budget.json", "$AOS_WS/rounds/*.json"], "writes": [], "grow_level": 3}`

`train/init/_metainfo`：`{"summary": "第 0 輪：複製 galtxt-b（排除 train/、plan/、human/ 的資料檔）到 $AOS_WS/tree/、寫 round.json；之後什麼都不做", "time_ms": {"val": 200, "max": 5000}, "resource": ["cpu", "disk"], "side_effect": true, "idempotent": true, "deterministic": true, "interrupt": "safe", "parallel": false, "reads": ["../（galtxt-b 本體）"], "writes": ["$AOS_WS/tree/", "$AOS_STACK/round.json"], "grow_level": 3}`

`train/run/_metainfo`：

```json
{"summary": "對 set/ 每題跑 k 次：runs/<輪>/<題>/<次>/ 各一個工作區，aos-exec --ws 它 tree/；可寫 daemon.json 交 aos-daemon 並行",
 "time_ms": {"val": 60000, "max": 1800000}, "resource": ["llm", "cpu"],
 "llm_calls": {"val": 48, "max": 132}, "llm_tokens": {"val": 205000, "max": 540000},
 "llm_endpoint": "http://localhost:4000/v1", "llm_model": "chatgpt-gpt-6-luna-low",
 "side_effect": true, "idempotent": false, "deterministic": false, "interrupt": "resumable", "parallel": true,
 "reads": ["$AOS_WS/set/*.json", "$AOS_WS/tree/", "$AOS_STACK/round.json"],
 "writes": ["$AOS_WS/runs/<輪>/<題>/<次>/{new,out,.stack}", "$AOS_STACK/run/daemon.json"],
 "grow_level": 3, "unit": "round",
 "note": "llm_* 是 12 次跑 tree 的合計（M6 外層自報）；這一格自己不問腦；parallel 指它自己可以用 daemon 同時起 6 個"}
```

`train/score/_metainfo`：`{"summary": "收 runs/<輪>/**/out/*/{score,measure}.json → rounds/<輪>.json：每題每次 dims、每風格平均、多樣性（k 稿 3-gram 重疊）、token、失敗數、跟上一輪的 delta；讀 human/calibration.json 標 calibrated", "time_ms": {"val": 100, "max": 5000}, "resource": ["cpu", "disk"], "side_effect": true, "idempotent": true, "deterministic": true, "interrupt": "safe", "parallel": false, "reads": ["$AOS_WS/runs/<輪>/", "$AOS_WS/rounds/<輪-1>.json", "$AOS_WS/human/calibration.json", "weights.json"], "writes": ["$AOS_WS/rounds/<輪>.json"], "grow_level": 4}`

`train/record/_metainfo`：`{"summary": "把 rounds/<輪>.json 的評級寫進 tree/_metainfo 與 tree/draft/tools/writer/_metainfo 的 ratings（只動這個 key；照四級門檻升／降級）；把上一輪改動的效果寫進 changes/<輪-1>.json", "time_ms": {"val": 50, "max": 2000}, "resource": ["cpu", "disk"], "side_effect": true, "idempotent": true, "deterministic": true, "interrupt": "safe", "parallel": false, "reads": ["$AOS_WS/rounds/<輪>.json", "$AOS_WS/rounds/<輪-1>.json", "$AOS_WS/changes/<輪-1>.json"], "writes": ["$AOS_WS/tree/_metainfo#/ratings", "$AOS_WS/tree/draft/tools/writer/_metainfo#/ratings", "$AOS_WS/changes/<輪-1>.json#/effect"], "grow_level": 3, "writer_of": ["ratings（human 以外）"]}`

`train/pick/_metainfo`：`{"summary": "主動學習挑 ≤ 6 筆給人評：評分器不合的、critic 中間分的、最高最低各一、多樣性最低的；每風格至少 1、台詞短優先 → human/samples.json；round.json.human 為 false 就什麼都不做", "time_ms": {"val": 30, "max": 2000}, "resource": ["cpu", "disk"], "side_effect": true, "idempotent": true, "deterministic": true, "interrupt": "safe", "parallel": false, "reads": ["$AOS_WS/rounds/<輪>.json", "$AOS_WS/runs/<輪>/**/out/*/answer.txt"], "writes": ["$AOS_WS/human/samples.json"], "grow_level": 3}`

`train/optimize/_metainfo`：

```json
{"summary": "黏合：把 tree 的 _metainfo 表（含 ratings）、本輪成果、上一輪改動的效果、白名單交給 tools/optimizer，收 changes/<輪>.json（1～3 條改動提案）；第 0 輪什麼都不做",
 "time_ms": {"val": 9000, "max": 300000}, "resource": ["llm", "cpu"],
 "llm_calls": {"val": 1, "max": 2}, "llm_tokens": {"val": 7000, "max": 15000},
 "llm_endpoint": "http://localhost:4000/v1", "llm_model": "chatgpt-gpt-6-luna-low",
 "side_effect": true, "idempotent": false, "deterministic": false, "interrupt": "resumable", "parallel": false,
 "reads": ["$AOS_WS/tree/**/_metainfo", "$AOS_WS/rounds/<輪>.json", "$AOS_WS/changes/<輪-1>.json", "whitelist.json"],
 "writes": ["$AOS_WS/changes/<輪>.json", "$AOS_STACK/optimizer/"],
 "grow_level": 4, "calls": ["tools/optimizer"]}
```

`train/optimize/tools/optimizer/_metainfo`（第 1 層優化器；它的 `ratings.moves` 由 tune 寫）：

```json
{"summary": "優化器 agent：讀 _metainfo 表與成果，用唯讀工具看 tree 裡的檔，提出 1～3 條白名單內的改動（JSON），不直接改檔",
 "time_ms": {"val": 8000, "max": 240000}, "resource": ["llm", "cpu"],
 "llm_calls": {"val": 1, "max": 4}, "llm_tokens": {"val": 7000, "max": 15000},
 "llm_endpoint": "http://localhost:4000/v1", "llm_model": "chatgpt-gpt-6-luna-low",
 "side_effect": false, "idempotent": false, "deterministic": false, "interrupt": "resumable", "parallel": true,
 "reads": ["$AOS_WS/new/*.json", "$AOS_WS/cur/*.json", "tree/**（經 read／json_read，唯讀）", "system.txt"],
 "writes": ["$AOS_WS/out/<n>.txt", "$AOS_STACK/{history.jsonl,llm.jsonl}"],
 "grow_level": 5, "shape": "demo/agent-dan（工具：read、json_read 捷徑到 proto8/lib/base）",
 "ratings": {"moves": {}}}
```

`train/apply/_metainfo`：`{"summary": "驗 changes/<輪>.json 每條改動合白名單（路徑、kind、old 唯一命中）→ 改 tree/、寫 diff；不合的標 rejected；fold 交 plan/aos-fold", "time_ms": {"val": 200, "max": 60000}, "resource": ["cpu", "disk"], "side_effect": true, "idempotent": true, "deterministic": true, "interrupt": "resumable", "parallel": false, "reads": ["$AOS_WS/changes/<輪>.json", "whitelist.json", "$AOS_WS/tree/"], "writes": ["$AOS_WS/tree/", "$AOS_WS/changes/<輪>.json#/moves/*/status", "$AOS_WS/snapshots/<輪>/（改前快照）"], "grow_level": 3}`

`train/verify/_metainfo`：`{"summary": "改完的 tree 形狀還對：fsm.json 可解、_metainfo 形狀、lib/lint 自測、假腦跑 set 第一題退 0；壞了就從 snapshots/<輪> 退回、改動標 reverted", "time_ms": {"val": 3000, "max": 120000}, "resource": ["cpu", "disk"], "side_effect": true, "idempotent": true, "deterministic": true, "interrupt": "safe", "parallel": false, "reads": ["$AOS_WS/tree/", "$AOS_WS/snapshots/<輪>/"], "writes": ["$AOS_WS/tree/（退回時）", "$AOS_WS/changes/<輪>.json#/verify"], "grow_level": 3, "note": "假腦跑一題不問腦，verify 零 token"}`

`train/tune/_metainfo`（第 2 層）：`{"summary": "第 2 層（規則、不問腦）：讀 changes/*.json 的 effect，累進 optimizer/_metainfo.ratings.moves（每類改動的 delta_mean、counter_samples）；某類 ≥ 3 筆且平均 ≤ 0 → 在 optimizer 的 system.txt 經驗段加「先不要用」，≥ +0.5 加「有效」", "time_ms": {"val": 20, "max": 2000}, "resource": ["cpu", "disk"], "side_effect": true, "idempotent": true, "deterministic": true, "interrupt": "safe", "parallel": false, "reads": ["$AOS_WS/changes/*.json"], "writes": ["optimize/tools/optimizer/_metainfo#/ratings/moves", "optimize/tools/optimizer/system.txt（經驗段）"], "grow_level": 3, "layer": 2, "writer_of": ["ratings.moves"]}`

`train/optimize/tools/_metainfo`、`train/set/_metainfo`（`kind: data`，六題）照既有寫法。

### 既有 `_metainfo` 的 diff

| 檔 | 改什麼 |
|---|---|
| `galtxt-b/_metainfo` | 加 `"ratings": {}`（空物件，record 會填）；`writes` 的 out 加 `score.json 第 2 級（val、dims）` |
| `draft/tools/writer/_metainfo` | 加 `"ratings": {}` |
| `judge/tools/critic/_metainfo` | 加 `"ratings": {"calibration": {}}`（import 填 agreement） |
| `judge/_metainfo` | `summary` 加「score.json 帶 val 與 dims」 |
| `brief/tables/_metainfo` | summary 加兩張人物卡、兩段樣本 |

---

**結論一句**：樹本身不再長（第 3 輪收完就是它），這輪長的是**圍著它的環**——評級進 `_metainfo.ratings`（跟宣告、實測分開住）、分數照四級結構長、一棵獨立的 `train/` 用 12 次跑樹換一條改動的效果、第 2 層用規則不用腦、人評 6 筆只校正不計分；塔在第 2 層停，理由是成本每層 ×6 而效果量越來越小。

## 11. 實作結果 A 段（opus，10-25；§8 第 0～3 項＋基準輪與人評樣本）

**中途改方向**（使用者 10-25，隊長轉）：「我這邊修改一下方向：把目標限縮到單一性格，單一場景。」「限縮角色設定，限縮故事背景。盡可能控制各種變量，然後我預期子樹會很深層...，因爲最終目標是讓整棵樹都不依靠LLM」。所以 §1 的「三種風格 × 兩事件」縮成**傲嬌（宮澤柚葉）× 一個固定場景**；害羞（木下柚葉）停掉（卡與 q02 樣本留著、不再擴）。B 段（§8 第 4～7 項）暫停，等規劃者的 round5。

- **範圍**：宮澤柚葉的卡縮成精簡、寫死的資料（type 只有「傲嬌（主軸）」、幾條固定特質、一個口癖「才不是為了你」、稱謂照稱謂階 1）。場景固定：梅雨傍晚的河鹿堂、主角＋宮澤柚葉、階 1、進新書日她挑了一疊提不動、嘴硬塞給主角、命令他下次也來（選進新書日不選讓書：「拿主角當提書工具」是 dossier 的既有特徵，最像她）。`train/set/` 只有兩個開關：誰先開口（主角／她）× 第二組必提詞（梅花章／集章冊）＝ 4 題，其餘全固定；開關記在每題的 `switches`。brief.json 多 `style`。
- **結構化分數**：score.json 加 `val`、`style`、`dims`；critic 的 dims 給承接、含蓄、角色味、反差（嘴硬心軟的反差）、文筆，judge 把反差長在角色味底下：`"語意": {"val", "承接", "含蓄", "文筆", "角色味": {"val", "反差"}}`（拆不出就不長、維持數字）。多樣性是程式算的：`train/score` 除了同一題 k 次，也算同一風格這輪全部稿子兩兩比（k＝1 也有）。舊欄位全留，measure.json 的 score 多 `val`。
- **雜訊**（[runs/round4/noise.md](runs/round4/noise.md)）：新場景第一題 3 次，總分 4、5、4，σ 0.58（≤ 0.7，k＝2 夠）；critic 語意三次都是 2，雜訊全部來自 lint 的語域（多一行旁白、多一個感嘆號）。限縮前的 q01、q08 各 3 次（σ 0.91）留作對照。
- **human/**：questions.json、import/、README；`train/score`、`train/pick` 先做了（基準輪要用）。
- **基準輪**（[runs/round4/round0/](runs/round4/round0/)、[rounds/0.json](runs/round4/rounds/0.json)）：4 題，第一題 3 次、其餘各 1 次＝6 次；總分 4／5／4、4、5、4，平均 4.33；傲嬌評級 ok（加權 0.735）、風格多樣性 0.68；合計 121963 tokens、27 次問腦。`human/samples.json` 6 筆全是這個性格 × 這個場景：3 筆評分器不合、1 筆 critic 中間分、最高與最低分錨各 1。
- **代定**（可翻案）：① 語料錨只給在場女角的段（samples 加 `cast`）。② 鉤的收尾句改成 `{heroine}` 由 brief 代入。③ style 沒寫時取女角卡 type 第一個、去括號、取「／」前。④ critic 的校正記成 `ratings.calibration = {"val": 一致率, "by_style", "counter_samples", "rated_at", "source"}`。⑤ import 合併人評時平手取較差的；同風格覆寫、別的風格不動；只換 `ratings` 那段原文。⑥ `samples.json` 的 lines 收台詞與旁白、不收【標題】；多一格 `why_picked`。⑦ critic 假腦加測試開關 `GALTXT_FAKE_CRITIC_DIMS`（no／bad）。⑧ 「多樣性」不交給 critic（單看一份稿判不出），由程式比多份稿算。⑨ code map（wf/）沒改（實作者只能動 galtxt-b 與 tests），交給隊長。
