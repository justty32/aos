# self-system：agent 改自己的 system 文字（aos-agent system＋self_system）

← [2026-11-11](../README.md)｜[thinking](../../../README.md)

## 使用者原話

11-11：「然後我們現在的工具沒辦法讓agent修改自身的system prompt，幫我看看是不是要添加一個self_settings工具，或是整合進self_history。self_settings工具可以改不少設定，只是有些與self_llm之類的東西重疊，幫我調查與思考看看」

選項框（四題）的答案：

| 題 | 使用者選 |
|---|---|
| 做成什麼 | 單獨一支工具（人用 `aos-agent system`，給腦的是它的純包裝） |
| 名字 | `self_system` |
| 兩種身體怎麼用 | fsm 取代、eca 附加 |
| 要不要擋 | 只給 reset、不擋 |

真腦怎麼驗：「公司有lmstudio，但只有破爛小模型。所以建議都使用eca，實際的loop fsm agent需要回家測。」「eca這塊，除了claude haiku之外，也試試看code gpt luna」

## 決定

- 這翻掉 11-10 隊伍代定的「system 不開放給 agent 調」（[self-tools 05](../../10/self-tools/05-llm設定改名與ls.md)、`templates/agent-fsm/llm_settings.py` 檔頭，兩處已加 11-11 註）。system 仍不是 `llm` 的鍵。
- 模子跟 tools／llm／hooks 一樣：定義 `interfaces.json` 的 `aos-agent` 宣告 `"system": "system.txt"`；這隻自己那份在 stack 同一個相對路徑；**自己那份在就整份用它**（不疊、不合併）；reset＝刪自己那份。定義那份不在＝空文字。
- 人用 `aos-agent system get [-l|--json] | set [檔|-] | reset [-y]`；腦用 `self_system`（`{"op": "get"|"set"|"reset"}`，`set` 帶 `text`），進 `self` 包，兩範本 35 支。
- agent-fsm：`fsm.json` 拿掉寫死的 `--system system.txt`，`brain.py` 照宣告找（先 stack、再定義），每格重讀＝同一題下一格生效；空文字＝不送 system 訊息、知識庫根照接。給了 `--system` 的照它、不看 stack（同 `--tools`）。reviewer 範本同。
- eca：claude 用 `--append-system-prompt-file`（不用整份取代的 `--system-prompt`），宣告了就一律加 `--system-prompt-snapshot off`；codex 用 `-c developer_instructions`。

施工結果、實測、代定與要重建什麼：[02](02-施工結果與代定.md)；調查摘要：[01](01-調查摘要.md)。
