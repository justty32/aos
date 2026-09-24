← [daemon](README.md)｜[spec 總導航](../README.md)

# 2. 孩子怎麼拉

`spawn` 的 `target` 照 [aos-exec](../aos-exec/README.md) 讀（三種目標、base、指示詞都照它）——**每次拉都重讀**，
包括重拉；檔被改了就照新的拉、檔不見了就 `SpawnFailed`。串流有兩點不同：

- **fd 0、fd 1 一律接成控制 pipe**（範式 §3）：fd 0 daemon 寫、孩子讀；fd 1 孩子寫、daemon 讀。
  inst 裡寫了 `stdin`／`stdout` ＝ `-32602`（會被接管，寫了就是誤會）。stderr 照 inst（沒寫＝/dev/null，
  kernel 替 cpu 寫的 inst 是接 `cpu.log`）。
- 孩子放進**自己的 process group**，但**同一個 session**：終端的 Ctrl-C 只打到 daemon，由 daemon 走階梯；
  daemon 死了孩子不會被 SIGHUP 帶走，靠 pipe EOF 自己溫和停。

**拉的順序（`go` 握手，範式 §6.1）**：fork → **寫孩子表**（pid、`running`）→ 往它的 fd 0 寫一行
`{"jsonrpc":"2.0","method":"go"}` → 寫回音。孩子等到 `go` 才開始碰它的家；daemon 崩在寫表之前，
孩子讀到的是 EOF、什麼都沒碰就退——不會有「沒人記得的孤兒還在改家」。崩在寫表之後、回音之前：
孩子在表裡、正常在跑，客戶收不到回音會重送 `spawn`，同名同目標 → 回它的 pid（冪等）。

**pipe 端點誰拿著**（範式 §5.1 要求「寫端不能漏」）：每條 pipe 的四個端點都在 daemon 手上開的，
全部標 close-on-exec；拉孩子時只把它自己的讀端／寫端 `dup2` 到 fd 0／1，其他一律不傳（`close_fds`）。
所以 A 孩子拿不到 B 孩子的寫端，B 的 EOF 不會被 A 卡住。孩子那邊再把 fd 0／1 搬走、標 close-on-exec，
是範式 §6.1 的事，孫子拿不到。孩子死了 daemon 就關它那兩個端點。

**pipe 怎麼讀寫**：daemon 忽略 `SIGPIPE`；兩條都用非阻塞 I/O，不讓任何一個孩子卡住主迴圈。
fd 1 那條讀走就丟，不拿來做決定（現在孩子不會往上寫；不讀會塞住孩子，所以要讀）。
fd 0 那條只寫 `go` 跟 `stop` 各一行；寫失敗（EPIPE）＝孩子那頭讀端關了＝它在死的路上或已經死了，
階梯直接跳到下一階（EPIPE 不證明它死了，只證明它不聽了）。

`target` 讀不到、inst 壞掉、起不來（aos-exec 的 kind=aos）：`spawn` 回 `error.code=-32000`、`data.code="SpawnFailed"`，
`message` 帶 aos-exec 那一行（含它的代號）；不登記。
（09-24 補）target 不存在（不管是不是 `.json`）、資料夾目標缺 `dir_target` 指的檔，在這裡也一律是 `SpawnFailed`——
不照同步 aos-exec 分成用法錯；只有 inst 顯式寫了 `stdin`／`stdout` 的 `-32602` 不變。起不來時不造 pid、不寫 exit 檔。

**誰能當孩子**：只有遵守範式 §6.1 控制 pipe 契約的程式（等 `go`、認 `stop`、EOF 就溫和停）——現在就是 `aos-cpu`。
一般工作程式不是 daemon 的孩子，是 exec cpu 跑的。
