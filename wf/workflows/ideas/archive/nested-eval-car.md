> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# `.aos` 是 car：資料夾預設 operative

← [nested-eval](nested-eval.md)｜[program-form](program-form.md)｜[ideas](README.md)｜[WORKFLOWS](../../WORKFLOWS.md)

**本檔是 [nested-eval](nested-eval.md) 的續節**——那份加上本節會超過檔案大小上限，所以
使用者 2026-09-03 對「資料夾巢狀」的回應另開一檔。**裁決見文末
[「裁決（2026-09-03）」節](#裁決2026-09-03)，其餘為 AI 觀察**（使用者可以否決）。

## 使用者回應（2026-09-03，續）：`.aos` 是 car、資料夾預設 operative

> 所以，一個資料夾，變成list，感覺會像是這樣：(.aos dir1 dir2 file1 file2)，然後dir1指向某個list: (.aos file1 file2)。用aos exec對這樣一個list求值，就是跑.aos，然後剩下的資料夾內容就是跑他的參數。lisp中會先跑dir1,dir2的.aos，但我們這邊不會，我記得這是另一種lisp運算模型

## AI 觀察（非裁決，可否決）

### a. 這個寫法把 car 講準了：car 是 `.aos` 本身

`(.aos dir1 dir2 file1 file2)` 一寫出來，入口就定了：**car ＝ `.aos` 這個資料夾，其餘項目
全是引數**。這比 [program-form 第三題](program-form.md) 的「car ＝ `series.json`」更準——
`series.json` 只是 `.aos` 裡**被先讀的那個檔**，是 car 的內部細節，不是 car 本身。

### b. 「另一種運算模型」有兩個候選名字

| 候選 | 意思 | 出處 |
|---|---|---|
| **normal order／lazy evaluation** | 引數先包起來，誰用到誰才算 | Haskell 一派 |
| **fexpr／operative** | 運算子拿到的是**未求值的原料**，自己決定怎麼辦 | Scheme special form、John Shutt 的 Kernel |

AI 認為**第二個更貼**：lazy 仍然是「自動幫你算，只是拖到用時才算」；fexpr 是「**完全不幫你
算，自己看著辦**」。使用者描述的正是後者——`.aos` 拿到 `dir1`，沒有人先幫他跑過。
（[nested-eval §d](nested-eval.md) 先寫的是 normal order，這裡是把它改得更準。）

### c. `.aos` 對子資料夾正好有三種處置，全是「自己看著辦」

1. **當資料讀**——只讀內容，不跑它。
2. **開它**——`G14` 載入器開一條 serie，此時 `dir1` 自己的 `.aos` 才上場。
3. **轉手**——`deliver` 給別人，自己不碰。

普通 lisp 只有第二種，而且**強制先做**。比喻：**lisp 的廚師收到的是切好的菜，aos 的廚師
收到整袋食材。**

### d. operative 拿得到環境——在 aos 就是資料夾本身

Kernel 的 operative 除了未求值的引數，還會拿到**當時的環境**。搬到 aos，環境就是**資料夾
本身**，而 `.aos` 本來就站在那裡、不必額外傳。這跟 [program-form](program-form.md) 已記的
「暫存資料夾＝環境框架」是同一件事：**list 與環境是同一個東西。**

### e. 「先跑子資料夾」不是做不到，是預設不做

Kernel 裡普通的 lisp 函數（**applicative**）只是 operative 外面包一層「先把引數算完」。放到
aos，那層包裝**也只是一種 `.aos`**——`series.json` 開頭寫「先跑完所有子資料夾，再做我的
事」就是了。所以 aos **不是「不能」照 lisp 先跑子資料夾，是「預設不」**；要的話寫在 car 裡。

### f. 兩個小修正

- **指令名**：使用者寫「用 `aos exec` 求值」，但照 [program-form 已裁](program-form.md)
  **`exec` ＝一步歸約、`run` ＝ eval**，這裡談的是求值，**應為 `aos run`**。
- **引數怎麼認**：lisp 依**位置**，aos 依**檔名**。所以更像具名引數
  `(.aos :dir1 … :file1 …)`——這跟「資料夾內順序不重要」那條裁決一致。

### g. 待裁 → **已裁**

**「`.aos` 是 car、資料夾預設 operative」**——本節全部觀察都掛在這一句上，
**使用者同日已裁，見下節。**

## 裁決（2026-09-03）

> 喔天啊，你說得太好了，我要的就是第二種！然後子資料夾是否要跑，全看父資料夾的.aos要不要跑他。然後先前說的f(g(x))拆成平攤，那就是.aos內的東西，和外面子資料夾的求值無關。

1. **資料夾＝operative（fexpr）**——選觀察 b 的第二個候選：`.aos` 收到的是**未求值的原料**，
   不是算完的值。
2. **子資料夾跑不跑，完全由父資料夾的 `.aos` 決定**——沒有自動求值，沒有預設順序。
3. **`f(g(x))` 的攤平（ANF／CPS）是 `.aos` 內部的事，與子資料夾的求值無關**——
   **兩層分開**：`.aos` **內**是 inst 鏈（**機器層**），`.aos` **外**是資料夾樹（**行程層**）。

**追問「最頂上那個資料夾（沒有父資料夾的）是誰開的」，同日再裁：**

> 就是我開的，但有時候我會開daemon，讓daemon幫我開。跟你說得差不多。

4. **頂層資料夾由使用者開**（terminal 下 `aos run`），**或使用者開 daemon、讓 daemon 代開**
   ——**不是資料夾自宣告 `init`**（[program-form 第三題 m](program-form.md) 的選項 2 落選）。

## AI 觀察續（非裁決，可否決）

### h. 兩層分開剛好接上既有裁決

這個「機器層／行程層」的分開，剛好對上 [verdicts A 區已裁](verdicts.md) 的那組換角度讀法：
**機器層＝CPU 取指—解碼—執行週期**（`.aos` 內的 inst 鏈就是它）、**多資料夾互相投遞＝
actor**（`.aos` 外的資料夾樹就是它）。於是 `G06`（行程誕生）有了一句定義：
**父資料夾的 `.aos` 開一個子資料夾。**

### i. 頂層不需要特例（承裁決 4）

「使用者開」與「daemon 開」都是**外面進來**的同一件事。而**把 daemon 也看成一個資料夾**，
它就自洽了：daemon 的 `.aos` ＝「盯著桌子、有東西就開」，**桌上那些資料夾就是它的引數**——
跟 [program-form](program-form.md) 已裁的「daemon ＝ REPL」是同一句話。再往上開 daemon 的是
shell 或 systemd，也就是 **Linux**。

於是**頂層資料夾的父層在 aos 外面**，接上「aos 跑在 linux 上」那條既有裁決
（[os-metrics-and-resources](os-metrics-and-resources.md)）：**頂層不需要特例**，
裁決 2「父 `.aos` 決定」在整棵樹上一致成立，最外面那個父只是不歸 aos 管。

## 相關

- [nested-eval-sugar](nested-eval-sugar.md)——本檔的續節（同日）：**inst 鏈是為省成本而存在的
  語法糖**，`.aos` 不能省的只有「原子 inst ＋ 開／讀／選」；薄的＝未編譯、厚的＝編譯過
- [nested-eval](nested-eval.md)——本檔的上游：運算式巢狀（flatten 壓平成 ANF）與資料夾巢狀
  （作用域，car 點名才開）
- [program-form](program-form.md)——檔案＝atom、資料夾＝list、三層（exec 一步／run ＝ eval／
  daemon ＝ REPL）、第三題「資料夾的 car」
- [assembly-and-chains/lisp-reconciliation](assembly-and-chains/lisp-reconciliation.md)——身分
  對照表：`G14` 載入器＝開 serie ＝ unquote
- [assembly-and-chains/series](assembly-and-chains/series.md)——`series.json` ＝行程表／PC
- [cpu-to-os-gaps](cpu-to-os-gaps.json)——`G06`（行程誕生）、`G14`（載入器）
