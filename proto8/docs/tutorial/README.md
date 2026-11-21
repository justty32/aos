# aos 教學：從空資料夾開始，架 daemon、灌 kernel、寫一份 agent.py、接著開發、起一隻 Claude Code 當腦的 eca_main（照著打就能走完，假腦不花錢；eca_main 那章用真的 claude）

← [docs](../README.md)｜[proto8](../../README.md)

使用者 2026-11-19 下午：「話說，幫我弄一份教學吧，從架daemon、灌kernel、寫一份原始碼、接著開發...」。章節順著他當天的比喻走：daemon＝板子、kernel＝灌上去的核心、agent＝應用程式、`agent.py`＝C 原始碼、編譯出的 json＝`.o`、`std`＝標準庫、資料夾＝命名空間、`aos-gdb`＝gdb。

**每一行指令都實跑過**（假腦、公司 WSL；11-20 換成 `defs.Agent(...)`、`@fn.tool` 的寫法後在乾淨複本 commit `726c30ba1` 從頭再跑一遍；11-21 家機在乾淨複本 commit `2060ee9d5` 把 01～05 與 05b 再跑一遍，05b 叫的是真的 `claude`），貼的是真的輸出（截短處標 `…`；pid、時間、信名每次跑都不一樣；實跑在暫存夾，輸出裡的路徑換成教學寫的 `~/code/aos-tut`、`~/repo/aos/proto8`）。沒實跑的都標「未實跑」：第 07 章整章（真模型）、`install.py`（在 repo 裡裝）、第 08 章表上兩個錯誤代號、05b 開畫面之後（只跑到信任提示）；另外視窗 A 的 Ctrl-C 關機沒按過（用的是等效的 `shutdown`）。

**只想最快起一隻 eca_main**：做 [01](01-開始前.md)、[02](02-架daemon.md)，直接跳 [05b](05b-起eca_main.md)。03～05（llm kernel、寫 `agent.py`、掛假腦的 ann）是另一種 agent 的路，eca_main 用不到，可以跳過；06～08 也是。

## 章節

| 章 | 做什麼 | 主要指令 |
|---|---|---|
| [01 開始前](01-開始前.md) | `AOS_HOME`、裝過沒、整套一張圖、兩個視窗 | `source $AOS_HOME/env.sh` |
| [02 架 daemon](02-架daemon.md) | 買板子開機：抄根範本、看表、關機、再開機 | `aos-exec root`、`aos-daemon-ctl ls`／`shutdown` |
| [03 灌 kernel](03-灌kernel.md) | 把 llm kernel 掛上板子、假腦回話 | `aos-daemon-ctl add`、`aos-llm ask` |
| [04 寫一份原始碼](04-寫原始碼.md) | 抄 `agent-python` 骨架、每個欄位是什麼、編譯、檢查 | `agent.py --dry-run`／`--compile`、`agent_def check` |
| [05 掛上去跑](05-掛上去跑.md) | 掛上、說話、聽回答、看全身、停了再跑 | `aos-agent ctl add`、`say`、`listen`、`ctl state`、`ctl stop`／`start` |
| [05b 起 eca_main](05b-起eca_main.md) | 抄 `eca-claude` 範本、掛上板子、跟真的 Claude Code 說話、開畫面、換模型（不用 llm kernel、不用 `agent.py`；從 02 直接跳來也行） | `cp -r …/eca-claude`、`aos-agent ctl add`、`say`、`listen`、`open` |
| [06 接著開發（一）](06-接著開發-1-改與工具.md) | 改了重新編譯（跑著的立刻讀到）；標準庫的包；自己寫一支工具、讓腦叫它；工具或 hook 直接寫在 agent.py | `@fn.tool`、`tool.py --compile`、`defs.tool` |
| [06 接著開發（二）](06-接著開發-2-連結與衍生.md) | 別的庫；靜態／動態連結；從另一隻衍生 | `defs.lib`、`--dynamic`、`defs.load`／`drop`／`extern` |
| [06 接著開發（三）](06-接著開發-3-除錯與腳本.md) | 下斷點、走一格、看它在幹嘛；用 Python 寫腳本 | `aos-gdb`、`a.bp.*`、`a.look`、`from aos.py import agent` |
| [07 換成真模型](07-換成真模型.md) | 改哪個檔、哪個欄位、金鑰放哪（未實跑） | `llm/kernel.json`、`llm={"model": "luna"}` |
| [08 出事時看哪裡、收尾](08-出事時與收尾.md) | 表、`stderr.txt`、常見錯誤行；全部關掉、刪掉 | `aos-daemon-ctl shutdown` |

走完的樣子：`~/code/aos-tut/` 底下有 `root/`（板子）、`llm/`（kernel）、`agents/ann`、`agents/bob`、`agents/eca_main`（應用程式）、`tools/shout`、`mylib/`，跑起來的都在 `.stack/`。

## 最容易卡住的地方

1. **`root/.env` 那一行**（第 02 章）：範本預設 kernel 在「旁邊另一個專案」；照教學把 kernel 掛上板子，就要先改成 `${AOS_STACK}/procs/llm`，而且要在開板子之前改（改了要重開板子）。
2. **用了 `$AOS_WS` 下的庫，編譯時要帶 `AOS_WS=$PWD`**（第 06 章之二）：`env.sh` 會清掉所有 `AOS_*`，不帶就 `SpecBad`。
3. **eca_main 要 `claude` 先登入過**（第 05b 章）：先在一般視窗打一次 `claude`、照畫面登入（沒登入時長怎樣未實跑）。第一次 `open` 開畫面會先問信不信任這個資料夾，選 Yes。
4. **別刪 `agent.py` 裡 `hooks={}` 那行**（第 04 章、06 之三）：骨架帶著它，agent 才掛得了斷點；拿掉（或衍生時沒寫 `hooks=`）＝`HooksMissing`，錯誤行後面那句就是修法。
