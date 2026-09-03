# list 裡還有 list：運算式巢狀與資料夾巢狀

← [program-form](program-form.md)｜[ideas](README.md)｜[WORKFLOWS](../../WORKFLOWS.md)

**本檔是 [program-form](program-form.md) 的續篇**——那份已經超過檔案大小上限，所以使用者
2026-09-03 接著問的這一題另開一檔。**本檔無裁決**：除了「使用者提問」那節的原話之外，
以下全部是 AI 觀察，使用者可以否決。

## 使用者提問（2026-09-03）

> 現在我們的對比已經算完整了。然後我開始思考，list的元素也可以是list，那麼求值...？

## AI 觀察（非裁決，可否決）

### a. 「list 裡有 list」在資料夾上對應兩種不同的東西

lisp 只有一種巢狀，資料夾這邊裂成兩種，而且它們的求值規則不一樣：

| 巢狀的種類 | lisp 的樣子 | aos 的樣子 |
|---|---|---|
| **運算式巢狀** | `(f (g x))`——子式是要先算出來的運算元 | 拆平器的工作，跑之前就沒了 |
| **資料夾巢狀** | 沒有直接對應 | 子資料夾住在父資料夾裡 |

後面兩節分別講這兩種，先講第一種。

### b. 運算式巢狀：跑之前就被壓平了

`(f (g x))` 在 aos 不會以巢狀的形態進入執行期。**拆平器**（flatten）把它改寫成
`t1 = (g x); (f t1)`——中間值有了名字，那個名字就是 `out/` 底下的一個檔案。這正是 **ANF**
（A-normal form），[lisp-reconciliation §二十八](assembly-and-chains/lisp-reconciliation.md)
的對照表已經把它對上了：macroexpand ＋ ANF ＝編譯／拆平，穩態到穩態、確定性。

結論很短：**跑的時候，`inst` 裡沒有巢狀。** 巢狀只活在源碼那一層，被確定性的程式吃掉。

### c. `series.json` 是明寫的 continuation——這台機器已經是 CPS 形態

把所有呼叫攤成「送出去 ＋ 一個 continuation」、讓運算式裡不再有巢狀，這件事有名字：
**CPS 轉換**。`series.json` 就是那個被寫成資料的 continuation
（[lisp-reconciliation §二十九](assembly-and-chains/lisp-reconciliation.md)：C 的堆疊不透明，
這裡的 continuation 是可看、可改、可 replay 的 json）。

**tool call 是現成的例子**：agent 碰到工具時不往裡遞迴，而是**送出一條 inst**、把自己停在
「等結果」那一格，下一輪再從 `out/` 讀值繼續。已知的那個坑——**手動 `aos agent step` 而不跑
`aos run`，就會永遠停在「等工具結果」**——用這套講法就是一句話：**外層在等內層的值，但沒有
人去求那個內層。** 求值器沒有在跑，continuation 就永遠不會被恢復。

### d. 資料夾裡的資料夾：那是作用域，不是運算式巢狀

子資料夾**預設是 quote 住的**（穩態），不會自己動。它要被求值，得由父資料夾的
**car** 點名「打開它」——而「打開」就是
[lisp-reconciliation §二十八](assembly-and-chains/lisp-reconciliation.md) 表第三列的那一刻：
**`G14` 載入器開一條 serie ＝ unquote ＝ funcall ＝ `G06` 行程誕生**。

所以資料夾的求值是 **normal order**（用到才算），不是 lisp 預設的 **applicative order**
（先把所有引數算完再進函數）。這對 `if` 這類 special form 剛好對味：**分支就是 car 決定
接下來要開哪一個子資料夾**，不會兩邊都先算掉。

### e. 三個邊界

**回傳 vs 傳訊。** lisp 只有 call——值沿著呼叫樹流回父層；actor 只有 send——沒有回傳值，
只能再送一則訊息。**aos 兩者都有**：子資料夾的 `out/` 被父層讀走＝回傳，`deliver` ＝傳訊。
但今天連 tool call 都走「deliver 出去、結果再送回來」，等於**用 send 模擬 call**。
**「要不要保留『子資料夾直接回傳』這條路」是一個可裁的點。**

**並行與 join。** 父層同時打開兩個子資料夾，就等於 Scheme 那個「引數求值順序未定」的自由度
——那是 actor 的形狀。而父層的下一個 inst 若同時要讀兩個 `out/`，那就是 **join**。這跟
[program-form](program-form.md) 已經記下的「一個資料夾不只一個 car」「留著批」是同一件事的
兩種說法。

**深度。** lisp 的巢狀是遞迴，可以無限深，代價只是堆疊。資料夾這邊**每深一層，就是一個
continuation 停在那裡等**。在回合制底下，深度直接翻譯成「**幾個回合回不來**」——那是 token
與可預測性的成本，不是堆疊的成本。這條接回
[os-metrics-and-resources §六／§七](os-metrics-and-resources.md) 的 RTOS 線：最壞情況要有界，
而這裡的界就是深度。

### f. 整體：aos 對「元素也是 list」的回答是「不要在跑的時候巢狀」

- **運算式巢狀** → 在 flatten 那一步壓平，執行期看不到。
- **資料夾巢狀** → 留給作用域與行程，只在 car 點名時才打開。

這也順帶說明了「順序不重要」是從哪來的：**順序被 continuation 與 `out/` 的名字接管了**。
資料夾本身無序沒關係，因為要排的東西已經不住在資料夾的排列裡。

## 相關

- [program-form](program-form.md)——本檔的上游：檔案＝atom、資料夾＝list、穩態暫態＝quote、
  三層（exec 一步歸約／run ＝ eval／daemon ＝ REPL）、資料夾的 car
- [assembly-and-chains/lisp-reconciliation](assembly-and-chains/lisp-reconciliation.md)——身分
  對照表：macroexpand ＋ ANF ＝拆平、`series.json` ＝ continuation、`out/` ＝值
- [assembly-and-chains/series](assembly-and-chains/series.md)、[interrupts](assembly-and-chains/interrupts.md)——`series.json`
  ＝行程表／PC，自供給＝CPS
- [os-metrics-and-resources](os-metrics-and-resources.md)——深度的成本落在 token 與可預測性
- [cpu-to-os-gaps](cpu-to-os-gaps.json)——`G06`（行程誕生）、`G14`（載入器＝開 serie ＝ unquote）
