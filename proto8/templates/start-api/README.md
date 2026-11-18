# start-api：起手範本（API 版）——一包抄好一棵能跑的樹：根、llm kernel、一隻 agent-fsm、樹裡的薄 `env.sh`

← [templates](../README.md)｜另一包：[start-eca](../start-eca/README.md)（Claude Code 當腦）

使用者 11-17 裁 L-10 A（做起手範本）、L-7 C（樹裡一份薄 `env.sh`，轉去 `$AOS_HOME/env.sh`；`AOS_HOME` 沒設就報錯），見 [08-要裁的題](../../thinking/2026-11/17/cpp-py-改名/08-要裁的題.md)。完整的安裝六步與更新五步在 [重建步驟單](../../thinking/2026-11/17/重建步驟單.md)。

## 用法

先做過一次：在 clone 下來的 `proto8/` 跑 `python3 install.py`，再把 `export AOS_HOME=<那個 proto8 的絕對路徑>` 寫進 `~/.bashrc`、開新視窗。

```sh
cp -r $AOS_HOME/templates/start-api ~/aos-home            # 一行抄好整棵樹（位置自己挑）
cd ~/aos-home && source env.sh                             # 每個視窗先做這行
aos-exec root                                              # 視窗 A：起根（前景；Ctrl-C＝整棵停）
cd llms && aos-exec --stack stacks/llm def                 # 視窗 B（先做上面那行 source）：起 llm kernel
aos-agent -d .stack ctl add --auto-restart -w . agents/ann # 視窗 C（同上）：把 agent 掛到根上
aos-daemon-ctl -d .stack ls                                # _clock、_sweeper、ann 都是 running
aos-agent -d .stack --target ann say hello && aos-agent -d .stack --target ann listen --timeout-s 20   # 假腦回 FAKE ANSWER to: hello …
aos-daemon-ctl -d .stack shutdown && aos-daemon-ctl -d llms/stacks/llm shutdown                       # 關樹；再起＝視窗 A、B 那兩行，睡下的自己醒
```

## 裡面有什麼

| 夾／檔 | 是什麼 | 從哪抄的 | 跟原範本不一樣的地方 |
|---|---|---|---|
| `env.sh` | 薄的：`AOS_HOME` 沒設報一行錯；有就 `source "$AOS_HOME/env.sh"`（清掉別棵樹的 `AOS_*`、把 `$AOS_HOME/bin` 放上 `PATH`）；最後可以加這棵樹自己的 `export` | — | — |
| `root/` | 根 daemon 的定義（時鐘＋清道夫） | [daemon-root](../daemon-root/README.md) | `.env` 的 `AOS_LLM_KERNEL` 指樹裡的 `llms/stacks/llm` |
| `llms/def/` | llm kernel（問腦的那台）的定義 | [kernel/llm-kernel](../kernel/docs/01-llm-kernel.md) | 沒有 |
| `agents/ann/` | 一隻 agent | [agent-fsm](../docs/02-agent-fsm.md) | `llm.json` 是 `{"model": "fake"}`（假腦，先試流程）；要真模型就換成 `llms/def/kernel.json` 的 `endpoints` 裡的名字 |

跑起來後樹裡多出 `.stack/`（根的 stack，agent 的 stack 在 `.stack/procs/ann/`）與 `llms/stacks/llm/`。

## 維護

`root/`、`llms/def/`、`agents/ann/` 是原範本的逐字抄本，只差上表那兩處；改了原範本要同步抄過來，[templates/tests/test_start.py](../tests/test_start.py) 會逐檔比對、不一樣就紅。`env.sh` 兩包是同一份。

repo 更新後，已經抄出去的樹哪些要重抄（`env.sh` 幾乎不用；各格的程式、接線檔可能要）見 [14-更新與重新複製](../../thinking/2026-11/17/cpp-py-改名/14-更新與重新複製.md)。
