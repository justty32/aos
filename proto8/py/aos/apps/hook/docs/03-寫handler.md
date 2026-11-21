寫一個 handler：收到什麼、怎麼回、退出碼在引擎層與各家規矩裡各代表什麼、工作夾與逾時。

← [入口](README.md)｜上一份 [02-宣告格式](02-宣告格式.md)｜下一份 [04-掛hook](04-掛hook.md)

## handler 是什麼

aos-exec 跑得動的都算：

- 可執行檔（`chmod +x`；腳本開頭 `#!/bin/sh`、`#!/usr/bin/env python3`，任何語言都行）；
- 一份 JSON `{"argv": ["python3", "x.py"]}`，`x.py` 放旁邊（不用 chmod）；
- 一個工具夾（有 `_entry`）。

被勾清單那格的 `handler` 寫路徑字串或指示詞；相對路徑從**那份清單所在的資料夾**算（`aos-agent hook add` 寫進 stack 那份時會換算好）。不能執行的普通檔＝起不來（`EntryBad`）。Python 寫的也可以是 agent.py 裡的 `@fn.hook` 函數，編譯時抽成 `fn/<名>.py`（見 [04](04-掛hook.md)）。

## 收到什麼

| 管道 | 內容 |
|---|---|
| stdin | 一行 JSON 物件：發事件那一方給的資料，加上 `event`（事件名）、`hook`（這格的名字）、`stack`（發事件那個程式的 stack 絕對路徑）；同一份也存成 `STACK/hookeds/<名>/event.json` |
| `$AOS_STACK` | **這個 hook 自己的工作夾** `STACK/hookeds/<名>/`（不是 agent 的 stack；agent 的 stack 在事件的 `stack` 欄）。寫在這裡的檔下次還在 |
| 目前資料夾 | handler 程式所在的資料夾（aos-exec 的規矩） |
| 其他環境變數 | 繼承發事件的程式（agent 的 `AOS_WS`、`AOS_DAEMON`、`AOS_CLOCK`…；aos-loop 四點另有 `AOS_LOOP_*`，見 [05](05-各家的點與規矩.md)） |
| stderr | 原樣透出，跟發事件的程式同一處（daemon 底下＝那個 stack 的 `stderr.txt`） |

每個事件帶哪些欄位：agent 看 [apps/agent/docs/06-hook「事件」](../../agent/docs/06-hook.md#事件)，kernel 看 [kernel README「hooks」](../../../../tools/aos/kernel/README.md#hooks)，aos-loop 看 [loop_hooks.json](../loop_hooks.json)。

## 怎麼回：分兩層講

**引擎層**（`aos.hook_run`、`aos-hook fire`，大家共用）只記下兩樣東西交回去：**退出碼**與 **stdout**。它不懂攔、不懂改、不懂失敗；10 對它沒有特別意思，只有 `aos-hook fire --stop-on-nonzero` 遇到 10 不印錯誤行（10＝「不」，N-43 的慣例）。逾時或起不來＝`code` 是 `null`、`error` 寫原因。

**各家的規矩**（發事件的程式自己讀結果）：

| 退出碼／stdout | agent 一家（agent-fsm、aos-eca-turn、aos-mcp） | aos-loop 四點（經 `--stop-on-nonzero`） | eca 的 before_compact | kernel 三點 |
|---|---|---|---|---|
| 0、stdout 空 | 放行、不改 | 照常 | 不改 | 不改 |
| 0、stdout 是 JSON 物件 | 能改的點拿認得的鍵改（before_queue `content`、before_tool `arguments`、after_tool `content`）；別的點不讀 stdout | stdout 不讀 | 設 `instructions`／`restore`（依名字順序，後蓋前） | 拿認得的鍵改（`body`；after_verdict 的 `verdict`、`error`、`next`） |
| 10 | before_queue＝丟掉這封信、before_tool＝工具不跑（腦看到 stdout）；別的點＝當 0 | before_run＝跳過這一圈；其他三點＝失敗 | 攔下不壓 | 攔下（拒信；before_reply 改代回一封 HookRejected） |
| 其他碼、逾時、起不來、stdout 不合 | 能攔的點（before_queue、before_tool）＝這個事件停（HookFailed，agent 停下；aos-mcp 只是那次工具回 isError）；其他點＝一行 warning、下一個照跑 | loop 收工（after_start 失敗＝起不來；after_stop 失敗＝本來要退 0 就改退它的碼，否則只一行 warning） | 一行 warning、照沒有這個 hook | 這一輪停（HookFailed），下一輪重來 |
| 多個 hook | 照名字跑，前一個改的後一個看得到；被攔就不往下 | 照名字跑，每個拿同一份；第一個非 0 就停 | 照名字跑，每個拿同一份 | 照名字跑，前一個改的後一個看得到 |

所以：掛在 agent 能改的點上、只想記一筆的 handler，**stdout 不要印東西**（印了不是 JSON 物件的東西＝失敗）。掛在 loop 四點的 handler 一定要退 0，除非你就是要讓 loop 停（before_run 退 10 是跳過這圈）。

## 工作夾

- `STACK/hookeds/<名>/`：引擎每次寫 `event.json`；handler 自己的狀態也放這裡（例 on_clock 的 `on_clock.json`、gdb 觸發器的 `trigger.json`、mail_notify 的 `notified.json`、kernel_gate 的站）。
- 名字就是夾名：不能空、不能有 `/`、不能 `.` 開頭、不能叫 `description`。
- 這個夾是執行期狀態，stack 的 `.gitignore` 不帶走它（[apps/agent/docs/05](../../agent/docs/05-gitignore指南.md)）。

## 逾時

- 那格的 `timeout_ms`：預設 60000，0＝不限。到了整個行程群組先 TERM、2 秒後 KILL，算這個 handler 失敗（各家怎麼看失敗見上表）。
- handler 自己一個行程群組；等它的時候發事件的程式被 Ctrl-C／TERM，handler 的群組也一起收掉。
- 外層還有限：aos-loop 給 `on_start`／`on_stop` 的 `on_timeout_ms`（預設 5000），所以 after_start／after_stop 的 handler `timeout_ms` 要更短；eca-claude 的 `compact_hook` 在 Claude Code 那邊的 `timeout` 是 60 秒。

## 小例子

只記一筆（任何點都安全）：

```sh
#!/bin/sh
# log_letters - after_queue hook: append each event to a log
cat >> "$AOS_WS/letters.jsonl"
```

攔（agent 的 before_tool，Python）：

```python
#!/usr/bin/env python3
import json, sys
ev = json.load(sys.stdin)
args = ev["arguments"] if isinstance(ev["arguments"], dict) else {}
if str(args.get("path", "")).startswith("/etc/"):
    print("no writing under /etc (hook %s)" % ev["hook"])   # 腦看到這句當工具結果
    sys.exit(10)
sys.exit(0)                                                  # stdout 空＝不改
```

改（agent 的 after_tool：結果太長就截斷）：

```python
#!/usr/bin/env python3
import json, sys
ev = json.load(sys.stdin)
if len(ev["content"]) > 4000:
    print(json.dumps({"content": ev["content"][:4000] + "\n[cut by hook %s]" % ev["hook"]}))
```

更多例子：[06-hook「最小 hook 範例」](../../agent/docs/06-hook.md#最小-hook-範例)、知識庫 `aos/me/self_hook.md#/Hook examples`、`#/daily`。
