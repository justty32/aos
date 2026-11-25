用 Python 標準庫自己講 FUSE 核心協議（不靠 libfuse），做了玩具 aos proc 與玩具 daemon，在公司 WSL2 上實測 proto9「proc 掛出自己的目錄、別人走 /proc/<PID>/cwd 進去」：做得順，主要坑在 kill -9 後的殘留掛載、自己讀自己會卡死、bwrap 走不進 /proc/<PID>/cwd。

# FUSE 版玩具 aos proc 小實驗（11-25，spike，不是正式實作）

需求來源：[9p-proc-1125](../../../proto8/thinking/2026-11/25/9p-proc-1125.md)。檔案：

| 檔 | 是什麼 |
|---|---|
| `toyproc.py` | 玩具 aos proc＋最小 FUSE 伺服器（`fusermount3` 掛、自己讀寫 `/dev/fuse`）。檔：`status`、`ctl`、`settings`、`attrs` |
| `toydaemon.py` | 玩具 daemon：本身也是 toyproc，多 `procs/`（每項是指到 `/proc/<kid PID>/cwd` 的 FUSE symlink）與別名 `proc -> procs`；kid 死了收屍時順手卸它的掛載 |
| `try.py` | 把問題 1～8 跑一遍印結果（`python3 try.py [1 2 ...]`） |
| `bench.py` | 補充量測：執行緒數不同時一次 READ 來回、`cat status`、`stat` 的延遲 |

環境：核心 6.6.114.1-microsoft-standard-WSL2、FUSE 協議 7.39、fusermount3 3.14.0、Python 3.12.3。

## 結論

1. **掛得起來**。不靠 libfuse，Python 標準庫（`socket.recv_fds` 收 fd、`os.read/os.write` 讀寫 `/dev/fuse`、`struct` 打包）就夠，FUSE 那層約 190 行。
2. 殼裡 `ls`／`ls -l`／`cat`／`echo >`／`cd` 都正常，要處理的操作：INIT、LOOKUP、GETATTR、SETATTR、OPEN、READ、WRITE、FLUSH、RELEASE、OPENDIR、READDIR、RELEASEDIR、READLINK（daemon 的 symlink 要），其他一律回 ENOSYS；FORGET／BATCH_FORGET／INTERRUPT 絕對不能回。
3. `echo x > ctl` 實際送來：`LOOKUP → GETATTR → OPEN(O_WRONLY) → SETATTR(size=0) → FLUSH → GETATTR → WRITE("x\n") → FLUSH → RELEASE`。
4. **ctl 的鎖要在 OPEN 和 WRITE 兩處都擋**：只在 OPEN 擋，兩人先開好檔再寫就漏；只在 WRITE 擋也行，但殼裡的錯誤字不一樣（見問題 2）。被拒的那次不動 `aos_ctl_*`，實測做到了。
5. `/proc/<PID>/cwd/status`、`/proc/<daemon>/cwd/procs/<名>/status` 連穿兩層都通；`cd` 進去 `pwd -P` 看得到真實掛載點。
6. kill -9 後：`/proc/<PID>/cwd` **馬上** No such file；**掛載會留下**（`Transport endpoint is not connected`），`fusermount3 -u` 收得掉；**這台 `auto_unmount` 實測收不掉**（原因不明）→ 改成 daemon 收屍時替 kid 卸，實測可行。
7. 伺服器在**處理請求的那條執行緒裡**讀自己的掛載點＝卡死，而且外面卡住的寫者連 `kill -9` 都殺不掉（D 狀態），只能殺伺服器；「做很久」放另一條執行緒就沒事，一條 FUSE 執行緒也讀得到 status。
8. 成本：Python 版一次 READ 來回約 50～120 µs，`cat status` 約 0.4～1.5 ms（tmpfs 約 15 µs）；閒著 CPU 0、執行緒停在 `fuse_dev_do_read`；一隻約 14 MB RSS；30 隻同時掛沒事，fusermount3 上限預設 1000。
9. stat size 寫 0：開 `direct_io` 就 `cat`/`wc`/`tail`/`cp` 全對；不開就全部讀到 0 bytes。內容要「開檔那刻拍一張」，不然分段讀會混到好幾版。
10. bwrap 沙箱（這台 bwrap 不是 setuid，必開 user namespace）**走不進 `/proc/<PID>/cwd`**（Permission denied，連普通行程的 cwd 也一樣），但直接用掛載點真實路徑讀得到。

## 逐題的實測

以下輸出取自 `try.py` 實跑（完整紀錄在 `~/.aos/scratch/proto9-fuse-1125/try-*.log`），有刪減。

### 問題 1：不靠 libfuse 掛得起來嗎？最少要哪些操作？

掛法（`toyproc.py` 的 `fuse_mount`）：建 `socketpair`，子行程跑 `fusermount3 -o fsname=toy-<名>,subtype=aosproc,default_permissions -- <掛載點>`，環境變數 `_FUSE_COMMFD=<一端的 fd 號>`（`pass_fds` 傳下去），另一端 `socket.recv_fds(a, 1, 1)` 收回 `/dev/fuse` 的 fd；`rootmode/user_id/group_id` 是 fusermount3 自己補的。接著幾條執行緒 `os.read(fd, 1MB+4K)` 一次讀一個請求、`os.write` 回覆。

```
$ grep toy-q1 /proc/mounts
toy-q1 /home/guanyu/.aos/scratch/proto9-fuse-1125/mnt/q1-3957023 fuse.aosproc rw,nosuid,nodev,relatime,user_id=1000,group_id=1000,default_permissions 0 0
INIT nid=0 kernel=7.39 flags=0x73fffffb      ← 回 7.31、flags=0、max_write=128K 就夠
```

每個殼指令送來的操作（entry 快取 1 秒，等過期後量的）：

| 指令 | 送來的 FUSE 操作 |
|---|---|
| `ls` | GETATTR ×2、OPENDIR、GETATTR、READDIR off=0、READDIR off=6（空＝結束） |
| `ls -l` | 上面＋GETXATTR、LISTXATTR（回 ENOSYS 後核心就不再問）＋每個檔 LOOKUP、GETATTR＋RELEASEDIR |
| `cat status` | GETATTR(根)、LOOKUP status、GETATTR、OPEN flags=O_RDONLY、GETATTR、READ off=0、READ off=117（回空＝EOF）、FLUSH、RELEASE |
| `echo stop-not > ctl` | GETATTR(根)、LOOKUP ctl、GETATTR、OPEN flags=O_WRONLY、**SETATTR valid=0x208 size=0**、FLUSH、GETATTR、**WRITE "stop-not\n"**、FLUSH、RELEASE |
| `printf pause > ctl` | 同上，WRITE 收到 `pause`（沒換行，也要認） |
| `cd .../cwd && cat settings attrs` | 一串 GETATTR(根)，之後各檔照 cat |
| `cat ctl` | LOOKUP、GETATTR → 核心自己回 Permission denied（`default_permissions` 照 mode 0200 擋），伺服器收不到 OPEN |
| `echo x > status` | 同上，核心照 0444 擋 |
| `touch newfile` | LOOKUP 回 ENOENT ×2 → Permission denied（根是 0555） |

- OPEN 的 flags 裡**看不到 O_TRUNC**（`0o100001`＝O_LARGEFILE|O_WRONLY），因為沒談 `FUSE_ATOMIC_O_TRUNC`，核心改送 `SETATTR size=0`（valid 0x208＝FATTR_SIZE|FATTR_LOCKOWNER）。所以 ctl 的 SETATTR 要回成功（回個 attr 即可，不必真的截斷）。
- 最少要做：INIT、LOOKUP、GETATTR、SETATTR、OPEN、READ、WRITE、FLUSH、RELEASE、OPENDIR、READDIR、RELEASEDIR；daemon 多 READLINK；STATFS 有做（`df` 用），沒有也只是 `df` 失敗。其餘（ACCESS、GETXATTR、LISTXATTR、CREATE…）回 ENOSYS。FORGET、BATCH_FORGET、INTERRUPT **不回**。
- 正常結束：`echo stop > ctl` → 行程退出碼 0、掛載沒了、掛載點夾也刪了。

### 問題 2：「另一個人寫不進去」做在哪一步？

先 `echo 'slow 2' > ctl`（做 2 秒），再 `echo pause > ctl`：

```
--- busy-check=open（OPEN 就回 EBUSY）---
$ echo pause > /proc/3958781/cwd/ctl; echo rc=$?
bash: line 1: /proc/3958781/cwd/ctl: Device or resource busy
rc=1
   FUSE 操作：GETATTR nid=1 | GETATTR nid=3 | OPEN nid=3 flags=0o100001 -> EBUSY
$ grep aos_ctl status
aos_ctl_cmd: slow 2
aos_ctl_state: working
aos_ctl_error:

--- busy-check=write（WRITE 才回 EBUSY）---
$ echo pause > /proc/3959170/cwd/ctl; echo rc=$?
bash: line 1: echo: write error: Device or resource busy
rc=1
   FUSE 操作：... | OPEN -> 0 | SETATTR size=0 | FLUSH | GETATTR | WRITE data=b'pause\n' -> -16 | FLUSH | RELEASE
```

兩人都先把 ctl 開好、再先後寫（Python `os.open` 兩次再 `os.write`）：

```
busy-check=open：第二個 write 成功（漏掉了鎖）；status aos_ctl_cmd='pause' state='done'
busy-check=both：第二個 write 失敗：[Errno 16] Device or resource busy；status aos_ctl_cmd='slow 1' state='working'
```

不認得的字：`echo dance > ctl` → rc=0（照「寫回來＝收到」），`aos_ctl_cmd: dance`、`aos_ctl_state: error`、`aos_ctl_error: unknown command: dance`。

建議：**WRITE 一定要擋（那是真正上鎖的地方，判斷與上鎖在同一把 lock 裡）；OPEN 順便擋**，好處是殼裡的錯誤字是「`ctl: Device or resource busy`」而不是「`echo: write error: …`」，也少送幾個操作。退出碼兩種都是 1。另外：OPEN 擋了還得防 SETATTR，鎖住時 SETATTR size=0 也只回 attr 不動任何狀態（本實驗就是這樣）。

### 問題 3：/proc/<PID>/cwd 與連穿兩層

```
$ ls -l /proc/3960844/cwd/ /proc/3960844/cwd/procs/
lrwxrwxrwx 1 guanyu guanyu 5 ... proc -> procs
dr-xr-xr-x 2 guanyu guanyu 0 ... procs
...
/proc/3960844/cwd/procs/:
lrwxrwxrwx 1 guanyu guanyu 17 ... kid1 -> /proc/3960859/cwd
lrwxrwxrwx 1 guanyu guanyu 17 ... kid2 -> /proc/3960883/cwd
lrwxrwxrwx 1 guanyu guanyu 17 ... kid3 -> /proc/3960901/cwd
$ cat /proc/3960844/cwd/procs/kid1/status
name: kid1
pid: 3960859
phase: running
aos_ctl_cmd:
aos_ctl_state: idle
aos_ctl_error:
...
$ cat /proc/3960844/cwd/proc/kid2/attrs          ← 別名 proc 也通
kind: fuse
live: yes
$ cd /proc/3960844/cwd/procs/kid3 && pwd && pwd -P
/proc/3960844/cwd/procs/kid3
/home/guanyu/.aos/scratch/proto9-fuse-1125/mnt/kid3-3960901
$ AOS_ROOT=/proc/3960844/cwd; echo pause > $AOS_ROOT/procs/kid1/ctl; grep -E 'phase|aos_ctl_cmd' $AOS_ROOT/procs/kid1/status
phase: paused
aos_ctl_cmd: pause
```

通。daemon 的 FUSE symlink 指到 `/proc/<kid>/cwd`（絕對路徑、指出自己的掛載），核心照常跟過去。

### 問題 4：kill -9 之後、怎麼收

單獨一隻 toyproc（沒人替它收）被 kill -9：

```
$ ls /proc/3980537/cwd/
ls: cannot access '/proc/3980537/cwd/': No such file or directory     ← 馬上不見
$ stat <掛載點>
stat: cannot statx '<掛載點>': Transport endpoint is not connected
$ grep toy-q4kill /proc/mounts
toy-q4kill <掛載點> fuse.aosproc rw,nosuid,nodev,relatime,user_id=1000,group_id=1000,default_permissions 0 0   ← 死掉的掛載留著
$ fusermount3 -u <掛載點>; echo rc=$?
rc=0                                                                    ← 收得掉，之後 rmdir 也成功
```

`auto_unmount`：fusermount3 確實留了一隻幫手行程盯著 socket；kill -9 之後幫手**自己退出了，但沒卸**，掛載還在、掛載點 `Transport endpoint is not connected`、`rmdir` EBUSY。試過：拿掉 subtype、拿掉 default_permissions、把 socket 的 fd 號換到比 `/dev/fuse` 大（讓 fuse fd 先關）、不回 INIT 就殺——全都一樣不卸，幫手 stderr 也沒有字。沒有 strace、不能 sudo，查不下去；**原因不明**。

改由 daemon 收：`toydaemon.py` 收屍（`waitpid`）時看 `/proc/mounts` 還有 kid 的掛載就 `fusermount3 -u -z`。實測 kid1 被 kill -9 後 0.5 秒內：掛載數 0、掛載點夾已刪、`procs/` 裡 kid1 消失、`cat procs/kid1/status` No such file。（根 daemon 自己被 kill -9 時就沒人收，要靠下一次起來時掃 `/proc/mounts` 裡 `fsname=toy-…`／`subtype=aosproc` 的清掉。）

有人站在裡面時（另一個殼 `cd` 進去）伺服器被 kill -9：

```
$ fusermount3 -u <掛載點>
fusermount3: failed to unmount <掛載點>: Device or resource busy
$ fusermount3 -u -z <掛載點>; echo rc=$?
rc=0
```

所以收屍一律用 `-u -z`（lazy）。

正常結束（`echo stop > ctl`）：proc 先 `chdir("/")`（**自己站在裡面時 umount 會 EBUSY**），再 `fusermount3 -u`（失敗才 `-z`），伺服器執行緒讀到 ENODEV 結束，最後 `rmdir` 掛載點。daemon 收到 stop 先對每隻 kid 的 ctl 寫 stop 等它們退，再收自己。實測對 daemon 寫 stop 後全部掛載與掛載點夾都沒了。

### 問題 5：單執行緒伺服器、自己讀自己、做很久時讀 status

設計是「FUSE 執行緒只收請求、回覆；ctl 的事交給另一條工作執行緒」，所以：

```
--threads 1
$ echo 'slow 3' > ctl; for i in 1 2 3; do grep aos_ctl_state status; done
aos_ctl_state: working      ×3，總共 38 ms     ← 做很久時一條 FUSE 執行緒照樣讀得到 status
$ （工作執行緒裡讀自己的 /proc/<自己>/cwd/status）
selfread: 8 lines in 0.9 ms                    ← 不在 FUSE 執行緒裡讀自己＝沒事
```

故意在**FUSE 處理執行緒裡**（處理 WRITE 時）讀自己的掛載點，`--threads 1`：

```
寫的人  4036534 S  request_wait_answer   bash -c echo selfread-inline > .../ctl
toyproc 執行緒 4036106 S request_wait_answer      ← 唯一那條 FUSE 執行緒在等自己
（對寫的人送 SIGKILL 之後）
4036534 D  request_wait_answer
State: D (disk sleep)   SigPnd: 0000000000000100  ← 收到 SIGKILL 仍卡住
kill -9 toyproc 之後，卡住的寫者才結束：rc=-9
```

`--threads 2`：同一招不卡（`selfread: 8 lines in 0.7 ms`），但只是把問題推到「同時有 2 個這種請求」才卡。結論：**伺服器的處理路徑裡絕對不要碰自己的掛載點**（要自己的狀態就直接讀記憶體）；ctl 做很久放工作執行緒，一條 FUSE 執行緒就夠用，多開幾條只為了別人同時讀很多。

### 問題 6：成本

```
open+read+close /proc/<PID>/cwd/status         1480 µs/次（2000 次平均）
open+read+close <掛載點>/status                 1335 µs/次
open+read+close /dev/shm 普通檔                   16 µs/次
open+read+close ~/.aos/scratch 普通檔             14 µs/次
寫 ctl（open+write+close）中位數 2175 µs、p90 7393 µs（300 次）；寫 /dev/shm 普通檔 26 µs
```

`bench.py`（另一次跑）：

```
threads=1 open+read+close median 401 µs p90 1746 µs | 單一 pread（一個 READ 來回）74 µs | stat 161 µs
threads=2 open+read+close median 774 µs p90 7326 µs | 單一 pread 52 µs | stat 152 µs
threads=4 open+read+close median 511 µs p90 2003 µs | 單一 pread 123 µs | stat 179 µs
```

數字抖很大（這台同時有別的 agent 在跑），量級是：Python 版**一個來回 50～120 µs**，一次 `cat status` 要 7～9 個來回（attr_valid 設 0，每次都重問 GETATTR），所以約 0.4～1.5 ms，比 tmpfs 慢 30～100 倍。給人與 agent 看夠用，拿來當高頻 IPC 不行。

- 閒著 3 秒的 CPU：**0 tick**；三條執行緒：主執行緒 `futex_wait_queue`、兩條 FUSE 執行緒 `fuse_dev_do_read`（阻塞在讀 /dev/fuse）。
- 記憶體：一隻 VmRSS **約 14.4 MB**（幾乎全是 Python 直譯器）；沒有 auto_unmount 時沒有額外的 fusermount3 行程。
- 一口氣起 30 隻：2.3 秒全部掛好、30 個掛載；寫 stop 後掛載數回到 0。
- 上限：`/etc/fuse.conf` 沒有生效的行 → fusermount3 的 `mount_max` 用預設 **1000**（`man mount.fuse3`：「The default is 1000」；沒實測撞上限）；核心 `/proc/sys/fs/mount-max` 是 100000。

### 問題 7：stat size 寫 0、讀到一半內容變

```
--- size=0 + FOPEN_DIRECT_IO ---
stat size=0；cat 正常；wc -c=127；tail -n 2 正常；head -c 40 正常；grep -c 正常；Python read() 127；cp 後 127
--- size=0、不開 direct_io（走 page cache）---
stat size=0；cat 空；wc -c=0；tail 空；head 空；grep -c 0；Python read() 0；cp 後 0     ← 全部讀不到
--- size=當場算的長度、不開 direct_io、attr_valid=0 ---
stat size=121；但 wc -c=122（stat 與讀之間又產生了一次，內容已變長）
```

- **size 寫 0 就要 direct_io**（OPEN 回 `FOPEN_DIRECT_IO`）。不開時核心照 size=0 判斷 EOF，連一個 READ 都不送。報真實長度的做法每次 stat 都得產生一次內容，而且 stat 與讀之間就可能對不上，不建議。
- 讀到一半內容變（status 墊 600 行，每次產生帶序號 gen；`dd bs=1000` 分 12 次讀）：

```
--gen open（OPEN 時拍一張，整次讀都讀那張）：600 行全是 gen=1
--gen read（每個 READ 當場重新產生）：一次讀混了 gen=1～11 共 11 版
```

所以內容要在 **OPEN 時產生、存在 fh 上，RELEASE 時丟**（`toyproc.py` 預設就是這樣），這跟 Linux `/proc/<PID>/status` 的行為（seq_file）一致。

### 問題 8：別的帳號、bwrap 沙箱

```
$ bwrap --dev-bind / / head -2 /proc/<PID>/cwd/status
head: cannot open '/proc/<PID>/cwd/status' for reading: Permission denied
$ bwrap --dev-bind / / --unshare-user --uid 0 ... / --uid 4242 ...    → 一樣 Permission denied
$ bwrap --dev-bind / / --unshare-pid --proc /proc ...
ls: cannot access '/proc/<PID>/cwd/': No such file or directory    ← 新的 PID 空間看不到外面的 PID
（同一個指令改讀掛載點真實路徑）name: q8 / pid: ...                ← 讀得到
$ bwrap --ro-bind / / --dev /dev --proc /proc --unshare-all sh -c 'head -2 <掛載點>/status'
name: q8                                                           ← 讀得到
```

再對照：從 bwrap 裡 `ls /proc/<外面的普通 zsh PID>/cwd/` 也是 Permission denied。所以**擋住的是 `/proc/<PID>/cwd` 這條路，不是 FUSE**。這台 `/usr/bin/bwrap` 不是 setuid，一定開新的 user namespace（裡面 `CapEff` 全 0、`NoNewPrivs 1`）；原因推測是 `/proc/<PID>/cwd` 的 ptrace 讀權限檢查跨不過 user namespace（沒深查）。FUSE 這邊：uid 對應回同一個 1000 時沒有 allow_other 也放行（上面直接路徑讀得到）。

別的 Linux 帳號：**沒測**（不能 sudo、沒有第二個帳號）。照文件（`man mount.fuse3` 的 allow_other 一節）：沒有 `allow_other` 時只有掛的那個人能進，**連 root 都不行**；這台 `/etc/fuse.conf` 沒開 `user_allow_other`，所以一般使用者也不能加 `allow_other`。另外 `/proc/<PID>/cwd` 本身就要過 ptrace 檢查，別的帳號本來就走不進（[9p-proc-1125](../../../proto8/thinking/2026-11/25/9p-proc-1125.md) 已記）。

### 問題 9：行數與改寫成 C++

- Python：`toyproc.py` 403 行（非空非註解 356），其中掛載 21 行、FUSE 伺服器 187 行、玩具 proc 本身約 150 行；`toydaemon.py` 112 行。
- C++（照 `/usr/include/linux/fuse.h`、不靠 libfuse）估：掛載（socketpair＋fork/exec fusermount3＋`recvmsg` SCM_RIGHTS）約 60 行；收發迴圈＋分派＋上面那十幾個操作約 350～450 行；status/ctl/鎖/工作執行緒約 200 行；合計**約 600～800 行**。結構體直接 include 標頭，不用自己算 offset，反而比 Python 的 `struct` 好寫。
- 最麻煩的地方：(1) 掛載與卸載的細節（fusermount3 的協議、auto_unmount 不可靠、lazy umount、殘留掛載的清理）；(2) 執行緒與鎖（ctl 的鎖、fh 表、不能在處理路徑碰自己的掛載點）；(3) 協議版本差異（INIT 的 minor 決定 init_out 長度、READDIR 的 8 byte 對齊與 offset 語意、哪些操作不能回）；(4) 錯誤要回負的 errno、被中斷的請求寫回會得到 ENOENT 要吞掉。

### 問題 10：沒問到的坑

見下一節。

## 坑

1. **`default_permissions` 要自己加**：不加的話核心不看 mode，`cat ctl`、`echo > status` 都會送到伺服器，全靠自己擋。加了核心照 0444/0200/0555 擋。
2. **O_TRUNC 不會出現在 OPEN 裡**，改送 SETATTR size=0；ctl 不處理 SETATTR 的話 `echo > ctl` 直接失敗。
3. **FORGET／BATCH_FORGET／INTERRUPT 回了會出事**（協議規定不回）。
4. **chdir 進自己的掛載點要在伺服器執行緒起來之後**：chdir 本身會送 GETATTR，單執行緒時順序錯就卡死。
5. **自己站在掛載點裡，umount 會 EBUSY**：正常結束先 `chdir("/")`；別人站在裡面就只能 `-z`。
6. **卡在 FUSE 請求裡的行程殺不掉**（D 狀態，SIGKILL 掛著不生效），只能殺伺服器或卸掉；伺服器 bug ＝ 讀它的人一起卡死。以後 daemon 讀 kid 的 status 要有「這隻不回就殺它」的準備，或者讀的人放另一個行程／執行緒。
7. **`/dev/fuse` 的 fd 會被子行程繼承**：`recv_fds` 收到的 fd 不是 close-on-exec；子行程拿著它，主行程死了掛載也不會斷線。程式裡 `os.set_inheritable(fd, False)`；Python 的 `subprocess` 預設 `close_fds=True` 也有擋。
8. **daemon 起 kid 要給 `cwd="/"`**：不然 kid 繼承「站在 daemon 掛載點裡」，daemon 要卸自己時 EBUSY。
9. **`auto_unmount` 在這台不收**（上面問題 4），殘留掛載得由 daemon 或下次啟動清。
10. **attr_valid／entry_valid 的取捨**：設 0 每次都重問 GETATTR（慢、但即時）；`procs/<名>` 的 symlink 一定要 entry_valid=0，不然 kid 死了還會看到舊的連結一秒。
11. **讀一個 FUSE 檔＝7～9 個來回**；Python 一個來回 50～120 µs，延遲大半在這裡。要快就拉長靜態檔的快取、或改 C++。
12. **bwrap 裡走不進 `/proc/<PID>/cwd`**：以後 agent 若跑在 bwrap 沙箱裡，`AOS_ROOT=/proc/<PID>/cwd` 這條路不能用，要另外把真實掛載點 bind 進去。
13. 不認得的 ctl 指令照「寫回來＝收到」回成功（rc=0），錯誤只在 status；要不要讓 write 直接回 EINVAL 是規格要決定的。一次寫多行目前回 EINVAL（一次只收一道）。

## 怎麼重跑

```
cd proto9/experiments/fuse-proc-1125
python3 try.py            # 全部（約 2～3 分鐘）；python3 try.py 1 2 只跑某幾題
python3 bench.py          # 補充量測
TOY_TRACE=/tmp/x python3 toyproc.py --name foo    # 手動玩；另一個殼：cat /proc/<印出的 PID>/cwd/status
```

掛載點與紀錄都在 `~/.aos/scratch/proto9-fuse-1125/`（`mnt/`、`trace.log`、`try-*.log`）。`try.py` 結束前會殺掉自己起的行程、`fusermount3 -u -z` 卸掉 `toy-` 開頭的掛載、刪空的掛載點夾，最後印一次檢查。

## 沒做到的

- `auto_unmount` 為什麼不收：沒有 strace、不能 sudo，查不下去。
- 別的 Linux 帳號看這個掛載：沒有第二個帳號，**沒測**，照文件寫。
- bwrap 裡 `/proc/<PID>/cwd` 被拒的確切原因：只推測是 ptrace 檢查跨 user namespace，沒查核心原始碼。
- unix socket（proc 活著時的訊息路）沒放進 FUSE 目錄裡測。要在 FUSE 夾裡 `bind` 一個 socket，伺服器至少得做 MKNOD（建 S_IFSOCK 節點），能不能穩定 connect 沒試；退路是 socket 放掛載點以外的夾、在 `settings` 寫路徑。這題沒實測。
- 完整跑一次 `try.py`（全部 8 題）：退出碼 0，最後檢查沒有殘留；數字與上面分開跑的同量級（`cat status` 1.3～1.7 ms、寫 ctl 中位數 5.1 ms，這次機器更忙）。
- C++ 版行數只是估計，沒寫。
- 沒撞 mount_max 上限（只起到 30 隻）。

## eca-aos 複核（11-25 15:1x）

- 重跑 `python3 try.py 2 3`：結果跟上面一樣（鎖、連穿兩層、別名 `proc`、`pause` 都對）。
- **`try.py` 只跑部分題目時收尾有洞**：跑完第 3 題，daemon 沒了、掛載也卸了，但三隻 kid 還活著（「收尾」那段把它們印出來，下一行卻寫「以上空白＝沒有殘留」）。它們的掛載是被 lazy 卸掉的，行程還站在裡面，所以 `/proc/<kid PID>/cwd/status` 照樣讀得到、`echo stop > /proc/<kid PID>/cwd/ctl` 照樣收得掉（我就是這樣收的）。這本身是一個發現：**daemon 死了、掛載被卸了，底下的 proc 還活著、還會回答**，已寫進介面草稿第 11 節。
- 複核後沒有殘留的行程與掛載。
