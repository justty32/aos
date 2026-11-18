這份教你手動看一隻 eca-claude agent 現在是什麼狀態：表、queue、信箱、對話、畫面、控制檔，以及 `aos-json-view`（試驗 17，11-18 晚在家機用 haiku 實跑過）。
← [目錄](README.md)

使用者原話：「手動確認狀態（aos json view、信箱、queue…）」

## 結論

- **先用一句話看全貌**：`aos-agent -d .stack ctl state -t ann`，十一類事實各一行（who、state、tools、llm、system、hooks、history、mailbox、subagents、resources、time）；要哪類的細節就把類別名接在後面。
- **看表**：`aos-agent ctl ls`（短）、`ctl ls -l`（多 QUEUE、RESTARTS、COOLDOWN、LAST ERROR 四欄）、`ctl ls -j`（JSON）；`aos-daemon-ctl -d .stack ls` 多 pid 與一行 daemon 狀態，而且 daemon 沒在跑也看得到。
- **看檔**：stack 裡的檔都是 JSON 或 JSONL，`aos-json-view 檔` 把 JSON 排成好讀的樣子（唯讀）。注意：**JSONL（一行一個 JSON，例如 `history.jsonl`）不能直接餵它**，會報 `FileBad … is not JSON: Extra data`，那種用 `aos-agent history ls`。
- **正在想的那一輪看不到「忙」這個欄位**：`ctl ls` 的 `busy` 是 `null`、`queue` 是 0，信已經被拿走。要看有沒有一輪在進行，看 `letters.json` 的 `pending` 有沒有那封信。
- 出錯怎麼查接著看 [18](18-agent出錯怎麼手動除錯.md)。

都在 `~/aos-home` 打，樹照 [README 的「共同準備」](README.md#共同準備)起好、ann 掛上、haiku。下面輸出裡的路徑縮成 `…`。

## 一步一步

**1. 看表**

```sh
aos-daemon-ctl -d .stack ls
```

```
_clock	running	424157	-	-	-
_sweeper	running	424158	-	-	-
ann	running	461334	-	/home/…/home	-
# daemon: running (pid 424155)
# root daemon (no supervisor)
```

欄位：名字、phase、pid、（理由）、工作區。`_clock`、`_sweeper` 是 daemon 自己的兩個內務 proc。

```sh
aos-agent -d .stack ctl ls -l
```

```
_clock	running	-	-	-	-	0	-	-
_sweeper	running	-	-	-	-	0	-	-
ann	running	/home/…/home	0	-	0	0	-	-
```

`-l` 多的四欄是 QUEUE（排著幾封）、RESTARTS、COOLDOWN（`until HH:MM (N)`）、LAST ERROR，出錯才有值（見 [18](18-agent出錯怎麼手動除錯.md)）。`ctl ls -j` 一隻一個物件：`{"name": "ann", "state": "running", "phase": "running", "ws": …, "stack": …, "queued": 0, "reason": null, "auto_restart": true, "queue": 0, "cooldown": null, "busy": null}`。

**2. 一句話看全貌**

```sh
aos-agent -d .stack ctl state -t ann
```

```
who       ann (def …/agents/ann, ws …/home, stack …/.stack/procs/ann)
state     running (daemon phase running); 0 queued; last answer "done15"
tools     34 tools (agent_def, clock_register, index_view, json_add, … ); no own changes
llm       model=haiku
system    0 bytes from none
hooks     6 hooks (brain_notify on brain_failed, context_wrap on on_clock, mail_notify on on_clock, screen_linger_start on after_start, screen_linger_stop on after_stop, timer on on_clock)
history   12 messages, 1606 bytes (assistant 6, user 6)
mailbox   0 letters waiting
subagents 0/4 subagents
resources limits none; memory 2.7 MiB, cpu 0.0 s, 1 processes
time      now 2026-11-18T21:02:13+0800; up 0h00m05s
```

接類別名看細節，例如 `ctl state -t ann who llm time` 會分段 `== who`、`== llm`、`== time`；`-j` 給 JSON；`all` 全印。`resources` 在 claude 正在跑那輪時會變大：實測看到 `memory 294.8 MiB, cpu 0.9 s, 6 processes`（平時 2.7 MiB、1 個行程）。這也是一個「有輪在跑」的旁證。

**3. 看 stack 裡的檔**

```sh
ls .stack/procs/ann
```

```
claude  ctl.json  history.jsonl  hooks  letters.json  queue  state_flux.json  state.json  stderr.txt
```

| 檔 | 是什麼 |
|---|---|
| `state.json` | loop 的狀態：`phase`、`paused`、`pid`、`updated_at`（見 [13](13-aos-loop控制停止與繼續.md)） |
| `ctl.json`、`state_flux.json` | 你下的控制命令（有人下過才有）、loop 的回應 |
| `letters.json` | `pending`（收了還沒答的信）、`dropped`（被丟的） |
| `queue/` | 信箱：`new/` 還沒被拿、`cur/`、`tmp/`、`order.json` |
| `history.jsonl` | 對話紀錄，一行一則 |
| `stderr.txt` | 出錯訊息（空的就是沒事） |
| `hooks/` | 每個 hook 自己的小狀態 |
| `claude/` | claude 那邊的東西：`session.txt`（對話編號）、`live.jsonl`、`transcripts/`、`env.json`（**有環境變數，不要貼**） |

**4. aos-json-view：把 JSON 排好看**

```sh
aos-json-view .stack/procs/ann/state.json
```

```
phase:            running
max:              null
interval_ms:      300
paused:           false
pid:              461334
started_at_ticks: 882715
boot_id:          85004dab-ef70-4c6b-b360-e26dd4b9b0c2
updated_at:       2026-11-18T13:02:08.189+00:00
```

指一個部分用 `檔#/指標`（JSON Pointer）：

```sh
aos-json-view .stack/procs_state.json#/procs/ann
```

```
# .stack/procs_state.json#/procs/ann
pid:              461334
phase:            running
stack:            procs/ann
ws:               ..
launch:           {exec: [../agents/ann]}
def:              ../agents/ann
auto_restart:     true
…
```

（上面省掉幾個值是 null 的鍵。）整份太長用 `--depth N` 只展開 N 層，更深的摺成 `{…12 keys}`：

```sh
aos-json-view .stack/procs_state.json --depth 2
```

```
procs:            {_clock: {…12 keys}, _sweeper: {…12 keys}, ann: {…12 keys}}
pid:              424155
…
```

`procs_state.json` 是 daemon 的表（`aos-daemon-ctl ls` 讀的就是它）。另外還有 `aos-json ls 檔#/procs`（列子項名字）、`aos-json get`（取值，指令總覽 `aos-json --help`）。用 `--no-color` 可以關顏色，貼到別處時用。

**5. 看信：queue、letters、信箱**

```sh
aos-agent -d .stack -t ann say "run the bash command 'sleep 12' once, then reply with the single word: fin"
sleep 4; aos-json-view .stack/procs/ann/letters.json; ls -R .stack/procs/ann/queue
```

```
pending:
| 000000000007.01795006951773724702.464827.885078
dropped: []
```

`queue/new/`、`cur/` 都是空的：信被 claude 拿走了，`pending` 裡那封就是「正在處理的那一輪」。等那輪答完，`pending` 變回 `[]`。

停著時寄的信則留在 `queue/new/`（見 [14](14-停著時say.md)）。

別人寄給 ann 的**信箱**（`aos-mailbox` 那種，不是 `say` 的 queue）：`aos-agent ctl state -t ann mailbox` 看有幾封，空的就印 `(no letters)`。信箱怎麼收發見 [07](07-aos-mailbox寄信收信.md)。

**6. 看對話**

```sh
aos-agent -d .stack -t ann history ls
aos-agent -d .stack -t ann listen --last 2
```

```
1	user	reply with the single word: ping
2	assistant	ping
…
== #5
> reply with the single word: woke
woke
```

`history ls` 一則一行（預設只印最後 20 則、每則截 200 字，`-l` 印全文、`-a` 全印）；`listen --last N` 是最後 N 組一問一答。**不能**用 `aos-json-view` 看 `history.jsonl`。

**7. 看 claude 本人的狀態**

```sh
aos-agent -d .stack -t ann peek /status
```

```
[aos] slash: /status: claude, model haiku; conversation 4e088aeb-…; screen closed; history 13 messages; transcript /home/…/.claude/projects/…/4e088aeb-….jsonl
```

`peek` 不進 queue、不寫對話紀錄，一輪進行中也能用。**`peek /usage` 會印你自己帳號的用量與 session 統計，貼到別處前先看一眼。** 要看 claude 的畫面：`aos-agent -d .stack -t ann open`（`Ctrl+\` 離開），見 [18](18-agent出錯怎麼手動除錯.md)。

**8. 看這隻的定義與設定**

```sh
aos-agent -d .stack -t ann tools ls | head -3
aos-agent -d .stack -t ann hook ls
```

`tools ls` 開頭會有一行 `warning: using the definition's …/agents/ann/tools.json (this agent has no file of its own)`（意思是這隻還沒改過工具，用定義那份）。`hook ls` 一個 hook 一行：`brain_notify	brain_failed	{"$env":"AOS_HOME","$path":"/lib/tools/agent/brain_notify"}` 等六行，與 `ctl state` 的 hooks 那行同一份。

## 沒實測的

- `subagents` 類別在有掛子 agent 時的樣子（這棵樹沒掛）。
- 信箱裡真的有信時 `ctl state mailbox` 的輸出。
- `aos-agent ctl state -j` 的 JSON 形狀。
- `aos-json-view` 的 `--width`、顏色。

## 發現的問題

1. **一輪進行中沒有明確的「忙」指標**：`ctl ls` 的 `busy` 欄一直是 `null`，要靠 `letters.json` 的 `pending` 或 `resources` 的記憶體間接看。
2. `ctl state` 的 `time` 那行 `up 0h00m05s`：我剛 `ctl stop`、`ctl start` 過，推測數的是這隻這次起來多久，不是 daemon 的（沒查程式，未確認）。
3. `aos-json-view` 對 `.jsonl` 只報 `FileBad … Extra data`，沒提示改用 `history ls`。
