aos-daemon-ctl 照 C-85 掃一遍：現況白話、裝不下的十樣、怪點逐點附實跑輸出。

← [入口](README.md)｜上一份 [01-aos-agent](01-aos-agent.md)｜下一份 [03-aos-exec與copy-out](03-aos-exec與copy-out.md)

# aos-daemon-ctl（指令本身是 Python 殼；動到 aos-daemon 本體的才算 lv2）

實跑同 [01](01-aos-agent.md)。程式 `proto8/cmd/aos-daemon-ctl/bin/aos-daemon-ctl`、`proto8/py/daemon_ctl/`。

## 現況的一段白話

> aos-daemon-ctl 管一台 daemon 表上的行程。`add 東西` 掛上去跑、`ls` 看表、`rm 名字` 下表（stack 留著）；停與起有三對：`stop／start`（請它自己收尾）、`sleep／wake`（直接叫它睡）、`pause／resume`（原地暫停）。`shutdown` 停整台 daemon。另外幾個維護用：`poke`（叫 daemon 馬上看一眼）、`ping`、`prune`、`sweep`。

## 這段話裝不下的（十樣）

1. **指令只是「寄一封信」**：印出來的是信名，退 0 只代表寄了，不代表做成。
2. **三對停與起到底差在哪**，以及 start／wake 不能混用。
3. **跑完退 0 的列自己從表上消失**（stack 留著）。
4. **`ls` 沒表頭、看不出 daemon 自己活著沒**；最後一行講的是「上司怎麼看這台」。
5. **`where` 只能寫 `where --stack 名字`**。
6. **`pause／resume／shutdown` 成功時只印一個數字**。
7. **`add` 的 XXX 有三種解讀**（loop 設定、aos-exec 入口、agent 資料夾＝別用這支），外加 `--def`。
8. **`--reply-to`／`--timeout-s`**：等的是「信被拿走」不是「做完」。
9. **`sweep` 跟常駐的 `_sweeper`（`aos-sweeper`）預設不一樣**（這邊預設不刪舊封存）。
10. **`prune` 不加旗標只檢查**，名字卻叫 prune。

## 怪點逐點

### 一、真問題

**B1　退 0 不代表做成：名字撞了、名字不存在，都安靜「成功」。**

```
$ aos-daemon-ctl -d stacks/root add defs/ann          （ann 已經在表上）
01794295603705057341.852786.2480588                   [rc=0]   ← 表沒變，也沒有任何提醒
$ aos-daemon-ctl -d stacks/root rm nobody
01794295630587749668.877589.2483073                   [rc=0]
$ aos-daemon-ctl -d stacks/root stop nobody
aos-daemon-ctl: error: ProcMissing nobody is not on the daemon table …  [rc=1]   ← stop 卻會先查
```

help 有寫（「"applied": true only means the letter was applied…」「0 sent」），所以算「講過」；但同一支裡 stop／start／sleep／wake 會先查表、add／rm 不查，人分不出哪些可以信退出碼。`aos-agent ctl add` 同樣情況會報 `InstanceExists`。

**B2　成功輸出是給程式看的：信名、或一個數字。**

```
$ aos-daemon-ctl -d stacks/root wake ann
01794295581475675957.848061.2478365
$ aos-daemon-ctl -d stacks/root pause ann
3
$ aos-daemon-ctl -d stacks/root2 shutdown
1
```

`shutdown` 是使用者每天下班打的那一行（「下班前對根下 shutdown 再 git push」），成功時畫面上只有一個 `1`。help 說「prints N」（N 是 ctl 的序號）。等不到退出會報 `StillRunning`、退 1，這部分是對的。

**B3　`ls` 看不出 daemon 自己有沒有在跑。**

```
$ aos-daemon-ctl -d stacks/root2 shutdown
$ aos-daemon-ctl -d stacks/root2 ls
_clock    sleeping  -  143  -                    -
_sweeper  sleeping  -  143  -                    -
eca       sleeping  -  143  /tmp/cli-sweep/proj  -
# root daemon (no supervisor)                    [rc=0]
```

最後一行「root daemon (no supervisor)」是「上司的看法」（`aos-daemon-ctl:537`），讀起來像「根 daemon 正常」。daemon 停了，這張表照樣印。`ping` 能驗，但它的錯誤說「busy, paused or not running」三選一。`shutdown` 用的那個核 pid 的檢查現成可用（它對停掉的 daemon 會說「no aos-daemon running at … (pid 887291 is gone)」）。`-j` 有 `"daemon": null`，但那格是上司不是自己。

**B4　`where` 的名字要寫成旗標的值。**

```
$ aos-daemon-ctl -d stacks/root where ann
aos-daemon-ctl: error: ArgumentsBad where needs --stack NAME (usage: … where --stack NAME)
$ aos-daemon-ctl -d stacks/root where --stack ann     ← 可以
$ aos-agent -d stacks/root ctl where --stack -t ann   ← 另一支：--stack 是開關
```

同一支的其他子命令都是 `動作 名字`。（`aos-daemon-ctl:575-577`）

**B5　`-d` 只能寫在子命令前**（同 A2）。

```
$ aos-daemon-ctl ls -d stacks/root
aos-daemon-ctl: error: FlagUnknown unknown flag -d (see aos-daemon-ctl ls --help)
```

**B6　`$AOS_DAEMON` 一個變數兩個意思。**（動到 aos-daemon 本體＝lv2，改法要保守）

- 人打指令時：「我要對哪台 daemon 說話」（`-d` 的預設）。
- 起 daemon 時：「我的上司是誰」（daemon 給子項設的，`impls/aos-daemon/src/child/child.cpp:66`）。

所以為了少打 `-d` 而 `export AOS_DAEMON=…/stacks/root` 的殼，再去起另一台根，那台會以為自己是 root 的下屬：

```
$ export AOS_DAEMON=/tmp/cli-sweep/proj/stacks/root
$ cd /tmp/cli-sweep/p3 && aos-exec --stack stacks/root defs &
$ aos-daemon-ctl -d stacks/root ls
# supervisor /tmp/cli-sweep/proj/stacks/root: this daemon is not on its table
$ aos-daemon-ctl -d stacks/root shutdown
aos-daemon-ctl: warning: this daemon is a proc of the daemon at /tmp/cli-sweep/proj/stacks/root; exiting 0 takes it off that table …
```

daemon-root 的 README 有叫人先 `unset AOS_CLOCK AOS_DAEMON AOS_STACK`，所以是「講過」；但「起之前要 unset 三個變數」本身就是白話裝不下的東西。指向自己的 stack 時沒事（實跑：照樣是 root）。

**B7　一次性的東西 `add` 上去，跑完就從表上消失，輸出也找不到。**

```
$ aos-daemon-ctl -d stacks/root add defs/tick     （_entry 印一行、睡 2 秒、退 0）
$ aos-daemon-ctl -d stacks/root ls                （3 秒後）→ 沒有 tick 這列
$ ls stacks/root/procs/tick
stderr.txt                                        ← 只有 stderr；它 echo 的那行在 daemon 的輸出裡也找不到
```

「退 0＝下表」是 aos-daemon 的規矩（help 有寫）。怪的是：表上沒痕跡、stack 留著（`prune` 不報這種沒有列的殘留夾）、stdout 去向沒有任何地方講。stdout 到底去哪我沒追源碼，列在「拿不準」。

### 二、設計如此，補說明就好

- **B8　三對停與起**。現在散在各子命令的 help 裡，頂層只有一行一個。建議頂層 help 放這張表（英文）：

  | 想做的事 | 指令 | 它怎麼停 | 之後表上 | 怎麼再起 | daemon 重開時 |
  |---|---|---|---|---|---|
  | 做完這圈就收 | `stop` | 寫它的 ctl、等它自己退；不讀 ctl 的程式停不了 | stopped | `start` | 不會自己起 |
  | 現在就睡 | `sleep` | SIGTERM（10 秒後 SIGKILL） | sleeping | `wake` | 自己醒 |
  | 原地暫停 | `pause` | 寫它的 ctl，行程還在 | running（aos-agent 看是 paused） | `resume` | — |
  | 下表 | `rm` | 同 stop 後移除 | 沒有這列 | 重新 `add` | — |
  | 停整台 | `shutdown` | 子項全部 sleep | 全 sleeping | 重起 daemon | 全醒 |

- **B9　sleeping 的列 CODE 印 143**（坑-63 已補文件）。
- **B10　`prune` 不加 `--older-than` 只檢查、加了是預覽、再加 `--apply` 才動**：三段式安全，但名字是「修剪」。help 第一行已寫「check rows and detach…」。
- **B11　`sweep` 預設不刪舊封存、常駐列預設 7 天**：help 有寫（「none = no deletion, the default here」）。
- **B12　`add` 沒有 `--envs`**（`aos-agent ctl add` 有）。
- **B13　help 還在講「ctl mailbox」**（頂層 help 三處），底下已改名 `procs_requests`。這是 HANDOFF 11-10 第 2 點「『ctl 信箱』說法要不要照新命名原則改」——已知未裁，不重報。

### 三、只是不熟

- `--reply-to BOX`（給程式用，只寄不等）；`poke --ctl|--mail|--all`；`ping`。

## 照推薦改完後的一段白話

> aos-daemon-ctl 管一台 daemon 表上的行程。`add 東西` 掛上去、`ls` 看表（最後一行說 daemon 活著沒）、`rm 名字` 下表（stack 留著）；停與起三對：`stop／start`、`sleep／wake`、`pause／resume`（差別在 help 開頭那張表）。`shutdown` 停整台，成功會說一句「stopped, N procs asleep」。指令都是寄信給 daemon，但名字打錯、撞名會當場告訴你。

少掉：1 的大半、4、5、6；2 變成一張表；3、7～10 留著（補說明）。
