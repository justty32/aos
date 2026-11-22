# `knowledge/aos/cli/agent.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/agent.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/agent.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Agent lifecycle`**

# Agent 的一生

用 aos-agent ctl 掛上 agent，並查看或改變它們在 daemon 裡的狀態。`aos-agent ctl --help` 會印出三組停止配對（stop/start、sleep/wake、pause/resume）和 rm 的表。

**`#/ctl add: attach one agent`**

# ctl add：掛上一個 agent

```sh
aos-agent -d stacks/root ctl add --auto-restart -w . defs/ann
# /.../stacks/root/procs/ann        (it prints the stack)
aos-agent ctl add --name bob --ws /work ../agents/bob
```

XXX 是定義夾（不是資料夾＝`PathMissing`）。它的 `interfaces.json` 可以宣告 `aos-agent`（例如一個 `entry`）；沒有這個宣告，就直接啟動那個資料夾本身。同名＝`InstanceExists`；daemon 或 kernel 拒絕＝`AddRejected`。

- 工作區：`--ws DIR`，再來是非空的 `$AOS_WS`，再來是目前所在的資料夾；不是資料夾＝`WsMissing`，什麼都不送出。
- `--stack DIR` 選它的 stack（預設 `<daemon stack>/procs/<name>/`）。
- `--ws-json`、`--stack-json`、`--path-json` 存一個指示詞（directive），例如 `'{"$env": "PROJ"}'`；每次啟動都會重新解析。
- `--dotenv-override`：用 `aos-exec --dotenv-override` 啟動它，這樣它的 `.env` 可以蓋過已經設好的名字（存在那一列裡；只對那一跳有效）。
- `--auto-restart`：它每次結束，daemon 就重新啟動它；只用在一直開著的 agent。
- `--limits '{"mem_mb":512}'` 取代定義裡的限制（aos-sandbox 的那些鍵）；`'{}'`＝不限制。`--envs NAME=VALUE` 可以重複給。絕對不要把祕密放進 `--envs`：那個值會以明文存在 `procs/<name>/exec.json`（權限 666 減掉 umask，通常是 644），而且會出現在命令列上；MCP token 要放在伺服器檔的 `env_file`（見 eca 範本 cli.json 的 `mcp_servers`）。
- `--parent P`（誰要求它的，存成 `AOS_PARENT_STACK`）和 `--notify-box B`（它的通知寄到哪，`AOS_NOTIFY_BOX`）跟 `--envs` 一樣存進它的 envs；`--kit KIT` 把一個配給包疊到新的定義上（aos/kits.md）。
- `--on-queued ok`：過了 `--timeout-s` 信還在排隊時，以 0 結束。
- 要給已經在表上的 agent 換另一個定義：`aos-agent ctl set-def NAME DEF` 會停掉它（等這一輪結束）、把它卸下（它的 stack 留著），再用 DEF 在同一個 stack 上重新掛上。它的 stack（對話歷史、佇列、信箱）、工作區、限制和 auto_restart 都留著。表上立刻顯示 DEF，daemon 重新啟動後也還是 DEF。原本在跑的會用 DEF 重新開始；停著的繼續停著，睡著的繼續睡著。它卸下期間寄給它的信會被拒絕。不適用於用 `--envs`（或 `--parent`／`--notify-box`）掛上的 agent，也不能對自己用（`ArgumentsBad`）。
- 改名：`aos-agent ctl rm OLD`（stack 留著），然後 `aos-agent ctl add -n NEW -s <old stack> [-w <ws>] [--auto-restart] <definition>`。stack 資料夾不會搬動（它的路徑還是舊名字；這沒關係）。這段期間寄給 OLD 的信會被拒絕。用 `--envs` 掛上的，要再給一次它的 `--envs`。

**`#/ctl ls and ctl state`**

# ctl ls 與 ctl state

```sh
aos-agent ctl ls                 # NAME STATE WORKSPACE QUEUED REASON (TAB-separated)
aos-agent ctl ls -l              # + QUEUE RESTARTS COOLDOWN LAST ERROR
aos-agent ctl state -t bob       # one line per part
aos-agent ctl state -t bob tools history   # only these parts, in full
```

表是空的就什麼都不印。`-j` 印 JSON。`state`（別名 `status`）有這些部分：who、state、tools、llm、system、hooks、history、mailbox、subagents、resources、time；要看細節就給部分的名字，或給 `all`。`state tools` 列出每個工具，如果 agent 改過它的工具，最後會有一行 `own: N listed, M set to null (...)`。

**`#/Stop, sleep, pause`**

# 停止、睡、暫停

```sh
aos-agent ctl stop bob     # finish this round; stopped; back with start
aos-agent ctl start bob
aos-agent ctl sleep bob    # SIGTERM now; sleeping; back with wake (or a daemon restart)
aos-agent ctl wake bob
aos-agent ctl pause bob    # hold between steps; back with resume
aos-agent ctl resume bob
```

配錯對會得到 `PhaseBad`（`ann is stopped; use start (wake only wakes sleeping ones)`）。已經是那個狀態的話，就是成功但什麼都不做（`already asleep (sleeping)`）。`stop`、`pause`、`sleep` 和 `rm` 可以加 `--no-wait`（daemon 一收到請求就返回；agent 停掉自己就是這樣做的）。一個很長的步驟可能讓 pause/resume 延後。rm 和 set-def 會先關掉畫面；正在回覆的畫面可以用 `SessionBad` 拒絕。stop 和 sleep 不碰畫面：eca 會從它的 after_stop hook `screen_linger_stop` 在 cli.json `screen_close_after_s` 秒後關掉畫面（預設 600，0＝立刻；`aos/cli/eca.md#/Delayed screen closure`），除非它在那之前又啟動了；`aos-agent close` 立刻關掉。有設 `$AOS_KERNEL` 又沒給 `--daemon` 時，add、start、stop、sleep、wake 和沒帶 `--purge` 的 rm 會經過 kernel，而且只讀那封信的回覆：這裡講的名字檢查（`InstanceExists`）、讀表和關畫面都不會發生，start、stop、sleep、wake 和 rm 會印出 `... accepted for NAME`。移除：`aos/cli/safety.md#/Removing an agent`。整個 daemon：`aos/cli/daemon.md#/shutdown: stop the whole daemon`。

**`#/Finding agents and stacks`**

# 找 agent 和 stack

```sh
aos-agent ctl where bob          # its stack
aos-agent ctl where --ws bob     # its workspace
aos-agent ctl who                # the owner of $AOS_STACK, also from a nested tool stack
aos-agent ctl who --stack /path/to/stack --json
# {"name": "ann", "stack": "...", "ws": "...", "def": "...", "daemon": "...", "parent": null, "notify_box": null}
```

`parent` 和 `notify_box` 是提出要求的人在 add 時寫的（`--parent`、`--notify-box`），不是證明。

在 where 裡不要同時用 `--stack` 和 `--ws`。who 讀的是 daemon 的表，不是上層資料夾。有設 $AOS_KERNEL（又沒給 --daemon）時，who、ls、where 和 state 會先送 {"procs_state_path": true} 給 $AOS_KERNEL，再讀回覆裡指名的表檔；--timeout-s（預設 3）內沒有回覆＝KernelFailed，不會退回去用 $AOS_DAEMON。--daemon D 直接讀那個 daemon。
