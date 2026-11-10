aos-agent 照 C-85 掃一遍：現況白話、裝不下的九樣、怪點逐點附實跑輸出。

← [入口](README.md)｜下一份 [02-aos-daemon-ctl](02-aos-daemon-ctl.md)

# aos-agent（lv5）

實跑：WSL `/tmp/cli-sweep/proj/`（`defs/`＝daemon-root、`defs/ann`＝agent-fsm 配假腦、`defs/eca`＝eca-claude 配假 claude；根 `stacks/root`、`stacks/root2`），工作樹 `ad8541e92`。程式在 `proto8/cmd/aos-agent/aos_agent/`。

## 現況的一段白話

> aos-agent 是跟「掛在 daemon 上的一隻 agent」打交道的遙控器。`say` 丟一句話給它、`listen` 等它回答、`chat` 連著聊；`ctl add 資料夾` 把一隻掛上去、`ctl rm 名字` 拿掉、`ctl ls` 看全部、`ctl stop／start` 停與起。另外能開它的畫面（`open／close／watch`）、改它自己的工具（`tools`）與腦設定（`llm`）。

## 這段話裝不下的（九樣）

1. **先得指出哪台 daemon**：`-d` 只能寫在最前面；不寫就看 `$AOS_DAEMON`、再不然 `./.stack`——日常用法的根是 `stacks/root`，預設永遠不中，等於每行都要打 `-d stacks/root`。
2. **指哪一隻有三種寫法**：`-t 名字`（位置還看子命令）、`$AOS_AGENT`、`ctl rm` 只收位置參數。
3. **停有三種、起有三種，要配對**：stop↔start、sleep↔wake、pause↔resume，配錯報 `PhaseBad`。
4. **`ctl rm` 會刪 stack**（`aos-daemon-ctl rm` 不刪）。
5. **看回答有五條路**：`listen`、`listen --follow`、`chat`、`watch`、`open`；後兩條只有 eca 有。
6. **`ctl ls` 沒表頭**；`-l` 九欄裡有 `QUEUED` 與 `QUEUE` 兩欄。
7. **`tools` 的寫法跟 `aos-tools` 不一樣**，而且每次都先印一行 warning 說用哪份檔。
8. **設了 `$AOS_KERNEL` 就改走判官**（`--on-queued`、排隊）。
9. **正常訊息也印成 `warning:`**。

## 怪點逐點

### 一、真問題

**A1　`-t` 的位置看子命令：`ctl` 要寫在動作後，`tools`／`llm` 要寫在動作前；頂層 help 卻說前後都行。**（lv5）

```
$ aos-agent -d stacks/root ctl -t ann state
aos-agent: error: FlagUnknown unknown flag -t (see aos-agent ctl --help)
$ aos-agent -d stacks/root ctl state -t ann            ← 可以
$ aos-agent -d stacks/root llm set -t ann endpoint=fake
aos-agent: error: FlagUnknown unknown flag -t (see aos-agent llm set --help)
$ aos-agent -d stacks/root llm -t ann set endpoint=fake ← 可以
$ aos-agent -d stacks/root tools add -t ann x y
aos-agent: error: FlagUnknown unknown flag -t (see aos-agent tools add --help)
```

頂層 help：「-t may go before or after the subcommand」。坑-68（11-10 已修）只補了「`aos-agent -t ann ctl state`」這一格；`ctl` 與動作之間、`tools`／`llm` 的動作之後還是不收。

**A2　`-d` 只能寫在子命令前。**（lv5；aos-daemon-ctl 同）

```
$ aos-agent ctl state -d stacks/root -t ann
aos-agent: error: FlagUnknown unknown flag -d (see aos-agent ctl state --help)
```

`aos-tools --file` 今天才改成前後都收（[aos-tools-cli 08](../aos-tools-cli/08-施工結果.md) 步 1），這裡還是舊規矩。

**A3　名字不能當位置參數（只有 `ctl rm` 可以、而且只能），跟 aos-daemon-ctl 相反。**（lv5）

```
$ aos-agent -d stacks/root ctl stop ann
aos-agent: error: ArgumentsBad stop takes no positional arguments: ann (pick the target with --target) …
$ aos-daemon-ctl -d stacks/root stop ann               ← 這邊只收位置
$ aos-agent -d stacks/root ctl rm                      ← 這個反過來只收位置
aos-agent: error: ArgumentsBad rm needs the name spelled out (no --target / AOS_AGENT: it deletes the stack…
$ aos-agent -d stacks/root say ann hi
aos-agent: error: TargetMissing no target: add --target NAME, or export AOS_AGENT=NAME …
$ AOS_AGENT=ann aos-agent say ann hi  →  送出去的話是「ann hi」
```

`rm` 不吃 `-t` 是故意的（怕誤刪）；但結果是同一支指令裡三套規矩。

**A4　`ctl rm`＝刪 stack，`aos-daemon-ctl rm`＝留 stack；同一個字。**（lv5／lv2 周邊）

```
$ aos-daemon-ctl -d stacks/root add -n t4 defs/tick
$ aos-agent -d stacks/root ctl rm t4 </dev/null
removed t4 (deleted stack /tmp/cli-sweep/proj/stacks/root/procs/t4)
```

不是 agent 的列（`tick` 沒有 interfaces.json）也照刪；不在終端就不問。B23 已把兩支 help 改清楚，行為沒動。

**A5　已經在那個狀態：aos-agent 當成功（退 0），aos-daemon-ctl 當錯（退 1）。**

```
$ aos-agent -d stacks/root ctl stop -t ann
already stopped (stopped)                              [rc=0]
$ aos-daemon-ctl -d stacks/root stop ann
aos-daemon-ctl: error: PhaseBad ann is already stopped [rc=1]
```

**A6　start 只起 stopped、wake 只起 sleeping，配錯就報錯——使用者要先知道它是哪一種停。**

```
$ aos-agent -d stacks/root ctl wake -t ann
aos-agent: error: PhaseBad ann is stopped; use start (wake only wakes sleeping ones)
$ aos-agent -d stacks/root ctl start -t ann     （它在 sleeping）
aos-agent: error: PhaseBad ann is sleeping; use wake (start only starts stopped ones)
```

訊息寫得很清楚，但程式既然知道該用哪個，還要人重打一次。是不是合成一個字，是方向題（README Q6）。

**A7　daemon 沒在跑時，`ctl add` 乾等 30 秒才報錯；`ctl ls` 完全看不出 daemon 停了。**

```
$ aos-daemon-ctl -d stacks/root2 shutdown        （停掉整台）
$ aos-agent -d stacks/root2 ctl ls
_clock  sleeping  -  -  -
eca     sleeping  /tmp/cli-sweep/proj  0  -      ← 看起來只是都睡了
$ aos-agent -d stacks/root2 ctl add -n e2 -w . defs/eca
aos-agent: error: DaemonFailed no result from the daemon at … within 30 s; letter withdrawn, it will not be applied
```

`shutdown` 自己會核 pid（「no aos-daemon running at … (pid 887291 is gone)」），同一個檢查沒用在 add／ls。`say` 那邊有提醒（「if the daemon itself is down, restarting it wakes eca too」），但也是猜的語氣。

**A8　`watch` 在沒有回答進行中時安靜卡住。**

```
$ timeout 10 aos-agent -d stacks/root2 watch -t eca
[rc=124]                                         ← 十秒沒有任何輸出
```

help 寫「follow its screen until one answer ends」；現在沒有在答就一直等下一輪，沒有一行說「正在等」。

**A9　`tools add` 的寫法跟 `aos-tools add` 不同。**（lv5；連帶 lv6 `self_tools`）

```
$ aos-agent … tools -t ann add /…/lib/base/math
aos-agent: error: ArgumentsBad add needs 2 arguments (usage: … add [--replace] [--no-cache] NAME PATH)
$ aos-agent … tools -t ann add --name m2 /…/lib/base/math
aos-agent: error: FlagUnknown unknown flag --name
$ aos-tools add [--name N] [--envs K=V] [--env-file F] [--path-json J] PATH     ← 另一支
```

`--envs`／`--env-file`／`--path-json` 在這邊都沒有；help 又說「PATH is resolved from the current directory」，而 aos-tools 是「跟著檔走」。這是 aos-tools-cli 第一輪 Q4 的 A 案（「`aos-agent tools add` 補上 `--name`／`--envs`…寫法改成跟 `aos-tools add` 一樣」，[README 第一輪](../aos-tools-cli/README.md)），使用者那題後來答的是覆蓋檔格式，這一半沒做。

### 二、設計如此，補說明就好

- **A10　`ctl ls` 的 STATE 跟 `aos-daemon-ctl ls` 的 PHASE 不同字**：pause 之後 aos-agent 印 `paused`、aos-daemon-ctl 還是 `running`（實跑）。`ctl state` 有並排印（`state running (daemon phase running)`）。這是兩層各自的看法，help 補一句「paused 只在這裡看得到」即可。
- **A11　`ctl ls -l` 的 `QUEUED`（第 4 欄：在判官那邊排隊的名次）與 `QUEUE`（第 6 欄：信箱裡等著的信數）**：兩個字只差一個 D。沒表頭時更分不出來（見 [06](06-跨指令不一致.md) X7）。
- **A12　`listen` 不帶旗標、又沒有新問題時，直接印上一個回答**（實跑：印出 `FAKE ANSWER to: while paused …`）。help 寫「wait for the latest answer」。合理，但「等」字會讓人以為它會卡住。
- **A13　`tools`、`llm` 每次都印一兩行 `warning:`**（「using the definition's …tools.json (this agent has no file of its own)」「created …llm.json」「keys changed for this agent」）——都是正常結果，不是警告。家規是「提醒走 stderr、前綴 warning」，所以不算錯；但人看到一排 warning 會以為出事。
- **A14　`open／close／watch` 只有宣告了畫面的 agent 有**（agent-fsm 回 `ScreenMissing … follow answers with aos-agent listen --follow`）。訊息已指路。
- **A15　`ctl add` 印的是 stack 路徑**（`aos-daemon-ctl add` 印信名）。各自合理。

### 三、只是不熟

- `ctl who`（哪隻 agent 擁有這個 stack）是給工具用的；`state`＝`status`。
- `chat` 的提示符走 stderr、回答走 stdout（管線裡看起來是 `> > …`）。

## 照推薦改完後的一段白話

> aos-agent 是跟「掛在 daemon 上的一隻 agent」打交道的遙控器；`-d`（哪台 daemon）、`-t`（哪一隻）寫在哪都行。`say`／`listen`／`chat` 跟它說話；`ctl add 資料夾` 掛上去、`ctl ls` 看全部（最後一行說 daemon 活著沒）、`ctl stop／start` 停與起、`ctl rm 名字` 拿掉並刪掉它的 stack。畫面、工具、腦設定各一組子命令，工具的寫法跟 `aos-tools` 一樣。

少掉：1 的一半（位置）、2、6、7、9 的一部分；3、4、5、8 還在，靠 README 的快選題決定。
