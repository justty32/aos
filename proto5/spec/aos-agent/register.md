← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 11. `start`／`stop`：登記進 kernel

**`aos-agent start [--target DIR]`**：

1. 讀驗 `info.json`（不過＝退 1）；K＝`AOS_KERNEL_HOME`。
2. **查 K 的退出碼約定相不相容**：讀 `K/info.json`（讀不到、不是 JSON、頂層不是字面物件＝`NotAHome`、退 1），**只解驗 `done_exit`、`bad_after` 兩格**：
   型別與預設照 kernel.md §1.1（沒寫＝100、10），帶原文件與位置、中心 K 解（`$ref:""`、相對 `$at` 照常定位）；其他格不解不驗，
   start 端只需要這兩格用到的 `$env`。這兩格解不開或型別錯＝那個代號、退 1。
   `tick` 會回 0／101／102／1，所以 `done_exit` 是 1、101 或 102（09-24 停車加）＝`KernelIncompatible`、退 1、不登記（kernel 判回音時先比 `done_exit`，
   撞到就會把 agent 當成「做完了」永久停排）。`done_exit` 是 0（關掉）或其他值都行。`bad_after` 是 0＝關掉退件，agent 一直退 1 也不會被標 `bad`，照登記。
   （09-24 停車）再看 K 認不認得停車：K 帳本讀得到、有 `chain`（真的 boot 過）、而 `features` 裡沒有 `"park"`＝`KernelIncompatible`（舊 kernel 把 102 當失敗，十次就 `bad`）、退 1，訊息叫人升級 kernel 後 `aos up`（或 boot）一次再 start；帳本不在（還沒 boot 過）或讀不懂就不擋。
   （2026-09-24 one-boot）帳本是 `K/ledger.sqlite`，用跟 `aos-kernel proc` 同一支 lib（`lib/aos_kernel_store.py`）讀 `chain`、`features` 兩個鍵。K 還是舊的 `K/state.json`（沒有 `ledger.sqlite`）＝`KernelIncompatible`、退 1，訊息叫人先 `aos up`（或 boot）一次換成 sqlite 再 start。
   這只在 start 當下查；之後人改 K 的 info，要自己重查。
3. `tick.json` 不在就寫一份；在就讀它記的 K（`envs.AOS_KERNEL_HOME`）：是字面字串且等於現在的 `AOS_KERNEL_HOME` 才照用，否則（不同、不是字串、檔讀不懂）＝`KernelMismatch`、退 1，
   stderr 說「tick.json 綁在另一個 K，要換就刪掉 tick.json 再 start」。寫出來的長這樣（09-24 fix-r4 改：`--target`、`AOS_KERNEL_HOME`）：

   ```json
   {"_metainfo": {"_type": "posix", "_version": 1},
    "argv": ["aos-agent", "tick", "--target", "/abs/agent-bob"], "cwd": "/abs/agent-bob",
    "envs": {"AOS_KERNEL_HOME": "/abs/K"},
    "stderr": {"$opt": ["append", "mkdir"], "$val": "/abs/agent-bob/log/agent.err"}}
   ```

   `.tmp` 再 rename 寫，所以「在」就是完整的。`aos-agent` 靠 `tick.pool` 那顆 cpu 的 PATH 找。
   （09-24 fix-r4 補）**舊版的 tick.json**（沒有 `envs.AOS_KERNEL_HOME`、只有舊鍵 `envs.AOS_K`）：舊鍵的值等於現在的 K 就**照上面的樣子重寫一份**再登記（舊的 argv 是位置參數，新版 tick 不收）；不等＝`KernelMismatch`。
   `stop`、`status`、`say` 讀「tick.json 記的 K」時也認舊鍵。
4. 放單並等回音（最多 10 秒），等於替人打：

   ```sh
   aos-kernel add /abs/agent-bob/tick.json --target "$AOS_KERNEL_HOME" --name agent-<資料夾名> --pool <tick.pool> [--interval-ms <tick.interval_ms>]
   ```

   `interval_ms` 沒寫就不帶（用 kernel 的預設）；不帶 `timeout_ms`、不帶 `--once`。收到回音就 ack。

**`aos-agent stop [--target DIR]`**：（09-24 試玩 r1 補）**不讀 info**（設定壞了也停得掉）：家是資料夾就行；只讀 `tick.json`——它記的 K 是字面字串且不等於現在的 `AOS_KERNEL_HOME`＝`KernelMismatch`、退 1，
讀不懂或不在就不管。（09-24 試玩 r2 補）沒設 `AOS_KERNEL_HOME` 就用 `tick.json` 記的那個（字面絕對路徑才算）；兩個都沒有＝用法錯 2。然後等於 `aos-kernel rm agent-<資料夾名> --target "$AOS_KERNEL_HOME"`，等回音最多 10 秒、ack。不查 done_exit。

（09-24 試玩 r1 補）成功時 stdout 印一行：start 印 `started agent-<資料夾名>`、stop 印 `stopped agent-<資料夾名>`（stop 只是撤銷排程，正在跑的那格照樣跑完，見下）。

start／stop 的 request 檔名是 `aa-<資料夾名>-<epoch ns>-<pid>.json`（id 同名去掉 `.json`）。**等回音逾時**：stderr 印一行
`aos-agent: ReadFailed: 等回音逾時，回音會出現在 <K>/responses/<檔名>，讀完自己放 ack（cpu.md §3.3）`、退 1——
操作可能已經生效，不會撤回；那則回音 agent 之後不會再管。

（09-24 fix-r5 補）**已登記退 0**：`start` 收到 `AlreadyExists` 時再查一次 K 帳本那一筆（2026-09-24 one-boot：用 `aos-kernel proc` 同一支 lib，只讀那一列）：`procs.agent-<資料夾名>` 在、`target` 就是這個家的 `tick.json`、它正在跑的那格沒標 `discard`（被 `rm` 了、還在跑）、`status` 不是 `bad`＝印 `already started agent-<資料夾名>`、退 0（每天開機腳本 `set -e` 不會斷）。
其他 `AlreadyExists`（上次 stop 的那格還在跑＝`discard` 那格；被判 `bad`；同名但別的家）照舊退 1，訊息各補一句：`discard`＝「上次 stop 的那格還在跑，等它跑完再 start」、`bad`＝「已登記但被判 bad，看 log/agent.err 修好後 stop 再 start」、別的家＝「同名行程是 <那個 target>，改資料夾名」。

退出碼：0＝kernel 回了 `{"name"}`，或（fix-r5）已登記；1＝`KernelIncompatible`、`KernelMismatch`、kernel 回 `error`（`AlreadyExists`：已登記或上次 stop 的那格還在跑；
`-32602`：池不在 K；`NotFound`）、讀驗錯、放檔錯、等回音逾時；stderr 一行 `aos-agent: <代號>: <白話>`；2＝用法錯。

stop 之後：正在跑的那格會跑完（kernel 丟掉它的回音）；當批送出去的工作照跑，回音留在 K，下次 start 之後再收。
kernel 行程名只看資料夾名，不同位置的兩個同名資料夾會撞 `AlreadyExists`（保證外，改資料夾名）。
`bad_after` 非 0 時，連續退 1 達那個次數 kernel 會把 agent 標 `bad` 不再排（是 0 就一直重跑）。被標 `bad` 後：看 `log/agent.err` 修好，再 `stop`（`rm` 刪得掉 `bad`）、`start`。
