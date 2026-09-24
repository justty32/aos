← [daemon](README.md)｜[spec 總導航](../README.md)

# 2. 孩子怎麼拉

（2026-09-24 proto5-2 池式納入：沒有 `spawn` 這個 method 了——daemon 照 `pool.json` 的宣告自己每圈把孩子補到位（§4）；孩子只留 fd 0 一條 pipe。
拉的順序、process group、每次重讀 target 沒變。）

第 i 號孩子的目標＝宣告的 `target` 樣板把 `{name}` 換成 i（§3）。照 [aos-exec](../aos-exec/README.md) 讀（三種目標、base、指示詞都照它）——**每次拉都重讀**，
包括重拉；檔被改了就照新的拉、檔不見了就 `SpawnFailed`。串流有兩點不同：

- **只有 fd 0 接成控制 pipe**（範式 §3）：daemon 寫、孩子讀 `go`／`stop`、看 EOF。**孩子的 fd 1 接 `/dev/null`**（第 1 版是另一條 pipe，孩子本來就不往上寫，開檔數因此減半）。
  inst 裡寫了 `stdin`／`stdout`＝拉不起來、進 `failed`（會被接管，寫了就是誤會；第 1 版是 `spawn` 回 `-32602`）。stderr 照 inst（沒寫＝/dev/null，kernel 替 cpu 寫的 inst 是接 `cpu.log`）。
- 孩子放進**自己的 process group**，但**同一個 session**：終端的 Ctrl-C 只打到 daemon，由 daemon 走階梯；
  daemon 死了孩子不會被 SIGHUP 帶走，靠 pipe EOF 自己溫和停。

**拉的順序（`go` 握手，範式 §6.1）**：fork → **寫 kids 檔**（pid、`running`、`gen`+1）→ 往它的 fd 0 寫一行 `{"jsonrpc":"2.0","method":"go"}`。
孩子等到 `go` 才開始碰它的家；daemon 崩在寫檔之前，孩子讀到的是 EOF、什麼都沒碰就退——不會有「沒人記得的孤兒還在改家」。
崩在寫檔之後：新任 daemon 開機照 kids 檔把它殺掉，再照宣告拉一顆新的（§6.1）。kids 檔寫不進去：不送 `go`、直接關 fd 0，當成死了。

**pipe 端點誰拿著**（範式 §5.1 要求「寫端不能漏」）：每條 pipe 的兩個端點都在 daemon 手上開的，全部標 close-on-exec；
拉孩子時只把它自己的讀端 `dup2` 到 fd 0，其他一律不傳（`close_fds`）。所以 A 孩子拿不到 B 孩子的寫端，B 的 EOF 不會被 A 卡住。
孩子那邊再把 fd 0／1 搬走、標 close-on-exec，是範式 §6.1 的事（fd 1 是 `/dev/null` 也照搬，不用改程式），孫子拿不到。孩子死了 daemon 就關它的寫端。

**pipe 怎麼寫**：daemon 忽略 `SIGPIPE`；用非阻塞 I/O，不讓任何一個孩子卡住主迴圈。fd 0 那條只寫 `go` 跟 `stop` 各一行；
寫失敗（EPIPE）＝孩子那頭讀端關了＝它在死的路上或已經死了，階梯直接跳到下一階（EPIPE 不證明它死了，只證明它不聽了）。

**拉不起來**：`target` 讀不到、不存在（不管是不是 `.json`）、資料夾目標缺 `dir_target` 指的檔、inst 壞掉、fork 失敗（aos-exec 的 kind=aos）
一律是 `SpawnFailed`：那號進 `failed`、stderr 一行帶 aos-exec 的代號、照退避再試（§4）。不造 pid、不寫 exit 檔。
第 1 版是「`spawn` 回錯、不登記」；現在沒有人等回音，失敗記在 kids 檔與摘要的 `failed`。

**誰能當孩子**：只有遵守範式 §6.1 控制 pipe 契約的程式（等 `go`、認 `stop`、EOF 就溫和停）——現在就是 `aos-cpu`。
一般工作程式不是 daemon 的孩子，是 exec cpu 跑的。
