家機用 Python 標準庫加 unshare／setpriv 做的玩具 daemon（自己是 PID namespace 的 1 號、唯一碰 Linux 權力的程式），把「daemon 當容器、kernel 接住名字」第四輪列的十項一次跑完，十項全過；最大的發現是同一個 uid 的 proc 會走 /proc/<PID>/root 看進 daemon 與別人的天空，上鎖要多鎖這一塊。

# 天空小實驗：daemon 當容器、kernel 接住名字（11-25 晚，spike，不是正式實作）

← [proto9](../../README.md)｜前情：[daemon當容器-1125](../../../proto8/thinking/2026-11/25/daemon當容器-1125.md)

這是玩具，只為了驗[第四輪](../../../proto8/thinking/2026-11/25/daemon當容器-1125.md#第四輪11-25-晚第-34-段)列的十項。設定的寫法、daemon 收的指令都是這次隨手定的，不是提案；草稿 01 沒動。全程不用 root、不用 sudo，不打任何外部網路（假的上游只聽 127.0.0.1）。

## 怎麼跑

```
cd proto9/experiments/sky-1125
python3 run.py                           # 約 3 秒；每項一行 PASS/FAIL/SKIP，最後一行 SUMMARY；全過退出碼 0
python3 run.py -v                        # 每項的細節全印
python3 run.py --pause                   # 第 8 項殺 daemon 前停住，可另開殼看：python3 sky.py ns <daemon.sock> drawer
python3 run.py --no-systemd --no-subuid  # 假裝沒有 systemd --user、沒有 subuid（第 9、10 項 SKIP）
```

- 用 `run.py` 不用 `run.sh`：使用者 10-15 定過「少用 sh」。
- 要有：user namespace（一般使用者能開）、util-linux 2.38 以上的 `unshare`（要 `--map-users`）與 `setpriv`、Python 3.12 以上。第 9 項要 `/etc/subuid` 有自己的範圍和 `newuidmap`；第 10 項要 `systemd --user`。syscall 號碼寫死 x86_64。
- 每次開一個新的 `/tmp/sky-1125-XXXXXXXX`，結束時刪掉。daemon 做的東西全放在它自己 mount namespace 裡的一塊 tmpfs（像一塊只有它看得到的白板），daemon 一死就跟著消失。`run.py` 最後印一行 cleanup，查過沒有留下行程、掛載、cgroup、systemd unit。
- `run.py` 自己被 `kill -9` 也不留行程（子行程設了 parent-death signal，實測過）；留下的暫存夾下一次跑會先清掉。

## 結果

家機 Manjaro，Linux 6.18.55，Python 3.14.7，util-linux 2.42.4，Landlock ABI 7。連跑多次都是 10 PASS；`--no-systemd --no-subuid` 是 8 PASS、2 SKIP。第 8 項放最後跑，因為它會殺掉 daemon。

| # | 驗什麼 | 結果 | 量到的 |
|---|---|---|---|
| 1 | 天空設定 | PASS | `leader.sky`（引進 `base.sky`）在 daemon 裡變成 22 列的表（14 個掛載＋8 個 symlink）。leader 的 `/proc/<PID>/mountinfo` 剛好 14 個掛載，一個不多一個不少；每個的來源（dev＋inode）、唯讀／可寫都對。4 隻 kernel 的天空也對得上。故意給錯的表（少了 /tmp、把 /etc 說成 /usr）會被抓到 |
| 2 | 名字交給 kernel | PASS | drawer 跑 `draw turtle`，退出碼 0；烏龜和 `drawn by draw-kernel (pid 2) for drawer (pid 14, uid 0)` 是 draw-kernel 直接寫進 drawer 的 stdout。外面的系統、leader 的天空都沒有 `/usr/bin/draw` |
| 3 | 只能往下傳自己有的 | PASS | 6 種給不出去的都被拒（見下面摺疊）；傳 leader 有的 `/toys` 成功 |
| 4 | 依賴鏈 | PASS | leader 問 perm-kernel，得到 `perm-kernel → draw-kernel`（perm-kernel 自己的天空也真的用了 draw）。選項 `no_cycles` 關著時 ring-a、ring-b 互相依賴也都登記成功，leader 問得到圈 `ring-a → ring-b → ring-a`，自己決定不用；選項打開後 ring-d 登記被拒 |
| 5 | llm proxy 是唯一出口 | PASS | drawer 的 network namespace 只有 `lo`；直接連上游 ECONNREFUSED，連 192.0.2.1 ENETUNREACH。走 `/srv/llm` 打 3 次：proxy 自己數到 36＋90＝126 token、記在 drawer 名下，跟 drawer 收到的加總一樣；上游收到 3 個請求，全部來自 proxy |
| 6 | 跑的時候改 | PASS | daemon 收到 `bind $TMP/live /srv/new`，正在跑的 watcher 看到 `hello.txt` 出現；表多了那一列（記成 live:user），還是跟 mountinfo 一對一 |
| 7 | 天空鎖住 | PASS | 鎖住的 proc（天空裡 uid 0）：umount、mount 不論直接呼叫還是跑指令都失敗；自己另開 user namespace 也卸不掉（EINVAL）；讀 `/proc/1/root`、旁邊 proc 的 `/proc/<PID>/root` 和 `/proc/<PID>/environ` 都 EACCES；送訊號給旁邊的 proc、連外面的 abstract socket 都 EPERM。對照一：不鎖時卸得掉 `/toys`，還能從 `/proc/1/root` 看到真的根目錄。對照二：只把 caps 清成 0 時 umount(2) 是 EPERM，下一次 execve 就全拿回來（`umount /tmp` 成功）。對照三：照樣上鎖但不加 Landlock，caps 全 0，卻還讀得到旁邊 proc 的天空和環境變數、送得了訊號、連得到 abstract socket |
| 8 | PID namespace | PASS | 從外面 `kill -9` daemon（外面一個 pid、裡面是 1），它那一片 17 支行程 0.05 秒內全部不見，systemd 的 scope 和 cgroup 也收掉。NSpid 例（每次不同）：draw-kernel 外面 1615148、裡面 2；drawer 外面 1615187、裡面 12 |
| 9 | subuid（加做） | PASS | alice（裡面 1001、外面 101000）、bob（裡面 1002、外面 101001）共用 `/shared`；bob 讀、寫 alice 的 0600 檔都 EACCES；那個檔在硬碟上屬於 uid 101000。全程沒有 root |
| 10 | cgroup 凍結（加做） | PASS | ticker（只會印數字，什麼界面都沒有）：凍住後 0.6 秒內 0 個 tick（`cgroup.events` 是 frozen 1），解凍後 0.6 秒 12 個。cgroup 只用 `systemd-run --user --scope -p Delegate=yes` 為這次開的那一塊 |

<details><summary>第 1 項：daemon 印出來的 leader 的表（像 Plan 9 的 ns）</summary>

```
# starter user  uid 0  gid 0  net host  lock on  state running
/                    tmpfs                                        ro  base.sky:3
/bin                 -> usr/bin                                       base.sky:6
/dev                 tmpfs (dev)                                  ro  base.sky:10
/dev/fd              -> /proc/self/fd                                 base.sky:10
/dev/full            bind /dev/full                               rw  base.sky:10
/dev/null            bind /dev/null                               rw  base.sky:10
/dev/random          bind /dev/random                             rw  base.sky:10
/dev/stderr          -> /proc/self/fd/2                               base.sky:10
/dev/stdin           -> /proc/self/fd/0                               base.sky:10
/dev/stdout          -> /proc/self/fd/1                               base.sky:10
/dev/urandom         bind /dev/urandom                            rw  base.sky:10
/dev/zero            bind /dev/zero                               rw  base.sky:10
/etc                 bind /etc                                    ro  base.sky:5
/lib                 -> usr/lib                                       base.sky:8
/lib64               -> usr/lib                                       base.sky:9
/proc                proc                                         rw  base.sky:11
/sbin                -> usr/bin                                       base.sky:7
/self                bind $RUN/procs/leader                       rw  base.sky:14
/srv/daemon          bind $TMP/daemon.sock                        rw  leader.sky:3
/tmp                 tmpfs                                        rw  base.sky:12
/toys                bind $TOYS                                   ro  base.sky:13
/usr                 bind /usr                                    ro  base.sky:4
```

最後一欄是這一列從哪一行設定來的。drawer 的表多了這三列（其餘從 leader 抄來，最後一欄寫成 `leader:base.sky:4` 這樣）：

```
/srv/draw-kernel     kernel draw-kernel (socket)                  rw  drawer.mods:2
/srv/llm             kernel llm-proxy (socket)                    rw  drawer.mods:3
/usr/bin/draw        kernel draw-kernel (exec)                    ro  drawer.mods:2
```

</details>

<details><summary>第 3 項：被拒的六種，daemon 回的原文</summary>

| 情況 | 起的一方寫的 | daemon 回 |
|---|---|---|
| 自己天空裡沒有 | `bind /var /var` | `/var is not in leader's sky (it falls on /, a root made fresh for leader)` |
| 唯讀想給可寫 | `bind -w /toys /toys` | `/toys is read-only in leader's sky; it cannot hand out write access` |
| 用 symlink 指到外面 | `bind /self/escape /hostroot`（leader 先在 /self 放了指向 /home 的 symlink） | `/self/escape leaves /self through a symlink or is missing (open escape: Invalid cross-device link)` |
| 給別的身分 | `uid 1001` | `leader runs as 0:0; it cannot give out identity 1001:1001` |
| 不上鎖 | `lock off` | `only the user can start an unlocked sky` |
| 自己沒網路卻給網路 | `net host`（起的一方是 `net none` 的 netless） | `netless has no host network to hand on` |
| （對照）自己有的 | `bind /toys /opt/toys2` | 成功，孩子列得出 /opt/toys2 裡的檔 |

</details>

## 檔案

| 檔 | 是什麼 |
|---|---|
| `run.py` | 跑全部十項、每項印一行、收尾檢查 |
| `daemon.py` | 玩具 daemon：PID namespace 的 1 號；起 proc、記每隻的表、kernel 公告欄（登記與依賴）、跑的時候改、cgroup 凍結 |
| `sky.py` | 函式庫：讀設定、從起的一方的表算出孩子的表（「只能往下傳自己有的」在這裡）、在 fork 出來的子行程裡組天空、上鎖、跑的時候掛、表與 mountinfo 對照、daemon 的用戶端。`python3 sky.py ns <daemon.sock> <名>` 印某隻 proc 的表 |
| `toys.py` | 天空裡跑的小程式：draw-kernel、perm-kernel、llm-proxy、ring kernel、leader、drawer、watcher、locktest、idtest、ticker、netless；另有在外面跑的假上游 |
| `base.sky`、`kernel.sky`、`perm.sky`、`leader.sky` | 天空設定（純文字，一行一條） |
| `drawer.mods` | leader 起 drawer 時寫的修改：drawer 的天空＝leader 的天空＋這幾行 |

想看做法，先看 `sky.py` 的 `compose`（算表）和 `build`（組天空），再看 `daemon.py` 的 `op_spawn`。

## 做法與理由

### 設定怎麼寫

一行一條，`#` 後面是註解；`include FILE`（或 Plan 9 的 `. FILE`）引進另一份。

| 寫法 | 意思 |
|---|---|
| `tmpfs PATH` | 一塊新的空 tmpfs；`tmpfs /` 是天空的根（組好後改成唯讀） |
| `bind [-w] SRC DST` | 把 SRC 掛到 DST；預設唯讀，`-w` 才可寫 |
| `mount KERNEL [DST]` | 選用某個 kernel 提供的名字；DST 不寫就用它登記的路徑 |
| `unmount PATH` | 拿掉從起的一方抄來的某一條（連同底下的） |
| `symlink TARGET PATH`、`dev PATH`、`proc PATH` | symlink；最小的 /dev（null、zero、full、random、urandom）；procfs |
| `net none`／`net host` | 新的 network namespace（只有 lo）／daemon 的網路；不寫就跟起的一方一樣 |
| `uid U [G]`、`lock off` | 身分；不上鎖（只給對照實驗用） |

`$TOYS`（這個夾）、`$RUN`（daemon 的 tmpfs）、`$TMP`、`$DAEMON`（daemon 的 socket）、`$SELF`（這隻 proc 自己的私有夾）只有使用者自己的設定能用；proc 寫的都是它自己天空裡的路徑。

### 天空怎麼組、表怎麼對

daemon fork 一個子行程，子行程：開新的 mount namespace（要的話再開 network namespace）→ 掛一塊新的 tmpfs 當根 → 照表一條一條掛上去（bind 都不帶底下的子掛載）→ pivot_root 進去、把舊的根卸掉 → 上鎖 → exec 那隻 proc 的程式。pivot_root 之後，它只看得到表上的東西。

- 「要的」表在 daemon 記憶體裡，`ns` 指令印出來。
- 「量到的」由 `run.py` 從外面讀 `/proc/<PID>/mountinfo`，每個掛載點用 stat 比對 dev＋inode，確認跟來源是同一個檔；也比唯讀／可寫，並且找出表上沒有的掛載。
- 根是從零組的（跟 bwrap 一樣），所以兩邊能一對一比。如果天空是「抄一份 daemon 的世界再蓋幾層」，mountinfo 會帶著整台機器幾十個掛載，只能比「表上的都有出現」。
- 孩子的天空是在「表」上算的：抄起的一方的表、套修改、再從零組出來。起的一方在跑的時候被改過（第 6 項那種），表也跟著改了，所以孩子拿到的就是改過的（照程式是這樣，沒測）。

### 把名字交給 kernel

kernel 是一隻普通的 proc，跟 daemon 登記「我提供 `/usr/bin/draw`，接口是我天空裡的 `/self/draw.sock`」。daemon 看它的表，把這個路徑換成真實位置，記在公告欄上。drawer 的設定寫 `mount draw-kernel /usr/bin/draw` 時，daemon 在 drawer 的天空裡：

- 把 kernel 的 socket 掛到 `/srv/draw-kernel`；
- 在 `/usr/bin` 疊一層 overlay，上層只有一支小程式 `draw`。

`draw` 一跑，小程式就連那個 socket，把 argv 和自己的 0、1、2 號 fd 傳過去（unix socket 可以夾帶 fd，像把自家的信箱鑰匙交給對方），再等 kernel 回退出碼。kernel 直接寫進呼叫者的 stdout。呼叫者是誰：socket 上有 Linux 填的 pid（呼叫者改不了），kernel 再問 daemon「這個 pid 是哪隻 proc」（daemon 順著 PPid 往上找，回名字）。

### 「有」怎麼判（第 3 項的規則）

孩子的天空先抄一份起的一方的表，再套修改。修改裡：

1. `bind SRC DST`：在起的一方的表裡找 SRC 落在哪一列（最長的前綴，會跟著表裡的 symlink 走）。那一列必須是「從某處接過來的」：bind、kernel 的 socket、裝置檔。落在起的一方自己的新 tmpfs、proc、根上，就算「沒有」。
2. 那一列唯讀，就不能給 `-w`。
3. 從那一列的真實來源往下開檔時用 `openat2` 的 `RESOLVE_BENEATH`：路上碰到絕對路徑的 symlink，或用 `..` 爬出那一列，都拒絕。子行程組天空時會再開一次，中間被換成 symlink 也擋得住。
   - 不擋會怎樣（scratch 實測）：leader 在自己的 `/self` 放一個指向 `/home` 的 symlink，daemon 照真實路徑一跟，就把使用者整個 home 交給 drawer（天真的 bind 列出 `['lorkhan']`）。
4. `uid`：proc 只能給跟自己一樣的身分；換身分只有使用者能做。
5. `net host`：自己沒有 host 網路就給不出去。`proc`、`dev`：自己有才能給。`lock off`：只有使用者能下。
6. `mount KERNEL`：kernel 在公告欄上就能選。拿得到 daemon socket 的 proc 都看得到公告欄，像 Plan 9 的 `/srv`。這條是我定的，見最後「要使用者選的」第 2 題。
7. `/self`：每隻 proc 一定拿到自己的一個新私有夾，抄表時這一列換成孩子自己的。新開的空夾不算多給。

### 上鎖：天空裡用 uid 0，加 securebits、no_new_privs、清空 bounding set，再加 Landlock

選的是「天空裡用 uid 0 加鎖」，不是「用非 0 的 uid」。理由：

- 天空裡的 0 號＝外面的使用者本人。proc 在真資料夾裡寫的檔就是使用者的檔；agent 要改使用者的 repo，這是最常見的情況。改用非 0 的 uid 就得用 subuid，寫出來的檔在外面屬於 100xxx 那種帳號，使用者自己改不動。
- 另一種排法（像 podman 的 keep-id：天空裡的 1000＝外面的 1000，天空裡的 0 號換成 subuid）也行，但 daemon 自己的檔會變成 subuid 的，收尾要進 namespace 才刪得掉，比較繞。
- 要不同身分時（第 9 項），再用 subuid 給個別的 proc。

0 號的坑（第 7 項對照二量到）：只把 caps 清成 0，下一次 execve 時 Linux 又把全部 caps 給 0 號。所以最後由 `setpriv` 一次做完：

1. `--securebits=+noroot,+noroot_locked,...`：0 號在 execve 時不再特別，而且鎖住改不回來（實測 securebits＝0x2f）。
2. `--no-new-privs`：execve 拿不到比現在多的權限，setuid 位元、file capability 都沒用。
3. `--bounding-set=-all`、`--inh-caps=-all`、`--ambient-caps=-all`：就算算出來要給，上限也是空的。
4. `--reuid`／`--regid`／`--clear-groups`。

照 capabilities(7) 推：第 1 件單獨就擋得住「0 號 execve 拿回全部 caps」；第 2 或第 3 件單獨，連 setuid 程式、file capability 那條也擋。四件一起是保險。這次只實測了四件一起，加上對照二的「只清 caps」。另外兩件是這次撞到才加的（見下面坑 1）：daemon 自己設成 non-dumpable；每隻 proc 在 exec 前進一個自己的 Landlock domain。第九輪定了天空不是牆，Landlock 這件可以拿掉（`lock nolandlock` 就是拿掉後的樣子），見最後「要使用者選的」第 1 題。

### 跑的時候改

`nsenter` 進去再 `mount --bind` 做不到（scratch 實測）：天空裡根本沒有那個來源路徑；改走 `/proc/1/root/...` 得到 EINVAL，因為來源必須在同一個 mount namespace。做法是新的 mount API：daemon fork 一個小幫手，先在 daemon 這邊用 `open_tree(OPEN_TREE_CLONE)` 把來源複製成一個還沒掛上的掛載，再 `setns` 進那隻 proc 的 mount namespace，用 `move_mount` 掛上去。要新建掛載點時，幫手把天空的根暫時改成可寫，建好再改回唯讀。誰能下這道指令：使用者，或那隻 proc 的起的一方。

### PID namespace、subuid、cgroup

- `unshare --user --map-users=0:1000:1 --map-users=1:100000:65536 …（gid 同樣兩段）--mount --pid --fork --mount-proc` 起 daemon，它就是 1 號。對照表有兩段時，unshare 會叫 newuidmap、newgidmap 寫進去。
- daemon 是 1 號，沒裝處理的訊號從外面送也會被忽略（另外實測：`unshare -Urpf sleep` 的 sleep 收到外面的 SIGTERM 還活著）。所以 daemon 裝了 SIGTERM 的處理，收到就退出（實測過）；1 號一退出，底下整片就被 Linux 收掉（第 8 項）。
- 有 systemd --user 時，外面再包一層 `systemd-run --user --scope -p Delegate=yes --unit=sky-1125-…`。daemon 只認自己這個 scope（啟動參數帶 unit 名，核對 `/proc/self/cgroup` 對得上才用），每隻 proc 開一個子 cgroup `sky-<名>`，子行程 exec 前把自己寫進去。凍結就是寫 `cgroup.freeze`、等 `cgroup.events` 變成 frozen 1。

## 撞到的坑

1. **同一個 uid 的 proc 看得進別人的天空。** 天空裡掛的 /proc 是 daemon 那一層的，同 uid 的行程彼此能走 `/proc/<PID>/root`（還有 cwd、fd、environ）進去。daemon 是 1 號，`/proc/1/root` 就是真的系統。拿掉 caps 也擋不住：這是 Linux 的「讀別人行程」檢查，同 uid 就放行（這台的 Yama 只管 attach）。對照三量到了。修法：daemon `prctl(PR_SET_DUMPABLE, 0)`（擋 /proc/1/root），每隻 proc 一個 Landlock domain（擋旁邊的 proc；ABI 6 起順便擋訊號和 abstract socket）。
2. **0 號的 caps 會在 execve 時回來**，上面講過。
3. **`/proc/self/setgroups` 是 deny 時，`setpriv --clear-groups` 會失敗。** 沒有 newgidmap、只能用 `--map-root-user` 時就是這樣，只好改 `--keep-groups`：使用者原本的附加群組（wheel 等）會跟進天空，而且拿不掉。
4. **只有 lowerdir 的 overlay，每個掛載的選項看起來是 rw**（唯讀的是 superblock）。要再 remount 一次唯讀，表跟 mountinfo 才對得上。
5. **bind 不帶子掛載時，來源底下有「鎖住的」子掛載就 EINVAL。** 例如直接 bind 整個 `/`。所以 /dev 只 bind 幾個裝置檔。
6. **remount 唯讀時要帶上 Linux 不准拿掉的旗標**（nosuid、nodev、noatime 等，從 statvfs 讀）；不帶就 EPERM。
7. **fork 前要先 flush stdout**，不然子行程會把父行程緩衝裡的字再印一次（第一版原型撞到）。
8. util-linux 的 `umount` 在天空裡（uid 0 但沒有 caps）回的是「must be superuser to unmount」，不是「permission denied」；判斷要看退出碼。

## 還沒測的

- **kernel 死了以後**：它會從公告欄消失（有寫）；已經選用它的天空裡名字還在，連上去應該是 ECONNREFUSED。沒測。
- **由 proc 下「跑的時候改」**：規則寫了（只有使用者或那隻 proc 的起的一方），沒測。
- **加入起的一方的網路**：起的一方是 `net none` 時，孩子預設加入它那個 network namespace。寫了，沒測。
- **Landlock ABI 小於 6 的核心**（公司 WSL 的 6.6）：會退成只擋讀別人的 /proc，不擋訊號和 abstract socket，第 7 項照實寫出來（不會假裝過）。完全沒有 Landlock 的核心會略過那一步，旁邊的 proc 看得到彼此的天空，第 7 項會 FAIL。都沒在那種核心上跑過。
- **公司 WSL 有沒有 subuid、newuidmap、systemd --user**：沒查；`--no-systemd --no-subuid` 模擬過沒有的情況。
- **Claude Code 住進天空**：它認的是 `ANTHROPIC_BASE_URL`（http 網址），不認 unix socket。天空裡只有 lo，要多一支小轉接：在天空自己的 lo 上聽一個埠，轉到 `/srv/llm`。沒做。
- **不同身分的 proc 用 kernel**：kernel 以 uid 0 建的 socket 是 0755，照 Linux 規則別的 uid 連不上（connect 要寫入權）。照規則推，沒實測。
- **量與規模**：daemon 是單執行緒，一個不送字的連線（5 秒逾時）或一個組很慢的天空會卡住它；很多隻 proc、很多請求都沒試。

## 對介面或做法有影響的發現

這份是照第四輪的十項做的。做的同時，第八輪也量到「兄弟之間沒隔開」，第九輪定了「天空是共用的路由，不是牆；要牆就去隔壁的 daemon」。下面第 1 條跟那兩輪接得上，只是補資料，不是要翻案。

1. **「天空鎖住」只鎖 mount／umount 不夠。**
   - **daemon 自己那條要先堵**：daemon 是 1 號，同 uid 的 proc 讀 `/proc/1/root` 就看到整台真的機器，「看不到的東西」其實看得到，天空當路由也會失準。daemon 自己 `prctl(PR_SET_DUMPABLE, 0)` 一行就擋掉（對照三量到）。
   - **兄弟之間**：`/proc/<PID>/root`、`/proc/<PID>/environ`（API key 常放這裡）、送訊號、連 host 的 abstract socket（X11、D-Bus 那種），這次全量到了，也量到便宜的擋法：每隻 proc 在 exec 前進一個自己的 Landlock domain，四條一起擋掉。不用 root、不用換 uid、不用每隻一個 PID namespace（那樣還得另放一支小的 1 號）。讀 /proc 那兩條 Linux 5.13 起就擋得住，訊號和 abstract socket 要 6.12 以上。
   - 如果哪天要在同一台 daemon 底下加一道牆，這是最便宜的一道；不加，就照第九輪去隔壁的 daemon。
2. **「只能往下傳自己有的」要在真實的檔上判，不能只比路徑字串。** symlink 會把 daemon 帶到起的一方看不到的地方。而且不只是檔：身分、網路、/proc、/dev、不上鎖，也都要當成「有沒有」來判。
3. **「天空長什麼樣」能回答得精確，靠的是根從零組。** 表跟 mountinfo 一對一，`ns` 印出來的就是全部。抄 daemon 的世界再蓋幾層，就答不出「沒有什麼」。
4. **天空裡的 proc 還是能開自己的 user namespace。** 在那裡面它又有 caps，能在自己那份複本上掛新東西（實測 tmpfs 掛得上），但天空原本的掛載是鎖住的，卸不掉、翻不開（EINVAL）。所以它只能把自己的世界再縮小或蓋住，看不到更多。要完全不准，可以用 seccomp 擋開 user namespace，或把 daemon 那一層的 `max_user_namespaces` 設成 0；但那樣 daemon 就不能疊 daemon（疊的時候要多開一層 user namespace）。
5. **PID 只在一層有意義，介面裡用名字。** kernel 收到的是自己那層的 pid（drawer 外面 1615187、裡面 12）；daemon 用 socket 上的 pid 往上找成名字（`whois`），proxy 就能把量到的 token 記在 drawer 名下。外面連進來的（使用者）pid 是 0，daemon 用這點分出「使用者」和「天空裡的 proc」。
6. **天空裡看得到別隻 proc 的命令列。** /proc 是 daemon 那一層的，所以 argv 裡別放秘密。要藏起來，得每隻 proc 一個 PID namespace（但那樣它就成了自己的 1 號，沒裝處理的訊號會被忽略），或不同 uid 加 `hidepid`。
7. **跑的時候改要用新的 mount API**（open_tree＋move_mount，Linux 5.2 起）。舊的 `nsenter + mount --bind` 對 pivot_root 過的天空做不到。
8. **kernel 宣告的依賴可以跟它天空裡實際用的對照。** daemon 知道它的表裡掛了哪些 kernel，登記時多回一個「用了但沒宣告」的清單（perm-kernel 這次是空的）。軟性檢查可以多一個來源。
9. **daemon 當 1 號要自己裝 SIGTERM 的處理**，不然 `kill`、systemd 停 scope（先送 SIGTERM）都沒反應，只剩 SIGKILL 有效。

### 要使用者選的

1. 同一台 daemon 底下，每隻 proc 要不要預設進一個 Landlock domain（發現 1）：不加，照第九輪「天空不是牆」；加，等於多一道不用 root 的便宜的牆，兄弟就互看不到。
2. 天空裡的 proc 准不准自己再開 user namespace（發現 4）：准（daemon 能疊 daemon，proc 也能替自己再縮小）；或不准（用 seccomp 擋，要疊 daemon 時另開口子）。
3. 選用 kernel 要不要「起的一方自己先有」（第 3 項規則第 6 條）：現在是「公告欄上的都能選」；如果要更嚴，leader 得先替自己選用 draw-kernel，才能給 drawer。
4. 天空裡預設用 uid 0（＝外面的使用者，現在這樣），還是每隻 proc 預設各用一個 subuid（彼此天生隔開，但寫出來的檔不屬於使用者；第九輪提到的「把一個 uid 分給某隻 proc」，第 9 項就是這樣做的）。
