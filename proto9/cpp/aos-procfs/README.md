aos-procfs：讓一支行程用 FUSE（不靠 libfuse，自己照 `linux/fuse.h` 講核心協議）把自己的目錄掛出來、照 aos proc 介面回答的 C++20 小庫，附一隻最小的 aos proc 範例 `aos-procfs-demo` 與測試。

# aos-procfs（proto9 第一塊正式程式，11-25）

← [proto9](../../README.md)｜介面：[01-aos-proc介面草稿](../../docs/01-aos-proc介面草稿.md)｜前身：[Python 玩具 fuse-proc-1125](../../experiments/fuse-proc-1125/README.md)

## 夾裡有什麼

| 檔 | 是什麼 |
|---|---|
| `include/aos/procfs.hpp` | 對外介面（唯一的標頭） |
| `src/answer.cpp` | 回答的線：讀 `/dev/fuse`、分派、回覆 |
| `src/ctl.cpp` | 指令檔：鎖、回饋四行、做事的線 |
| `src/fs.cpp` | 節點表、掛上／卸下的流程 |
| `src/mount.cpp` | `fusermount3`＋socketpair、mountinfo、abort、清死掉的掛載 |
| `src/kv.cpp` | 「名稱: 值」文字小工具 |
| `src/internal.hpp` | 庫內部共用的型別 |
| `demo/main.cpp` | `aos-procfs-demo` |
| `tests/run.py` | 測試（`tests/common.py` 是共用小工具） |
| `tests/probe_abort.py` | 實測 abort 的細節（印觀察，不判對錯） |
| `tests/bench.py` | 跟 Python 玩具比延遲與記憶體 |

## 怎麼編、怎麼跑

```
cd proto9/cpp/aos-procfs
make                 # build/libaos-procfs.a、build/bin/aos-procfs-demo；-Wall -Wextra 沒有警告
make test            # = python3 tests/run.py；只跑某幾組：python3 tests/run.py basic kill
python3 tests/bench.py 500
python3 tests/probe_abort.py
```

手動玩：

```
$ build/bin/aos-procfs-demo foo ~/.aos/scratch/proto9-procfs-1125/mnt/foo &
pid: 12345
AOS_ROOT=/proc/12345/cwd
$ cat /proc/12345/cwd/status
aos_name: foo
aos_phase: running
aos_pid: 12345
aos_started_at: 2026-11-25T15:48:45+08:00
aos_ctl_cmd: -
aos_ctl_state: -
aos_ctl_error: -
aos_ctl_count: 0
$ echo pause > /proc/12345/cwd/ctl
$ echo stop > /proc/12345/cwd/ctl          # 行程退出、掛載與掛載點夾都沒了
$ build/bin/aos-procfs-demo --cleanup <掛載點>   # 收 kill -9 之後留下的死掛載
```

demo 的參數：`NAME MOUNTPOINT [--threads N] [--socket] [--persist PATH]`，或 `--cleanup PATH [--force]`。ctl 收 `stop`、`pause`、`resume`，測試用另有 `slow N`（做 N 秒）、`link 名 目標`／`unlink 名`（在 `links/` 底下隨時加、拿掉 symlink，模擬 daemon 的 `procs/<名>`）。`--socket` 讓根夾可以放 unix socket，並在裡面 bind 一個 echo socket `sock`。

## 庫的介面一覽

全部在 `namespace aos::procfs`。

| 東西 | 做什麼 |
|---|---|
| `Fs(Options)` | 一個要掛出來的目錄。`Options`：`fsname`（實際寫成 `<fsname>:<PID>`）、`threads`（回答的線幾條，預設 1）、`root_sockets`、`on_gone`（連線沒了時叫一次） |
| `add_dir(path, sockets=false)` | 子目錄；`sockets` 允許在裡面 bind unix socket |
| `add_text(path, Producer)` | 只讀純文字。開檔那刻叫 `Producer` 產生一份、整次讀都讀那份；size 報 0＋`direct_io` |
| `add_json(path, 內容)` | 只讀、內容不變（`_metainfo.json`）；報真長度、可快取 |
| `add_ctl(path, prefix)` → `Ctl&` | 只寫指令檔；`prefix` 例 `aos_ctl_`、`aos_procs_ctl_` |
| `add_symlink(path, 目標)`／`remove(path)` | 隨時可加、拿掉；名字與屬性都不快取（entry_valid＝0） |
| `mount(掛載點)`／`unmount()` | 掛上（夾不在就建）、起回答的線與每個 ctl 的做事的線；卸下見下 |
| `Ctl::on(字, Action, Check)` | 註冊一個字。`Check` 在回答的線上看參數（回 `"代號 原因"` 就拒）；`Action` 在做事的線上做，回 `Result::done()`／`failed("代號 原因")`／`hold_until_exit()` |
| `Ctl::feedback()` | 回饋四行，放進 status 的 Producer 裡 |
| `kv_line`／`Kv` | 「名稱: 值」：值裡的換行換成空白、空值寫 `-` |
| `connection_id(path)` | 從 `/proc/self/mountinfo` 找連線編號（`/sys/fs/fuse/connections/<編號>`） |
| `abort_connection(path)` | 往那個編號的 `abort` 寫 1 |
| `cleanup_dead_mount(path, force)` | 給 daemon 收屍：`fusermount3 -u -z`。伺服器 PID（從 fsname 認）還在就回 `Alive` 不動；不是 aosproc 的回 `Foreign` |
| `on_answer_thread()` | 這條是不是回答的線 |

**「回答的線不碰檔案系統」怎麼讓人難違反**：檔的內容只能經 `Producer` 給（介面文件寫明不可阻塞、不可碰路徑，連 `localtime` 都別叫——demo 的 `aos_started_at` 是起來時先算好的）；ctl 的事一律交給做事的線，回答的線上只跑 `Check`（只看參數）；庫裡會碰檔案系統的函數（`mount`、`unmount`、`abort_connection`、`cleanup_dead_mount`）在回答的線上叫就丟 `std::logic_error`。叫 `Producer` 時不拿著節點表的鎖。庫擋不住的是使用者在 `Producer`／`Check` 裡硬去讀檔——這只能靠文件。

**掛載與卸載**：socketpair 一端給 `fusermount3`（環境 `_FUSE_COMMFD`，fork 之前就把 argv／envp 備好），另一端 `recvmsg(MSG_CMSG_CLOEXEC)` 收 `/dev/fuse` 的 fd，收到那刻就是 close-on-exec。選項 `fsname=<fsname>:<PID>,subtype=aosproc,default_permissions`（不用 `auto_unmount`，玩具實測這台不收）。`unmount()`：自己站在掛載點裡就先 `chdir("/")`，`fusermount3 -u`；失敗（別人站在裡面）才 `-u -z`，再 abort 那條連線讓回答的線醒來；等回答的線最多 2 秒；最後刪掉 mount 時建的夾。

**避開的玩具十三坑**：`default_permissions` 有加（1）；ctl 的 SETATTR size=0 回成功、什麼都不動（2）；FORGET／BATCH_FORGET／INTERRUPT 不回（3）；demo 掛好、回答的線起來之後才 chdir（4）；卸之前先離開自己的掛載點、失敗才 lazy（5）；回答的線不碰路徑（6）；fd close-on-exec（7）；`fusermount3` 子行程 cwd 是 `/`（8）；不靠 `auto_unmount`，給 `cleanup_dead_mount`（9）；symlink 與 socket 的 entry／attr 都不快取，其餘固定節點快取 1 秒（10）；C++ 一個來回快很多（11，見延遲）；bwrap（12）庫管不到，照舊；不認得的字讓寫入失敗、多行就拒（13，照草稿【定】）。另外：OPENDIR 那刻拍一份名單，`procs/` 分段讀時名單變了也不漏不重。

## 照了草稿哪些【擬】

- 第 5 節：名稱小寫加底線、冒號後一個空白、沒有值寫 `-`；行的先後沒意思。
- 第 6 節：基礎三字 `stop`、`pause`、`resume`。
- 第 6 節鎖的細節：寫不進去＝那次開檔或寫入當場 EBUSY、不動 `aos_ctl_*`；`pause` 停住就算做完（放鎖）；`stop` 的做完是行程結束（`hold_until_exit`，鎖到退出，`aos_ctl_state` 停在 `doing`）。
- 第 7 節 `settings` 兩行 `aos_persist`、`aos_mailbox`（demo 沒有就寫 `-`）。
- 第 4 節保留名：demo 自己多擺的夾叫 `links/`，沒佔 `procs/`。

## 碰到的【開】與怎麼處理（都挑保守的，使用者看了不對就改）

| 碰到的 | 怎麼做 |
|---|---|
| 還沒收過指令時 `aos_ctl_state` 寫什麼 | `-`（跟 `aos_ctl_cmd` 一樣） |
| 被拒的那次算不算 `aos_ctl_count`、動不動 `aos_ctl_cmd` | 算、會動（被拒的原因也要在回饋裡，回饋講的是「最後一次」）；只有「鎖著被擋」的不動 |
| 被拒時寫入回什麼錯 | `EINVAL`（殼裡是 `write error: Invalid argument`）；鎖著是 `EBUSY` |
| 多行被拒的回饋 | 照不認得的字一樣記 `rejected`、`aos_ctl_error: LinesTooMany 2 lines in one write` |
| 參數不對（`slow x`） | 跟不認得的字一樣：`rejected`、`ArgumentsBad …`、寫入失敗 |
| 空寫入（`echo > ctl`） | 什麼都不動、回成功 |
| 收下了、做的時候失敗 | `aos_ctl_state: done`＋`aos_ctl_error` 寫原因（不另開第四種 state） |
| `aos_started_at` 的格式 | ISO 8601 本地時間帶時差（`2026-11-25T15:48:45+08:00`） |
| socket 叫什麼（第 9 節） | 沒定；demo 只為了測試叫 `sock`，不是標準名 |
| 掛載點放哪 | 呼叫的人給；測試全放 `~/.aos/scratch/proto9-procfs-1125/mnt/` |
| `_metainfo.json` 的內容 | demo 只放一行 `summary` |

另外發現一件會影響「一次寫入一道」的事：**bash 的 `printf 'a\nb\n' > ctl` 會拆成兩次 write**，於是兩道各自被收（或第二道撞到鎖 EBUSY），不會被當成「多行就拒」。真正一次寫兩行（例 Python `os.write(fd, b"a\nb\n")`）才會被拒。測試用的是後者。

## 實測一：伺服器不回答、abort

`tests/probe_abort.py`（對 demo 送 SIGSTOP，草稿第 8 節【定】「被 Linux 暫停的算卡住」）：

```
mountinfo dev 0:89 -> connection 89; exists in /sys/fs/fuse/connections: True
one reader, server SIGSTOPped 1s: S wchan=request_wait_answer, rc=None
waiting = 1
after SIGKILL to it: Z wchan=0, rc=-9
two more readers 1s: S wchan=request_wait_answer / S wchan=request_wait_answer
waiting = 2
after abort: reader rc=1 stderr='cat: /proc/287553/cwd/status: Software caused connection abort'
after abort: reader2 rc=1 stderr='cat: /proc/287553/cwd/settings: Software caused connection abort'
mount still in /proc/mounts: True
stat mountpoint: ... Transport endpoint is not connected
ls /proc/PID/cwd/: ... Transport endpoint is not connected
server after SIGCONT: exited rc=0
mount after server exit: False ; dir exists: False
```

- **編號怎麼對**：`/proc/self/mountinfo` 第 3 欄是 `major:minor`（這裡 `0:89`），連線編號＝`major<<20 | minor`（major 是 0 時就是 minor），即 `/sys/fs/fuse/connections/89/`。那幾個檔的主人是掛的人，不用 sudo 就寫得了。庫的 `connection_id()` 只讀 mountinfo，不 stat 掛載點（stat 卡住的掛載會跟著卡）。
- **卡住**：讀 `status` 的人卡住（`waiting` 跟著加）。
- **寫 abort**：卡住的人**當場被放開**，拿到 `ECONNABORTED`（殼裡是 `Software caused connection abort`），退出碼 1。之後那個掛載變**死殼**：還在 `/proc/mounts`，`stat`、`ls`、`cat` 都是 `Transport endpoint is not connected`；因為伺服器還活著、站在裡面，`/proc/<PID>/cwd/` 也是同一個錯（不是 No such file）。
- 伺服器 SIGCONT 之後讀 `/dev/fuse` 拿到 ENODEV，庫叫 `on_gone`，demo 照正常結束走：`fusermount3 -u` 卸得掉、夾也刪了、退出碼 0。伺服器若不配合，就得靠 `cleanup_dead_mount(path, force=true)`（PID 還在，不 force 會回 `Alive`）。
- **跟草稿「殺不掉」不完全一樣**：伺服器被暫停時請求還排在核心裡、沒被拿走，卡住的人 **SIGKILL 殺得掉**（上面 Z）。玩具踩到的「殺不掉」（D 狀態）是伺服器已經把請求讀走、卻不回的情形。第一次跑時另見到第二個讀同一個名字的人卡在 `d_alloc_parallel`（D 狀態，排在前一個人的 LOOKUP 後面），那個殺不殺得掉沒測。
- 測試裡另有一組 `abort` 把這幾點斷言了一次。

## 實測二：在掛出來的目錄裡 bind unix socket

**做得到**，做成庫的選項（`add_dir(path, true)` 或 `Options::root_sockets`）。庫多做 MKNOD（只收 `S_IFSOCK`）與 UNLINK（只准刪 socket 節點）；開了的夾權限是 0755（`default_permissions` 要寫的權限才放 bind 過去）。demo `--socket` 在根夾 bind `sock`，從 `/proc/<PID>/cwd/sock` connect、送 `ping` 收到 `pong: ping`（測試 `socket` 組）。普通檔照樣建不了（CREATE、MKDIR… 回 EPERM）。

要知道的：開了之後，同一個帳號的別人也能在那個夾裡 bind 自己的 socket（只擋普通檔）；socket 節點在 unmount 時跟著掛載消失。路徑長度照 unix socket 的 108 字元限制，`/proc/<PID>/cwd/sock` 很短沒問題。

## 延遲與記憶體（`tests/bench.py 500`，兩次）

每次都是 Python 裡 `open`＋`read` 到底＋`close`（不含起 `cat` 行程），兩邊都只開一條回答的線；寫 ctl 是 `open`＋`write("resume\n")`＋`close`，撞到上一道還鎖著（EBUSY）就等一下重來、那次不算。中位數，微秒：

| | 第 1 次 | 第 2 次 |
|---|---|---|
| 普通檔（scratch） | 2.6 | 2.5 |
| C++ 讀 `status` | 40.0 | 48.9 |
| Python 玩具讀 `status` | 313.6 | 249.8 |
| C++ 寫 `ctl` | 31.1 | 36.6 |
| Python 玩具寫 `ctl` | 1525.1 | 1861.7 |
| 記憶體 VmRSS | C++ 約 4.2 MB | 玩具約 13.4 MB |

C++ 讀 `status` 比玩具快 5～8 倍，寫 ctl 快約 50 倍（玩具每道指令另開一條執行緒）；比普通檔仍慢約 15～20 倍（一次讀是好幾個 FUSE 來回）。

## 測試（`tests/run.py`）

35 條全過（basic 19、kill 5、abort 3、socket 4、links 3，加最後一條「沒有殘留的行程與掛載」）。驗的有：status 八行；`pause` 後 `aos_phase: paused`；`slow 3` 進行中別人寫 `pause` 當場 busy、回饋沒動、`status` 照樣讀得到（約 5～9 ms）；兩人先開檔再先後寫第二個 EBUSY；不認得的字寫入失敗且 `rejected`；一次寫兩行被拒；`stop` 後退出、掛載與夾都沒了；`kill -9` 後 `/proc/<PID>/cwd` 馬上不見、死掛載留著、`--cleanup` 活著時不動、死了收得掉；abort；socket；symlink 隨時加、拿掉（拿掉後馬上走不到）。

收尾：`tests/common.py` 用 atexit＋SIGTERM 收——叫醒被暫停的、殺掉起過的、`fusermount3 -u -z` 卸掉 scratch 底下 `fuse.aosproc` 的掛載、刪空夾。只跑部分、或跑到一半被 `timeout` 殺掉也會收（實測過）。限時的殼指令到時只 kill、不等（卡在 FUSE 裡的人等不到）。

## 行數

庫（`include/`＋`src/`）1233 行（非空非註解約 1030）；demo 265 行；測試與量測 499 行。`src/answer.cpp` 391 行，超過 300 行的門檻，之後可以把各操作拆出去。玩具估的 600～800 行偏少，多出來的是鎖與做事的線、mountinfo／abort／清理、socket、目錄名單快照。

## 還沒做的

- daemon 的部分（`procs/`、`procs_ctl`、`procs_status`、卡住的檢查）：庫備好了零件（symlink 隨時加拿、ctl 可設字首、`connection_id`／`abort_connection`／`cleanup_dead_mount`），還沒有 daemon 本身。
- 各檔的 json 版（`status.json`…）、`persist` 怎麼擺。
- 卸載時回答的線 2 秒內醒不來（abort 也失敗）就只 detach、不關 fd；這時 `Fs` 若被解構，線會碰到已經釋放的記憶體——現在只有行程馬上要結束的情形會走到，沒處理。
- 回答的線只靠文件守規矩：`Producer` 裡硬去讀檔，庫攔不到。
- 收到的請求長度、名稱都有防越界，但沒做模糊測試；INIT 只對過這台的 7.39。
- 別的 Linux 帳號、bwrap 沙箱裡用 socket：沒測。
- 沒進 `proto8/cpp/Makefile`、沒進 code map 與 `_index.json`（只准寫這一夾）。
