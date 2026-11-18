這份教你兩種停 daemon 的方法、原地重開，以及把 stack 複製到別處再重開時哪些接得上、哪些會壞、怎麼救（試驗 01，11-18 在公司 WSL 用 haiku 實跑過）。

← [目錄](README.md)

使用者原話：「1.停掉daemon(ctrl+c,daemon-ctl指令)、複製stack過去，重開。」

## 結論

- **兩種停法結果一樣**：在視窗 A 按 Ctrl+C，或打 `aos-daemon-ctl -d .stack shutdown`，表上每一隻都變成 `sleeping`（code 143），agent 行程全部收掉，stack 裡的東西全部留著（對話紀錄、claude 的對話編號、queue）。
- **原地重開**：agent 自己醒，接得上上一句，claude 也接著同一段對話（對話編號沒變）。
- **整棵樹一起複製**（`cp -a ~/aos-home ~/aos-home2`），再從新位置起：agent 回得來，也記得上一句。但 **claude 會開一段新對話**：它認出工作區換了位置，就把 aos 自己記的對話紀錄（`history.jsonl`）當前情帶過去。指到舊位置的路徑全部自動換成新的，**一處都不用改**。
- **只複製 `.stack`**、不帶 `agents/`：agent 起不來，報 `EntryMissing`。原因是表上記的定義位置是相對 stack 的 `../agents/ann`。**要救只改一處**：把 `agents/` 也抄到新 `.stack` 的旁邊，再 `aos-daemon-ctl start ann`。
- 一句話：**表上的路徑都是相對 stack 記的，所以要搬就整棵樹一起搬。**

## 先準備

照 [README 的「共同準備」](README.md#共同準備)起一棵 eca 樹（`~/aos-home`，模型用 haiku）。視窗 A 跑 `aos-exec root`；視窗 C 已經 `ctl add` 過 `ann`。先讓它記一個字，等一下才驗得出接不接得上：

```sh
aos-agent -d .stack --target ann say "Remember the word: pineapple. Reply with just OK." && aos-agent -d .stack --target ann listen --timeout-s 120
```

會看到兩行：第一行是信件編號，第二行是 `OK`（約 7 秒）。

## 停法一：在視窗 A 按 Ctrl+C

在跑著 `aos-exec root` 的視窗 A 按 **Ctrl+C**。我是 AI 沒有鍵盤，用 `tmux send-keys C-c` 對那個視窗送了一次 Ctrl+C，效果等於你按 Ctrl+C（行程收到 SIGINT）。

會看到視窗 A 冒出 `^C` 和三行 sleeping，然後回到提示字元：

```
^C{"at": "…", "name": "_sweeper", "phase": "sleeping", "pid": 1651156, "code": 143, "signal": null}
{"at": "…", "name": "_clock", "phase": "sleeping", "pid": 1651154, "code": 143, "signal": null}
{"at": "…", "name": "ann", "phase": "sleeping", "pid": 1653354, "code": 143, "signal": null, "ws": "/home/你/aos-home"}
```

到視窗 C 看表：

```sh
aos-daemon-ctl -d .stack ls
```

```
_clock	sleeping	-	143	-	-
_sweeper	sleeping	-	143	-	-
ann	sleeping	-	143	/home/你/aos-home	-
# daemon: not running (pid 1651152 is gone); the table above is what it left
```

- agent 行程：都沒了（`pgrep` 找不到）。
- tmux 畫面：沒開過畫面就沒有畫面要關。開過畫面的話，畫面會照 `cli.json` 的 `screen_close_after_s` 延後關，預設 600 秒，見 [03](03-自訂定義掛上去.md)。
- stack 裡留下的：`.stack/procs_state.json`（表，三列都是 sleeping）、`.stack/procs/ann/` 裡的 `history.jsonl`（對話）、`claude/session.txt`（claude 的對話編號）、`queue/`、`hooks/`、`stderr.txt`。

## 原地重開（對照組）

視窗 A：

```sh
aos-exec root
```

會看到三行 `running`，其中有 `ann`，不用再 add。視窗 C 問它：

```sh
aos-agent -d .stack --target ann ask --timeout-s 120 "What word did I ask you to remember? One word."
```

會看到 `pineapple`（約 6 秒）。`ask` 等於 `say` 加 `listen`，只印回答，不印信件編號。`cat .stack/procs/ann/claude/session.txt` 印出的編號跟停之前一樣，代表 claude 接著同一段對話。

## 停法二：用 aos-daemon-ctl 指令

這支指令的名字就叫 `aos-daemon-ctl`，關整台的子指令是 `shutdown`（`aos-daemon-ctl --help` 最上面那張表有列）。在視窗 C：

```sh
aos-daemon-ctl -d .stack shutdown
```

```
daemon at /home/你/aos-home/.stack stopped (ctl seq 1); 3 procs asleep, they wake when it starts again
```

視窗 A 會自己印三行 `sleeping` 然後回到提示字元，不用再按 Ctrl+C。表的樣子跟停法一一樣。再打一次 shutdown 會看到：

```
aos-daemon-ctl: error: DaemonMissing no aos-daemon running at /home/你/aos-home/.stack (pid 1660020 is gone)
```

而且退出碼是 1。意思是它本來就停了，不用理。

## 整棵樹複製到別處再重開

先停好（上面兩種停法都行）。然後：

```sh
cp -a ~/aos-home ~/aos-home2
```

```sh
cd ~/aos-home2 && source env.sh && aos-exec root
```

會看到 `ann` 是 `running`，`ws` 欄已經是新位置 `/home/你/aos-home2`。視窗 C 先 `cd ~/aos-home2 && source env.sh`，再：

```sh
aos-agent -d .stack --target ann ask --timeout-s 120 "What word did I ask you to remember? One word."
```

會看到 `pineapple`（約 8 秒）。但 `cat .stack/procs/ann/claude/session.txt` 換成了一個新編號，也就是 claude 開了新對話。原因：aos 記得那段對話是在哪個工作區開的（`claude/.session_home` 的 `ws`），工作區一換，就不 `--resume` 舊的，改成開新對話、把 `history.jsonl` 帶過去當前情。所以它還記得，只是 claude 那邊是另一段對話。

我搬之前找了寫死舊路徑的檔，有這幾個：`claude/mcp.json`、`claude/env.json`、`claude/.session_home`、`hooks/*/event.json`、`hooks/*/on_clock.json`。新位置起來後，這幾個**全部自動換成新路徑**，一個都不用改。表（`procs_state.json`）本來就寫相對路徑：`"stack": "procs/ann"`、`"ws": ".."`、`"def": "../agents/ann"`，所以搬了照樣對。

**卡點**：新舊兩棵不要同時開著，我沒試兩棵同時跑會怎樣。

## 只複製 `.stack`（壞掉的例子＋怎麼救）

只抄 `.stack` 到 `~/only/.stack`，再用原樹的根定義起：

```sh
mkdir ~/only && cp -a ~/aos-home/.stack ~/only/.stack && cd ~/only && aos-exec --stack .stack ~/aos-home/root
```

會看到 `ann` 連跳三次 `running`→`done`，最後停在 `stopped`。打 `aos-daemon-ctl ls`：

```
ann	stopped	-	1	/home/你/only	failed to start: exited within 3s of wake/start (code 1): aos-exec: error: EntryMissing entry not found: /home/你/only/agents/ann; restarted 3 times in a row, each exited within 3s; not restarting again
```

原因是表上的定義位置是相對的 `../agents/ann`，換到新位置就變成 `~/only/agents/ann`，那裡什麼都沒有。工作區也是相對的 `..`，所以它自動變成了 `~/only`。

**救法**：把定義也抄到它找的位置，再叫它起來：

```sh
cp -a ~/aos-home/agents ~/only/ && aos-daemon-ctl start ann
```

然後 `aos-agent -t ann ask --timeout-s 120 "What word did I ask you to remember? One word."` 會回 `pineapple`。這裡沒帶 `-d`，因為人站在 `~/only`，那裡就有 `.stack`，見 [02](02-預設stack與站在agent夾裡.md)。

## 發現的問題

1. **`ctl add` 的說明跟實際不一樣**：說明寫「你打絕對路徑，表上就記絕對路徑」，但我用絕對路徑 add 一隻 stack 在樹外的 agent（[03](03-自訂定義掛上去.md) 的 bob：`-s ~/bob-stack -w ~/bob-ws ~/my-defs/bob`），表上記成 `../../bob-stack`、`../../bob-ws`、`../../my-defs/bob`。這樣整棵樹搬到別的深度時，這種掛在樹外的 agent 應該會找不到它的 stack 和定義。**這是推論，搬家沒實測。**
2. 只複製 `.stack` 時，錯誤原因有寫在表上，但要打 `ls` 才看得到；視窗 A 只看得到 `done`／`stopped`。
