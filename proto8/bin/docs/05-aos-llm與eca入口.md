← [入口](../README.md)｜涵蓋：aos-llm（改定義裡的腦）、aos-eca-screen、aos-eca-llm（eca 的 screen／llm 子介面身體）｜上一份 [04-aos-daemon-ctl續](04-aos-daemon-ctl續.md)

## aos-llm - 看／改 agent 定義裡的腦設定（11-04）

使用者 11-04 晚：「aos-agent llm改正在跑著的，aos-llm改定義」。跟 `aos-tools`（改定義的工具箱）並列；改正在跑的那一隻用 `aos-agent llm --target 名字`（[extras/agent](../../extras/agent/README.md)）。

```
aos-llm XXX [show|set 鍵=值…]        XXX＝agent 定義資料夾；沒給動作＝show
aos-llm proto8/demo/agent-fsm               # url=… model=chatgpt-gpt-6-luna-low key=
aos-llm proto8/demo/eca-claude set model=haiku   # 改 cli.json 的 --model；kind=claude 只印
```

- 它不懂格式：讀 `<XXX>/interfaces.json` 的 `aos-agent.llm`（宣告的資料夾程式），那個資料夾的 `interfaces.json` 要宣告 `aos-agent/llm`，再 `aos-exec --ws <XXX> --stack <暫存資料夾> <XXX>/<llm> def 動作…`（stack 用完就刪：不給的話 aos-exec 會建 `<XXX>/.stack`、寫到定義），stdio 透傳、結束碼照傳。
- 改了＝之後從它 add 的、**沒有副本**的那幾隻下一題都變；有副本（`aos-agent llm set` 過）的不跟，要跟用 `aos-agent llm --target 名字 reset`（使用者 11-04「不跟。風險自行處理。但我們可以給reset。」）。
- 錯：stderr 一行 `aos-llm: 代號 原因`、退 1：`ArgumentsBad`、`FlagUnknown`、`PathMissing`、`InterfaceMissing`、`InterfaceBad`、`LlmMissing`（沒宣告 llm）、`LlmBad`（llm 資料夾不在或沒宣告 `aos-agent/llm`）；入口自己的錯（`KeyUnknown`…）它自己說。

## aos-eca-screen、aos-eca-llm - eca 的兩個子介面身體（11-04）

`demo/eca-claude/screen/_entry`＝`["aos-eca-screen", ".."]`、`llm/_entry`＝`["aos-eca-llm", ".."]`（`..`＝eca 資料夾，入口的 cwd 是它自己的資料夾）。人不直接打，經 `aos-agent open／close／watch／llm` 或 `aos-llm`；介面規格在 [thinking aos-agent 03/02](../../thinking/2026-11/04/aos-agent/03-種類與契約/02-子介面規格.md)。

- `aos-eca-screen <eca 資料夾> open [-d]|close|watch`：吃 `AOS_STACK`（那隻的 stack）、`AOS_WS`；open／close／watch 的身體 11-04 從 aos-eca 原樣搬來（畫面＝`<stack>/<kind>/tty.sock` 的 tmux，Ctrl-] 跳出）。錯：`ArgumentsBad`、`StackMissing`、`SessionBad`（正在答題時 close），加 cli_session 的。
- `aos-eca-llm <eca 資料夾> def|stack show|set 鍵=值…|reset`：鍵 `kind`（只印）、`model`；`def`＝cli.json `flags` 裡 `--model` 後面那格（只改那格、排版照舊），`stack`＝`$AOS_STACK/llm.json`（只放改過的鍵；`reset` 刪檔）。`lib/agent/cli_session.py` 每題讀 `llm.json` 換 `--model`、讀 `$AOS_STACK/tools.json` 當登記檔（cli.json 沒明寫 `tools` 時）＝下一題生效。錯：`ArgumentsBad`、`KeyUnknown`、`StackMissing`、`CfgBad`、`WriteFailed`。
