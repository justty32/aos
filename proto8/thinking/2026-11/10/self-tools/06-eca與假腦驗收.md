# 06 eca＋haiku 與 fsm 假腦驗收：self_tools、新寫法的 self_llm

← [README](README.md)

**結論**：都過。eca 上 haiku 會叫 self_tools、self_llm 的四個 op，參數都對，「stored anyway」那行 warning 腦看得到；fsm 改了 temperature 之後，下一次送出的請求就帶上 `0.2`，rm 之後就拿掉。兩題 eca 共花 0.0099 美金。

<details><summary>怎麼驗</summary>

- 環境：scratchpad 用目前 main 的範本 `cp -r` 起一棵（kernel、根、agent-fsm、eca-claude）。eca 的 llm.json 設 `{"model":"haiku"}`、`--max-budget-usd 0.15`。驗完兩台 daemon 都已 shutdown，沒留下行程。
- fsm：抄一份 llm_fake，把每次收到的請求裡 messages／tools 以外的鍵記下來。劇本是 set temperature=0.2 → wall_clock → rm temperature → 回答。

</details>

<details><summary>結果原文</summary>

- eca self_tools：transcript 有 `mcp__aos__self_tools {"op":"ls"}`，回答列出 12 支工具名。
- eca self_llm：
  - `ls` long → `model=haiku\tdefinition`
  - `set {"temperature":"0.2"}` → `aos-agent: warning: temperature is not a setting the body of eca reads (it reads: model); stored anyway` 接 `model=haiku`、`temperature=0.2`、`(takes effect from your next brain call)`；haiku 回答時照抄了 warning
  - `rm ["temperature"]` → `model=haiku` 接結尾句
  - `reset` → 同上
- fsm 四次腦呼叫記到的鍵：`{}`／`{"temperature": 0.2}`／`{"temperature": 0.2}`／`{}`。數字型，下一拍就生效。結束碼 11（REBUILD）沒單獨看，只從這個結果間接確認。
- fsm 另一支劇本 set → ls long → rm → ls → reset 都正常；ls long 是 `model=pt-temp\tagent`、`temperature=0.2\tagent`。

</details>

<details><summary>怪處</summary>

1. reset 的輸出兩邊不一樣：fsm 印 `(no settings: your body uses its defaults)`（定義沒寫 llm.json），eca 印 `model=haiku`（定義的值）。都看得懂，不改。
2. 之前看到的「llm_fake: ArgumentsBad unknown key priority」沒再出現（04 已把 llm_fake／llm_http／llm_forward 標成開放）。
3. daemon 的 PATH 上要找得到 `claude`，不然 `aos-eca-turn: error: CliMissing claude is not on PATH`，eca 停在表上。這是起樹的問題，[02](02-試驗場怎麼玩三個工具.md) 已補一行 `command -v claude`。
4. 驗收時清 listen 用了 `pkill -f "listen --target eca"`，同機別隊如果剛好也有一樣的 listen 在跑，可能會被殺掉，沒法確認。
5. 沒用 gemma 跑第 3 項，用假腦就驗得到請求有沒有帶 temperature。

</details>
