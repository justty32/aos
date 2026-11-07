# `aos-daemon-ctl add` 直掛 agent 定義資料夾、回 `applied: true` 卻在 `ls` 看不到列——重現、根因、判斷與選項（11-07 調查，只讀沒改程式）

← [入口](README.md)｜上一份 [08-aos-daemon-ctl永遠直寄實作結果](08-aos-daemon-ctl永遠直寄實作結果.md)｜工作流 [investigation](../../../../../wf/workflows/investigation.md)

## 白話結論

- **daemon 沒壞，是兩條已定的設計疊在一起，變成「靜悄悄失敗」。** agent 定義資料夾的 `_entry` 是「把自己掛上 daemon」（＝跑 `aos-agent ctl add 自己`，使用者 11-05 題 4）；`aos-daemon-ctl add XXX` 是「讓 daemon 照 aos-exec 的走法跑 XXX」（11-04「看最終指向的json的內部結構」）。兩個疊起來＝**daemon 把「掛 bob」這件事當成一次性小程式、用 bob 這個名字跑一次**。
- 那支一次性小程式（`aos-agent ctl add bob`）一查表，發現表上已經有 `bob`——就是它自己——於是報 `InstanceExists` 退 1；一次性的列退了就照規矩從表上拿掉。所以列只活了約 200 毫秒，`ls` 幾乎看不到；錯誤只寫在 `procs/bob/stderr.txt`。
- `applied: true` 沒說謊：它的意思本來就是「這封信 daemon 收了、套進名單了」，不是「那隻還在跑」。
- 加 `--name bobx` 反而「成功」：表上出現的是 `bob`（不是 `bobx`），而且是 aos-agent 繞一圈掛的——`--name` 被吃掉。
- **建議**：照設計、補文件與 help 一句（推薦，0 程式）；要不要讓「一次性 proc 退非 0 也留表寫原因」是方向題，留給使用者裁。

## 重現（11-07 家機，scratch 資料夾，沒動 `~/code/playground`）

建置：`pgrep -f "cmake --build"` 沒有結果；用 `proto8/impls/*/bin`（aos-daemon 是 11-06 21:09 建的）與 `proto8/cmd/*/bin`。下面 `$S`＝`mktemp -d` 建的 scratch 資料夾（實際是 `/tmp/claude-1000/…/scratchpad/direct-agent.D4BA`），`env.sh` 照試驗場那份只放 PATH、清掉 `AOS_KERNEL`／`AOS_DAEMON`／`AOS_STACK`／`AOS_WS`／`CLAUDE*`。agent 是 `templates/agent-fsm` 的複本 `$S/bob`（沒改；只是要看它上不上表，不用問腦）。

```sh
cd $S && source ./env.sh
mkdir -p ws/.stack && echo '{"procs": {}}' > daemon.json
cp -r $R/templates/agent-fsm bob
(AOS_STACK=$S/ws/.stack/ AOS_WS=$S/ws setsid aos-daemon --enable-logs daemon.json >daemon.log 2>&1 </dev/null &)
cd ws
aos-daemon-ctl add $S/bob; for i in 1 2 3; do aos-daemon-ctl ls; sleep 0.5; done
```

```text
01794013299459924378.58169.645144
bob	running	58170	-	-	-
# root daemon (no supervisor)
# root daemon (no supervisor)
# root daemon (no supervisor)
```

daemon 的 log 與那一列的 stderr：

```text
{"at": "2026-11-07T01:01:39.593+00:00", "name": "bob", "phase": "running", "pid": 58170, "code": null, "signal": null}
{"at": "2026-11-07T01:01:39.793+00:00", "name": "bob", "phase": "done", "pid": 58170, "code": 1, "signal": null}
```

```text
$ cat $S/ws/.stack/procs/bob/stderr.txt
aos-agent: error: InstanceExists bob is already on the daemon; pick another name (--name), or first aos-agent ctl rm bob
```

看回信（`aos-post init $S/replies` 先建信箱）：

```text
$ aos-daemon-ctl add --reply-to $S/replies $S/bob
01794013320186389378.58804.647217
$ cat $S/replies/new/*/letter.json
{
  "sender": ".../direct-agent.D4BA/ws",
  "sent_at": "2026-11-07T01:02:00.208+00:00",
  "in_reply_to": "01794013320186389378.58804.647217",
  "body": {
    "applied": true
  }
}
$ aos-daemon-ctl ls
# root daemon (no supervisor)
```

對照組：

| 做法 | 結果 |
|---|---|
| `aos-daemon-ctl add --name bobx $S/bob` | log：`bobx running` → `bob running`（ws＝`$S/ws`）→ `bobx done code 0`；`ls` 只剩 **`bob`**（`--name bobx` 沒用上） |
| 第二台 daemon、**沒設** `AOS_WS` 起，`aos-daemon-ctl add $S/bob` | 同樣 `InstanceExists`、列消失 |
| `cd ws && aos-exec $S/bob`（文件寫的正路） | 印 stack、`ls` 有 `bob running` |
| `aos-daemon-ctl add --name carl --def $S/bob $S/bob/body.json`（直接掛身體） | `ls` 有 `carl running`；表上 `exec`＝`../../bob/fsm.json`、`def`＝`../../bob` |

收尾：只對自己起的兩台 daemon 的 pid 送 SIGINT，`pgrep -af direct-agent.D4BA` 沒有殘留。

## 根因（檔:行）

1. **agent 的 `_entry` 是「掛自己」的單子**：`proto8/templates/agent-fsm/_entry`＝`{"argv": ["aos-agent", "ctl", "add", {"$env": "AOS_CD"}], "cwd": {"$env": "AOS_WS"}}`（說明在 `proto8/cmd/aos-agent/README.md:67-68`、`proto8/templates/docs/02-agent-fsm.md`）。
2. **aos-daemon-ctl 判型把它當 exec 型**：`proto8/py/daemon_ctl/entry.py:101-102`（有 `argv` 的物件＝單子＝回 `None`＝exec 型）；名字預設資料夾名 `entry.py:182`；送出 `{"procs_added": {"bob": {"exec": "<bob 絕對路徑>", "def": …}}}`（`entry.py:186`、`197`、`210`）。
3. **`applied: true` 在套完名單、對完表後就回**：`proto8/impls/aos-daemon/src/daemon/mailbox.cpp:144-146`（`done_letters`，好信有 `reply_to` 就回）；套信只是改名單底 `mailbox.cpp:100-102`；呼叫順序 `tend.cpp:253`（`reconcile` 後 `done_letters`）。它不追蹤那一列之後活多久。文件也這樣定義：`proto8/cmd/docs/03-aos-daemon-ctl.md:13`「daemon 套了＝`{"applied": true}`」、`:18`「結果看 ls」。
4. **daemon 起 exec 型 `bob`**＝`aos-exec -- <bob>`，走 `_entry` 單子＝跑 `aos-agent ctl add <bob>`；子行程環境有 `AOS_DAEMON`＝這台 daemon 的 stack（`impls/aos-daemon/docs/02-看寫法決定怎麼起.md`「起 exec 型」），所以 aos-agent 找到的就是同一台。
5. **aos-agent 撞名**：`proto8/cmd/aos-agent/aos_agent/ctl/add.py:88`（名字＝資料夾名 `bob`）→ `:90` `row_named("bob")` 找到的正是那列 exec 型的自己 → `:94` `InstanceExists`、退 1，**信沒寄出**。
6. **exec 型退了就下表**：`proto8/impls/aos-daemon/src/daemon/tend.cpp:166-180`——loop 型退非 0 才留 `stopped`＋`reason`（`!c.once` 那條，11-05 晚例外），exec 型不管碼多少都 `done`、拿掉。條文 N-28「子項結束後不自動重起、不留名單」（`proto8/docs/NORMS/04-基礎設施-loop與daemon/02-N-28.md:29`）。
7. `--name bobx` 時：外層列叫 `bobx`、裡面 aos-agent 照資料夾名用 `bob`，不撞名、寄出、上表；`bobx` 退 0 下表——所以看起來「成功但名字不對」。

不是：agent 資料夾 `_entry` 形狀壞掉（它是合法單子）、不是 daemon 拒信（`mailbox_warning` 是 `null`）、不是列加了又被 rm。

## 判斷：照設計的組合，不是 daemon／ctl 的 bug；但失敗方式是使用面缺陷

對照的使用者原話與裁定：

- `aos-daemon-ctl add XXX`＝掛到 daemon 上、自動識別，「add這塊，就是看最終指向的json的內部結構」（11-04，`cmd/docs/03-aos-daemon-ctl.md:5`、`:20`）→ 照 aos-exec 的走法判型，定義資料夾走到 `_entry` 單子＝exec 型，**照設計**。
- portable-flow 題 4（11-05）：「aos-agent add。當然，你也可以把_entry寫成aos agent add，這樣我們也可以aos-exec了。」→ `_entry`＝掛自己，**照設計**；同處決定 6「介面維持 aos-agent add」。
- os-impl 08（11-07）：「aos-agent＝經作業系統（判官），aos-daemon-ctl＝人直接敲板子」——掛 agent 的正門是 `aos-agent ctl add` 或 `aos-exec 定義資料夾`；`aos-daemon-ctl` 是給任意 proc 的低層手把。用它掛 agent，要給的是**身體**（`bob/body.json`）而不是定義資料夾——這就是 `aos-agent ctl add` 自己在做的（`aos-agent/README.md:67`：宣告了 `entry` 時送 `aos-daemon-ctl add --def <定義> <定義>/<entry>`）。
- `applied` 的語意（`cmd/docs/03:13`）＝信套了；N-28 一次性子項結束不留名單、「表上看不到結束的，結束碼看 log」→ 列消失也**照設計**。

所以每一段都照條文走；問題在於這個組合沒人想過，結果是：回信說好、`ls` 空、錯誤只在 `stderr.txt`、`--name` 被吃掉。按 [user.md](../../../../../wf/workflows/common/user.md) 的通則，這屬於「挖出來的邊緣狀況」，攤給使用者判斷。

另外一個從程式推出、**沒實測**的連帶：外層 exec 列裡跑的 `aos-agent ctl add` 會繼承 daemon 的環境；若起 daemon 時環境裡有 `AOS_KERNEL`，這封內層的掛子信會**經判官**（`py/daemon_ctl/post.py:28-34`，aos-agent 不帶 `direct`）——也就是「aos-daemon-ctl 永遠直寄」在這條路上其實沒直寄。缺的證據：開判官的模式 2 下用 `--name` 跑一次。

## 建議與選項（方向的留給使用者裁）

**不需裁、可直接做（推薦，0 程式）**：文件與 help 各補一句——

- `cmd/docs/03-aos-daemon-ctl.md` 與 `aos-daemon-ctl add --help`：「XXX 是 agent 定義資料夾時，跑的是它的 `_entry`（多半是『把自己掛上 daemon』），會撞名、什麼都沒掛上；掛 agent 用 `aos-agent ctl add` 或 `aos-exec 定義資料夾`，硬要直掛就給身體：`aos-daemon-ctl add --def bob bob/body.json`」；`applied: true`＝信收了、不是還在跑，結果看 `ls`／log。
- `templates/docs/02-agent-fsm.md` 的 `_entry` 說明補同一句。
- `cmd/docs/03:21` 的舊例子 `aos-daemon-ctl add ../../agents/bob -- "…"`（eca 時代）會踩到同一坑，順手換掉。

**方向題（1 題，推薦放第一）：要不要讓 `ls` 看得到這種失敗？**

背景：現在一次性（exec 型）的 proc 不管成功失敗，退了就下表；只有 loop 型退非 0 會留 `stopped`＋`reason`（使用者 11-05「留成stopped，並寫原因」那次只改了 loop 型）。

- **維持現狀，只補文件 (Recommended)**：守 N-28「不留名單」與「exec 型只有跑和拔」（使用者原話「exec就是只有執行中和拔掉」）。代價：一次性 proc 失敗仍只看得到 log 與 `stderr.txt`，這個坑靠文件擋。
- **exec 型退非 0 也留表**（例：`phase` 標 `failed` 或沿用 `stopped`，帶 `reason`＝stderr 最後一行，要 `rm` 才清）：`ls` 一眼看到 `InstanceExists`。代價：翻 N-28 的「不留名單」與「exec 型只有跑和拔」兩句使用者原話；`start` 收不收它要另定；短命的一次性工作失敗會在表上堆著要人清。
- **aos-daemon-ctl add 認出 aos-agent 介面就拒或自動改掛身體**：一步到位。代價：下層（aos-daemon-ctl）要認上層（aos-agent 的 `interfaces.json`），違反單向分層（conventions「下層不可以知道上層存在」）；不推薦。
- （不列為選項）改 agent 範本 `_entry` 不再掛自己＝翻 11-05 題 4 裁定；aos-agent 在撞到「自己」時換代號＝認名型特例，照 C-52 續第一次就消，也不推薦。

## 使用者裁定（11-07）

方向題「要不要讓 `ls` 看得到這種失敗？」使用者選 **A：維持現狀，只補文件**。原話：「A。」

已落實（與本段同一個 commit，訊息開頭「os-impl 09 裁定 A」）：`aos-daemon-ctl add --help` 補兩句（定義資料夾＝跑它的 `_entry`、agent 的 `_entry` 掛自己所以不留表、改用 `aos-agent ctl add` 或給身體；`applied` 只表示信已套進名單）；[cmd/docs/03](../../../../cmd/docs/03-aos-daemon-ctl.md) 補同一段，並把 eca 時代的舊例子 `add ../../agents/bob -- …` 換成 `add ./hello.sh -- world`。另兩個邊緣狀況（`--name` 被吃掉、這條路上 `AOS_KERNEL` 會經判官）使用者沒回應，照通則不處理。
