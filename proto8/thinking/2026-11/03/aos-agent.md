# 2026-11-03 aos-agent：通用的 agent 介面（只記原文）

← [thinking README](../../README.md)｜月份表 [2026-11](../README.md)

狀態：**記下、未規劃**。

## 使用者原文（11-03，逐字）

> 對了，之後aos-say/listen之類與agent相關的，會被整合進aos-agent xxx這套體系中。這會是通用的agent介面，可以對接上eca, aos體系的loop fsm agent

> 以後的事情，現在先不管

> 這裡還有些想法：cd進資料夾就能say，這或許不應該用到stack相關概念。這應該是agent本身會在工作區建立.aos/agent/相關東西，然後aos-agent say就是看這個。

（背景，頂層補記、不是使用者原話：這句是談到要不要拿掉 `aos-daemon-ctl add --ws` 在 `<工作區>/.stack` 建的捷徑、改用 `aos-daemon-ctl where --stack 名字` 時說的。狀態同上：記下、未規劃。）

> （11-03 晚，頂層解釋完 `lib/aos/aos_ws.py`＝say／listen／aos-ai 共用的「放話、等答案、看狀態」小零件之後）好，那我就不管這個了，aos_ws,aos-say/listen,aos-ai這些之後都會整合進aos-agent。

決定：`aos_ws`、aos-say／aos-listen、aos-ai 以後一起整合進 aos-agent；在那之前不另外整理、不封存（含 `aos_ws.loop_state`）。

## 使用者原文（11-04，逐字）

> 接下來是弄aos loop/fsm agent了，讓fable去規劃吧

> 這個好了之後，就可以綜合eca和這個的特性，弄出統一的aos-agent介面

決定（11-04）：先做 aos 體系自己的 loop／fsm agent（規劃在 [11-04 loop-fsm-agent](../04/loop-fsm-agent/README.md)，對外接法盡量跟 eca 對齊、不一樣的地方標出來），做完才綜合兩邊弄統一的 aos-agent 介面；統一介面本身還沒規劃。

## 使用者原文（11-04 下午，逐字；aos-agent 介面起頭）

> 然後可以開始來做aos-agent介面了。我這邊先起個頭：agent本身運行所需的東西都會放在其stack，然後我預期是一個agent會佔據一個workspace，所以指定給agent的workspace，會在啟動時被agent放一個.aos/資料夾，裡面放著一些資料，比如信箱的捷徑/位置，daemon的stack位置之類

（上面「一個agent會佔據一個workspace」被下一句翻掉。）

> hmmm，感覺有點捨本逐末了。agent不需要佔據workspace。agent本身就是一支aos proc，由daemon管理(對，先暫時忽略直接aos-exec出來的那些)，所以我們要找agent，那就是透過環境變數AOS_DAEMON，然後藉此找到agent這個aos proc的stack

（頂層問：環境變數是不是現有的 `AOS_DAEMON_STACK`；沒有 workspace 可認時，找 agent 是不是一定要給名字。）

> 1.是的，是AOS_STACK_DAEMON。2.啊，這確實有些麻煩，所以可以做擴充，也就是aos-say會去找當前資料夾下有沒有.aos/，有的話去找agent.json。這就是agent佔據資料夾的證據，如果有其他agent想要佔據資料夾，那就是看這個。當然，agent通常是不需要佔據資料夾的。

> 拍謝，打反了，應該是AOS_DAEMON_STACK

決定（11-04）：
- agent 運行所需的東西都在它自己的 stack；agent 是 daemon 管的一支 proc（先不管直接 aos-exec 起的）。
- 找 agent：環境變數 `AOS_DAEMON_STACK`（沿用現有名字）→ daemon 表上的名字 → 那支 proc 的 stack。
- agent 通常不佔資料夾；可選的擴充：資料夾裡有 `.aos/agent.json`＝被某隻 agent 佔了，`aos-say` 在當前資料夾找到它就知道找誰；別的 agent 想佔同一個資料夾也看這個。
- 介面的細節等 loop／fsm agent 做完後由 fable 規劃。
