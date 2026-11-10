# self-tools（11-10 晚）：給腦改自己的工具——self_tools、self_llm，與試驗場驗收

← [11-10](../)

## 使用者原話

- 「然後aos-agent tools應該已經弄好了吧。可以的話，self_tools也來看看」
- 「我要玩試驗場，最重要的就是三個工具：agents, self_tools, memory，並且是在eca/fsm agent都好了的情況下」
- self_tools 方向：「我原本想說，這支工具就是aos-agent tools的包裝，只是目標改自己」；路徑限制「A，拿掉限制」
- tools 五題：「1.改 2.統一 3.顯示 4.補上 5.順」（記在 [aos-tools-cli 08](../aos-tools-cli/08-施工結果.md)）
- 頂層提議 self_brain：「self_brain來做吧，但改名self_llm」

## 檔

| 檔 | 內容 |
|---|---|
| [01-self_llm知識庫節點](01-self_llm知識庫節點.md) | 要交 json-memory 隊加進 knowledge 的節點內容 |
| [02-試驗場怎麼玩三個工具](02-試驗場怎麼玩三個工具.md) | 照抄指令：fsm 叫它改自己的工具與腦、eca 掛上看工具；刷新 ~/code/playground 的指令 |
| [03-驗收結果](03-驗收結果.md) | 11-10 晚 scratchpad 實跑：每段怎麼驗、結果、改了 self_tools tooldef 兩行、怪處 8 條 |
| [04-不認得的鍵報錯](04-不認得的鍵報錯.md) | 使用者「那就報錯」：tool_io 集中擋不認得的 stdin 鍵、各工具盤點 |

## 做了（commit）

- self_tools 純包裝、tools 五題：`7872d0c9e`；之前 `556d37b31`（override→replace、lv6 收尾）、`d7c3c1240`（knowledge 頁）。
- self_llm：新工具 `lib/agent/self_llm/`（show／set／reset，包裝 `aos-agent llm --target 自己`），agent-fsm、eca-claude 範本預設登記（比照 self_tools）。

## 代定

- self_tools 相對路徑從 `$AOS_WS` 算（aos-agent 在工作區跑）。
- self_tools `path_json` 只收指示詞物件（純字串走 `path`）。
- `ls -l` 的 null 列形狀：`名 TAB null TAB 它蓋掉的那支 TAB 寫 null 的那份#/tools/名 TAB null TAB -`。
- self_llm `set` 收 `settings` 物件（`{鍵: 字串}`），不收 `KEY=VALUE` 字串陣列——腦寫物件比較不會錯。
