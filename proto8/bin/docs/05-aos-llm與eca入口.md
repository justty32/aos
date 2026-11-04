← [入口](../README.md)｜涵蓋：aos-llm（Python 那支已刪）、aos-eca-screen（eca 的 screen 子介面身體）、aos-eca-llm（11-04 晚刪了）｜上一份 [04-aos-daemon-ctl續](04-aos-daemon-ctl續.md)

## aos-llm（Python 那支已刪，11-04 晚）

原本這裡的 `aos-llm XXX [show|set 鍵=值…]`（看／改 agent 定義裡的腦設定，經每隻 agent 的 `llm/` 入口程式）**刪了**：使用者 11-04 晚「aos llm,tool這兩個，我希望他們的定位是跟aos post一樣，作為基礎工具」，名字 `aos-llm` 給寄請求信、收回信的那支 C++ 基礎工具 [impls/aos-llm](../../impls/aos-llm/README.md)（`send`／`recv`／`ask`／`regret`；由 aos-llm-send 改名，[think-as-function 衝突 1 (a)](../../thinking/2026-11/04/think-as-function/05-衝突與方向題.md)）。
改定義裡的腦設定＝人直接改 `llm.json`（例 `aos-json set <定義>/llm.json#/endpoint sol`），跟 aos-tools 改定義一樣是人的事。

## aos-eca-screen - eca 的 screen 子介面身體（11-04）

`demo/eca-claude/screen/_entry`＝`["aos-eca-screen", ".."]`（`..`＝eca 資料夾，入口的 cwd 是它自己的資料夾）。人不直接打，經 `aos-agent open／close／watch`；介面規格在 [thinking aos-agent 03/02](../../thinking/2026-11/04/aos-agent/03-種類與契約/02-子介面規格.md)。

- `aos-eca-screen <eca 資料夾> open [-d]|close|watch`：吃 `AOS_STACK`（那隻的 stack）、`AOS_WS`；open／close／watch 的身體 11-04 從 aos-eca 原樣搬來（畫面＝`<stack>/<kind>/tty.sock` 的 tmux，Ctrl-] 跳出）。錯：`ArgumentsBad`、`StackMissing`、`SessionBad`（正在答題時 close），加 cli_session 的。
- **aos-eca-llm 11-04 晚刪了**（連同 `demo/eca-claude/llm/`）：使用者 11-04 晚「aos llm,tool這兩個，我希望他們的定位是跟aos post一樣，作為基礎工具」——eca 的模型改放定義的 `llm.json`（`{"model": "sonnet"}`），`lib/agent/cli_session.py` 每題讀定義 `llm.json` 疊 `$AOS_STACK/llm.json` 補 `--model`；看／改副本＝`aos-agent llm show／set model=haiku／reset`（aos-json 的語法糖），改定義＝人直接 `aos-json set <定義>/llm.json#/model x`。見 [thinking think-as-function 03 § 2、§ 4](../../thinking/2026-11/04/think-as-function/03-呼叫端.md)。
