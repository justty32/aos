← [入口](README.md)｜涵蓋：規劃（fable 11-02 晚第二版，照使用者決定與實測改寫；可翻案） › 4. 資料夾程式長什麼樣、怎麼請 daemon 掛起、5. 使用者在 shell 怎麼用｜上一份 [05-3-loop-那半-控制器](05-3-loop-那半-控制器.md)｜下一份 [07-6-要動的程式與步驟表-不實作](07-6-要動的程式與步驟表-不實作.md)

### 4. 資料夾程式長什麼樣、怎麼請 daemon 掛起

```
agents/resident_bob/            ← C-54：資料夾名小寫加底線
  _entry                        ← install（Python 小殼，十幾行）：建 bob 小格與 FIFO、add bob（有殘留就 --resume）、add bob_ctl
  README.md                     ← 玩法（第 5 節）
  bob/
    _entry.json                 ← 第 2 節那張單子
    system.txt                  ← 現有 bob 的，多兩句
  ctl/
    _entry.json                 ← {"argv": ["aos-loop", "loop.json"], "stdout": FIFO}
    loop.json                   ← {"exec": "relay", "interval_ms": 300, "ctl": "loop_ctl.json", "state": "loop_state.json"}
    relay/
      _entry                    ← 第 3 節的身體（Python）
```

- **`_entry`（install）做四件事然後結束**——這就是「配合 daemon 進行 exec 和 loop 的掛起」：① `D=$AOS_DAEMON_STACK`（沒設＝退 1 `DaemonMissing`，同 aos-daemon-ctl、N-63）；`mkdir -p $D/loops/bob`、`mkfifo $D/loops/bob/in.fifo`（已在就跳過）。② 讀 `$D/loops/bob_ctl/relay_state.json` 的 `session_id`：有＝`aos-daemon-ctl add --name bob <自己>/bob -- --resume <id>`（**起來時續接殘留**，使用者決定；⑩）、沒有＝`aos-daemon-ctl add --name bob <自己>/bob`。③ `aos-daemon-ctl add --name bob_ctl <自己>/ctl/_entry.json`。④ stdout 印兩個信號與一句「掛上了：`aos-say --stack $D/loops/bob_ctl 話`」。它不跑 bob、不跑 loop、不留行程；跑第二次＝重掛（表上已有的照 N-54「已在跑的不重起」，等於沒事；兩個都做完了就重新起）。寫 Python 不寫 sh（user/03）。
  - 先 add bob 再 add bob_ctl：控制器的 aos-exec 開 FIFO 寫端會**等到 bob 開了讀端**，bob 的 aos-exec 開讀端會等到有寫端——兩個都在 daemon 底下並行，誰先誰後都接得上；但只掛了控制器沒掛 bob，控制器會一直卡在 `open`，表上 `running` 卻什麼都沒做。
  - 殘留的 session 接不回（claude 那邊刪了）：bob 起來就退非 0 → `relay` 第 1 步看到 bob 不在 → 退 1；人刪掉 `relay_state.json`（或只刪 `session_id`）重跑 install 就是新對話。
  - 工作區：兩個子項都不給 `--ws`＝繼承 daemon 的 `AOS_WS`（bob 的 `--add-dir` 拿到 `ws/`）。要服務別的工作區＝install 多收 `--ws` 原樣轉給兩個 add（第二版；`<WS>/.stack` 的捷徑只會指到先 add 的那一隻——指到 `bob_ctl` 才有用，所以那時改成先 add bob_ctl）。
  - 為什麼不讓 install 自己 `aos-post send` 一封 `execs_added`：aos-daemon-ctl 已包好轉絕對路徑、`--name`、`-- 參數`；`execs` 雖然 11-02 晚起收內嵌單子，但本題兩個目標都是現成的檔，不需要。
- **daemon 要給子項 `AOS_DAEMON_STACK`**：控制器的單子（FIFO 路徑）、`relay`（讀 `loops_state.json`、叫 `aos-daemon-ctl`）都要知道 daemon 的 stack 在哪；兄弟之間沒有父子交代，只有共同的上一代能告訴他們（N-64 ④「用 hub 型變數」）。daemon-env 方向題 2 使用者裁「等常駐 bob 用到再說」——就是現在（[衝突 2](12-要使用者看的衝突與方向題-11-02-晚.md#衝突-2兄弟要共用位置--daemon-得把-aos_daemon_stack-設給子項)）。只設這一個（不設定義資料夾與 ws 三名，使用者 11-02 定）。
- **daemons/main 的 `daemon.json` 不用改**（state-window 裁定後的 `daemon_ctl.json`／`daemon_state.json`、`loops_ctl_mailbox`）；bob 與 bob_ctl 用信掛、不寫進 daemon.json，daemon 重起不會自動回來（[衝突 4](12-要使用者看的衝突與方向題-11-02-晚.md#衝突-4n-28子項結束不重起vs常駐)）。要開機就掛可以寫死 `"execs": {"bob": "../../agents/resident_bob/bob", "bob_ctl": "../../agents/resident_bob/ctl/_entry.json"}`（FIFO 仍要先建一次；`--resume` 寫不進靜態的 daemon.json，開機掛＝新對話）。

### 5. 使用者在 shell 怎麼用

```sh
# 視窗一：起 daemon（照 11-02 試驗場 daemon）
cd ~/code/playground && source env.sh && cd ws
aos-exec ../daemons/main

# 視窗二
cd ~/code/playground && source env.sh && cd ws
export AOS_DAEMON_STACK=$PWD/.stack            # daemon-env 定案的名字

aos-exec ../agents/resident_bob                # 掛上：mkfifo、add bob（有殘留就 --resume）、add bob_ctl
aos-daemon-ctl ls                              # bob exec running、bob_ctl exec running（兩個都 running 才算掛好）

S=$AOS_DAEMON_STACK/loops/bob_ctl              # 之後都對控制器的小格說話
aos-say --stack $S "在 env:AOS_WS 寫一首詩，詠桃花，檔名 peach.txt。" && aos-listen --stack $S   # 等這題答完、印 bob 的回答（11-02 晚起 listen 不收信號、等最新那封）
aos-say --stack $S "再把它改成七言。"; aos-say --stack $S "加個標題。"   # 連丟兩句：忙時會被併成一題、一個回答回兩封（正常）
aos-listen --stack $S --last 3                 # 最近三段（幾則 user＋一則回答）
aos-listen --stack $S --follow                 # 像 tail -f 跟著看
tail -f .stack/loops/bob/out.jsonl             # 原汁事件流（工具呼叫、花費、session_id）
cat .stack/loops/bob/stderr.txt .stack/loops/bob_ctl/stderr.txt   # 出錯看這裡
cat $S/relay_state.json                        # bob up/asleep、session_id、還在答的信

echo '{"paused": true}'  > $S/loop_ctl.json    # 暫停：新信排著、bob 閒著
echo '{"paused": false}' > $S/loop_ctl.json    # 續

# 停掉（都會讓兩個都走）
echo '{"stopped": true}' > $S/loop_ctl.json    # 控制器收工 → 管子關 → bob 答完手上那題退 0（最溫和）
aos-daemon-ctl rm bob_ctl                      # 同上，由 daemon 送 SIGTERM 給控制器
aos-daemon-ctl rm bob                          # 急停：bob 立刻退 143、丟掉手上那題；控制器下一輪看到它不在、退 1

# 再起來＝續接同一段對話（relay_state.json 還在、有 session_id）
aos-exec ../agents/resident_bob
rm $S/relay_state.json && aos-exec ../agents/resident_bob     # 要開新對話就先把殘留刪掉
```
