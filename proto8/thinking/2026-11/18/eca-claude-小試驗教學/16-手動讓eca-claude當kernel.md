這份教你不用 `kernel_gate` 這類一鍵工具，手動把一隻 eca-claude agent 變成這棵樹的 kernel（別人掛、停 proc 的請求先送到它、由 claude 決定放不放），再退回普通 agent（試驗 16，11-18 在公司 WSL 用 haiku 實跑過）。
← [目錄](README.md)

使用者原話：「還有：eca claude，我們手動讓他成為kernel」

## 結論

- **kernel 在 aos 裡＝「請求寄到哪，那裡就是 kernel」**。掛、停、叫醒 proc 的請求寄到 `$AOS_KERNEL`；沒設就直接寄 daemon（daemon 來者不拒，是最簡單的 kernel）。問模型的 `AOS_LLM_KERNEL` 是另一回事（幫大家轉接模型的總機），這題講的是前者。
- 範本 kernel（`templates/kernel/daemon-kernel`、`procs-kernel`）**不是 fsm＋llm**，是一支純程式「框架站」（`$AOS_HOME/lib/tools/aos/kernel`）：每跑一輪就照 `kernel.json` 收信、判、轉寄，沒有腦。
- 讓 claude 當 kernel 的做法：**把同一支框架站掛在 ann 身上當 `on_clock` hook**，再加一支 `after_verdict` hook 把每封請求「先留著」並通知 ann；claude 用 Write 工具寫一個 `decisions/<信名>.json`（pass 或 refuse），站下一輪照辦。要準備的只有一個夾、三個檔，一行 `hook add`。
- 別人怎麼指向它：寄件人的殼 `export AOS_KERNEL=…/hooks/gate/requests`；要整棵樹的 agent 都走它，寫進 `root/.env`、重起根。kernel.json 沒寫 `max_running`，所以 `count_daemon` 不用填。
- **實測通了**：放行（`worker1` 掛上）、拒絕（寄件人看到 `AddRejected … NotNow <claude 寫的原因>`）、stop／start 也先問它、另一隻 eca（bob）在自己那一輪裡下 `ctl add` 一樣先到 ann。每封約 7～11 秒。
- **代價**：ann 停著或正在想別的事時，站不跑，請求沒人理，寄件人等到逾時；`ctl ls` 只等 3 秒，常常 `KernelFailed`。ann 自己在一輪裡下 `ctl` 會等自己，一定逾時。

## 先弄清楚：三種「kernel」

| 叫法 | 是什麼 | 誰設、設成什麼 |
|---|---|---|
| daemon 本身 | 沒設 `AOS_KERNEL` 時請求直接進 daemon 的 ctl 信箱，照單全收 | 不用設 |
| 框架站（範本 `daemon-kernel`／`procs-kernel`） | 一支程式，一輪一輪跑：白名單 `allowed`、上限 `max_running`、排隊 `queue`，放行的轉寄 daemon | 寄件人 `AOS_KERNEL=<站的 stack>/requests` |
| llm kernel（範本 `llm-kernel`） | 問模型的總機，只收「問腦」的信 | `AOS_LLM_KERNEL`；eca-claude 自己叫 claude，用不到它 |

判斷法：請求是「掛／停 proc」→ `AOS_KERNEL`；是「幫我問模型」→ `AOS_LLM_KERNEL`。範本 `daemon-kernel` 有 `max_running`、沒 `count_daemon`，原樣只能當最後一站（使用者 11-18 裁過不補）；這份的 `kernel.json` 不設上限，碰不到。

## 一步一步

前提：樹照 [README 的「共同準備」](README.md#共同準備)抄好、改成 haiku。起根改用 `cd ~/aos-home && source env.sh && aos-exec root`（視窗 A），ann 掛上去（視窗 C 那行）。下面都在 `~/aos-home` 打。

**1. 建站的夾和設定**

```sh
mkdir -p ~/aos-home/gate && echo '{"hooks": {"hold": {"event": "after_verdict", "condition": "pass", "handler": "hold"}}}' > ~/aos-home/gate/kernel.json
```

意思：規則先判（這裡沒規則＝全部放行），放行的再交給 `hold` 這支 hook。

**2. 寫 `gate/run`（叫框架站跑一輪）**

```sh
#!/bin/sh
# run one round of the stock kernel station; its stack is this hook's cell ($AOS_STACK)
exec aos-exec --stack "$AOS_STACK" "$AOS_HOME/lib/tools/aos/kernel" "$(dirname "$0")/kernel.json"
```

**3. 寫 `gate/hold`（留住請求、通知 ann）**

```python
#!/usr/bin/env python3
# after_verdict hook: hold every request the rules let through (except table questions) and tell the agent once
import json, os, subprocess, sys
event = json.load(sys.stdin)
body = event.get("body") if isinstance(event.get("body"), dict) else {}
if event.get("decision") == "pass":
    sys.exit(0)                      # somebody already decided: let the rules' verdict stand
if body.get("procs_state_path") is True and [k for k in body if k.startswith("procs_")] == ["procs_state_path"]:
    sys.exit(0)                      # table question: pass without asking
cell = event["stack"]                # the station's stack = <agent stack>/hooks/gate
agent = os.path.dirname(os.path.dirname(cell))
text = ("[aos] gate: a request waits at your kernel station.\n"
        "letter: %s\nfrom: %s\nrequest: %s\n"
        "To let it through write {\"verdict\": \"pass\"} to %s/decisions/%s.json ; "
        "to refuse write {\"verdict\": \"refuse\", \"error\": {\"code\": \"NotNow\", \"msg\": \"<one line for the sender>\"}} there."
        % (event.get("letter"), event.get("sender"), json.dumps(body, ensure_ascii=False), cell, event.get("letter")))
subprocess.run(["aos-post", "send", os.path.join(agent, "queue")],
               input=json.dumps({"role": "user", "content": text}), text=True, stdout=subprocess.DEVNULL, check=False)
print(json.dumps({"verdict": "hold"}))
```

```sh
chmod +x ~/aos-home/gate/run ~/aos-home/gate/hold
```

`ctl ls` 這類「表在哪」的問題直接放行，不然每次看表都要等 claude。

**4. 掛到 ann 身上**

```sh
aos-agent -d .stack -t ann hook add --event on_clock --every-cycles 1 --on-error continue --name gate gate/run
```

```
added gate (…/.stack/procs/ann/hooks.json#/hooks/gate: {"event": "on_clock", "handler": "../../../gate/run", "every_cycles": 1, "on_error": "continue"})
```

幾秒後多出 `.stack/procs/ann/hooks/gate/requests/`，這就是 kernel 的收件信箱。定義夾 `agents/ann` 一個檔都沒動。

**5. 跟 claude 講規則**

```sh
aos-agent -d .stack -t ann ask --timeout-s 180 "You are now the kernel gate of this tree. Messages that start with [aos] gate: are requests from other procs, held for you. Rule: let through a request only if every proc it adds or starts has a name starting with worker; refuse anything else with a one-line reason. Requests that only stop procs: let through. Decide by writing the JSON file the message names (use your Write tool). Reply now with one short sentence that you understood."
```

會看到 `Understood: I'll review each [aos] gate: request …`（約 12 秒）。

**6. 寄件人指向它，試放行與拒絕**（另開一個殼）

```sh
export AOS_KERNEL=~/aos-home/.stack/procs/ann/hooks/gate/requests
```

```sh
aos-agent -d .stack ctl add -n worker1 -w ws-w --timeout-s 150 $AOS_HOME/templates/agent-fsm
```

十來秒後印 `…/.stack/procs/worker1`，表上多一列 `worker1 running`。

```sh
aos-agent -d .stack ctl add -n evil2 -w ws-w --timeout-s 150 $AOS_HOME/templates/agent-fsm
```

```
aos-agent: warning: routing via AOS_KERNEL=…/hooks/gate/requests
aos-agent: error: AddRejected the add letter was refused: NotNow Refused: the request adds proc 'evil2', which is not named with a worker prefix.
```

退出碼 1，約 7 秒。ann 那邊收到的是一則 `[aos] gate: a request waits at your kernel station.` 加信名、寄件人、請求原文；它叫的是 `Write {"file_path": "…/hooks/gate/decisions/<信名>.json", "content": "{\"verdict\": \"refuse\", …}"}`。決定檔站用完就刪。

**7. 其他請求**

- `ctl stop worker1`、`ctl start worker1`：也各通知 ann 一次、它放行，各約 7～8 秒。
- `say`：**不經 kernel**，直接進對方的 queue，0.2 秒。
- `aos-agent ctl ls`（不帶 `-d`）：表的問題直接過，0.9 秒；帶 `-d .stack` 的 `ls` 是指名 daemon，根本不問 kernel。
- 不設 `--timeout-s` 時 `ctl` 只等 30 秒；claude 每封 7～11 秒，平常來得及，忙的時候不一定。

**8. 讓整棵樹都走它（root 的 `.env`）**

先 `aos-daemon-ctl -d .stack shutdown`，在 `root/.env` 最後加一行：

```sh
AOS_KERNEL=${AOS_STACK}/procs/ann/hooks/gate/requests
```

再起根（視窗 A 的 `aos-exec root`），睡下的都自己醒。另掛一隻 eca `bob`（抄 `agents/ann`），叫它在自己那一輪用 Bash 打 `aos-agent ctl add -n badkid …` 和 `-n worker3 …`，它貼回來的是：

```
aos-agent: warning: routing via AOS_KERNEL=…/.stack/procs/ann/hooks/gate/requests
aos-agent: error: AddRejected the add letter was refused: NotNow Refused: the request adds proc 'badkid', …
aos-agent: warning: worker3 attached; the daemon chose its stack, …
```

agent 也照樣先過 ann。你自己的殼 `source env.sh` 不讀 `root/.env`，所以人打的指令照舊直達 daemon，除非你自己 export。ann 自己也繼承到指向自己的 `AOS_KERNEL`，站會認出是自己、跳過，放行的照樣轉給 daemon。

## kernel 停著、在忙、壞掉時（實測）

| 情況 | 寄件人看到 |
|---|---|
| ann 被 `aos-daemon-ctl -d .stack stop ann` 停掉 | `ctl add --timeout-s 10`：10 秒後 `DaemonFailed no result … letter withdrawn, it will not be applied`。`ctl ls`：3 秒後 `KernelFailed no reply from AOS_KERNEL=…` |
| ann 正在答別的（寫一篇 400 字故事） | `ctl ls`：3.5 秒 `KernelFailed`。`ctl add`：等 ann 答完才輪到，23 秒才掛上 |
| ann 自己在一輪裡下 `aos-agent ctl ls`／`ctl add`（root `.env` 指向自己時） | 等的是自己：`KernelFailed`，與 20 秒後 `DaemonFailed`。**當 kernel 的那隻自己不能用 `ctl`** |
| `gate/kernel.json` 寫壞 | ann 照常活著，只是 `stderr.txt` 每秒一行 `kernel: error: CfgBad aos-directive exited 1`；請求沒人判，寄件人逾時。改回來下一輪就好 |

ann 停著時要叫它回來：`aos-daemon-ctl -d .stack start ann`（這支永遠直寄 daemon，不經 kernel）。同一個 Linux 帳號下誰都能這樣繞過 kernel，要真擋得靠帳號權限。

## 退回普通 agent

```sh
aos-agent -d .stack -t ann hook rm gate
```

```
removed gate (…/.stack/procs/ann/hooks.json#/hooks/gate: deleted)
```

之後還寄到那個信箱的請求沒人理，10 秒後 `DaemonFailed`。所以還要把寄件人那邊拿掉：殼裡 `unset AOS_KERNEL`；寫進 `root/.env` 的把那行刪掉、重起根。實測刪掉、重起後，bob 再下 `ctl add -n worker6` 就沒有 `routing via`，直接印 stack。`gate/` 夾和 ann 的對話留著也無妨，要乾淨就跟 claude 說一聲它不再當門。

## 做不到的部分／要補什麼

- **沒辦法「快」**：claude 每封要 7～11 秒，而且一輪只判一件事；它在想別的、睡著、停著時整棵樹掛不了 proc。框架站本來是要快、要確定的（範本當 daemon 身體時每 300 ms 一輪）。適合當「少量、要人味判斷」的門，不適合當主要 kernel。（實測）
- **ann 自己不能下 `ctl`**：要它也能掛 proc，ann 自己的環境得 `AOS_KERNEL` 指向別處或不設。這份沒試怎麼只給 ann 拿掉（例如給 ann 的定義放 `.env`），是推測的做法。
- **claude 的判斷不保證照規則**：這次 haiku 全對（9 封），但它是讀字串做判斷；寄件人在請求裡多寫的字會原樣進它的對話（提示注入風險自己承擔，使用者 11-13 說過）。硬規則應寫成 `kernel.json` 的 `allowed`，讓站先擋，只把邊緣的留給 claude。（推測）
- 一鍵版 `kernel_gate` 工具做的是同一件事（11-13 實跑過）；這份是拆開手做。
- 沒試：拒絕 `stop` 時寄件人看到什麼（推測 `CtlRejected` 加原因）；加 `max_running` 後（照文件，下一站是 `$AOS_DAEMON` 時自動數那台，`count_daemon` 不用填）。

## 發現的問題

1. 經 kernel 逾時的錯誤行一律寫 `inspect adjacent …/hooks/gate/queue.json`，但「先留著」的站用的是 `hold.json`，`queue.json` 根本不存在，會指錯地方。
2. `kernel.json` 不是合法 JSON 時，錯誤只寫 `CfgBad aos-directive exited 1`，看不出是哪個檔、哪裡壞；而且 ann 的 `stderr.txt` 每個時鐘週期重印一次（15 秒 16 行），不像 daemon 身體失敗那樣只在變化時印。
3. 帶 `-d .stack` 的 `ctl add` 仍走 `AOS_KERNEL`，同樣帶 `-d` 的 `ctl ls` 卻不問 kernel；同一個旗標兩種意思，容易以為自己繞過或沒繞過 kernel。
4. 經 kernel 掛上時有時印 stack 路徑、有時只印 `worker3 attached; the daemon chose its stack`（後者是不帶 `-d` 的時候），寄件人拿不到 stack 位置。
