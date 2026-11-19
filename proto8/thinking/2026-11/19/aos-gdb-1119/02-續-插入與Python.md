# aos 現況（續）：跑到一半插入新東西今天做得到哪些（實測），以及從 Python 能不能直接驅動一棵樹

← [README](README.md)｜上一份：[02-aos現況](02-aos現況.md)｜下一份：[03-別人怎麼做](03-別人怎麼做.md)

## 先講結論

1. **「邊跑邊長」在 aos 今天大半做得到，而且多數不用停**：加工具、換 system、加 hook 都寫在這隻自己的 stack 疊層，**下一次問腦／下一個事件就生效**；改 `fsm.json`（加一格、改箭頭）**下一格就生效**——實測都沒重起。
2. **兩個例外**：`loop.json` 只在 loop 起跑時讀一次（改了要重起）；`ctl set-def`（整份換定義）會「這輪做完停下、換定義、再起」，pid 會換。
3. **最大的不對稱**：工具、system、hook、llm 有「這隻自己的疊層」；**`fsm.json` 沒有**——要在指令中間插一格，只能改定義夾本身，等於同一份定義的所有 agent 一起被改。
4. **從 Python 驅動**：`aos` 套件 import 得到（把 `proto8/lib` 放進 `sys.path`），但**沒有給人用的 Python API**；起 agent、送話、加 hook 的函式都是「吃一串命令列參數、印到螢幕」的形狀。今天在 Python REPL 裡最穩的寫法是 `subprocess.run(["aos-agent", …])` 加直接讀 stack 的 JSON 檔。

## 一、跑到一半插入新東西（實測，10.log、11.log）

對一隻正在跑的 ann（agent-fsm 範本、假腦），不停它，依序：

| 插什麼 | 怎麼插 | 要不要停 | 何時生效 | 實測 | 寫到哪 |
|---|---|---|---|---|---|
| 加一個工具 | `aos-agent tools add -t ann -n math2 <工具夾>` | 不用 | 下一次問腦（下一份 `think/request.json` 就有 `math2`） | 有 | stack 的 `tools.json`（只記這隻加減的；定義後來的改動照樣透出） |
| 換 system | `aos-agent system set -t ann -` | 不用 | 指令自己印「takes effect from its next brain call」；下一份請求就有新字 | 有 | stack 的 `system.txt`（整份取代定義的） |
| 加斷點／hook | `aos-agent hook add …` | 不用 | 下一個事件 | 有（[02](02-aos現況.md) 第三節） | stack 的 `hooks.json` |
| 在 fsm 中間插一格 | 改定義夾的 `fsm.json`：act 結束碼 10 改走新格 `note`，`note` 跑完回 idle | 不用 | **下一格**——`aos-fsm` 每一格都重讀 `fsm.json`（loop 每拍重跑 `aos-exec fsm.json`） | 有：答完後 `note.log` 多一行，`stage.txt` 回 idle | **定義夾**（沒有疊層） |
| 改 loop 的節拍 | 改定義夾的 `loop.json`：`interval_ms` 300→1500 | — | **不生效**，要重起 loop | `state.json` 的 `interval_ms` 照舊 300 | 定義夾 |
| 換整份定義 | `aos-agent ctl set-def NAME DEF`（可帶 `--kit`） | 它自己會停 | 這輪做完停、拔下、用新定義再掛上；stack、ws、表上設定保留 | 讀 `--help`，未實測 | daemon 表 |
| agent 自己長 | `self_tools`、`self_system`、`self_hook`、`self_llm` | 不用 | 同上面對應的那一列 | 讀知識庫，未另測 | 同上（就是那幾份疊層） |
| 改定義的工具表 | `agent_def tools …` | 不用 | 下一次問腦（定義透過疊層透出） | 讀 `_tooldef.json`，未實測 | 定義夾：用這份定義的**所有** agent 都變 |

試完把暫存樹的 `fsm.json`、`loop.json` 抄回原樣（備份在 `fsm.json.orig`、`loop.json.orig`）。

### 這張表對「邊跑邊長」的意思

- 使用者 11-07 說的走法「agent 作爲萬能函數，拆出來的子功能先弄成 agent 呼叫，後續再慢慢優化成函數」（[00](00-使用者原話.md) 第三段）在 aos 已經有兩條現成的路：**給它加工具**（不停、下一輪生效）、**在 fsm 裡加一格寫死的程式格**（不停、下一格生效，C-22「能寫死的節點換成程式」）。
- 前者有「這隻自己的」疊層、能 `reset` 回去；後者沒有，改的是共用的定義。
- **插進去的東西沒有任何「這是什麼時候、誰插的」紀錄**。疊層檔只有現在的樣子；`fsm.json` 被改了也沒痕跡（除非定義夾在 git 裡）。這正是 [03](03-別人怎麼做.md) 裡 Pharo 的 `.changes` 檔、LangGraph 的 checkpoint 分支在解的問題。

## 二、從 Python 能不能直接驅動一棵樹

使用者的想像是「進入 python repl，用 aos-gdb 庫，下斷點，然後跑」。今天的底子：

**能 import 的**：`proto8/bin/` 的 19 支 Python 指令都是小殼——把 `proto8/lib` 插進 `sys.path`，再 `runpy.run_module("aos.apps.<名>.main")`（`bin/aos-agent` 前 6 行）。所以 REPL 裡 `sys.path.insert(0, "~/repo/aos/proto8/lib")` 之後 `import aos` 就行。注意 `lib/` 是 `install.py` 從 `py/` 抄出去的（`py/README.md` 第 5 行）。

| 想做的事 | 有可 import 的函式嗎 | 現況 |
|---|---|---|
| 起樹、起 daemon | 沒有 | 只有 `aos-exec root`（C++）；要 `subprocess` |
| 掛一隻 agent | 有，但是命令列形狀 | `aos.apps.agent.ctl.add.cmd(argv)` 吃參數串、印結果 |
| 送話、等回答 | 有，命令列形狀 | `aos.apps.agent.say.cmd(argv)`（印信名）、`listen.cmd(argv)`；內部有 `listen.wait_latest(a, timeout, …)` 但要先湊出 `a`（目標物件） |
| 停、續、關 | 有，較底層 | `aos.daemon_ctl.ctl.write_ctl(d, name, cmd)`、`shutdown(d)` |
| 讀狀態 | 有，內部函式 | `aos.apps.agent.ctl.state` 的 `part_who`、`part_state`… 各吃一個 `a`；`cmd(argv)` 印十一類 |
| 讀 stack | 不需要函式 | 都是 JSON／JSONL 檔，`json.load` 就好 |
| 掛 hook | 有，兩層 | 命令列：`aos.apps.agent.hook.cmd(argv)`；引擎：`aos.agentlib.hooks.load(def_folder, stack)`、`fire(event, data, …)`（`py/aos/agentlib/hooks.py` 第 130、158 行） |
| 起一個 hook 的事件、看它怎麼回 | 有 | `aos.hook_run.fire(...)`；hook 的事件 JSON 從 stdin 進、回話從 stdout 出 |

白話：**零件是 Python 寫的，但包裝成「給 shell 用的指令」，不是「給 REPL 用的函式」**。這些函式沒有承諾過不改簽名，直接 import 等於綁在內部實作上。

**hook 這一塊跟「REPL 裡下斷點」的距離**：hook 是 agent 那邊叫起來的**另一支行程**（`subprocess.Popen`，`hook_run.py` 第 145 行），事件從 stdin 給、等它結束才繼續。所以「REPL 裡的斷點」要成立，得有一條路讓那支 hook 行程**把事件交給 REPL、等 REPL 說放行**——今天沒有這條路；本線實測是用「寫檔＋等放行檔」土法做出來的（`~/.aos/scratch/aos-gdb-1119/hooks/bp.sh`，十來行 bash）。

## 三、遠景「搞不好最終我會用 lisp 整個給他整合好」會不會被今天的樣子擋到

只看會不會擋，不為它設計：

- **不擋的**：所有東西都是檔與命令列，任何語言都能驅動；hook 是「任何可執行檔」，Lisp 寫的也行；C-43（10-19「一套 library，用 lua／lisp 一類語言把整套資料夾布局生成出來」）本來就是這條路。
- **可能擋的**：如果 aos-gdb 做成「只有 Python 能用的物件」（例如斷點是 Python 函式、狀態是 Python 類別），換成 Lisp 就要重做。反過來，如果 aos-gdb 的核心是「一組檔案與指令的約定」（斷點寫成檔、放行寫成檔），Python 庫只是一層薄殼，Lisp 再包一層就好。這是 [05](05-發想.md) 該攤的一個取捨。
