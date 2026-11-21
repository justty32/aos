# start-api：起手範本（API 版）——一包抄好一棵能跑的樹：根（最小核心）、掛在根上的 llm kernel、一份選裝不開的權限站、一隻 agent-fsm、樹裡的薄 `env.sh`

← [templates](../README.md)｜另一包：[start-eca](../start-eca/README.md)（Claude Code 當腦）｜初始 kernel 由哪幾塊組成：[kernel 入口「初始 kernel」](../kernel/README.md#初始-kernel買了板子之後灌什麼)

使用者 11-17 裁 L-10 A（做起手範本）、L-7 C（樹裡一份薄 `env.sh`，轉去 `$AOS_HOME/env.sh`；`AOS_HOME` 沒設就報錯），見 [08-要裁的題](../../thinking/2026-11/17/cpp-py-改名/08-要裁的題.md)。11-20 改成 llm kernel 掛在同一塊板子上（使用者「掛同一塊板子」）、加一份選裝、預設不開的權限站（使用者「加一份選裝、預設不開」），題目與答案在 [aos-init-kernel-1120](../../thinking/2026-11/20/aos-init-kernel-1120/06-使用者已答.md)。完整的安裝六步與更新五步在 [重建步驟單](../../thinking/2026-11/17/重建步驟單.md)。

## 用法

先做過一次：在 clone 下來的 `proto8/` 跑 `python3 install.py`，再把 `export AOS_HOME=<那個 proto8 的絕對路徑>` 寫進 `~/.bashrc`、開新視窗。

```sh
cp -r $AOS_HOME/templates/start-api ~/aos-home            # 一行抄好整棵樹（位置自己挑）
cd ~/aos-home && source env.sh                             # 每個視窗先做這行
aos-exec root                                              # 視窗 A：起根（前景；Ctrl-C＝整棵停）。要真模型，先在這個視窗 export 金鑰（LITELLM_KEY）再起
aos-daemon-ctl -d .stack add --auto-restart llm            # 視窗 B（先做上面那行 source）：把 llm kernel 掛上板子，成為表上一列（只要第一次）
aos-agent -d .stack ctl add --auto-restart -w . agents/ann # 把 agent 掛到根上（只要第一次）
aos-daemon-ctl -d .stack ls                                # _clock、_sweeper、llm、ann 都是 running
aos-agent -d .stack --target ann say hello && aos-agent -d .stack --target ann listen --timeout-s 20   # 假腦回 FAKE ANSWER to: hello …
aos-daemon-ctl -d .stack shutdown                          # 關樹：一句全關（llm kernel 是板子上的一列，跟著睡下）；再起＝視窗 A 那行，睡下的自己醒
```

11-20 在暫存樹照這段從零跑過（假腦）：表上 `_clock`、`_sweeper`、`llm`、`ann` 都是 `running`，回 `FAKE ANSWER to: hello (tool said: …)`；`shutdown` 一句之後根與 llm kernel 的表都是 `sleeping`，只起視窗 A 那行，全部醒來、再問一句照答。

**要把工具關進沙箱（[aos-sandbox](../../py/aos/apps/sandbox/README.md)）的話**：上面 `-w .` 讓 agent 的工作區＝整棵樹，樹的控制台（根的 `.stack/` 信箱、llm kernel 與各隻的定義）都在裡面，沙箱裡的 agent 碰得到它們、還能叫 daemon 在沙箱外再開一隻——這是使用者自己承擔的風險（使用者 11-18 晚：「好，沙箱這個基本上是使用者要自己承擔的風險吧。」）。要隔得乾淨就給它專用的工作夾：`mkdir work && aos-agent -d .stack ctl add --auto-restart -w work agents/ann`。

## 選裝：權限件（預設不開）

`perm/` 是一台權限站（框架站掛成板子上的一列，抄自 [kernel/procs-kernel](../kernel/README.md)），出廠沒掛、沒人用。要開：

```sh
aos-daemon-ctl -d .stack add --auto-restart perm                 # 1. 把站掛上板子
sed -i 's|^# AOS_KERNEL=|AOS_KERNEL=|' agents/ann/.env           # 2. 打開 ann 的 .env 裡那行註解
aos-daemon-ctl -d .stack stop ann && aos-daemon-ctl -d .stack start ann   # 3. ann 重起才讀到
```

之後 ann 的開 proc、停 proc、「我是誰」、讀表都先寄這一站（`AOS_KERNEL` 指 `<根的 stack>/procs/perm/requests`），站照 `perm/kernel.json` 判了再轉給根。11-20 在暫存樹照這三步跑過：ann 的環境多了 `AOS_KERNEL=…/.stack//procs/perm/requests`，再問一句照樣回 `FAKE ANSWER to: hello again …`。

- **出廠的 `perm/kernel.json` 是 `{}`**：什麼都不管、全部原樣轉給根（啥都不管也是一種管理）。要管什麼自己加鍵：`allowed`（名字白名單）、`max_running`（同時幾個在跑，數根的表，站自己、`llm`、鐘、清道夫都算）、`queue`、`hooks`…，鍵的意思在 [kernel 入口](../kernel/README.md#kerneljson-的鍵)。設定每輪重讀，改了不用重起。這是唯一跟原範本不一樣的檔（原範本的白名單只放 `peek_now_time`，照抄的話 ann 生不了任何子）。
- **那行寫在 ann 的 `.env`，不寫在 `root/.env`**：寫在根上，整塊板子都繼承到，llm kernel 也會把每一次問腦的 proc 經這一站掛到根上（它自己的表上看不到、問腦失敗）。11-20 實跑過寫在根上的樣子：ann 的問腦失敗，根的表上多一列 `llm_<信名> stopped`。要讓別隻 agent 也經這站，在牠的 `.env` 寫同一行。
- **一開就要知道（基底體檢 P4，使用者 11-19 選「維持現狀，只寫明」）**：開了之後，ann 的「我是誰」、讀自己信箱、設鬧鐘、`self_*` 都要先問這一站，**站 3 秒不回＝這些全部 `KernelFailed`**。11-20 實跑：把 `perm` 停掉，經站的 `aos-agent ctl ls` 等 3.8 秒後 `KernelFailed no reply from AOS_KERNEL=… within 3 s`。站是 `--auto-restart` 掛的，掉了會自己起；被人 `stop`、`sleep` 了要自己 `start`／`wake`。
- **權限件是給守規矩的人用的規矩，不是牆；牆是換 Linux 帳號**（使用者 11-20「明寫」）：`AOS_KERNEL` 是寄件人自己的環境變數，拿掉它、直接寫根的 ctl 信箱就繞過這一站；`aos-daemon-ctl` 也一律直寄根。同一個 Linux 帳號底下擋不住（[kernel 02「誰能繞過 kernel」](../kernel/docs/02-kernel-modes.md#誰能繞過-kernel靠-linux-權限)）。
- guard、sandbox 不算權限件（使用者 11-20「不算」），留在 agent 與工具那邊，這一站不帶它們的設定。

## 裡面有什麼

| 夾／檔 | 是什麼 | 從哪抄的 | 跟原範本不一樣的地方 |
|---|---|---|---|
| `env.sh` | 薄的：`AOS_HOME` 沒設報一行錯；有就 `source "$AOS_HOME/env.sh"`（清掉別棵樹的 `AOS_*`、把 `$AOS_HOME/bin` 放上 `PATH`）；最後可以加這棵樹自己的 `export` | — | — |
| `root/` | 根 daemon 的定義：最小核心（板子、時鐘、清道夫） | [daemon-root](../daemon-root/README.md) | `.env` 的 `AOS_LLM_KERNEL` 指 `${AOS_STACK}/procs/llm`（掛在根上的那一列） |
| `llm/` | llm kernel 的定義，`add` 之後是根上的一列 `llm` | [kernel/llm-kernel](../kernel/docs/01-llm-kernel.md) | 沒有 |
| `perm/` | 權限站（選裝，出廠沒掛） | [kernel/procs-kernel](../kernel/README.md) | `kernel.json` 是 `{}` |
| `agents/ann/` | 一隻 agent | [agent-fsm](../docs/02-agent-fsm.md) | `llm.json` 是 `{"model": "fake"}`（假腦，先試流程）；要真模型就換成 `llm/kernel.json` 的 `endpoints` 裡的名字。多一個 `.env`：只有一行註解掉的 `AOS_KERNEL`（開權限件用）。**不帶格程式**（11-21）：`fsm.json` 四格動態連結 `$AOS_HOME/templates/agent-fsm/` 的 `idle.py`…（跟 `agent.py` 的 `std.fsm()` 編出來的一字不差），`interfaces.json` 的 `hook_points` 寫 `{"provider": "agent-fsm"}`；所以沒有那八支 `.py` 與 `hook_points.json`，`README.md` 在原樣後面多一段說明怎麼改某一格（[ann 的 README](agents/ann/README.md#起手範本這一隻格程式動態連結11-21)） |

跑起來後樹裡多出 `.stack/`：根的 stack；llm kernel 的在 `.stack/procs/llm/`，agent 的在 `.stack/procs/ann/`，開了權限站的話站的在 `.stack/procs/perm/`。

不想掛在根上、要 llm kernel 自己一台（關板子時不跟著關、好幾塊板子共用一台 llm daemon）也可以：`aos-exec --stack <它的 stack> llm` 另起，`root/.env` 的 `AOS_LLM_KERNEL` 改指那個 stack（[kernel 01](../kernel/docs/01-llm-kernel.md)）。主線是掛在根上。

## 維護

`root/`、`llm/`、`perm/`、`agents/ann/` 是原範本的逐字抄本，只差上表那幾處（`agents/ann/` 另外不帶格程式，執行時從 `$AOS_HOME` 拿）；改了原範本要同步抄過來，[templates/tests/test_start.py](../tests/test_start.py) 會逐檔比對、不一樣就紅。`env.sh` 兩包是同一份。

repo 更新後，已經抄出去的樹哪些要重抄（`env.sh` 幾乎不用；各格的程式、接線檔可能要）見 [14-更新與重新複製](../../thinking/2026-11/17/cpp-py-改名/14-更新與重新複製.md)。
