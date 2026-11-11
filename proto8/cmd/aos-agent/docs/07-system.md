← [回入口 README.md](../README.md)｜段落：system（11-11）｜上一份：[06-hook](06-hook.md)

# system：改這隻自己的 system 文字

**一句話**：`aos-agent system set` 在這隻的 stack 放一份自己的 system 文字，它在就**整份**用它、不在就用定義那份；`reset` 刪掉回到定義的。給腦用的同一件事是工具 `self_system`。

使用者 11-11：「然後我們現在的工具沒辦法讓agent修改自身的system prompt，幫我看看是不是要添加一個self_settings工具，或是整合進self_history。」選項框裁：單獨一支工具（人用 `aos-agent system`、腦用 `self_system`）、「fsm 取代、eca 附加」、「只給 reset、不擋」。決定與代定在 [thinking self-system](../../../thinking/2026-11/11/self-system/README.md)。

## 宣告

定義的 `interfaces.json` 在 `aos-agent` 裡寫 `"system": "system.txt"`（定義裡的相對檔名，跟 `tools`、`llm`、`hooks` 同一種寫法）。這隻自己那份＝`<stack>/system.txt`（同一個相對路徑）。沒宣告＝`SystemMissing`；宣告的不是定義內相對檔名、是資料夾＝`SystemBad`。定義那份不在＝空文字。三個範本都宣告了：agent-fsm、reviewer 帶自己的 `system.txt`；eca-claude 沒帶檔（＝預設什麼都不附加）。

## 身體怎麼用

| 身體 | 怎麼用 | 空文字 | 何時生效 |
|---|---|---|---|
| agent-fsm（含 reviewer） | `brain.py` 當最前面那則 system 訊息（**取代**定義那份）；知識庫根照樣接在後面 | 不送 system 訊息（有知識庫根就只放根） | 每格 think 重讀＝同一題的下一格 |
| eca claude | 起 claude 時加 `--append-system-prompt-file <檔>`（**附加**在 claude 自己的 system prompt 後面）；宣告了就一律加 `--system-prompt-snapshot off`（claude 預設把對話第一輪的 system 記下來、`--resume` 照舊送；off 才每輪重讀） | 只加 snapshot off | 下一輪（11-11 haiku 實測：同一段 `--resume` 對話裡換檔、reset，下一輪都跟著變）；畫面開著＝要關掉再開 |
| eca codex | 起 codex 時加 `-c developer_instructions=<文字>`（附加成 developer 訊息） | 不加 | **下一段新對話**：codex 只在對話開頭讀一次，`exec resume` 帶新的不生效（11-11 gpt-6-luna 實測）；`set`／`reset` 會提醒 |

改了會讓腦的 prompt cache 失效一次（system 在最前面）。

## 用法

```
aos-agent system get                    # 印目前生效的全文
aos-agent system get -l                 # 第一行 FROM<TAB>FILE（agent｜definition｜none），再接全文
aos-agent system get --json             # {"text","from","file","bytes"}
printf 'Be brief.\n' | aos-agent system set      # 從 stdin（也可 set - ）
aos-agent system set my-system.txt      # 從檔
aos-agent system reset [-y]             # 刪自己那份；終端會問、-y 不問
```

沒給動作＝`get`。`set` 不給檔而 stdin 是終端＝`ArgumentsBad`（不卡住等你打字）。畫面開著時 `set`／`reset` 照做，stderr 一行提醒「要重開畫面才生效」。同一份定義掛了別的名字時提醒「只改了這隻的」（同 `llm`）。

`llm set system=…` 不是改 system：照存（`llm` 不擋），但 stderr 一行提醒改用 `aos-agent system`（`self_llm` 把這句也給腦看）。
