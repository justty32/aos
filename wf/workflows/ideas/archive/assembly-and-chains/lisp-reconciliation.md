> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# lisp 三層套回彙編／C 線：身分對照（§二十七–§三十）

← [assembly-and-chains](README.md)｜[ideas](../README.md)｜[WORKFLOWS](../../../WORKFLOWS.md)

**使用者的提問（2026-09-03，玩系統時）**：

> 到了這邊，我想回去重新想想「一串彙編」、`.h`／`.c` 在這套模型下的狀況。因為我們拿 lisp
> 對標，這和彙編／C 的區別……

（話沒說完。）觸發點是同日在 [program-form](../program-form.md) 裁下的三層——
**`aos exec` ＝一步歸約、`aos run` ＝ eval 到不動點、daemon ＝ REPL**，以及**穩態／暫態＝
quote**。這一篇是頂層 session 的回應：**整篇都是 AI 觀察，不是裁決，使用者可否決。**

## 第九部分 · 我的觀察（頂層 session，非裁決）

### 二十七、C 線本來就是 lisp 的形狀，只是掛 C 的名字

lisp 系統同時有 eval 與 compile，但 **compile 是 eval 的最佳化，不是另一條管線**：同一棵
樹、同一套語意，宏展開就是「拆平」。C 不是這樣——**源碼與執行檔是兩個世界**，靠語言外的
工具鏈連起來。

而 9 月 1 日已裁的兩條，講的其實是 lisp 那一種：**「拆平器是樹到樹的同型改寫」**
（[source-and-ir §二十三](source-and-ir.md)）、**「複雜式由程式確定性拆平」**
（[compile-pipeline §二十](compile-pipeline.md)）。那是**宏展開 ＋ ANF**（A-normal form：
把 `f(g(x))` 拆成先算 `g` 存臨時值再餵 `f`）的說法，不是 C 工具鏈的說法。

**所以 C 線不用改**，只是名字換成更準的。

### 二十八、身分對照表

| lisp | C 線用的名字 | aos 裡是什麼 | 穩態／暫態 |
|---|---|---|---|
| quoted form（資料） | `.h`／`.c` 源碼 json | 源碼檔 | 穩態 |
| macroexpand ＋ ANF | 編譯／拆平 | 拆平器輸出的 IR | 穩態→穩態，確定性 |
| funcall／apply（拿掉 quote） | 呼叫、開子串、載入 | 從模板開一條 serie（`G14` 載入器＝`G06` 行程誕生） | **穩態變暫態的那一刻** |
| 控制堆疊／continuation | series、PC | `series.json` | 暫態 |
| environment frame／let 綁定 | 堆疊框、暫存器、代號 | 臨時資料夾、串內符號表（§十八–§十九） | 暫態 |
| primitive op | 機器指令 | inst 批 | 暫態的最底 |
| value | 回傳值寫到父串指定處 | `out/` 檔 | 產出後轉穩態 |
| normal form | 行程結束 | 游標到底／資料夾不動點 | 穩態 |

三句話收攏：**源碼是 quote 住的部分，series 是正在被求值的部分，inst 是求值碰到底的
primitive。** 程式／行程分界（`G07`）＝**quote 有沒有拿掉**；**「開串」就是 unquote**。

### 二十九、跟 C 真正不同的一點：continuation 是資料

C 的行程狀態（機器堆疊、暫存器）是**不透明**的；這裡 `series.json` 是 json——**可以看**
（可見窗口）、**可以在跑到一半時改**（[interrupts §一](interrupts.md)：中斷＝外部換掉
下一格、跳轉＝自己改下一格）、**可以 replay**。這正是
[theses-review §一](../theses-review.md)「同像性撐的是自我改寫」的落地點：
**C 做不到的就是這件事。**

為什麼 continuation 必須是**明的**（顯式 series），不是像 lisp 那樣藏在 eval 的遞迴裡？
不是因為 lisp 比喻要求，是因為**回合制**——loop 在兩步之間不存在，continuation 必須活在
檔案裡。這是 [turing-to-os §一](../turing-to-os.md)「體積不能膨脹 → 狀態在 loop 之外」的
直接後果。[series §九](series.md) 說「自供給＝CPS」，用今天的話講就是
**defunctionalized continuation**。

全塔 json 的裁決（[§二十六](source-and-ir.md)）在這裡剛好夠用：承重的是**「樹」與
「可改寫」**，不是括號。

### 三十、三個邊緣狀況

1. **`.h` 存在的理由是分開編譯 ＋ 連結。** lisp 沒有 header，簽名跟定義住一起。aos 有沒有
   「分開編譯」？有——模板（函數）**獨立拆平**，開子串時才**連結**（[§十四](c-language.md)
   呼叫＝開子串掛父串 id），而連結＝把代號解析到實際目標＝`G14`。所以 `.h` 留著有理由，
   但**它不必是獨立檔**，可以是源碼 json 裡的一個欄；[`B5`](../verdicts.md) 的車位還在。
2. **不動點在有 series 時有便宜的判法**：**游標到底＝正規形**，不用比對整個資料夾。沒有
   series、純靠 LLM 決定停的資料夾（例如 `aos chat`），只能靠 LLM 自己說停——這就是
   **可預測性的來源差**：series 是 eval 裡確定的那部分，LLM inst 是不確定的 primitive。
   拆平把工作從 LLM 搬到 series，就是在**買可預測性**（呼應
   [os-metrics-and-resources 第八節提案 2](../os-metrics-and-resources.md)）。
3. **順序**：使用者裁「資料夾無序沒差」對**quote 住的部分**成立；正在求值的部分需要順序，
   而順序由 `series.json`（json 陣列）提供，**不是資料夾的性質**——[series §九](series.md)
   早就說裂縫 1 在這條線上不必解，今天多了一個理由：**順序是 continuation 的性質，不是
   記憶體的性質。**

## 相關

- [program-form](../program-form.md)——三層（exec／run／daemon）、穩態暫態＝quote 的出處
- [theses-review](../theses-review.md)——同像性的承重點是自我改寫
- [turing-to-os](../turing-to-os.md)——體積不能膨脹 → 狀態在 loop 之外
- [os-metrics-and-resources](../os-metrics-and-resources.md)——縮小 LLM 出場面積＝買可預測性
- [c-language](c-language.md)、[compile-pipeline](compile-pipeline.md)、[source-and-ir](source-and-ir.md)——被套回來的那條 C 線
- [interrupts](interrupts.md)、[series](series.md)——彙編線：中斷／跳轉、CPS 與 `series.json`
- [cpu-to-os-gaps](../cpu-to-os-gaps.json)——`G06`／`G07`／`G14`／`G24`
