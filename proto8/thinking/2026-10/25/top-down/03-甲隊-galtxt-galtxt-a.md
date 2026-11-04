← [入口](README.md)｜涵蓋：甲隊：galtxt（galtxt-a）｜上一份 [02-乙隊-galtxt-galtxt-b](02-乙隊-galtxt-galtxt-b.md)

## 甲隊：galtxt（galtxt-a）

原型 proto8/topdown/galtxt-a/；fable 規劃在 plan/，經驗在 lessons。使用者「跟甲隊說差不多可以收尾了，我抓到了一些問題點」後收尾。

### 使用者原文（10-25，逐字；頂部那段以外、直接給甲隊或甲隊依據的）

- 「差不多30%的時候就該換手了其實」「我人在外面，不方便評」

### 結論

**範圍**：一個角色×一個場景——宮澤柚葉（傲嬌）× 文化祭收攤的教室；舊題留著當回歸。

**拆法**：
```
galtxt-a/            根＝五格內嵌單子 brief→write→check→judge→pick（不要腦的都是單子）
├─ writer/           agent 節點；stage.json 記 agent→semi→program
├─ grader/           評審 agent；尺，不固化
├─ tools/lint/       純程式護欄，輸出 hits（指到格 id）
├─ data/             人寫的表，拆成有 id 的格
├─ train/            verify→train→rate→optimize 迴圈；weigh/（判斷器樹）、optimize/（優化器樹）
├─ optkit/           自我優化工具包（任何節點可掛；含叫 claude code 的工具）
├─ meta/             metatable、collapse、rollup
└─ human/ plan/ idle/
```
- 第一層切在「要不要腦」與資料形狀變化處：要腦的（寫手、評審）各是 agent 資料夾，其他全是根 fsm 的內嵌單子。
- 刻意不拆：pick／check／brief 不給資料夾；lint 不拆維度（一次掃完便宜）；評審不分成三個 agent（三倍 token）。
- 三棵樹：台詞樹被改（只改參數表、`stage.json`、模板）；優化器只讀根 rollup 挑一棵子樹；判斷器只讀兩份 diff＋人寫優先序表、不改任何東西。

**反向收攏**：併「一格一夾」的 glue 與重複的 idle、縮薄中間層。不縮的判準＝`fs_needs`（自己的 stack、tool json、隔離、要單檔 diff、別的行程寫）＋伴隨檔 ≥2＋共用真身；有旁檔（ratings／stage／grad／rollup）的子樹不縮。

**`_metainfo`**：只看表指得出**該優化什麼**，指不出**該優化多少**（要實測欄）；表最大的洞是資料流（`reads`／`writes`／狀態 key）。缺的 key：`measured`、prompt／completion 分開、`cache`、`timeout_ms` 與資源上限分開、`max_rounds`、`max_children`、`parallel_safe`／`max_parallel`、`entry_kind`、`callers`、`llm_model`、`role`、`derived`、`steps`、`opt_writes`、旁檔 `$ref`。metatable 只當人看的索引；決策讀**樹中有樹**的 rollup——每棵子樹的 `rollup.json` 只彙總直接子樹、一層層往上算，搬到別棵樹也帶著走。

**拆格**：id＝JSON key 路徑（`cast.yuzu.tic.03`），檔長成資料夾 id 不變（C-72）；給腦的散文只在 brief 最後一步從格渲染。停止條件：再拆一格要答得出「有程式只讀這格嗎／控制變量只動這格嗎／梯度或規則會單指這格嗎」，三個都否就不拆；真腦後仍 0 引用的格併回陣列。

**自我優化**：優化器不親自改節點，挑子樹（照 rollup）→ 寫一句「請優化 X」＋附先前結果 → 叫節點自己做（agent 節點多掛 `opt_*` 工具；純程式節點臨時配殼；或叫 claude code）→ `accept` 判 → 不收就回滾。工具包：describe、history、read／edit／write（白名單內）、extract、try、test、note（改 `_metainfo` 只寫建議，不直接改）。防作弊全靠程式：在整棵樹的拷貝裡改，`accept` 檢白名單、錨的 sha256、契約測試；背正解、讀絕對路徑擋不住、只能事後抓。分工（預測）：自優化改**內容**（抽工具、蒸餾模板、改 prompt）；外部優化器翻**開關**（stage、switch、hints）並當收貨人；連兩次被拒退回外部動作。

**頂層代定（照 fable 推薦先做，可翻）**：① 場景選教室收攤；② 傲嬌細項權重 反差 2、像柚葉 2、其餘 1，人評出來再調；③ 固化寫手（到 program）與判斷器（到 rules），評審（尺）留 agent；④ 判斷器優先序 護欄 > 分不掉超過 min_loss > 評級升 > token 省 > 確定性升 > 標籤，半固化期允許 token 暫升；⑤ measure 題每個 epoch 都跑；⑥ 有旁檔不縮與 `steps`／`brain`／`grad` 三個 `$ref` 名先只在甲隊用、不進通用表。自優化預設走 gpt，claude code 是例外工具（使用者點名），台詞樹本身的腦照舊 gpt。

**對 fable 的評估**：切在「要不要腦」與資料形狀處、刻意不拆都有理由；自加的 `fs_needs` 直接成了收攏判準；方向改變時能把十幾句新想法收成一份可做的順序。要人修的：資料流與逾時（外層逾時 < 子上限總和，違 P-36）、上限欄混兩種意思、規劃檔偏大、量法細節想當然。

**未做**：真腦整條跑（round4 只跑了假腦，分數不代表品質）、真腦人評樣本、gpt vs claude 自優化對照、振盪檢查。
