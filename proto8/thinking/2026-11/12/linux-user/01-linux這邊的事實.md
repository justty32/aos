# linux user 初步調查之一：linux 眼中的「使用者」是什麼、誰在誰上面、權限與上限照什麼算（11-12 晚家機唯讀實看）

← [linux-user](../linux-user.md)｜下一份 [02-對到aos現況](02-對到aos現況.md)

## 使用者不是行程，是行程身上的一個號碼

linux 裡沒有一個叫「使用者」的東西在跑。使用者只是一個號碼，叫 uid（user id，使用者編號）；`/etc/passwd` 這張表把號碼對到名字、家目錄、登入後用的殼。真正在跑的只有行程，每個行程身上貼著一個 uid，孩子行程預設跟父行程同一個號碼。

所以「這個使用者」在 linux 眼中是**一群貼著同一個號碼的行程，加上屬於這個號碼的檔案**，不是一個行程。使用者沒登入、一個行程都沒有的時候，這個使用者照樣存在（號碼在表上、檔案還在）。

家機實看：

```
$ id
uid=1000(lorkhan) gid=1001(lorkhan) groups=1001(lorkhan),3(sys),…,998(wheel),…
```

## 最接近「代表這個使用者的那個行程」的東西

有三個候選，從最像到最不像：

1. **`systemd --user`**：systemd 是 linux 開機後的第一個行程（pid 1），負責起別的行程、看它們活著。它替每個有行程在跑的 uid 另外起一隻小的自己，身分就是那個使用者，專門管這個使用者的東西。一個 uid 只有一隻；這個使用者的其他行程幾乎都是它的子孫。預設是使用者登入時起、全部登出時收；開了 linger（「留著」）就開機就起、沒人登入也在。
2. **user slice**：cgroup（control group，把一群行程圈成一組、整組一起算資源的機制）裡，systemd 給每個 uid 一格，叫 `user-<uid>.slice`。這個 uid 的所有行程都在這一格裡，整格可以設總上限。它不是行程，是一個圈。
3. **登入的殼或圖形 session**：人坐在鍵盤前的那一個。一個使用者可以同時有好幾個（好幾個終端機、ssh），所以它代表的是「這一次登入」，不是「這個使用者」。

家機實看（`loginctl` 是問「現在誰登入著」的指令）：

```
$ loginctl
SESSION  UID USER    SEAT  LEADER CLASS   TTY
      1 1000 lorkhan -     770    manager -      ← systemd --user 那隻
      2 1000 lorkhan seat0 886    user    tty1   ← 圖形登入
$ loginctl show-user lorkhan
Slice=user-1000.slice   State=active   Linger=yes   RuntimePath=/run/user/1000
$ ps -o user,pid,ppid,cmd -p 770
lorkhan  770  1  /usr/lib/systemd/systemd --user
```

家機這個使用者的 `systemd --user` 是 pid 770、父行程是 pid 1，而且 Linger=yes——人不登入它也在。

## 誰是誰的上一層

行程樹是「誰起了誰」。家機現在這個 Claude Code 主 session 的一路往上：

```
systemd(1) ─ systemd --user(770) ─ ghostty 終端機(1670) ─ zsh(2578) ─ claude(3141) ─ …
```

root daemon 的父行程就是起它的那個東西：在終端機打指令起的，父是那個殼；用 `setsid nohup … &`（試驗場的起法，意思是「跟這個終端機脫鉤、關掉終端機也別死」）起的，殼一走它就變孤兒，被最近的收養者接走——在家機就是 `systemd --user`。實看到幾台測試留下的 aos 樹正是這樣：

```
USER     PID      PPID  CMD
lorkhan  1152480  770   aos-daemon --enable-logs daemon.json     ← 父是 systemd --user
lorkhan  1152532  770   aos-exec --stack stacks/root defs
lorkhan  1152533  1152532 aos-daemon --enable-logs daemon.json
```

（這幾台在 `/tmp/aos-daily-…` 底下，是測試留下沒收的，不是試驗場；沒去動。試驗場 `~/code/playground` 的根 daemon 停著，`state.json` 的 `phase` 是 `stopped`。）

被收養不等於被照顧：`systemd --user` 只是名義上的父，不會幫它重起。要它真的照顧（死了重起、開機自動起），得把 root daemon 登記成它的一個服務（一份小設定檔放在家目錄下，不需要 root）。

## 權限、訊號、上限各照什麼算

| 事情 | 照什麼算 | 白話 |
|---|---|---|
| 檔案能不能讀寫 | uid 與群組 | 每個檔記著擁有者、群組、三組權限（擁有者／同群組／其他人）；行程拿自己身上的 uid 去比 |
| 能不能送訊號（殺、停別的行程） | uid | 同一個 uid 的行程可以互殺；殺不了別的 uid 的 |
| 能不能偷看別的行程的記憶體 | uid（加一個系統開關） | 家機 `ptrace_scope`＝1：同 uid 也只能看自己的子孫 |
| 單一行程的上限（ulimit／rlimit） | 行程，往下繼承 | 記憶體、CPU 秒、開檔數；孩子只能更嚴、不能更寬 |
| 「這個使用者總共能開幾個行程」 | uid | rlimit 裡唯一照 uid 加總的（家機 246988） |
| 一群行程的總量上限 | cgroup | 圈一組、整組一起算；user slice 是現成的一格（家機開了 cpu、memory、pids 三種，memory 沒設上限） |

在自己那一格底下再圈小格、設上限，一般使用者自己就能做（`systemd-run --user --scope`），但要連得到 `systemd --user` 的連絡窗口（user bus，一個放在 `/run/user/<uid>/` 的 socket）。家機連得到，實測：

```
$ systemd-run --user --scope -q -p MemoryMax=64M -p MemorySwapMax=0 \
    python3 -c 'x=bytearray(300*1024*1024); print("survived")'
（沒印 survived）結束碼 137        ← 超過 64MB 被 linux 殺掉
```

[no-pid P8](../../05/no-pid/18-P8實作結果.md) 在公司那邊同一條指令報 `Failed to connect to user scope bus`，是因為當時在沙箱裡、沙箱連不到這個窗口。

## root 這個使用者特別在哪

root 是 uid 0。它特別在三件事：權限檢查對它幾乎全部放行（任何檔都能讀寫、任何行程都能殺）；它能把一個行程的 uid **換成任何人**（一般使用者不能換）；建帳號、設別人那格的上限、改系統設定都只有它能做。

一般使用者要暫時借 root 的手有兩條路：`sudo`（照一張規則表 sudoers，准某人以某身分跑某指令）與 setuid 程式（檔案上有個記號，誰跑它它都以檔案擁有者的身分跑——`sudo` 自己就是這種）。

## 不同使用者之間現成的互動管道

| 管道 | 怎麼運作 | 家機有沒有 |
|---|---|---|
| 檔案與資料夾權限、共享群組 | 把兩個帳號放進同一個群組，資料夾開給群組寫 | 有（linux 本來就有） |
| 傳統 unix 信 | 每個使用者一個信箱檔 `/var/spool/mail/<名字>`，`mail 名字` 寄、登入時提示「你有新信」 | 指令 `mail` 在、`/var/spool/mail` 在；有沒有人在送信沒查 |
| `write`／`wall` | 把一行字直接印到對方（或所有人）正開著的終端機；對方沒登入就送不到 | 指令在 |
| socket | 檔案系統上的一個連絡點，兩邊行程接起來對話，能不能接照檔案權限 | 有 |
| sudo／setuid | 借身分跑東西（見上） | `sudo` 在；`s6-setuidgid` 不在 |

注意傳統 unix 信跟 aos 信箱是同一個形：**地址就是使用者名字、信箱放在家目錄以外的公共位置、人不在信就躺著、登入時才提醒**。

家機目前 `/home` 底下只有一個帳號；家目錄權限是 700（只有自己進得去），所以家目錄裡的任何東西，別的 uid（root 以外）連路都走不到。
