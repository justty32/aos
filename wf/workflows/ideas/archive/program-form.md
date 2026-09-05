> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# 在 aos 上寫程式的形式：檔案是 atom，資料夾是 list

← [ideas](README.md)｜上游 [turing-to-os](turing-to-os.md)｜[WORKFLOWS](../../WORKFLOWS.md)

**使用者原話（2026-09-01）**：「關於在這個 aos 上寫程式這塊，其實就是類似 lisp，只是 lisp
的原語是 atom。但 aos 的程式載體就是資料夾，原語就是檔案。所以囉，要寫 aos 的程式，那個
抽象其實只有 lisp 有能力承載。」

> **最後那句「只有 lisp」使用者同日收回了**（改為偏好；Python／Lua 也適合）——見下方
> 專節，別把它當前提引用。**檔案＝atom、資料夾＝list 這組對應本身沒有被收回。**

這條是 [turing-to-os §四](turing-to-os.md)（檔案系統同時是記憶體與程式的載體）往下一層的
展開，也是缺口 `G20`（方便人寫程式）的實質內容。

## 對應關係

| lisp | aos |
|------|-----|
| **atom**——原語，不可再分 | **檔案** |
| **list**——複合、可巢狀 | **資料夾** |
| S-expression 是程式的載體 | 資料夾是程式的載體 |

巢狀那一格是對得最準的：資料夾可以裝資料夾，就像 list 可以裝 list。

## 這一步把同像性搬了家

workshop 那場（[lisp-in-aos](../workshop/records/lisp-in-aos.md) 第 10 點）否定過「JSON
陣列＝S-expression」，結論是**同像性來自 macro 與 eval 讀同一種 form，不是來自長得像括號**。

本條主張的不是那件事。它說 **S-expression 是資料夾樹本身**，JSON 只是檔案的內容格式之一
——同像性的落點從 JSON **搬到了檔案系統**。

所以缺口 `G24` 是**被改寫，不是被解決**：要問的不再是「JSON 是不是同像」，而是
**「資料夾樹是不是同像」**——macro 與 eval 是不是讀同一棵樹。這個問題還沒問過。

## 「只有 lisp 有能力承載」——使用者當日收回了排他性

原話裡有一句排他性主張：「那個抽象其實**只有 lisp** 有能力承載。」**同一天使用者自己把它
降級了**：

> 其實**很多程式語言也能表達抽象**，只是我自己**比較喜歡 lisp 的簡潔**。不然 **python 和
> lua 也很適合**。

所以正確的記法是：**lisp 是偏好，不是必要條件**。理由是**簡潔**。點名同樣適合的還有
**Python** 與 **Lua**。前面第一節那句「只有 lisp 承載得了」不要再被當成前提引用。

> **一個因此冒出來的問題（我的觀察，不是裁決）**：Python 與 Lua **都不是同像的**。如果
> 它們也「很適合」，那**同像性就不是「表達這個抽象」的必要條件**——那 `G24`
> （同像性要在資料夾樹上成立）到底在撐什麼？它可能撐的是別的東西（例如 macro／自我改寫、
> 或「程式與行程同型」那條線），而不是表達力。這條值得你哪天回答一次。
>
> **同日複審**（[theses-review §一](theses-review.md)，仍是觀察）：承重點是**自我改寫**（同日另有答案候選）；
> 下面四條裂縫的**第 3 與第 4 是同一題**。

## 四條裂縫——使用者已裁決（2026-09-01）

使用者的通則：**他沒回答的邊緣狀況，就是「要麼只是比喻上的天然差異（coding agent 只是
比喻成 REPL／lisp），要麼實作的時候自然能解決」**——不必追問，也不列待辦。下面四條照這條
通則處理，記著供實作時想得起來：

1. **list 有序，資料夾無序。** cons 的順序是本體的一部分；資料夾裡的檔案沒有順序，靠檔名
   排序是慣例不是語意。求值順序要靠什麼決定？
   **2026-09-03 使用者回應：這條被裁「沒差」**——順序不是重點，求值才是（見下方
   [使用者回應（2026-09-03）](#使用者回應2026-09-03求值才是重點穩態與暫態)）。
2. **檔案比較像 binding，不像 atom。** atom 只有值；檔案有**名字＋內容**兩樣。若檔名是
   symbol、內容是 value，那一個檔案其實是一個 binding，不是 atom。
   **2026-09-03 使用者回應：沒有直接回答這條**，但穩態／暫態把「檔案」重新切了一刀——
   切的是**這份會不會被求值改掉**，不是它是 binding 還是 atom（見下方
   [使用者回應（2026-09-03）](#使用者回應2026-09-03求值才是重點穩態與暫態)）。
3. **哪一棵樹正在被求值。** eval 要分得出「這份是碼」與「這份正在跑」——就是缺口 `G07`。
   同像性讓兩者同型，反而讓這件事更難。
   **2026-09-03 使用者回應：正在被求值的就是「暫態的部分」**——`aos exec xxx` 就地歸約
   `xxx`，穩態（quoted）的留著不動（見下方
   [使用者回應（2026-09-03）](#使用者回應2026-09-03求值才是重點穩態與暫態)）。
4. **quote 從哪裡來。** 已知現有機制**不能**直接當 lisp 的 quote 用
   （[pre-agent-loop-core R1](../workshop/records/pre-agent-loop-core/r1.md)）。資料夾模型
   下，quote 是什麼形狀？
   **2026-09-03 使用者回應：quote ＝穩態／暫態的那條界**——「可以很簡單地用有沒有
   `(quote (...))` 來理解」（見下方
   [使用者回應（2026-09-03）](#使用者回應2026-09-03求值才是重點穩態與暫態)）。

## 使用者回應（2026-09-03）：求值才是重點，穩態與暫態

> **2026-09-03 口述完畢**：本節前半是求值／穩態暫態那段，末尾「續：REPL」是他後來把
> 「而所謂的 repl……」講完的那段。

**使用者原話（整理，盡量保留他的話）**：

> 把檔案系統拿去與 lisp 做同像性會遇到一個問題：list 可以 eval 求值，但資料夾沒有；而且
> list 天然有順序，資料夾沒有。**順序這件事其實沒差，重點在於求值。**
>
> 我的理解是一個 list 有**穩態**與**暫態**的區別：穩態就是不管求值幾次都不會變的 list，
> 暫態就是以後某次求值可能導致 list 變化；可以很簡單地用有沒有 `(quote (...))` 來理解。
>
> 我們拿 lisp 做計算時，編寫的就是一個暫態的大 list，拿去求值（或說 process），並期望它
> 變化狀態後的內容是我們想要的。例：寫了 `(+ 1 2)`，不拿去求值就啥事都沒有，但我們想要
> 它的結果，所以……（省略）
>
> 套用到資料夾：我們弄了一個新資料夾 xxx，在裡面放了一堆東西，然後期望 `aos exec xxx`
> 可以讓這個資料夾變成我們想要的內容。而所謂的 repl……（未完）

**這段直接回答了上面四條裂縫裡的兩條**：

- **第 1 條（資料夾無序）** → 使用者裁「**沒差**」。同像性的承重點不在順序，在**求值**。
- **第 4 條（quote 從哪來）** → **穩態／暫態就是 quote**：有 `(quote …)` 的是穩態，沒有的
  是暫態。這同時給了第 3 條（哪棵樹正在被求值）一個具體形狀——正在被求值的是暫態那部分。
  這與 [theses-review §一](theses-review.md)（「那個標記就是這台機器的 quote」、第 3 與
  第 4 條是同一題）對得上。

### AI 觀察（非裁決，可否決）

**a. lisp 的 eval 不改原 list、回傳新值；`aos exec` 是就地改資料夾。** 所以這個對應比較像
**「帶副作用的 eval」**，或說**資料夾同時是運算式與結果暫存器**。後果落在 replay
（`G04`）：lisp 能重算是因為**源碼還在**；資料夾被改寫，源碼就沒了——除非資料夾裡
**穩態的部分（quoted）留著、只有暫態的部分被歸約**。這正好就是 `G07`（程式／行程分界）的
具體形狀：**quote 標記＝哪些檔案是穩態**。

**b.「變成我們想要的內容」可以定義成 exec 的不動點。** 再 `aos exec` 一次資料夾不再變，就
是穩態、就是「跑完了」。這給了一個**可機器判定的「結束」**，也給了
[os-metrics-and-resources §三](os-metrics-and-resources.md) 的**可預測性**一把尺——到達
不動點要幾回合、分布多寬。

**c. LLM 非確定性下，穩態不能定義成「每次求值結果相同」**，只能定義成「**exec 不再改
它**」；而且可能**永遠到不了**（震盪），所以要有**預算**——對上
[game-process-model](game-process-model.md)「超過預算等下一格」與
[os-metrics-and-resources §七 p](os-metrics-and-resources.md)（RTOS 的 deadline）。

**d. 順序「沒差」在 aos 有個更強的理由。** lisp 的求值順序**只在有副作用時**要緊；資料夾裡
的檔案是被 LLM **一次全部看見**的，**順序被「同時可見」取代**——這與
[verdicts B3](verdicts.md)（一回合內無資料流）是同一件事的兩面。

**e. `(+ 1 2)` 那個例子裡被省略的「所以…」，在 lisp 是「所以 REPL 幫你求值並印出」。**
使用者停在「而所謂的 repl…」，下一段大概會接這裡——下面本檔原本的 REPL 段
（agent loop ＝ REPL、資料夾＝image）要準備跟這段對接，**先不改**。
（**已接上**：見下面「續：REPL」，接法跟這裡猜的不同——他把 REPL 指給了 daemon。）

### 續：REPL——桌上有 list 就抓起來跑（2026-09-03 口述完畢）

**使用者原話（整理，盡量保留他的話）**：

> REPL 簡單來說，就是一個持續的迴圈：**檢查桌子上有沒有 list，有的話就抓起來跑，跑完的
> 結果給人看。** 如果要完全套用到我們這邊，就會變成 **aos daemon**，然後在我們給它指令
> 「去 aos exec 某個資料夾」之後，才去跑。**這跟我們的 aos loop 不太一樣。**

**這是對下一節（[寫的方式也是 lisp 的：REPL](#寫的方式也是-lisp-的repl)）的修正**：嚴格
套用的 REPL 是 **daemon ＋「exec 某資料夾」的指令**，不是 `aos run` 那條 loop。原文保留在
下面，讀的時候以本段為準。

#### AI 觀察（非裁決，可否決）

**a. R／E／P／L 逐字對上去，`aos run` 對不上 P，也對不上 R 的來源。**

| | REPL | aos（照使用者這段） |
|---|---|---|
| **R** | 讀一句輸入 | 一條指令進來：「exec 這個資料夾」 |
| **E** | 求值 | 對那個資料夾做一次 `aos exec` |
| **P** | 印出結果 | 結果給人看 |
| **L** | 回去等下一句 | daemon 回去等下一條指令 |

`aos run` **沒有 P**（它不對人印，只改資料夾），而且它的 **R 來自資料夾自己**——`.aos/every/`
每回合自投、空回合就盯 `inbox/` 與 `say/` 的簽章開下一回合（`core/loop`）。自供給的讀不是
REPL 的讀。所以 **`aos run` 不是 REPL，是一個正在跑的行程**。lisp 系統本來就同時有 REPL
（互動頂層）與一堆跑著的行程，aos 也是：**daemon 是 REPL，run 是行程**。兩個都叫 loop 會
混，建議之後文件用「**daemon**」與「**run**」分稱，別再用「aos 的 loop」泛指。

> 提醒：**今天沒有 `aos exec` 子命令**（`core/exec` 只是函式庫，見
> [verdicts D2](verdicts.md)）。這裡照使用者的話用 `aos exec` 指「**對一個資料夾做一次
> 求值**」這個概念動作。

**b.「桌子」＝收件匣／spool，但 aos 的桌子有三個投件人。** REPL 的桌子只有人會放東西；aos
有三個來源：**人**（`aos deliver`／CLI 指令）、**資料夾自己**（series／`every/` 的自供給）、
**時鐘**（`core/tick` 的 routine／schedule 到期投遞）。daemon 這張桌子要收得下三種，否則
「檢查桌上有沒有 list」只看得到人放的那一疊。

**c. 桌子有兩層，這正好是 `G10`「排程器住哪一層」的答案方向。** daemon 的桌上放的是
**「哪個資料夾要推進」**；run 的桌上放的是 **「這個資料夾下一批是什麼」**（`.aos/inbox/*.json`
搬進 `batch/<turn>/insts/`）。**外層 daemon 排資料夾、內層 run 排批。**

跟 [home-daemon-spec](home-daemon-spec.md) 已裁的八條對帳，結論是**方向一致、但有一處要
注意**：

- **一致**：裁決 1（子行程 supervisor）＋「daemon 本身不含回合邏輯」＝ 兩層分得很乾淨，
  回合邏輯只在 run；裁決 3（`add` 預設 `own`）＝ 外層只決定「誰在跑、多快」，不決定批內容。
- **一致**：`G10` 的訊號（使用者把 `series.json` 放進 **loop** 讀，排程輸入落在 loop 層）
  講的是**內層那張桌子**，不與外層有 daemon 這件事衝突——兩張桌子收的是不同東西。
- **要注意（不是衝突，是尚未涵蓋的一格）**：spec 裡外層那張桌子目前是**清單**
  （`daemon.json` 的 `targets`，常駐、`add`／`rm` 是登記），**沒有「一次性指令」這個入口**
  ——而使用者這段講的 R 正是一次性的「去 exec 某資料夾」。要當 REPL，daemon 得多一個
  **一次性投遞**（形狀像 `aos daemon exec <folder>`，或把它化約成往 `~` 的 `inbox/` 投一條）。
- **要注意**：裁決 2 把 `sync` 實作成主世界 `~/.aos/every/` 的一條 `aos run <sub> --step 1`
  ——**外層的排序其實是用內層機制做的**。所以「外層排資料夾」在 spec 裡目前只做到**並行
  監督**（起／停／退避重啟），真正的「同拍排序」還是落回 `~` 這個 world 的內層桌子。這與
  `G10` 的訊號同向（排程輸入在 loop 層），但也表示 **`G10` 不會被「有 daemon 了」自動關掉**。

**d. P（給人看）在 aos 只剩通知。** 資料夾本身就是輸出（**上一組觀察 a**：資料夾同時是
運算式與結果暫存器），所以 daemon 的「印出」不是印值，而是**事件通知**——「xxx 到不動點
了」（**上一組觀察 b** 的不動點定義）或「預算用完了」（**上一組觀察 c** 的預算）。這條線的位置就是 `aos state`
／[home-daemon-spec §2](home-daemon-spec.md) 的 status，以及「投遞即喚醒」那條。

**e. 這個 REPL 是非同步的。**「給指令才跑」配上 2026-09-01 已裁的節奏裂縫（一次 E 可能
十幾分鐘、不是缺陷），得到的形狀是：**送出指令 → 之後被通知**，不是打完 enter 等結果。
[home-daemon-spec](home-daemon-spec.md) 的**投遞即喚醒**（`core/loop` 空回合盯 `inbox/`
與 `say/` 簽章、一有新檔立刻開下一回合）就是這個非同步 REPL 的 **R**；觀察 d 的通知是它的
**P**。兩者中間隔著牆鐘，這也是為什麼 `G08`／`G22`（看得見誰在跑）在這個讀法下是必要的。

**f.「那我們的 aos loop 更像啥呢？」——三個候選，頂層推薦第一個。**
**使用者 2026-09-03 裁決：就是這樣。**

1. **eval 本身（小步歸約迭代到正規形）** ← 推薦。lisp 的 eval 內部就是個迴圈，逐層歸約
   子式直到值。對上今天的穩態／暫態：**`aos exec` ＝一步歸約（small-step）**、
   **`aos run` ＝把暫態資料夾一路歸約到不動點（big-step eval）**、**daemon ＝外面的
   REPL**。三層剛好各佔一個名字，而且把今天講的 eval、穩態、不動點、REPL 全串成一條。
2. **actor（Erlang 那種行程）**：收件匣＝mailbox、資料夾＝私有狀態、一批＝一則訊息、
   `say --to` ＝送訊息、可以寄給自己、沒有回傳值只能靠訊息觀察、彼此不共享記憶體
   （`G03` 隔離）。多個資料夾互相投遞時，每個跑著的資料夾看起來就是一個 actor；這是
   「多 CPU／IPC」那半邊最貼的比喻。
3. **CPU 的取指—解碼—執行週期**：[assembly-and-chains](assembly-and-chains/README.md)
   已對過（pending 投遞位＝PC、inst／鏈／批＝指令／行程／tick）。與 1 不衝突：**1 是
   語意層的說法，3 是機器層的說法**。

使用者自己的 game loop 比喻（一次 exec ＝ 一格 `_process(delta)`，
[game-process-model](game-process-model.md)）與三者都相容——**一格就是一步歸約**。
三個候選互相不排斥：**單一資料夾看是 eval，多資料夾互投遞看是 actor，機器層看是
CPU 週期**。

**本節結論（2026-09-03 已裁）**：**三層各一個名字：`aos exec` ＝一步歸約、`aos run` ＝
eval（歸約到不動點）、daemon ＝ REPL；多資料夾互投遞＝actor、機器層＝CPU 週期。**

## 使用者提問（2026-09-03，續）：deliver 算 REPL 嗎、寫 `.c` 是不是規劃資料夾

**使用者原話（照記，玩系統時的兩次追問）**：

> 我在 terminal 輸入 `aos deliver xxx`，這樣的行為算是 REPL 嗎？套用到我們這套概念上又算
> 是啥？然後在這套概念上進行編程，也就是撰寫 `.c`，是不是就是去規劃資料夾結構、和在資料夾
> 內新增檔案？

> 既然在這套體系上編程是在資料夾內新增或修改檔案，那麼跟 lisp 相比，這個資料夾的運行入口
> 是什麼？lisp 的運行入口就是 list 中的第一個元素。

**以下三節全是頂層回應（AI 觀察，非裁決，使用者可否決）。**

### 第一題：deliver 不是 REPL，是 REPL 的 R——按下 enter 那一下

**a. R／E／P／L 對上去，deliver 只佔 R 那一格。**

| | REPL | `aos deliver` 這個行為 |
|---|---|---|
| **R** | 讀一句輸入 | **`aos deliver`**——把 list 放上桌子 |
| **E** | 求值 | `aos run`／daemon 抓起來跑 |
| **P** | 印出結果 | 你之後自己去看資料夾、或 `aos state` |
| **L** | 回去等下一句 | **是你自己** |

沒有 daemon 時，**人就是那個迴圈**；daemon 出現之後 L 才搬過去。這跟
[turing-to-os §三之一](turing-to-os.md)「恰一個使用者，而他也是一隻 agent 住 `~`」同向：
**人是桌邊的一個 agent**，不是站在系統外面的操作員。

**b. 但 deliver 送的是 inst 這一層，不是源碼 form。** 所以它更像舊時代機器碼 monitor 的
提示符（直接餵組合語言），不是 lisp 的 REPL。lisp 層級的 R 應該是**「送一份源碼 json →
拆平 → 進 series → run」**，那個入口今天**還沒有**。

> **核對程式後的兩點修正（`core/loop`、`core/agent`）**：
>
> 1. **`aos deliver` 一次送的是「一條」inst，不是一批。** CLI 形狀是
>    `aos deliver [folder] <inst.json>` 或 `aos deliver [folder] -- <argv...>`，作用是把
>    **一份 `Inst`** 原子寫進 `.aos/inbox/<id>.json`（先 `.tmp` 再 `rename`）。**批是 loop
>    湊的**——每回合開頭把 `inbox/*.json` 全部搬進 `batch/<turn>/insts/`。所以「一條 vs
>    一批」的分界線就在**回合邊界**，這與 [interrupts §七](assembly-and-chains/interrupts.md)
>    「整批 claim 之後才執行、外部投遞只落在 tick 之間」是同一條線。
> 2. **今天最接近 REPL 的是 `aos chat`，但它的 E 比「一次 LLM 呼叫」大。** 實際形狀是：
>    `aos chat <text>` ＝（沒有 agent 就先 init）→ **`say` 一則 `.md` 訊息**進
>    `.aos/agents/<name>/say/` → 若沒有活著的 `run.pid` 就**自己反覆 `run_turn`**（有的話
>    就等既有 loop）→ 直到 history 長出新的 assistant 回覆才印出來，預設等五分鐘。所以
>    chat 的 **R 是一則訊息**（不是 inst）、**E 是「推回合到出現回覆」**（可能多回合、多次
>    LLM 呼叫，形狀接近 `aos run` 的 big-step 而非 small-step）、**P 是印回覆**、**L 是人**。
>    它是三個入口裡唯一四格都齊的。

**c. 所以 R 有兩層**：**源碼層**（未來）與 **inst 層**（現在的 deliver）。兩層恰好對上
[lisp-reconciliation §二十八](assembly-and-chains/lisp-reconciliation.md) 對照表的**第一列**
（quoted form ＝源碼 json）與**倒數第二列**（primitive op ＝ inst 批）。

### 第二題：對，但要加一個精確化——寫 `.c` 是寫「quote 住的那部分檔案」

**d. 一個資料夾裡有四種東西，編程只碰前兩種。**

| 種類 | 是什麼 | 穩態／暫態 | C 的說法 |
|---|---|---|---|
| **程式** | 模板 | 穩態 | `.c`／`.h` |
| **資料** | 值 | 穩態 | `.c`／`.h`（初始化資料） |
| **continuation** | `series.json` | 暫態 | `.o`／執行檔裡的 IR、PC |
| **產出** | `out/`、臨時資料夾 | 暫態轉穩態 | 執行期記憶體 |

後兩種是**跑出來的**，不是寫出來的。

**e.「新增檔案」＝定義 binding；「規劃資料夾結構」＝設計 scope 與壽命。** 上面
[四條裂縫](#四條裂縫使用者已裁決2026-09-01)的第 2 條（檔案更像 binding，不像 atom）在這裡
從裂縫翻成正面說法：**寫程式就是在環境裡加 binding。** 而資料夾結構就是 scope——
[c-language §十五](assembly-and-chains/c-language.md) 已經把**臨時資料夾＝堆疊框、世界資料夾
＝heap**對過，兩者**差別只在壽命**。

**f. 但資料夾結構有兩個層級要分開。**

- **一個「會跑的資料夾」之內** ＝ **scope**——這才是使用者說的「編程」。
- **多個「會跑的資料夾」之間** ＝ **actor 拓樸**——哪些東西各自是一個 actor、怎麼互投遞。
  那是**系統設計**，對上前面
  [「aos loop 更像啥」](#ai-觀察非裁決可否決-1)的候選 2。

對照 C：**拆函數** vs **拆成多個程式**。使用者問的「規劃資料夾結構」大概兩層都包，值得
分開想——因為第一層改的是可讀性，第二層改的是隔離（`G03`）與排程（`G10`）。

**g.「跑起來」＝unquote＝deliver 第一條 serie**
（[lisp-reconciliation §二十八](assembly-and-chains/lisp-reconciliation.md) 表第三列：
funcall／apply ＝拿掉 quote ＝穩態變暫態的那一刻）。所以**編程與執行的分界，在檔案層面就是
「哪些檔是你放的、哪些是 run 長出來的」**。

**h. 邊緣狀況：源碼、IR、series、產出全住同一個資料夾**——等於**在源碼目錄裡 build**。
這對人類可理解性（[os-metrics-and-resources §三](os-metrics-and-resources.md)）不利，需要
**版面慣例**把「人放的」與「機器長的」分開。分類的尺現成：
[game-process-model 第三部分](game-process-model.md) 的判別式**「刪掉它，世界語意變不變？」**
——只變節奏的歸機器，語意會變的歸世界。方向也現成：**`.aos/` 給機器、頂層給人**。
（今天沒有一份專講版面歸屬的 `aos-folder` 文件；最接近的位置是
[machine-shape/layout-and-spec §28](machine-shape/layout-and-spec.md) 的 ownership table，
而 game-process-model 第三部分已經指出**它還得多記一欄「這條路徑算不算世界的一部分」**。）

### 第三題：資料夾的「car」＝ loop 第一個讀的那個約定檔名

**i. 資料夾沒有「位置上的第一個元素」，所以 car 只能是約定的檔名。** 今天那個檔就是
**`series.json`**——loop 另讀它決定抓哪筆（[series §十一](assembly-and-chains/series.md)）；
再往下一層是**收件匣裡 pending 的投遞位**（[interrupts §六](assembly-and-chains/interrupts.md)：
pending 的投遞位就是 PC）。**入口不是位置，是約定的檔名**——這是資料夾與 list 在「入口」
這件事上**唯一**的差別。

**j. car 決定其餘元素怎麼被看待。** lisp 的 special form（`quote`、`if`、`lambda`）全住在
car，所以那個約定檔天然就是**放 quote 標記的地方**：

- 它說「quote」→ 整個資料夾是**穩態資料**；
- 它說「模板」→ 這是 **lambda**，只在被開串時才 unquote；
- 它有**游標** → 這是**正在跑的行程**。

於是 **`B1`（批 header）、`series.json`、`G07`（程式／行程標記）在這個讀法下是同一個東西：
資料夾的 car。** ——[lisp-reconciliation §二十八](assembly-and-chains/lisp-reconciliation.md)
表的第一列（quoted form）與第四列（continuation）在這裡合流。

**k. car 空＝穩態＝不動點。** 沒有 series、收件匣也空的資料夾，`aos run` 一次什麼都不動。
這跟本日
[觀察 b](#ai-觀察非裁決可否決)的「exec 不再改它就是穩態」完全一致，而且**判法便宜**：
看 car 就好，不用比對整個資料夾（同
[lisp-reconciliation §三十之 2](assembly-and-chains/lisp-reconciliation.md)「游標到底＝正規形」）。

**l. 一個資料夾不只一個 car。** list 只有一個 car，但 `series.json` 記的是**「哪些串在跑」
（複數）**——所以資料夾更像**一批 list**，不是一個 list。這是
[series §十](assembly-and-chains/series.md)「該模仿的不是單發射 CPU，是遊戲引擎」與
[interrupts §五](assembly-and-chains/interrupts.md)「留著批」兩條裁決在「入口」這題上的
迴響：**資料夾的 car 是一批，不是一個運算子。**

**m. 入口從哪來，兩個選項**（未裁，實作時會被迫選）：

1. **從外面給**——人 `aos deliver` 第一條 serie。**今天的做法**；冒煙路徑就是 `aos say`
   再 `aos run`。
2. **資料夾自己宣告**——header 裡有 `init`，daemon／載入器啟動這個資料夾時**自動開第一條
   串**。對應 lisp image 的 toplevel function、C 的 `main`。

**lisp 走 (2)**（car 在 list 裡面），**現在的 aos 走 (1)**。兩者可並存：**(2) 是把 (1) 寫進
header 的糖**，而「header」正是 `B1` 那個車位。

**2026-09-03 已裁：走外部**——頂層資料夾由使用者開、或使用者開的 daemon 代開，不是自宣告 `init`，見 [nested-eval-car](nested-eval-car.md#裁決2026-09-03)。

**n. car 可以是算出來的**（lisp 的 `((lambda …) args)`）。這裡對應
[interrupts §一](assembly-and-chains/interrupts.md)「跳轉＝自己改下一格」，**已裁**——
不新增問題。

**2026-09-03：car 進一步精確為 `.aos` 本身**（`series.json` 只是 `.aos` 裡被先讀的那個檔），見 [nested-eval](nested-eval.md)／[nested-eval-car](nested-eval-car.md)。

## 寫的方式也是 lisp 的：REPL

> **2026-09-03 使用者修正**：嚴格套用的 REPL 是 **daemon ＋「exec 某資料夾」的指令**，
> 不是 aos loop——見上面「續：REPL」。以下原文保留不刪。

**使用者原話（2026-09-01）**：「最近我一直在想，用 coding agent 做事，其實很像是在使用
repl 方式寫程式。」

這條接得上前面，因為 **REPL 也是 lisp 那個傳統的東西**：前面講的是程式的**形式**是
lisp（檔案／資料夾），這條講的是**寫的方式**也是——不是編譯、不是批次交件，是逐次求值、
看結果、再下一句。

**agent loop 本身就是一個 read-eval-print-loop**：讀（`say/`、inbox）→ 求值（模型思考
＋工具）→ 印（`log.md`、`aos listen`）→ 回圈。所以「agent loop ＝ CPU」與「agent loop
＝ REPL」是同一個東西的兩種讀法——**CPU 是「它是什麼計算單元」，REPL 是「人怎麼跟它
互動」**。[turing-to-os](turing-to-os.md) 記的是前者；使用者定義的「作業系統＝方便人
使用」要的其實是後者，而後者到現在才被講出來。

**資料夾就是 image。** lisp／Smalltalk 的 image 是一份活的、可持續變異的狀態，開發方式
是往裡面逐步加東西，不是重新編譯出一個新的。aos 把檔案系統當記憶體與程式載體，那個
資料夾就是 image——[usability-target](usability-target.md) 裡「停掉、隔天再來，記憶還在
不在」問的其實是 image 活不活得下來。

### 四條裂縫——使用者已裁決（2026-09-01）

**1. 節奏差一個數量級 → 不是缺陷，是設計特性。** 使用者裁決：

> 節奏本來就會有差，就像我說的**快世界與慢世界**，而且**使用者可能會同時跟多個 REPL
> 交流**，加上 REPL 跑下去，思考＋工具一路下去，**可能十幾分鐘才搞定，這很正常**。

所以「一回合秒到分鐘」不必往「像不像 REPL」的方向修。REPL 的本質是**逐次求值、看結果、
再下一句**，不是低延遲；延遲只是快世界那一端的特徵，不是 REPL 的定義。

> **`快世界／慢世界` 有前作背書**，但兩處用的軸不同，別混：[prior-work](prior-work.md)
> 引 `agent-world/README` 第 8 條是**粒度**軸（粗粒度走 agentfs/9P、可信且熱的邊走
> in-process）；這裡是**節奏**軸（互動延遲）。同一組詞，兩個軸。

**這條裁決反過來加重了另一件事**：既然使用者會**同時跟多個 REPL 交流**、而且每個都可能
跑十幾分鐘，那「看得見誰在跑、跑到哪、死了沒」就從**便利**變成**必要**——`G08`（控制介面）
與 `G22`（方便人管理正在跑著的程式）的優先序因此上升，不是因為單一 REPL 難用，是因為
**N 個慢 REPL 沒有 `ps` 就管不動**。

**2–4 → 使用者裁決「之後實作的時候自然能有解」**，不擋設計，不必現在拍板：

- print 印的是敘述不是值，餵不回下一次 eval（`G23`）
- eval 不確定，REPL 的「重打一次看看」失效（`G19`）
- 沒有輸入歷程可重放，而 git 買不到 replay（已裁決，見 [prior-work](prior-work.md)）

記在這裡是為了實作時想得起來，不是當成待辦。

## 相關

- [turing-to-os](turing-to-os.md)——上游：三要件、agent loop ＝ CPU、檔案系統即記憶體
- [cpu-to-os-gaps.json](cpu-to-os-gaps.json)——`G20`（方便人寫程式）、`G24`（同像性）、`G07`（程式與行程的分界）、`G14`（程式的可命名性）
- [usability-target](usability-target.md)——順手判準：在 shell 打 `aos xxx` 要有 pi coding agent 的效果（REPL 那節量的就是它）
- [call-format](call-format.md)——CLI 呼叫＝Lisp 呼叫的序列化（argv 是 list、旗標是 keyword）
- [workshop／lisp-in-aos](../workshop/records/lisp-in-aos.md)——同像性在 JSON 上不是免費的
- [assembly-and-chains／lisp-reconciliation](assembly-and-chains/lisp-reconciliation.md)——三層套回 C 線的身分對照表（源碼／series／inst）
- [assembly-and-chains／series](assembly-and-chains/series.md)、[interrupts](assembly-and-chains/interrupts.md)、[c-language](assembly-and-chains/c-language.md)——`series.json`＝資料夾的 car、pending 投遞位＝PC、臨時資料夾＝堆疊框
- [machine-shape/layout-and-spec](machine-shape/layout-and-spec.md)——ownership table：哪條路徑歸機器、哪條歸世界
- [theses-review](theses-review.md)／[game-process-model](game-process-model.md)——同日的複審與第三個模型
- [os-metrics-and-resources](os-metrics-and-resources.md)——可預測性（不動點要幾回合）、預算與 RTOS 的 deadline
- [nested-eval](nested-eval.md)——**本檔的續篇**（2026-09-03，因本檔已超長另開）：「list 的元素也可以是 list」拆成運算式巢狀（flatten 壓平）與資料夾巢狀（作用域，car 點名才開）
