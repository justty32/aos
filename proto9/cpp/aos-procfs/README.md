aos-procfs：讓一支行程用 FUSE（不靠 libfuse，自己照 `linux/fuse.h` 跟核心講）把自己的目錄掛出來、照 aos proc 介面回答的 C++20 小庫（含照 Maildir 收信的 `mailbox/` 夾、認環境變數是不是給自己的），附一隻最小的 aos proc 範例 `aos-procfs-demo` 與測試。

# aos-procfs（proto9 第一塊正式程式，11-25）

← [proto9](../../README.md)｜介面：[01-aos-proc介面草稿](../../docs/01-aos-proc介面草稿.md)｜前身：[Python 玩具 fuse-proc-1125](../../experiments/fuse-proc-1125/README.md)

## 夾裡有什麼

| 檔 | 是什麼 |
|---|---|
| `include/aos/procfs.hpp` | 對外介面（唯一的標頭） |
| `src/answer.cpp` | 回答的線：讀 `/dev/fuse`、分派、回覆、屬性 |
| `src/ops.cpp` | 回答的線上一般節點較長的操作（開檔、讀寫、列夾、socket 節點） |
| `src/mail_ops.cpp` | 回答的線上信箱的操作：分派、讀、刪、搬進 `new/`（不覆蓋、可拒收） |
| `src/mail_write.cpp` | 回答的線上信箱的「寫」：在 `tmp/` 開檔或信夾、寫入、截短、改屬性，照上限擋 |
| `src/mailbox.cpp` | 收信這一邊：`add_mailbox`、`take()`、`stats()`、丟掉過期的 `tmp/` |
| `src/env.cpp` | `env_assignment()`：`AOS_NAME`、`AOS_MOUNT` 是不是給自己的 |
| `src/ctl.cpp` | 指令檔：鎖、回饋四行、做事的線 |
| `src/fs.cpp` | 節點表、掛上／卸下的流程 |
| `src/mount.cpp` | `fusermount3`＋socketpair、mountinfo、abort、清死掉的掛載 |
| `src/kv.cpp` | 「名稱: 值」文字小工具 |
| `src/internal.hpp` | 庫內部共用的型別 |
| `demo/main.cpp`、`demo/mail.cpp`（＋`mail.hpp`） | `aos-procfs-demo`；信箱那一部分在 `mail.cpp` |
| `tests/run.py` | 測試：ctl、status、abort、socket、symlink、環境變數（`tests/common.py` 是共用小工具） |
| `tests/mail.py`、`tests/mail_more.py` | 信箱的測試 |
| `tests/probe_abort.py` | 實測 abort 的細節（印觀察，不判對錯） |
| `tests/bench.py` | 跟 Python 玩具比延遲與記憶體 |

## 怎麼編、怎麼跑

```
cd proto9/cpp/aos-procfs
make                 # build/libaos-procfs.a、build/bin/aos-procfs-demo；-Wall -Wextra 沒有警告
make test            # = tests/run.py 與 tests/mail.py；只跑某幾組：python3 tests/run.py basic kill、python3 tests/mail.py clash big
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
$ cd /proc/12345/cwd/mailbox
$ printf 'hello\n' > tmp/a && mv tmp/a new/a   # 寄一封：tmp/ 寫好，再搬進 new/
$ printf 'again' > tmp/a && mv tmp/a new/a
mv: cannot overwrite '/proc/12345/cwd/mailbox/new/a': File exists
$ echo take > ../ctl; grep mail_ ../status     # demo 拿走一封
$ cd /
$ echo stop > /proc/12345/cwd/ctl          # 行程退出、掛載與掛載點夾都沒了
$ build/bin/aos-procfs-demo --cleanup <掛載點>   # 收 kill -9 之後留下的死掛載
```

demo 的參數：`NAME MOUNTPOINT [--threads N] [--socket] [--persist PATH] [--mail-max-bytes N] [--mail-max-letters N] [--mail-max-total N] [--mail-stale S]`，或 `--cleanup PATH [--force]`。不給 NAME、MOUNTPOINT 時用 `$AOS_NAME`、`$AOS_MOUNT`，但只在 `$AOS_NAME_PID` 等於自己的 PID 時（見下面「環境變數」）。ctl 收 `stop`、`pause`、`resume`，測試用另有 `slow N`（做 N 秒）、`link 名 目標`／`unlink 名`（在 `links/` 底下隨時加、拿掉 symlink，模擬 daemon 的 `procs/<名>`）、`take`（從 `mailbox/new/` 拿走最早的一封；沒有信＝`failed`＋`MailEmpty`）、`refuse on|off`（拒收開關：開著時搬進 `new/` 那一步失敗、`EPERM`）。`--socket` 讓根夾可以放 unix socket，並在裡面 bind 一個 echo socket `sock`。demo 一律擺 `mailbox/`，`attrs` 多一行 `aos_mailbox: yes`；`status` 多幾行不帶 `aos_` 的：`mail_waiting`（`new/` 幾封）、`mail_writing`（`tmp/` 幾項）、`mail_bytes`、`mail_delivered`、`mail_taken`、`mail_refused`、`mail_dropped_stale`、`mail_last_refusal`、`mail_refusing`、`mail_last_name`、`mail_last_bytes`（最後 `take` 的那封）。demo 不讀 eventfd，信等 ctl 的 `take` 才拿。

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
| `Ctl::on(字, Action, Check)` | 註冊一個字。`Check` 在回答的線上看參數（回 `"代號 原因"` 就拒）；`Action` 在做事的線上做，回 `Result::done()`（`aos_ctl_state: done`、error `-`）／`failed("代號 原因")`（`failed`＋原因）／`hold_until_exit()` |
| `Ctl::feedback()` | 回饋四行，放進 status 的 Producer 裡 |
| `kv_line`／`Kv` | 「名稱: 值」：值裡的換行換成空白、空值寫 `-` |
| `connection_id(path)` | 從 `/proc/self/mountinfo` 找連線編號（`/sys/fs/fuse/connections/<編號>`） |
| `abort_connection(path)` | 往那個編號的 `abort` 寫 1 |
| `cleanup_dead_mount(path, force)` | 給 daemon 收屍：`fusermount3 -u -z`。伺服器 PID（從 fsname 認）還在就回 `Alive` 不動；不是 aosproc 的回 `Foreign` |
| `on_answer_thread()` | 這條是不是回答的線 |
| `add_mailbox(path, MailLimits, Accept)` → `Mailbox&` | 擺出信箱夾 `path/{tmp,new,cur}/`（見下面「信箱資料夾」）；要在 `mount` 之前加 |
| `Mailbox::take()` | 拿走 `new/` 裡最早搬進來的一封（`Letter`：名字、內容、信夾裡每個檔、byte 數、搬進來那次請求的 uid／pid、時間）；沒有回 `nullopt`。執行緒安全、只碰記憶體 |
| `Mailbox::fd()` | eventfd：每寄到一封加 1；可讀＝有新信，讀掉 8 byte 清零再 `take()` 到拿不到 |
| `Mailbox::stats()` | 幾封在等、幾項在寫、合計 byte、寄到／拿走／拒收／過期丟掉的次數、最後一次拒收的原因；O(1)，可以在 `status` 的 Producer 裡叫 |
| `env_assignment()` | `AOS_NAME`、`AOS_MOUNT`，只在 `AOS_NAME_PID` 等於 `getpid()` 時給，否則 `nullopt` |

**「回答的線不碰檔案系統」怎麼讓人難違反**：檔的內容只能經 `Producer` 給（介面文件寫明不可阻塞、不可碰路徑，連 `localtime` 都別叫——demo 的 `aos_started_at` 是起來時先算好的）；ctl 的事一律交給做事的線，回答的線上只跑 `Check`（只看參數）與信箱的 `Accept`（只看那封信）；庫裡會碰檔案系統的函數（`mount`、`unmount`、`abort_connection`、`cleanup_dead_mount`）在回答的線上叫就丟 `std::logic_error`。叫 `Producer` 時不拿著節點表的鎖。庫擋不住的是使用者在 `Producer`／`Check` 裡硬去讀檔——這只能靠文件。

**掛載與卸載**：socketpair 一端給 `fusermount3`（環境 `_FUSE_COMMFD`，fork 之前就把 argv／envp 備好），另一端 `recvmsg(MSG_CMSG_CLOEXEC)` 收 `/dev/fuse` 的 fd，收到那刻就是 close-on-exec。選項 `fsname=<fsname>:<PID>,subtype=aosproc,default_permissions`（不用 `auto_unmount`，玩具實測這台不收）。`unmount()`：自己站在掛載點裡就先 `chdir("/")`，`fusermount3 -u`；失敗（別人站在裡面）才 `-u -z`，再 abort 那條連線讓回答的線醒來；等回答的線最多 2 秒；最後刪掉 mount 時建的夾。

**避開的玩具十三坑**：`default_permissions` 有加（1）；ctl 的 SETATTR size=0 回成功、什麼都不動（2）；FORGET／BATCH_FORGET／INTERRUPT 不回（3）；demo 掛好、回答的線起來之後才 chdir（4）；卸之前先離開自己的掛載點、失敗才 lazy（5）；回答的線不碰路徑（6）；fd close-on-exec（7）；`fusermount3` 子行程 cwd 是 `/`（8）；不靠 `auto_unmount`，給 `cleanup_dead_mount`（9）；symlink 與 socket 的 entry／attr 都不快取，其餘固定節點快取 1 秒（10）；C++ 一個來回快很多（11，見延遲）；bwrap（12）庫管不到，照舊；不認得的字讓寫入失敗、多行就拒（13，照草稿【定】）。另外：OPENDIR 那刻拍一份名單，`procs/` 分段讀時名單變了也不漏不重。

## 環境變數：只認給自己的（照 systemd 的 `LISTEN_PID`）

daemon 起一支底下的 proc 時給 `AOS_NAME`、`AOS_MOUNT`、`AOS_ROOT`。孫子行程會原樣繼承前兩個，以為是給自己的。現在 daemon 另給 `AOS_NAME_PID=<那一支的 PID>`（fork 之後、exec 之前由孩子自己填），庫的 `env_assignment()` 只在 `AOS_NAME_PID` 等於 `getpid()` 時把名字與掛載點交出來，否則當沒給。demo 與 aos-daemon 起來時都走它。`AOS_ROOT` 不在此限：底下每一支都該知道根。

**後果**：包一層殼的（例 `sh -c '...; demo'`）要 `exec` 真的程式，PID 才會不變；不 exec 的話真的程式是孫子，會不理這兩個變數（demo 退 1、說 `need NAME and MOUNTPOINT (or $AOS_NAME and $AOS_MOUNT with $AOS_NAME_PID = own pid)`）。測試：`run.py` 的 `env` 組（沒有 `AOS_NAME_PID` 不認；殼設成殼自己的 `$$` 再 fork 出 demo 不認；`exec` 的認）、aos-daemon 的 `envpid` 組。

## 信箱資料夾 `mailbox/`（草稿第 9 節「信箱資料夾，照 Maildir，先做這個」）

### proto8 怎麼寄一封信（照著做的對象）

讀了知識庫 `aos/mailbox.md`、`aos/cli/mailbox.md` 與寄信的程式碼（全部只讀）：`aos-mailbox send`（Python，`proto8/py/aos/apps/mailbox/`）自己不碰信箱，叫 C++ 的 **`aos-post send`**（`proto8/cpp/aos-post/src/send/send.cpp`，檔名產生在 `aos-util`）。aos-post 實際做的：

| 步 | 系統呼叫 | 說明 |
|---|---|---|
| 0 | `stat` 信箱、`tmp/`、`new/`；`access(tmp/ 與 new/, W_OK\|X_OK)` | 不是夾＝`MailboxMissing`，不可寫＝`MailboxBad`；不看 `cur/`（但 `aos-mailbox send --box` 要三個夾都在） |
| 1 | `mkdir tmp/<名>` | **一封信是一個夾**。名字預設 `<UTC 奈秒 20 位>.<pid>.<行程起動 tick>`；`mkdir` 撞名（EEXIST）就換一個時間再試，最多 100 次；自己給的名字撞名＝`LetterExists` |
| 2 | 附檔：在 `tmp/<名>/` 裡複製（`copy_file`） | 選用 |
| 3 | `open(tmp/<名>/.letter.json.<pid>.tmp, O_WRONLY\|O_CREAT\|O_TRUNC)`、`write`、`fsync`、`close`、`rename` 成 `letter.json` | aos-util 的 `write_json`（先 `create_directories` 那一夾，已經在） |
| 4 | `rename(tmp/<名>, new/<名>)` | 夾改名是一步完成的；失敗就整個 `tmp/<名>` 刪掉（`remove_all`：先 `unlink` 檔、再 `rmdir`）。`EEXIST`／`ENOTEMPTY`＝`LetterExists`，其餘＝`WriteFailed` |

不用 `link`。`--ordered` 另在信箱根拿 `order.lock/`（`mkdir`）、寫 `order.json`。舊的 `send_prepared` 用 `tmp/.<名>` 再搬成 `new/<名>`。收信的 `take` 是 `rename new/<名> → cur/<名>`。

### 這裡的形狀

`mailbox/` 底下 `tmp/`、`new/`、`cur/` 三個夾，跟 proto8 同形，所以**同一支寄信程式不改一個字就能寄進活著的 proc**：實測 proto8 的 `proto8/bin/aos-post send /proc/<PID>/cwd/mailbox` 寄進 demo，退 0、`new/<名>/letter.json` 讀得到原樣的 body（`mail.py` 的 `aospost` 組；不帶任何 `AOS_*` 環境變數、站在 scratch 裡跑，不碰任何活的樹）。同一組也驗了：同一個自己給的名字寄兩次，第二次 aos-post 報 `LetterExists`、第一封原樣、它自己把 `tmp/` 清掉；proc 拒收時 aos-post 報 `WriteFailed ... Operation not permitted`、`tmp/` 清掉。`aos-post send --ordered` 寄不進來（`MkdirFailed cannot create .../mailbox/order.lock: Permission denied`，什麼都沒留下；手動試的，沒進測試）。

- **一封信可以是一個檔（Maildir、殼裡 `printf > tmp/x && mv tmp/x new/x`），也可以是一個夾（aos-post）**。信夾裡只能放檔、不能再開夾。
- `tmp/`：寄的人在這裡開檔、開信夾、寫、截短、改名（同一夾裡）、刪。
- `new/`：**只能從 `tmp/` 搬進來**（`rename`／`renameat2` 的 `RENAME_NOREPLACE` 都收）。搬進來那一刻就封住：權限拿掉寫的位，之後寫、刪、搬、在裡面開東西都失敗；`cat` 照樣讀得到。只有 proc 的 `take()` 拿得走。
- `cur/`：永遠是空的、不能寫，只為了跟 proto8／Maildir 同形（`aos-mailbox send --box` 要看到三個夾）。
- 信箱根：不能寫（所以 `--ordered` 的 `order.lock/` 開不了）。

### 存在哪、上限、錯誤號

信全在 proc 的記憶體裡（節點表上的一個個節點），回答的線只碰記憶體。上限都有預設，`MailLimits` 可改（demo 用 `--mail-*`）：

| 上限 | 預設 | 超過時 |
|---|---|---|
| 一封幾 byte（`max_letter_bytes`；信夾＝裡面全部的檔加起來） | 8 MiB | 那次 `write`（或截長）失敗 `EFBIG` |
| `tmp/`＋`new/` 頂層合計幾項（`max_letters`） | 4096 | 在 `tmp/` 開新的一項時失敗 `ENOSPC` |
| `tmp/`＋`new/` 合計幾 byte（`max_total_bytes`） | 64 MiB | 那次 `write` 失敗 `ENOSPC` |
| 一個信夾裡幾個檔（`max_files`） | 64 | 開檔失敗 `ENOSPC` |
| `tmp/` 裡多久沒動就丟（`stale_tmp_seconds`） | 36 小時（Maildir 的數字） | 整項丟掉（`mail_dropped_stale` 加 1） |

其他會失敗的地方：搬到 `new/` 已有的名字＝`EEXIST`（不覆蓋）；名字 `.` 開頭搬進 `new/`、名字有控制字元＝`EINVAL`；正在投遞中（等 accept 回話）的那一項再搬＝`EBUSY`；在 `new/` 或 `cur/` 開東西、刪 `new/` 的、從 `new/` 搬出去、信夾裡開夾、`link`、`symlink`＝`EPERM`（不用 `EXDEV`：`mv` 碰到 `EXDEV` 會改成複製）；`cur/` 與根被權限位擋＝`EACCES`。`fsync` 一律成功（記憶體裡沒有可以再往下寫的地方）。過期的 `tmp/` 不另開一條線清：在 `tmp/` 開新東西、列 `tmp/`、`stats()` 時順手掃（最多一秒一次，只掃 `tmp/`）。

### 收信這一邊（給 proc 用的）

- **回答的線上沒有會等的回呼**。寄到時庫只做三件事：把那一項從 `tmp/` 搬到 `new/`、封住、往 eventfd 加 1。
- `Mailbox::take()` 拿走 `new/` 裡**最早搬進來的**一封（照搬進來的先後，不照名字排）；`Letter` 帶名字、內容（單檔＝它的內容；信夾＝`letter.json` 的內容，另有每個檔的清單）、byte 數、**搬進 `new/` 那次請求的 uid／pid**（FUSE 請求表頭裡核心填的；是做 `rename` 的那支行程，例 `mv`，不是它的殼）、時間。拿走後 `new/` 裡就沒有了。
- `Mailbox::fd()`：eventfd，`poll` 它、讀掉、再 `take()` 到拿不到為止。
- `Accept`（選用）：搬進 `new/` 那一刻在回答的線上叫，不拿著庫的鎖（先把那一項封住，叫完再拿鎖、再確認一次名字沒被別人先佔）。規矩同 ctl 的 `Check`：只看那封信、只讀記憶體、不可阻塞。回 `{errno, 原因}` 就拒：那次 `rename` 失敗、回那個 errno（`EXDEV` 換成 `EPERM`），信留在 `tmp/`（寄的人自己清；aos-post 會清），原因記進 `stats().last_refusal`。
- `stats()` 是 O(1)（加上掃一次 `tmp/`），`new/` 等多少封都一樣快。

### 量到的（這台 WSL2、Python 直接下系統呼叫、中位數）

- 寄一封小信（`open(O_CREAT|O_EXCL)`＋`write`＋`fsync`＋`close`＋`rename`）約 250～265 微秒（四次跑）。
- 1 MB 的信分 11 次 `write`、再搬進 `new/`：約 7～16 毫秒，讀回來逐 byte 一樣。
- 讀 `status`：沒有信時約 36～51 微秒，`new/` 裡等著 1000 封時約 38～43 微秒（同一個量級；以前沒有信箱時是 40～49）。
- proc 被 SIGSTOP 時寄信會卡住（跟讀它的 `status` 一樣，是預期的）；SIGCONT 後那次寄信接著做完、信寄到。

## 照了草稿哪些【擬】

- 第 5 節：名稱小寫加底線、冒號後一個空白、沒有值寫 `-`；行的先後沒意思。
- 第 6 節：基礎三字 `stop`、`pause`、`resume`。
- 第 6 節【定】（使用者 11-25）：收下了、做的時候失敗＝`aos_ctl_state: failed`、原因在 `aos_ctl_error`；`done` 一定是做成了、`aos_ctl_error: -`。`rejected` 照舊（門口就不收、寫入失敗）。
- 第 6 節鎖的細節：寫不進去＝那次開檔或寫入當場 EBUSY、不動 `aos_ctl_*`；`pause` 停住就算做完（放鎖）；`stop` 的做完是行程結束（`hold_until_exit`，鎖到退出，`aos_ctl_state` 停在 `doing`）。
- 第 7 節 `settings` 兩行 `aos_persist`、`aos_mailbox`（demo 沒有就寫 `-`）。
- 第 4 節保留名：demo 自己多擺的夾叫 `links/`，沒佔 `procs/`。
- 第 9 節【擬】：擺了信箱夾的 proc 在 `attrs` 寫 `aos_mailbox: yes`（demo 有）。`settings` 的 `aos_mailbox` 意思不變（掛了的時候信投到哪，硬碟上的；demo 沒有，寫 `-`）。

## 碰到的【開】與怎麼處理（都挑保守的，使用者看了不對就改）

| 碰到的 | 怎麼做 |
|---|---|
| 還沒收過指令時 `aos_ctl_state` 寫什麼 | `-`（跟 `aos_ctl_cmd` 一樣） |
| 被拒的那次算不算 `aos_ctl_count`、動不動 `aos_ctl_cmd` | 算、會動（被拒的原因也要在回饋裡，回饋講的是「最後一次」）；只有「鎖著被擋」的不動 |
| 被拒時寫入回什麼錯 | `EINVAL`（殼裡是 `write error: Invalid argument`）；鎖著是 `EBUSY` |
| 多行被拒的回饋 | 照不認得的字一樣記 `rejected`、`aos_ctl_error: LinesTooMany 2 lines in one write` |
| 參數不對（`slow x`） | 跟不認得的字一樣：`rejected`、`ArgumentsBad …`、寫入失敗 |
| 空寫入（`echo > ctl`） | 什麼都不動、回成功 |
| `aos_started_at` 的格式 | ISO 8601 本地時間帶時差（`2026-11-25T15:48:45+08:00`） |
| socket 叫什麼（第 9 節） | 沒定；demo 只為了測試叫 `sock`，不是標準名 |
| 掛載點放哪 | 呼叫的人給；測試全放 `~/.aos/scratch/proto9-procfs-1125/mnt/` |
| `_metainfo.json` 的內容 | demo 只放一行 `summary` |

**信箱與環境變數碰到的【開】**（都挑保守的）：

| 碰到的 | 怎麼做 |
|---|---|
| 一封信是一個檔還是一個夾 | 兩種都收（Maildir 是檔、proto8 aos-post 是夾）；信夾只有一層，裡面不能再開夾 |
| 上限的預設 | 一封 8 MiB、合計 4096 項、合計 64 MiB、一個信夾 64 個檔、`tmp/` 36 小時；都可改 |
| 超過上限回什麼 | 單封太大 `EFBIG`；項數、總量、檔數 `ENOSPC`。都算進 `refused`、原因記進 `last_refusal` |
| 項數上限數哪些 | `tmp/`＋`new/` 頂層合計；在 `tmp/` 開新的一項時就擋（早點失敗，不必寫完才知道） |
| 拒收回什麼 | 由 proc 的 `Accept` 自己挑；demo 用 `EPERM`（`Operation not permitted`），原因 `MailRefused ...` |
| demo 怎麼拒收 | 另一個 ctl 字 `refuse on|off`，不跟 `pause` 綁在一起 |
| 被拒的信 | 留在 `tmp/`、解封，寄的人自己刪（aos-post 會刪）；過期了也會被丟 |
| `take()` 的順序 | 照搬進 `new/` 的先後（不是 aos-post 的「有序名在前、照名字排」）；要照名字的 proc 之後再加 |
| 寄件人是誰 | 記搬進 `new/` 那次 `rename` 請求的 uid／pid；不擋 |
| `cur/`、信箱根 | 擺著、不能寫；所以 `aos-post send --ordered`（要在根開 `order.lock/`）寄不進來 |
| 搬出 `new/`、刪 `new/` 的、改 `new/` 的 | 一律拒（`EPERM`）：寄到了就歸 proc，只有 `take()` 拿得走；`cat` 照讀 |
| 名字 | `.` 開頭的不能搬進 `new/`（`EINVAL`；Maildir、aos-post 都說 `.` 開頭不算信）；控制字元、`/`、超過 255 字拒 |
| 過期怎麼算 | 寄的人最後一次動它（開、寫、截短、改名）起算，不看 `stat` 的時間（寄的人改得了那個） |
| 過期誰來清 | 不另開線：在 `tmp/` 開新東西、列 `tmp/`、`stats()` 時順手掃 |
| `fsync` | 一律成功 |
| 屬性快取 | 信箱裡的一切名字與屬性都不快取（`entry_valid`、`attr_valid` 都是 0），檔用 `direct_io` |
| `AOS_NAME_PID` 對不上、或格式不對 | 當沒給（不報錯），程式照沒給環境變數的情形走 |

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

## 測試（`tests/run.py`、`tests/mail.py`）

`tests/run.py` 40 條全過（basic 19、kill 5、abort 3、socket 4、links 5、env 3，加最後一條「沒有殘留的行程與掛載」）。驗的有：status 八行；`pause` 後 `aos_phase: paused`；`slow 3` 進行中別人寫 `pause` 當場 busy、回饋沒動、`status` 照樣讀得到（約 5～9 ms）；兩人先開檔再先後寫第二個 EBUSY；不認得的字寫入失敗且 `rejected`；一次寫兩行被拒；收下了、做的時候失敗（`unlink` 不存在的）是 `failed`＋原因；`done` 時 error 是 `-`；`stop` 後退出、掛載與夾都沒了；`kill -9` 後 `/proc/<PID>/cwd` 馬上不見、死掛載留著、`--cleanup` 活著時不動、死了收得掉；abort；socket；symlink 隨時加、拿掉（拿掉後馬上走不到）；`AOS_NAME_PID` 三種情形（見上面「環境變數」）。

`tests/mail.py`（後半在 `tests/mail_more.py`）36 條全過（shell 3、half 3、clash 2、limits 5、refuse 3、take 3、stale 1、big 2、guards 2、folder 3、aospost 3、stopped 2、many 3，加「沒有殘留」）。掛載與暫存放 `~/.aos/scratch/proto9-mailbox-1125/`。驗的有：`attrs` 有 `aos_mailbox: yes`、`settings` 的照舊是 `-`；殼裡 `printf > tmp/a && mv tmp/a new/a` 寄到、`status` 的 `mail_*` 跟著動；寫一半的只在 `tmp/`、`new/` 看不到；搬進 `new/` 後還開著的 fd 再寫＝`EPERM`；撞名＝`EEXIST`（`rename` 與 `mv` 都是）、第一封原樣；`.` 開頭搬不進 `new/`；三種上限各自 `EFBIG`／`ENOSPC`、拿走與刪掉後又有空間；拒收時 `mv` 失敗、`new/` 沒東西、信還在 `tmp/`，關掉拒收同一個 `mv` 就過；`take` 拿最早的、計數跟著動、沒信時 `failed MailEmpty`；過期的檔與信夾被丟、新的留著；1 MB 的信逐 byte 一樣；不該做的九樣都擋下；信夾的形狀（aos-post 那幾步用殼做一次）；proto8 `aos-post` 實寄三種情形；被 SIGSTOP 時寄信卡住、SIGCONT 後寄到；1000 封等著時讀 `status` 一樣快。整支要放在 `timeout` 底下跑（`make test` 沒包；直接下系統呼叫的那幾步，伺服器真壞掉時會卡住）。

收尾：`tests/common.py` 用 atexit＋SIGTERM 收——叫醒被暫停的、殺掉起過的、`fusermount3 -u -z` 卸掉 scratch 底下 `fuse.aosproc` 的掛載、刪空夾。只跑部分、或跑到一半被 `timeout` 殺掉也會收（實測過）。限時的殼指令到時只 kill、不等（卡在 FUSE 裡的人等不到）。

## 行數

庫（`include/`＋`src/`）1903 行；demo 383 行；測試與量測 901 行。每個檔都在 300 行以內（最長 `demo/main.cpp` 287、`src/answer.cpp` 240）：原本 391 行的 `answer.cpp` 拆成 `answer.cpp`（分派、屬性）與 `ops.cpp`（一般節點的較長操作），信箱另三個檔。

## 還沒做的

- daemon 的部分（`procs/`、`procs_ctl`、`procs_status`、卡住的檢查）：庫備好了零件（symlink 隨時加拿、ctl 可設字首、`connection_id`／`abort_connection`／`cleanup_dead_mount`），還沒有 daemon 本身。
- 各檔的 json 版（`status.json`…）、`persist` 怎麼擺。
- 卸載時回答的線 2 秒內醒不來（abort 也失敗）就只 detach、不關 fd；這時 `Fs` 若被解構，線會碰到已經釋放的記憶體——現在只有行程馬上要結束的情形會走到，沒處理。
- 回答的線只靠文件守規矩：`Producer` 裡硬去讀檔，庫攔不到。
- 收到的請求長度、名稱都有防越界，但沒做模糊測試；INIT 只對過這台的 7.39。
- 別的 Linux 帳號、bwrap 沙箱裡用 socket：沒測。
- 信箱：plumber 那種「一個只寫的檔 `msg`」、socket 上的一行一則、各檔的 json 版都沒做。`aos-post send --ordered` 寄不進來（要在信箱根開 `order.lock/`）。`link()` 式的投遞（老的 qmail 那樣 `link tmp/x new/x` 再 `unlink`）不收。信只在記憶體裡：proc 一死，還沒 `take()` 的信就沒了（草稿「收到後還沒處理就死：介面不保證」）。`new/` 裡找名字、拿最早的一封都是線性掃，幾千封還好，再多要換資料結構。
- 沒進 `proto8/cpp/Makefile`、沒進 code map 與 `_index.json`（只准寫這一夾）。
