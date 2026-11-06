← [回入口 03-基礎設施.md](../03-基礎設施.md)｜段落：inst、loop 與 daemon、proc 之間的交流（10-29）、tasks 組合子、fsm｜上一份：—｜下一份：[01-續-C-75](01-續-C-75.md)

## inst

實作：[inst](../../../impls/aos-inst/README.md)：C lib、不提供命令列，單子由 aos-exec 行程內跑（[ideas § 20](../../../thinking/2026-10/19/ideas/README.md)）。C-36 的層層遞進從 inst 起，條文放在下面 loop 與 daemon。

- **C-08** 計算任務＝一個 POSIX 行程，不是 thread；不必再往下分種類。（2.7）
- **C-34** 求值＝放開讓它算、過一段時間看狀態變化的結果；求值的定義就是空間狀態的變化。對資料夾求值＝執行這個資料夾；求值還回來的是一個正在變動的資料夾，不是一個值。（3h、3f.1、3f.3）
- **C-42b** inst 的 JSON 裡可以多放東西：九軸特性、traits、資源標籤、優先順序標籤、工具……inst 不認的別人可以讀。工具用 JSON schema 限制引數；schema 怎麼轉成 argv——走 schema→argv 這條路，或先定義一些通用的東西，沒定。（3g.13b）這個抽屜叫 `_metainfo`，見 [thinking 10-13 §3](../../../thinking/2026-10/13/json-path/README.md)。

## loop 與 daemon

實作：loop＝[aos-loop](../../../impls/aos-loop/README.md)；daemon＝[aos-daemon](../../../impls/aos-daemon/README.md)。

> **daemon 兩義**：①[C-04](../01-設計理念/01-C-01～C-48.md) 說的 daemon＝aos 與 Linux 之間的借階層（Linux 那邊的事全在這層）；②這裡的 daemon＝管一群 loop 的程式（`aos-daemon`，C-36）。[名詞表](../附錄1-名詞.md)兩列都留。

- **C-36** 層層遞進：inst（求值一次）→ loop（持續求值）→ node（loop 服務的資料夾）→ daemon（統管 loop）；daemon 跑的 inst 可以是另一個 daemon。（3f.2）落實：inst＝單子＝入口的一種、由 aos-exec 行程內跑（沒有 aos-inst 命令列，C-73、N-59）；loop＝`aos-loop [FLAGS...] loop.json`（`{"exec", "max"}`；設定檔是唯一的位置參數，[ideas 10-21 § 9](../../../thinking/2026-10/21/ideas/05-7-審後的五個細縫與修正.md#9-設定檔是唯一的位置參數path-改字串拼接10-21-傍晚)；`exec` 收 aos-exec 的目標（字串或陣列，每次 `aos-exec` 它；`loop.json#/body` 也是目標），也可以直接放單子物件、行程內跑〔[thinking 10-24](../../../thinking/2026-10/24/exec-relative/01-使用者原文.md#10-24-exec-直接放單子)〕，[ideas 10-21 § 8](../../../thinking/2026-10/21/ideas/05-7-審後的五個細縫與修正.md#8-aos-loop10-21-下午)；子程式退 10 就停，P-06、P-19）；一次一格的 fsm＝`aos-fsm fsm.json`（P-07；設定檔是唯一的位置參數；格的 `exec` 收 aos-exec 的目標（每次 `aos-exec` 它；`fsm.json#/states/<名>/body` 也是目標），也可以直接放單子物件、行程內跑，[計畫 10-21](../../../thinking/2026-10/21/plan/README.md) F1、F2）；node＝被 loop 反覆跑的那個資料夾程式；daemon＝管一群 loop 的 `aos-daemon`（[N-28、N-54](../../NORMS/04-基礎設施-loop與daemon.md)）。只有 impls 的 C++ 版（使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」）。「要跑什麼」叫 `exec`：使用者先選「只有 loop、daemon 用 run」，再「fsm.json，現在是用val，幫我改成exec」、選「exec，loop／daemon 的 run 也一起改 exec」（[thinking](../../../thinking/2026-10/23/naming.md)）。

## proc 之間的交流（10-29）

出處：[thinking 10-28 medium](../../../thinking/2026-10/28/medium/README.md)（使用者原文第三、四、十、十四段，決定 5、12～15、19、28）、[10-29 medium-plan](../../../thinking/2026-10/29/medium-plan/README.md)（使用者 10-29「都照建議」）。規範在 [窗 N-14～N-16](../../NORMS/05-基礎設施-窗.md)、[父子交代 N-64](../../NORMS/10-基礎設施-定義與工作區.md)。

<a id="c-75"></a>
- **C-75**（三種基本概念：投遞、窗、父子交代）11-06 起逐字搬到 [01-續-C-75](01-續-C-75.md)。

## tasks 組合子

實作：現無實作，待做成資料夾程式。使用者 10-15：tasks 組合子「**地位等同於 C 語言的 stdlib**」。

- **C-41** 巢狀：list 的元素也是 list，求值時先對元素求值（畫家裡的畫筆 agent 先算）。（3g.11）比喻用 table（C-71）：table 的元素也是 table。**元素要不要先求值，由 entry 決定**（10-19 晚使用者裁）——原話「算元素？由entry指定，你看，lisp的quote就是那個功能。」像 lisp 的 quote：元素預設只是資料、不求值，entry 要算才算、要叫誰自己叫。所以「求值時先對元素求值」不是規則，是 entry 可以選的一種做法；跟 C-70（aos 不管巢狀、入口自己決定）、C-52（只管自己這一層）一致。（[ideas § 12](../../../thinking/2026-10/19/ideas/README.md)）

## fsm

使用者 10-15：「把 fsm 也跟 tasks 放一起」——fsm 是組合子、同為 stdlib 地位；[agent](../05-agent.md) 是用 fsm 組出來的（一個定義資料夾，C-50）。規範：[NORMS 組合子 § fsm](../../NORMS/07-基礎設施-組合子/01-N-20～N-36.md#fsm)（N-20、N-36、N-38、N-39、N-41）；慣例：[CONVENTION](../../CONVENTION.md) P-07～P-10；實作：[aos-fsm](../../../impls/aos-fsm/README.md)。

- **C-18** agent 是狀態機、是函式、也是計算任務；直接接進核心，不特別處理。（2.13、2.14）〔這裡的「核心」＝名詞表的「系統本體」，不是 C-74 分層裡的核心 aos-exec〕
- **C-25** 大操作（問模型、跑久的工具）丟到另一個資料夾讓另一個行程處理；agent 自己每次 eval 短促。（9/19）aos 的 agent 每次被叫只走一次、由外面的 loop 驅動（C-62、[N-53](../../NORMS/10-基礎設施-定義與工作區/06-N-50～N-53.md)；做法是 P-07 一次一格）。
- **C-39** agent 是一個資料夾、一個 node、一條很長的 list（模型、context、工具、記憶……各占一個元素），持續被求值。最普通的 agent＝狀態機，在等待、思考、行動之間切換，需要思考就丟 LLM。（3f.7、3g.8、3g.9）「list」用 table 比喻（[C-71](../01-設計理念/06-C-68～C-72.md#資料夾程式與環境變數10-19-使用者定)）：各占一個元素、靠名字找，意思不變。
- **C-49** fsm 要很單純：「當現在是A狀態的時候，執行指定inst，就這樣，那個狀態內部、inst內部的東西，fsm不該管。」所以 fsm 只留表與記現在狀態的 state 檔；錯誤處理、計數、暫停、格之間傳資料都歸格自己或跑它的 loop。（10-15 收工後，[thinking 意見 1～4](../../../thinking/2026-10/15/opinions-1-4.md)；規範 N-36、N-38、N-39、N-41；慣例 P-07～P-10）
