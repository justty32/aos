怎麼掛 hook：aos-agent hook、self_hook、直接改 hookeds.json、編譯時 hooks=；只攔某支工具怎麼寫；loop 的點為什麼要重新編譯並重起。

← [入口](README.md)｜上一份 [03-寫handler](03-寫handler.md)｜下一份 [05-各家的點與規矩](05-各家的點與規矩.md)

## 四種掛法

| 掛法 | 寫到哪 | 影響誰 | 什麼時候生效 |
|---|---|---|---|
| `aos-agent hook add …`（人在 shell） | 那隻 agent 的 `<stack>/hookeds.json` | 只有那一隻 | 下一個事件（每次事件都重讀清單） |
| `self_hook`（agent 自己） | 同上（就是 `aos-agent hook --target 自己` 的包裝） | 只有自己 | 同上 |
| 直接改被勾清單 | 定義的 `hookeds.json`（kernel：`kernel_hookeds.json`），或 stack 那份 | 定義那份＝用這個定義的每一隻 | 同上；kernel 每一輪重讀 |
| 編譯時 `hooks=`（agent.py） | 編譯出的定義 `hookeds.json`（＋`interfaces.json` 的兩鍵、`loop.json` 的接線） | 用這個定義的每一隻 | 重新編譯之後；loop 的點還要重起 |

前提：定義的 `interfaces.json` 最外層要有 `hookeds`（範本與 agent-python 骨架都有）；沒有＝`aos-agent hook` 說 `HooksMissing`，gdb 也下不了斷點。

## aos-agent hook 與 self_hook

```sh
aos-agent hook -t bob                       # = ls：NAME TAB EVENT TAB HANDLER
aos-agent hook -t bob ls -l                 # 多 CONDITION TIMEOUT_MS FROM，也列被設成 null 的
aos-agent hook -t bob add --event before_tool --condition shell --timeout-ms 5000 ./guard
aos-agent hook -t bob add --event on_clock --every-ms 600000 -n check ./check
aos-agent hook -t bob add --event brain_failed -n ping --path-json '{"$env": "AOS_HOME", "$path": "/lib/x"}'
aos-agent hook -t bob rm guard              # 定義裡有的＝寫 null（關掉）；自己加的＝刪掉那格
aos-agent hook -t bob reset -y              # 刪 stack 那份，回到定義的
```

```json
{"op": "add", "event": "before_tool", "path": "hooks/guard", "condition": "shell"}
```

- `add` 的旗標：`--event`（必填；**不驗**，掛到不會發的事件＝掛得上、永遠不跑）、`-n/--name`（預設＝檔名或夾名；`--path-json` 時必給）、`--timeout-ms`、`--replace`、`--path-json`；agent 一家自己的 `--condition`（可重複）與 on_clock 的 `--every-cycles`／`--every-ms`、`--clock`、`--config`。
- `self_hook` 收同一組參數（JSON），相對路徑從 agent 的工作區算；`event` 在它的說明裡是列舉（給腦看的）。
- 完整用法、錯誤代號：[apps/agent/docs/06-hook「指令」](../../agent/docs/06-hook.md#指令)、知識庫 `aos/me/self_hook.md`、`aos/cli/hook.md`。

## 只攔某支工具（condition）

使用者 11-21「1.對。」：引擎不做篩選，agent 一家自己保留這個寫法，寫在被勾清單那格裡；不然每叫一次工具，所有掛在工具上的 handler 都會被起來一次。

```json
"guard": {"event": "before_tool", "handler": "guard", "condition": ["ws_write", "shell"]}
```

- 字串或字串陣列；事件的那個欄位**完全相等**才跑。比哪個欄：`before_tool`／`after_tool`／`tool_added` 比 `name`（工具名），`brain_failed` 比 `name`（錯誤代號）。
- 寫在不比的點（before_queue、after_queue、on_clock、loop 四點…）＝照收、不比、不報錯。
- kernel 也有一個：`after_verdict` 的 `condition` 比 `verdict`。
- loop 的點沒有 condition：例如「只在 think 之前」要 handler 自己讀 `<stack>/stage.txt` 判斷。

## 直接改被勾清單

```json
{"description": "What is hooked on this agent.",
 "guard": {"event": "before_tool", "handler": "guard", "condition": "shell", "timeout_ms": 10000},
 "timer": null}
```

- 形狀：`{hook 名: 格 或 null}`；格裡引擎只看 `event`、`handler`、`timeout_ms`，其他鍵原樣留給發事件那一家（agent 的 `condition`、on_clock 的 `every_cycles`／`every_ms`／`clock`／`config`）。以前的 `intercept`、`async`、`on_error` 拿掉了，寫了也不讀。
- 格壞了（沒 `event`、`handler`，名字不合）＝整份讀不了（`HooksBad`），發事件的那一家照它的規矩處理（agent 停下、kernel 這輪 `CfgBad`、`aos-hook` 退 1）。
- 定義是原始碼：agent 不要手改自己的定義（知識庫 `aos/rules.md`），改自己用 `self_hook`。

## 編譯時 hooks=（agent.py）

```python
from aos.py.agent import defs            # 骨架 agent.py 上面那幾行已經有
from aos.py import fn
std = defs.std

@fn.hook("before_tool", condition="shell", timeout_ms=5000)
def no_shell(event):
    return fn.block("shell is off")          # 退 10；回 None＝放行，回 dict＝要改的鍵

agent = defs.Agent("...", system="...", tools=[std.pack("ws-write")], llm={}, fsm=std.fsm(),
                   hooks=[std.hooks(), {"timer": None}, no_shell])
```

- `hooks=` 收：一張表 `{名: 格}`、`std.hooks()`（範本的 hookeds，靜態連結進來）、`defs.load(...)` 的 `hooks`、`@fn.hook` 標的函數、它們的串列（後面同名蓋前面、`None` 拿掉），或 `defs.extern("../shared/hookeds.json")`（整份動態連結）。
- 編譯寫出 `hookeds.json`，`interfaces.json` 最外層補 `"hookeds": "hookeds.json"` 與 `"hooks"`（aos-loop 與 agent-fsm 的宣告），`loop.json` 補 `on_start`／`on_stop` 兩行。`interfaces=` 能蓋 `hooks`、不能蓋 `hookeds`（`SpecBad`）。
- 事件名不驗；`fn.block` 用在不能攔的點也不擋（到時 agent 一家把 10 當放行）。
- 細節：[templates/agent-python/README](../../../../../templates/agent-python/README.md)（`hooks`、「Functions as tools and hooks」）。

## loop 的點：before_run／after_run 要重新編譯並重起

使用者 11-21 選「編譯時決定」：

- `after_start`／`after_stop`：範本與編譯出的 `loop.json` 一律接（`on_start`／`on_stop` → `aos-hook fire -q --stop-on-nonzero --def $AOS_CD …`），掛了就有。
- `before_run`／`after_run`：編譯時**有 hook 掛這兩點**才把 `on_before_run`／`on_after_run` 寫進 `loop.json`；沒人掛就不寫，閒著不多起行程（接了＝每跑一次身體多起一支 `aos-hook`，約 36 毫秒）。手寫範本預設不接。
- 事後才掛（`aos-agent hook add`、`self_hook`、gdb 下斷點）：照樣寫進清單，但 `loop.json` 沒接那條線就多一行 warning——要**重新編譯**定義（或照 `on_start` 的樣子手加那一鍵），再**重起**那隻（aos-loop 只在起來時讀 `loop.json`）。
- `hooks=` 是 `defs.extern(...)` 時，編譯不打開連結看內容，`loop.json` 只接起停兩點。
- kernel 的 loop 身體（`procs-kernel`、`kernel-python`）同一套：`aos.py.kernel.defs` 編譯時有人掛才接。aos-daemon 的 `daemon.json` 不收 `on_before_run`／`on_after_run`（寫了＝`CfgBad`）。

## kernel 怎麼掛

kernel 沒有 `aos-agent hook`：直接編那個 kernel 定義夾的 `kernel_hookeds.json`（`interfaces.json` 的 `hookeds` 指的那份），每一輪重讀。kernel 只讀定義夾那份、不疊 stack 抄本；`aos-hook fire --def` 給 loop 點時會疊 stack 裡同名那份（不在＝沒有）。例子：[kernel README「hooks」](../../../../tools/aos/kernel/README.md#hooks)。
