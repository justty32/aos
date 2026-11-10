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

## 決定

- **四包**（[lib/packs](../../../../lib/packs/README.md)，每包一份工具清單）：1 看 look（read、ls、view、stat、json_read）；2 改 change（write、edit、copy、move、mkdir、json_write）；3 刪 delete（trash、remove）；4 殼 shell（shell、run_python）。
- **名字**：`bash`→`shell`、`json_edit`→`json_write`、新做 `remove`（真的刪；`trash` 是丟進工作區 `.trash/`）；proto8 不留舊名。
- **預設**：agent-fsm 範本四包全開（`tools.json` 的 `"$override"` 一串四份），想要安全自己收；eca-claude 範本不掛四包（claude 自帶）。
- **工作區限制拿掉**：這 15 支不再「出工作區＝PathBad」；相對從 `$AOS_WS` 算、絕對照用，能不能動看 Linux 權限。
- **memory_write 預設登記**；記憶庫工具改名 `memory_read`；工具本身沒有內建預設位置（叫的人給旗標／目標、環境變數或在定義裡給），範本在定義裡指 `$AOS_HOME/knowledge`。

## 結論

施工結果見 [01-施工結果](01-施工結果.md)。
