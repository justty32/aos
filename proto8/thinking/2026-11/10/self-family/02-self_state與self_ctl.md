# 02 self_state 與 self_ctl（11-10 晚）

← [self-family](README.md)｜施工結果見 [03](03-self_state與self_ctl施工結果.md)

## 使用者原話（逐字，頂層轉來）

- （談 mailbox 時）「給一個工具，mailbox-peek，讓agent自己決定是否要看信。對了，以後可能會有工具：self_peek，用於自檢，讓agent看看自身情況，其中就會包含信箱是否有信。這是兩個工具，因爲有時候是只想看信箱。」
- 「來聊self_peek」。頂層攤現況（`aos-agent ctl state` 已印狀態、路徑、queue、最近回答、自己的工具改動）與八類可看的（我是誰／現在狀態／裝備：工具、腦、hook／history 幾則多大／信箱幾封新信／孩子與配額／資源上限與用量／時間），問五題：1 範圍；2 一次全吐或點菜；3 只給數字或也給建議；4 擴充 ctl state 或另開指令；5 要不要每輪自動帶進 prompt。使用者：「1.可選。2.點菜，內部可以包裝成偷偷呼叫別的工具，也可以點總覽。3.只給數字。給建議的話後續再做別的工具。4.這個工具改名爲self_state，擴充原有的吧。5.自己叫。啊，需要self_ctl嗎？」
- 頂層對 self_ctl 的分析：agents_ctl（`aos-agent ctl` 完整包裝、對象表上任何一隻）已能對自己下指令；self_ctl 的用處是「不給管別人的權力、但能管自己」；逐動作：stop（這輪結束就停，最有用）、pause（自己醒不來）、sleep 與 rm（工具沒回話自己就被殺）、start／wake／resume（對自己沒意義）、state（已是 self_state）。問三題：1 做不做；2 照純包裝全給或只給有意義的（stop、pause、sleep、rm）；3 sleep／rm 殺到自己時工具寄出指令就立刻回「已送出」、不等結果。使用者：「1.做。2.只給有意義的。3.可以。」

## 決定

- 人用的 `aos-agent ctl state` 擴充成十類（who state tools llm hooks history mailbox children resources time）：不給類別＝總覽（每類一行），給類別＝那幾類的細節，`all`＝全部，`-j` 出 JSON。只給數字與事實。各類盡量轉叫既有指令；拿不到的類別印 not available＋原因，不整支失敗。
- `self_state`＝它的純包裝、目標自己；不自動帶進 prompt。
- `self_ctl`＝`aos-agent ctl` 的包裝、目標自己，只給 stop、pause、sleep、rm；寄出就回、不等結果。為此 `aos-agent ctl stop／pause／sleep／rm` 加 `--no-wait`。
- 兩支都登記進 agent-fsm、eca-claude 範本。
