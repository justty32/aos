← [回入口 05-agent.md](../05-agent.md)｜段落：self 一家與 hook（C-90）、goal 與 todo（C-91）、小模型裝不下工具說明（C-92）｜上一份：[05-C-89-不同質與族譜](05-C-89-不同質與族譜.md)｜下一份：—

## self 一家與 hook

<a id="c-90"></a>
- **C-90** **self 一家：每支 `self_X` 是人用指令 `aos-agent X` 的純包裝、目標改成自己；人用的指令先有**（使用者 11-10：「我原本想說，這支工具就是aos-agent tools的包裝，只是目標改自己」，[self-family](../../../thinking/2026-11/10/self-family/README.md)）。改的是正在跑的這一隻在 stack 裡那份，定義不動（C-46）。現有：`self_tools`（工具覆蓋層，加減同一輪就生效，[C-42](01-續-C-42.md)）、`self_llm`（腦設定）、`self_system`（system 文字，C-19）、`self_history`、`self_hook`、`self_state`、`self_ctl`。
  - **history**（`aos-agent history`／`self_history`）：看、刪一段、把一段換成摘要、任一行隨便改，四種都給，風險使用者自擔；正在進行的那一步（叫 self_history 的那則與它的結果）動不了；改掉的原文預設搬到旁邊（`history_removed.jsonl`），可選搬到哪或不留；eca 給縮水版（history 被改過，下一輪就開新對話）。使用者：「1.全給，風險自己擔。2.可以。3.可選，默認搬到旁邊(可以選要搬到哪) 4.接受縮水版。5.對」。摘要那則的角色預設 user，內容固定成 `[aos] summary: …`，一眼看得出是系統寫的（使用者「self_history的摘要這塊，身份可以是user，只是內容這塊希望能符合特定格式，比如我們現有的error那樣，就aos:...。」，[tonight-rulings](../../../thinking/2026-11/10/tonight-rulings/README.md)）。
  - **hook**（`aos-agent hook`／`self_hook`）：事件發生時跑一個 aos 函數（aos-exec 跑得動的都算），事件內容是一份 JSON、從 stdin 進（使用者「還有self_hook，用於在有東西進到queue，或是一些事件發生，比如呼叫了某特定工具，比如brain呼叫失敗，或是新增了某些特定工具之類時，執行指定aos函數。」，[hook](../../../thinking/2026-11/10/self-family/hook/README.md)）。事件前、後都有觸發點（事件清單見 [aos-agent docs/06-hook](../../../cmd/aos-agent/docs/06-hook.md)）；每個 hook 自己選：能不能改結果（`intercept`，預設開；改不了的事件只當通知）、等不等它跑完（`async`，預設等）、hook 自己失敗時 agent 停不停（`on_error`，預設跟著停）；只在某些情況觸發寫 `condition`。連鎖觸發（hook 又觸發 hook）不檢測，風險自擔；eca 給縮水版。使用者：「1.讓規劃者回去看過去的定義，基本上就是你理解的這樣。2.可選。我是希望能改變結果啦，只是有些東西不能改，那就不用動。3.都要。4.可選，默認等他跑完。5.可選，默認跟着停。6.自行承擔。7.接受」；預設與選項名：「3.幫我改成預設是開，選項名稱這塊，可以參考c#或java的hook那樣。」「hook這塊，主要走A, 但filter改condition。」hook 清單存在 agent 自己的 stack、蓋在定義那份上，`self_hook` 照上面的包裝原則包 `aos-agent hook`（代定、可翻案，[hook](../../../thinking/2026-11/10/self-family/hook/README.md)）。
  - **看自己、管自己**（`aos-agent ctl state`／`self_state`、`self_ctl`；使用者 11-10：「1.可選。2.點菜，內部可以包裝成偷偷呼叫別的工具，也可以點總覽。3.只給數字。給建議的話後續再做別的工具。4.這個工具改名爲self_state，擴充原有的吧。5.自己叫。啊，需要self_ctl嗎？」「1.做。2.只給有意義的。3.可以。」，[self-family 02](../../../thinking/2026-11/10/self-family/02-self_state與self_ctl.md)）：`ctl state` 分十類（who state tools llm hooks history mailbox children resources time），不給類別＝每類一行總覽，給類別＝那幾類的細節；只給數字與事實、不給建議；不自動帶進 prompt，要看自己叫。`self_ctl` 只給對自己有意義的 stop、pause、sleep、rm，寄出就回、不等結果。

## goal 與 todo

<a id="c-91"></a>
- **C-91** **goal：agent 自己停下來時，aos 把目標丟回給它；todo：清單放自己小格、不自動帶進 prompt**（[goal](../../../thinking/2026-11/11/goal/README.md)、[goal 02](../../../thinking/2026-11/11/goal/02-裁定與施工結果.md)、[new-tools](../../../thinking/2026-11/11/new-tools/README.md)）。goal 原話：「然後自動給agent看的，可能要做goal工具。預期是當agent自己停下來時(在沒有新user prompt的情況下，自己不再呼叫工具)，自動丟goal給他，」「agent可以用goal_pause，宣告說自己因為一些原因所以暫時不做goal，還有goal_resume。」「對，我知道這很靠agent自覺。但這就夠了，沒有自覺的agent你再怎麼催他他也不會做。」
  - 一隻 agent 一個目標，存在自己的 stack（`goal.json`）。agent 用一支工具 `goal` 分動作（get／set／done／pause／resume）；人與父 agent 用 `aos-agent goal` 設、改、清（「agent 自己和外面都行」）。
  - **什麼時候丟**：沒有新的信、自己也不再叫工具（最後一則是沒叫工具的回答）時，aos 把一則很短的 `[aos] goal: …`（目標一句加一行提示）接進 history。有信時信優先。history 還是空的、外面先 set 了也丟，當開場題目（「也丟，當開場題目」）。
  - **結束與暫停**：agent 自己宣告完成或放棄、附一句理由，之後不再丟。等人回覆時 agent 自己 pause、自己 resume；暫停中有新信不自動 resume（「不自動，agent 自己 resume」）。
  - **上限**：連續沒進展才計數，預設十次、設的時候可改；到上限就停、留一則說到上限了（「有，預設十次可調」「連續沒進展才算」）。進展＝叫了 goal 以外的工具（do_task 也算）；goal 只看 history，跟 do_task 不耦合（使用者「算。兩者不要耦合太深，就goal那邊稍微檢查一下history就好。」）。
  - **eca**：goal 機制 fsm 與 eca 都有；eca 範本不掛 goal 工具（使用者「eca基本都有goal，所以goal不用給eca。todo也不用。」，[playground 04](../../../thinking/2026-11/11/playground/04-修與第二輪實測.md)），由人或父 agent 用 `aos-agent goal` 替它設、aos 照樣丟提醒（代定、可翻案，同出處）。
  - **todo**：一支 `todo`（ls／set／add／mark），清單存自己的小格；**不自動帶進 prompt，腦自己查**（使用者選「不帶，腦自己查」；自動給 agent 看的東西由 goal 做）；子 agent、fork 的分身各有自己一份（「各自獨立」）。

## 小模型裝不下工具說明

<a id="c-92"></a>
- **C-92** **工具說明塞不進小模型的 context 時，先去 LM Studio 把 context 開大；真的裝不下，那個模型就不適合當 aos agent，只能當普通的 aos 函數用**（使用者 11-10 深夜：「1.小模型裝不下說明，那就是去把lm studio那邊調整一下。真的裝不下的，那就代表這個小模型不適合aos體系，或是只能作爲普通的aos函數。」，[tonight-rulings](../../../thinking/2026-11/10/tonight-rulings/README.md)）。
