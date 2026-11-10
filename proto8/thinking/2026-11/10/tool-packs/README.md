# tool-packs — 通用工具分四包、純包裝、拿掉工作區限制（11-10 深夜）

← [2026-11-10](../README.md)

## 使用者原文

1. 「然後我們目前沒有一個基本的，類似pi coding agent的read/write工具。」（頂層答：lib/base 有，但範本沒登記）
2. 「通用工具這塊，memory_write也預設登記。然後你列的這些，首先是真的基礎的read/write/edit/shell/ls/view/copy/move/mkdir/state/trash/remove，這些就是/usr/bin的包裝。然後是json_read/write，這是aos-json的包裝。run_python這塊...好啦，可以有。　然後預設是否開啓...我覺得應該學習claude，最基礎的就是read/ls/view/stat要有。然後是普通的編輯如write/edit/copy/move/mkdir，再來是trash/remove，最後是shell。就是說，這是一包一包的」（「state」是 stat 的筆誤）
3. 頂層複述四包、三處名字差異（bash→shell、json_edit→json_write、remove 現在沒有，「照你的名字改、新做 remove」使用者沒反對），問四題。使用者：「1.預設開到第四包，想要安全就自行限制。2.好。3.對。4.沒有預設，你得自己指定」
4. 確認第 4 題範圍時：「memory_read也是」
5. 「memory_read吧。然後...應該說，memory_read/write，就是吃旗標或目標，或是吃環境變數，啊這些都要自己給。或是在定義中給。定義中我們可以指定knowledge/aos」
6. 「或是knowledge/」；頂層問指 knowledge/aos 還是 knowledge/：「指knowledge/」
7. eca 範本掛不掛四包：「Hmmm，感覺我們現在的預設工具好像太多了。對於eca，其實那些基礎工具就不用了。」
8. 頂層問預設工具太多怎麼收：「照包砍。」；選項框四包（自我管理／子 agent／通訊／記憶）都勾；fsm 基礎包「維持四包全開」；wall_clock「等等，我有些意見」
9. 「就是說，wall_clock他的功能我記得是去看daemon的clock proc。所以感覺要改名爲peek_clock。然後我會覺得，可以這樣分...我的一家之言啦：clock_register,self_hook兩個分一組，self_tools/llm/state/ctl/history一組。agents一組。mailbox_*一組，memory_*一組。peek_clock一組。」
10. 「1.不對，agent_def另外放。之後可能會有tools_def。2.都開吧。peek_clock就是純粹看daemon clock。wall_clock改peek_now_time。」
11. 「這種peek_clock,peek_now_time放一起，就是小工具的感覺。」；頂層問現成的 math 要不要也收進小工具包：「好」

## 決定

- **四包**（[lib/packs](../../../../lib/packs/README.md)，每包一份工具清單）：1 看 look（read、ls、view、stat、json_read）；2 改 change（write、edit、copy、move、mkdir、json_write）；3 刪 delete（trash、remove）；4 殼 shell（shell、run_python）。
- **名字**：`bash`→`shell`、`json_edit`→`json_write`、新做 `remove`（真的刪；`trash` 是丟進工作區 `.trash/`）；proto8 不留舊名。
- **預設**：agent-fsm 範本四包全開（`tools.json` 的 `"$override"` 一串四份），想要安全自己收；eca-claude 範本不掛四包（claude 自帶）。
- **工作區限制拿掉**：這 15 支不再「出工作區＝PathBad」；相對從 `$AOS_WS` 算、絕對照用，能不能動看 Linux 權限。
- **agent 工具也分包**（第 8～11 條）：小工具 gadgets（peek_clock、peek_now_time、math）、事件 events（clock_register、self_hook）、自我管理 self（self_tools、self_llm、self_state、self_ctl、self_history）、子 agent children（agents_children、agents_ctl）、定義 def（agent_def）、信箱 mailbox（mailbox_peek／read／send）、記憶 memory（memory_read、memory_write）。七包兩個範本都開；範本 `tools.json` 只剩 `$override` 串＋記憶兩格的 `env`。
- **時間工具**：`wall_clock`→`peek_now_time`（功能不變）；新做 `peek_clock`（讀 `$AOS_CLOCK` 回 cycle 與 interval_ms，沒設或缺檔＝`ClockMissing`）。
- **memory_write 預設登記**；記憶庫工具改名 `memory_read`；工具本身沒有內建預設位置（叫的人給旗標／目標、環境變數或在定義裡給），範本在定義裡指 `$AOS_HOME/knowledge`。

## 結論

施工結果見 [01-施工結果](01-施工結果.md)；memory 改名、沒有預設庫根、出廠根上移見 [02-memory-read施工結果](02-memory-read施工結果.md)。
