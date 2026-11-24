# start-eca：起手範本（eca 版）——一包抄好一棵樹：根、一隻 Claude Code 當腦的 agent（eca-claude）、樹裡的薄 `env.sh`

← [templates](../../README.md)｜另一包：[start-api](../start-api/README.md)（aos 自己的 agent-fsm，問 llm kernel）

使用者 11-17 裁 L-10 A（做起手範本）、L-7 C（樹裡一份薄 `env.sh`，轉去 `$AOS_HOME/env.sh`；`AOS_HOME` 沒設就報錯），見 [08-要裁的題](../../../thinking/2026-11/17/cpp-py-改名/08-要裁的題.md)。完整的安裝六步與更新五步在 [重建步驟單](../../../thinking/2026-11/17/重建步驟單.md)。

## 用法

先做過一次：在 clone 下來的 `proto8/` 跑 `python3 install.py`，再把 `export AOS_HOME=<那個 proto8 的絕對路徑>` 寫進 `~/.bashrc`、開新視窗；`claude` 指令要在 `PATH` 上、登入過。

```sh
cp -r $AOS_HOME/templates/starts/start-eca ~/aos-home            # 一行抄好整棵樹（位置自己挑）
cd ~/aos-home && source env.sh                             # 每個視窗先做這行
aos-exec root                                              # 視窗 A：起根（前景；Ctrl-C＝整棵停）
aos-agent -d .stack ctl add --auto-restart -w . agents/ann # 視窗 C（先做上面那行 source）：把 agent 掛到根上
aos-daemon-ctl -d .stack ls                                # _clock、_sweeper、ann 都是 running
aos-agent -d .stack --target ann say hello && aos-agent -d .stack --target ann listen --timeout-s 120   # 真的叫 claude，會花額度
aos-daemon-ctl -d .stack shutdown                          # 關樹；再起＝視窗 A 那行，睡下的自己醒
```

**要把工具關進沙箱（[aos-sandbox](../../../py/aos/apps/sandbox/README.md)）的話**：上面 `-w .` 讓 agent 的工作區＝整棵樹，樹的控制台（根的 `.stack/` 信箱、llm kernel 與各隻的定義）都在裡面，沙箱裡的 agent 碰得到它們、還能叫 daemon 在沙箱外再開一隻——這是使用者自己承擔的風險（使用者 11-18 晚：「好，沙箱這個基本上是使用者要自己承擔的風險吧。」）。要隔得乾淨就給它專用的工作夾：`mkdir work && aos-agent -d .stack ctl add --auto-restart -w work agents/ann`。

## 裡面有什麼

| 夾／檔 | 是什麼 | 從哪抄的 | 跟原範本不一樣的地方 |
|---|---|---|---|
| `env.sh` | 薄的：`AOS_HOME` 沒設報一行錯；有就 `source "$AOS_HOME/env.sh"`（清掉別棵樹的 `AOS_*`、把 `$AOS_HOME/bin` 放上 `PATH`）；最後可以加這棵樹自己的 `export` | — | — |
| `root/` | 根 daemon 的定義（時鐘＋清道夫） | [daemon-root](../../daemons/daemon-root/README.md) | `.env` 的 `AOS_LLM_KERNEL` 指樹裡的 `llms/stacks/llm`（這包沒帶 llm kernel；要的話照 start-api 抄 `kernel/llm-kernel` 到 `llm/`、掛上根，並把這行改成 `${AOS_STACK}/procs/llm`） |
| `agents/ann/` | 一隻外部 coding agent（Claude Code） | [eca-claude](../../agents/eca-claude/README.md) | 沒有（`llm.json` 照範本是 `sonnet`） |

跑起來後樹裡多出 `.stack/`（根的 stack，agent 的 stack 在 `.stack/procs/ann/`）。

## 維護

`root/`、`agents/ann/` 是原範本的逐字抄本，只差上表那一處；改了原範本要同步抄過來，[templates/tests/test_start.py](../../tests/test_start.py) 會逐檔比對、不一樣就紅。`env.sh` 兩包是同一份。

repo 更新後，已經抄出去的樹哪些要重抄見 [14-更新與重新複製](../../../thinking/2026-11/17/cpp-py-改名/14-更新與重新複製.md)。
