# 遊戲 `_process(delta)` 模型：一次 exec 就是一格 tick

← [ideas](README.md)｜上游 [turing-to-os](turing-to-os.md)｜[WORKFLOWS](../../WORKFLOWS.md)

使用者口述（**2026-09-01**）的第三個心智模型。[turing-to-os](turing-to-os.md) 講**憑什麼是
CPU**、[program-form](program-form.md) 講**程式長什麼形**，這篇講**它怎麼跑**。同日他還
口述了 L1/L2 cache 的類比（第三部分），兩者同源：都在回答**「機器用來管自身的東西，跟
世界的東西怎麼分」**。

## 第一部分 · 使用者口述：`_process(delta)`

### 一、世界＝能存取到的資料夾，本體＝cwd

使用者口述（整理）：

- `aos exec` 執行時**能存取到的資料夾，就是它的世界**。
- **cwd ＝這個正在執行的傢伙的「本體」**。
- 其他能存取到的資料夾＝**它能碰到的外在世界**。

所以「世界」不是設定出來的邊界，是**掛載出來的**：掛了什麼，現象世界就有多大。

### 二、一次 `aos exec` ＝ 一次 `_process(delta)`

每跑一次 `aos exec`，就等於執行一次遊戲的 `_process(delta)`。世界不是被一支長跑程式
持續改寫，而是**每一格被叫起來一次，做完就返回**。

> **和「不吃 delta time」的裁決不衝突（我的觀察，可否決）**：
> [turn-based-folder/model](turn-based-folder/model.md) 定的是
> 「aos **不以經過時間作為語意輸入**，而採回合制」。這裡借的是 `_process` 的**呼叫結構**
> ——每格被叫一次、自己在預算內返回——不是 `delta` 這個參數。真實經過的時間仍只用在
> 節奏判定（`every_ms` 那類），不進世界語意。

### 三、決策照 GOAP 走

參照遊戲 AI 的 **GOAP**（Goal-Oriented Action Planning）演算法，一格之內做四件事：

1. **觀察**外界與自身狀態
2. **查看自身的目的**
3. **決策**
4. **行動**

### 四、預算：超過就等下一次 `_process()`

遊戲的一格預算是 1/60 秒。**若這次 `_process` 超過預算，其他事情等下一次 `_process()`
再做。** 使用者原話：

> **agent loop 很適合這套模型。**

## 第二部分 · 我的觀察（主 session，不是裁決，使用者可否決）

### 五、這一個模型一次回應三個缺口

| 缺口 | 這個模型怎麼回答 |
|---|---|
| **`G01` 中斷與時鐘** | **時鐘就是 tick 本身**，不需要外部中斷線——每一格由呼叫者發動，控制權天然週期性回到機器手上 |
| **`G09` context switch 與可搶佔** | 遊戲引擎**從不搶佔 `_process`**，靠每格自願在預算內返回。「一回合十幾分鐘很正常」（[program-form](program-form.md) 的 REPL 裁決）在此拿到理論靠山：不是還沒做搶佔，是這類機器**本來就是 cooperative 的** |
| **`G04` 架構狀態與可存的 context** | **GOAP 的 plan 就是可存檔的架構狀態**——context 具體化為一個檔案：「排好但還沒執行的行動佇列」 |

### 六、GOAP 正面壓上「核心方程要宣告 footprint」

第十輪開放項之一是**核心方程要宣告 footprint**（一筆 inst 應當只動哪裡、越界算什麼；見
[machine-shape/instruction §24](machine-shape/instruction.md)、
[debts §2](machine-shape/debts.md)）。**GOAP 規劃依賴每個 action 聲明
precondition／effect**，而 `inst` 目前**什麼都不聲明**（`argv`／`env`／`cwd`／`stdin`／
`timeout_ms`，沒有一欄講它會碰到什麼）。所以——

> **想走 GOAP，footprint 就從「值得做」升格成「必要條件」。** 沒有 effect 宣告，規劃器
> 無從連鎖；沒有 precondition，規劃器無從剪枝。

### 七、`G13` 的正面講法

「cwd ＝本體、可存取資料夾＝世界」給 `G13`（命名空間、掛載與權限位）一個**正面**說法：

> **命名空間不是安全機制，是世界的定義。** 掛載了什麼，決定這個世界有多大。

`G13` 過去記的是防守面的欠缺（沒有隔離與授權的著力點）。換成這個講法，它變成**建構面的
必需品**：不掛載就沒有世界可觀察，GOAP 的第一步根本無從開始。與
[verdicts B13](verdicts.md)（`path` 是 symbol、handle 才是 capability，只有 exec 層碰得
到）指的是同一個位置。

### 八、兩條邊緣狀況

1. **預算由誰執行？** 遊戲引擎不搶佔，靠寫 `_process` 的人自律。換到這裡，「自願返回」
   要求 **agent 能中途封存意圖**——半成品狀態要能被下一格讀懂。GOAP 的 plan 檔是答案的
   一半（**還沒執行**的行動佇列）；另一半是**「執行到一半的 action 怎麼記」**，目前沒有
   形狀。
2. **不同 tick 率的世界共享資料夾。** 快世界與慢世界（[program-form](program-form.md)
   的節奏軸）在**粒度**、**節奏**之外長出第三軸：**一致性視窗**——慢世界會**整格拿著
   stale 資料在跑**。[nested-worlds](nested-worlds.md) 用 `every_ms` 讓子世界跑得比主
   世界慢，已經是這個狀況；它與 [debts §1](machine-shape/debts.md)（兩顆 CPU 共寫一份
   記憶體、沒有記憶體模型）是同一筆帳的兩個入口。

## 第三部分 · 使用者口述：L1/L2 cache

### 九、原話

> **cpu 的 l1/l2 cache，那就是一些與任務、或者說行程無關的、底層的 cpu 用於管理自身的
> 東西。像是 every.json，某種程度上就算是 l1/l2 cache。**

（版面上實際是 `.aos/every/<stem>.json` 一整個資料夾，不是單一檔；下面按實際路徑談。）

### 十、（觀察）判別式：刪掉它，世界語意變不變？

cache 的**定義性特徵不是快**，是**不在 ISA 裡**——清空只影響時間，不影響語意。這正是
CPU 的**架構狀態 vs 微架構狀態**之分。所以判別式很短：

> **刪掉它，世界語意變不變？只變節奏＝微架構狀態（機器自己的）；語意變＝架構狀態
> （世界的記憶體）。**

拿 `.aos/` 現況過一遍：

| 路徑 | 刪掉之後 | 分類 |
|---|---|---|
| `run.pid`／`run.lock` | 控制介面要重找，世界語意不變 | **純 cache** |
| `every/.last/<stem>` | 定期事務立刻重跑一次，時間亂了、語意沒壞 | **cache** |
| `every/<stem>.json` | 定期事務**永遠不跑** | **架構狀態** |
| `turn` | **現在**只影響 `batch/<turn>/` 編號；批 header／去重落地、回合編號成為 PC 之後就不是了 | **會升格** |

**使用者說「某種程度上」是對的**：登記檔（`every/<stem>.json`）與執行痕跡
（`every/.last/`）住在同一棵子樹裡，卻**要分開歸類**。

而 `turn` 那列是這條線最重要的性質：**邊界會隨設計落地移動**——ownership table（第十輪，
[layout-and-spec §28](machine-shape/layout-and-spec.md)）除了記「誰能寫」，**還得記這件
事**，否則它會在 PC 落地那天整張過期。

### 十一、（觀察）兩個直接後果

1. **第十輪「版面要 ownership table」拿到分類判準。** 過去只說「每條路徑該標唯一 writer
   與方向」，沒說**這條路徑到底算不算世界的一部分**。判別式補上這一欄。
2. **C 區「git 撞 `.aos` 暫態」的 `.gitignore` 政策就是這條線**
   （[verdicts C](verdicts.md)、[debts §2](machine-shape/debts.md)）：**cache 永不入
   commit。** 「回滾到含 `run.pid` 的 commit 造成死鎖」，本質就是**把微架構狀態當架構
   狀態存了檔**。

### 十二、（觀察）另一條軸：記憶體層級對速度

我較早的另一種讀法，**軸不同，與使用者的版本不衝突**——使用者談的是**架構 vs 微架構**
（語意），這條談的是**層級 vs 速度**（延遲）：

| 現代 | aos |
|---|---|
| 暫存器 | context window |
| cache（副本，會 stale） | 索引／摘要檔 |
| RAM | 資料夾樹 |
| 磁碟 | 別的世界 |

**stale cache 這格重新推導出 C 區「沒有記憶體模型」那筆欠帳**：一個 agent 拿著過期索引
做決定，就是 **cache incoherence**。當日 `verdicts.md` 漂掉正是實例；而「實作閉合同一個
commit 回寫文件」就是 **write-through**。

## 相關

- [turing-to-os](turing-to-os.md)——上游：三要件、agent loop ＝ CPU、檔案系統即記憶體
- [turn-based-folder/model](turn-based-folder/model.md)——回合制模型本體（「不吃 delta time」那條裁決）
- [program-form](program-form.md)——REPL 讀法、快／慢世界的節奏軸、「十幾分鐘一回合很正常」的裁決
- [assembly-and-chains](assembly-and-chains/README.md)——同日同源的下一格：批＝tick 的裁決、指令自供給
- [theses-review](theses-review.md)——同日三方複審：REPL 句＝回合＝批、同像性承重點
- [cpu-to-os-gaps](cpu-to-os-gaps.json)——`G01`／`G04`／`G09`／`G13`
- [verdicts](verdicts.md)——第十輪 footprint／ownership table／PC 不存在；C 區 git 撞暫態
- [machine-shape/debts](machine-shape/debts.md)——記憶體模型、git 與暫態、中斷線
- [nested-worlds](nested-worlds.md)——子世界靠主世界的 inst 推進（不同 tick 率的現成案例）
