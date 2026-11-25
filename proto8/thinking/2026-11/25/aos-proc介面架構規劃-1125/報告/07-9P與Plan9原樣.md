9P 與 Plan 9 的 /proc 原樣（對過原始手冊與核心原始碼）、逐條對照使用者定的、「基於 9P」的三個層次：思想大半照搬得過來，但 status 格式其實是 Linux 式、錯誤那句話一掛載只剩錯誤碼、proc 自己回答比核心替大家回答多出強制手段、死後紀錄、列表三件要另外定。

# 9P 與 Plan 9 的 /proc 原樣，以及「基於 9P」的三個層次

← [架構規劃入口](../README.md)

**出處怎麼標**：這次外網連得上，所以大部分內容對過原文，不是憑記憶。`名(節)`＝Plan 9 第四版手冊（9p.io）；`devproc.c:行`、`parse.c`、`proc.c`、`lib.h`、`devmnt.c`、`lib9p/srv.c`、`ps.c`、`echo.c`、`/rc/bin/*`＝Plan 9 核心、函式庫、指令與腳本的原始碼（GitHub `plan9foundation/plan9`）；`linux/…:行`＝Linux 上游 v6.6（這台是微軟的 6.6.114 分支，行號沒逐行對）；`p9p 名(節)`＝plan9port（把 Plan 9 的工具搬到 Unix 上的那套）手冊；9P2000.u 是 ericvh 的 9p-rfc 草稿，9P2000.L 是 diod 專案的 `protocol.md`。抓下來的副本與實驗程式在 `~/.aos/scratch/aos-proc-arch-1125/07/`（`dl/`、`exp/`；暫存，不在 repo）。仍然憑記憶的地方逐處標「憑記憶」；我的推論標「推論」。

## 1. 結論

1. 使用者定的這幾條——ctl／status 純文字、要更多資訊就多給一個檔、目錄在＝活著、系統服務就是擺出檔的普通行程——都是 Plan 9 原樣的思想。aos 自己加的是：`_metainfo`（json）、`settings`、`persist`、token 用量、daemon 的 procs 夾、掛了改寄信。
2. 有三處跟 Plan 9 原樣不一樣，寫規格時要知道：Plan 9 的 `status` 是靠位置認欄位的一筆固定寬度紀錄，一行一個「名稱: 值」是 Linux 的樣子；Plan 9 的 `stop` 是暫停、`kill` 才是結束；Plan 9 寫 ctl 回來，有的字代表做完了（`stop` 會等到真的停），有的只是收到（`kill`）。
3. 最大的結構差別：Plan 9 是核心一個人替所有行程回答，aos 是每個 proc 自己回答。這帶出三件要另外定的事：卡死的 proc 回答不了自己的 ctl（強制手段得歸 daemon）；proc 一死，它目錄裡的東西跟著沒（死因與最後用量得留在別處）；列出全部要去問很多個回答者（一個卡住就拖住）。
4. 「基於 9P」的三個層次（只學長相／socket 上真的講 9P／掛成檔案系統）可以同時成立，條件是規格分成「語意一份、接法三份」，而且語意只規定三層都做得到的事。9P 才有的好處（錯誤一句話、讀了會等、誰最後寫的）列成加分項。
5. 9P 的錯誤是一句字串，但只有直接講 9P 的那一層送得到；在 Linux 上一掛載（FUSE 或核心的 9p），程式拿到的只剩錯誤碼。所以「為什麼被拒」要另有一個讀得到的地方。
6. stat 的欄位裡，三層都拿得到、對 aos 有用的只有 mtime、length、mode。muid（誰最後寫的）與版本號很好用，但一掛載就看不到。
7. 背景：Plan 9 的 `/proc/n` 是核心替每個行程擺出來的一夾檔——`ctl`（寫一句字去控制）、`status`（一筆紀錄）、`note`（送一句短訊）、`wait`（讀了會等）、`ns`、`fd`、`args`、`mem`…。`ps`、`kill` 都只是讀寫這些檔的小程式。
8. 實測：一個最小的 9P2000 伺服器 189 行 Python、用戶端 112 行；`echo stop > ctl` 在線上是 4 來 4 回、共 137 bytes。

## 2. 查到的事實

Plan 9 是貝爾實驗室做的作業系統；9P 是它裡面所有東西互相講話用的檔案協議；/proc 是它把行程擺成檔的那個目錄。

### 2.1 先分清楚三個容易混的名字

| 名字 | 是什麼 |
|---|---|
| 9P 的 stat | 協議裡**每個檔都有的一筆屬性紀錄**（名字、大小、時間、擁有者…，二進位），`ls -l` 印的就是它。不是一個檔。 |
| Linux 的 `/proc/<PID>/stat`、`statm` | Linux 才有的**檔**，內容是一行靠位置認的數字。Plan 9 的 /proc 沒有這兩個檔名。 |
| `status` 檔 | Plan 9 與 Linux 都有。Plan 9 的是固定寬度、靠位置認（其實比較像 Linux 的 `stat`）；Linux 的是一行一個「名稱: 值」。 |

使用者原話「就是9p現有的實作上，比如stat那些，他們給的不是json，那就按照他們的來。只是說，你知道的，cat /proc/<PID>/stat,status,statm，他就是給出不同東西」裡的 stat，兩種讀法都通：讀成協議的屬性紀錄，結論是「檔的屬性照 9P 的欄位，不另外發明」（見 2.3、3.5）；讀成 /proc 底下那幾個檔，結論就是已經定的「status 用純文字、目前只給 status」。兩種讀法不衝突。

### 2.2 9P2000 的訊息

9P 是「用戶端問一句（T 開頭）、伺服器答一句（R 開頭）」的協議，全部只有 13 種問答加一種錯誤回覆。每則訊息的開頭都是：總長度 4 bytes、種類 1 byte、tag 2 bytes；數字一律低位在前；字串是「2 bytes 長度＋UTF-8」，不能含 NUL（`intro(5)`）。

| 訊息（T／R 編號） | 做什麼 |
|---|---|
| version（100／101） | 連線的第一句。講好單則訊息最大幾 bytes（msize）與版本字串 `9P2000`；伺服器不懂就回 `unknown`。成功後這條連線上舊的 fid 全部作廢。 |
| auth（102／103） | 可有可無。拿一個「認證用的檔」（afid），在上面用 read／write 跑認證；認證協議本身「不屬於 9P」。伺服器不要求認證就回錯。 |
| attach（104／105） | 報上名字（uname）、選哪棵樹（aname）；成功後給的 fid 指向樹根。 |
| walk（110／111） | 從一個 fid 往下走最多 16 段名字，走到的地方記成新的 fid；0 段＝複製 fid；第一段就走不通回錯，只走通前幾段就回前幾段、新 fid 不成立；`..` 是上一層。 |
| open（112／113） | 檢查權限、把 fid 準備成可讀寫。模式：讀 0、寫 1、讀寫 2、執行 3，可再加「清空」（OTRUNC）與「關掉時刪檔」（ORCLOSE）。**權限只在這一刻檢查**。 |
| create（114／115） | 在目錄裡建新檔（權限帶 DMDIR 就是建目錄）並開啟。 |
| read（116／117） | 從某個位移讀若干 bytes，回的可以比要的少。讀目錄回的是一筆筆完整的 stat 紀錄。**伺服器可以晚點才回**（例如等鍵盤、等事件）。 |
| write（118／119） | 寫。回覆裡的 count 是實際收下幾 bytes。 |
| clunk（120／121） | 「這個 fid 我不用了」（＝close）。 |
| remove（122／123） | 刪檔，順便 clunk。 |
| stat（124／125） | 回這個檔的屬性紀錄（2.3）。不需要任何權限。 |
| wstat（126／127） | 改名、改長度、改權限與 mtime、改群組；要嘛全改、要嘛全不改；不想動的欄位填「別碰」的值；整筆都是「別碰」＝請把內容寫到穩固的地方。擁有者不能改。 |
| flush（108／109） | 「tag 是某某的那個請求我不等了」。伺服器一定回 Rflush，不會回錯。 |
| error（只有 R，107） | 任何請求失敗都回這個，內容是**一句說明原因的字串**。沒有錯誤碼。 |

三個詞：

- **tag**（2 bytes）：用戶端替每個請求取的號碼，回覆帶同一個號碼。有它，才能同時發好幾個請求、回覆不照順序回來。
- **fid**（4 bytes）：用戶端取的號碼，代表「伺服器上我現在指著的那個檔」。像檔案描述符，但還沒開啟的檔（正在走、正在查屬性）也用 fid。
- **qid**（13 bytes）：伺服器給每個檔的身分證＝種類 1 byte＋版本號 4 bytes＋唯一編號 8 bytes。兩個檔是同一個，若且唯若 qid 相同；檔每改一次版本號通常加一；刪掉重建的同名檔，唯一編號要不同（`intro(5)`）。

### 2.3 stat 紀錄的欄位（`stat(5)`、`stat(2)`）

| 欄位 | 長度 | 意思 |
|---|---|---|
| size | 2 | 後面總共幾 bytes |
| type、dev | 2、4 | 核心自己用 |
| qid.type | 1 | 種類：目錄 0x80、只能附加 0x40、獨佔（一次只准一個人開）0x20、認證檔 0x08、暫時檔 0x04、普通檔 0 |
| qid.vers | 4 | 版本號 |
| qid.path | 8 | 這個檔在這台伺服器上的唯一編號 |
| mode | 4 | 低 9 位元是擁有者／群組／其他人的讀寫執行；高位元重複上面的種類 |
| atime | 4 | 最後一次被讀的時間（1970 年起的秒數） |
| mtime | 4 | 最後一次改內容的時間（秒）。目錄的 mtime 是裡面最近一次建檔、刪檔或 wstat |
| length | 8 | 幾 bytes。目錄與大多數裝置類的檔慣例填 0；管線這類串流填「現在不用等就讀得到幾 bytes」 |
| name | 字串 | 檔名（樹根固定叫 `/`） |
| uid | 字串 | 擁有者的**名字**（是字串，不是數字） |
| gid | 字串 | 群組的名字 |
| muid | 字串 | 最後一個改它的人的名字 |

一筆最多 65535 bytes。Plan 9 的 `ls -l` 印前面這些，`ls -m` 印 muid，`ls -q` 印 qid（`ls(1)`）。

### 2.4 9P2000.u 與 9P2000.L 多了什麼

- **9P2000.u**（給 Unix 用的擴充，一份沒寫完的草稿，好幾節是 TODO）：Rerror 多一個數字錯誤碼；attach／auth 多一個數字 uid；stat 多 `extension` 字串（放 symlink 的目標、裝置號）與數字的 uid／gid／muid；mode 多 symlink、裝置、named pipe、socket、setuid 等位元。草稿自己寫了一句：自製伺服器回的自訂錯誤字串對不上任何標準錯誤時，建議「另外找個機制」讓應用程式拿得到（草稿的 2.1.2 節）。
- **9P2000.L**（照 Linux 的檔案系統介面重排，Linux 核心預設用它）：留下 version、auth、attach、flush、walk、read、write、clunk、remove；open／create／stat／wstat 換成 lopen、lcreate、getattr、setattr；新增 readdir、mkdir、symlink、readlink、link、mknod、rename、unlinkat、statfs、fsync、檔案鎖、延伸屬性（xattr）。錯誤換成 `Rlerror`，**只有一個 Linux 錯誤碼、沒有字串**。getattr 回的是 Linux 的那套屬性（數字 uid／gid、奈秒時間、連結數），沒有 muid、沒有名字字串（`diod protocol.md`、`linux/include/net/9p/9p.h`）。

### 2.5 Linux 核心的 v9fs 怎麼掛（`linux/Documentation/filesystems/9p`、原始碼）

`mount -t 9p -o trans=<走哪種連線>,<其他選項> <位址> <掛載點>`

| trans | 位址寫什麼 | 備註 |
|---|---|---|
| tcp | IP | 預設埠 564（`linux/net/9p/trans_fd.c:33`） |
| unix | unix socket 的路徑 | 路徑要短於 108 bytes，否則 `ENAMETOOLONG`（同檔 1047-1050） |
| fd | 隨意 | 用掛載的人已經開好的檔案描述符：`rfdno=`、`wfdno=` |
| virtio | 掛載標籤 | 虛擬機用 |

常用選項：`version=`（`9p2000`、`9p2000.u`、`9p2000.L`；不寫是 .L，伺服器回比較舊的版本就照伺服器的：`linux/net/9p/client.c:143`、`943-948`）、`uname=`、`aname=`、`access=`（每個 Linux 帳號各 attach 一次，或全部當同一人）、`cache=`（預設不快取）、`msize=`（預設 128K＋24：`client.c:35`）。

本機查到的：

- 這台核心內建 9p：`CONFIG_9P_FS=y`、`CONFIG_NET_9P_FD=y`（tcp、unix、fd 三種都在這個選項裡）、`CONFIG_NET_9P_VIRTIO=y`（`zcat /proc/config.gz`）。
- 這台天天在用 9P：WSL 的 `/mnt/c` 就是它掛的。`/proc/mounts`：`C:\134 /mnt/c 9p rw,noatime,aname=drvfs;…,cache=5,access=client,msize=65536,trans=fd,rfd=6,wfd=6`（沒印 version＝預設的 .L）。
- **掛 9p 要 root**：它的檔案系統旗標只有 `FS_RENAME_DOES_D_MOVE`，沒有「可在使用者命名空間裡掛」那個（`linux/fs/9p/vfs_super.c:345`）。agent 不能 sudo，所以這條路 agent 自己走不了；FUSE 可以（`/usr/bin/fusermount3` 是 setuid）。做不做得出來歸 [09](09-FUSE與9P實作可行性.md)。

### 2.6 Plan 9 的 `/proc/n` 底下有哪些檔（`proc(3)`、`devproc.c`）

| 檔 | 誰能動（預設，簡化過） | 讀到什麼 | 寫進去代表什麼 |
|---|---|---|---|
| `ctl` | 擁有者寫 | （不能讀） | 一次寫一句控制訊息，見 2.7 |
| `status` | 大家可讀 | **一筆 176 bytes 的固定寬度紀錄**，12 欄、用空白隔開、靠位置認：程式名、使用者、狀態、六個時間（毫秒：自己的 user／sys／real，子孫的 user／sys／real）、記憶體（K）、基礎優先權、目前優先權（`devproc.c:72`、`837-870`，`lib.h:171`） | — |
| `args` | 擁有者 | 啟動時的參數（帶空白的欄用單引號括） | 行程可以改寫自己顯示出來的參數 |
| `note` | 擁有者 | 拿走最舊一則還沒送達的 note（它就不會送到了；除錯器用） | 一句字串＝**送一則 note 給這個行程**。note 像 Unix 的信號，但內容是字串；短於 127 bytes；最多積 5 則。外面送來的 note 沒人接，行程就結束（`notify(2)`） |
| `notepg` | 只能寫 | — | 同上，但送給同一個 note 群組的全部行程（寫的人自己除外） |
| `noteid` | 可讀 | 這個行程的 note 群組編號 | 換到另一個（同使用者的）群組 |
| `wait` | 擁有者讀 | 讀一次拿一筆「結束了的子行程」紀錄：`pid 三個時間 '結束訊息'`。**還沒有紀錄就卡住等**。stat 的 length 大於 0 表示有紀錄可拿（`devproc.c:252-254`、`894-928`） | — |
| `ns` | 大家可讀 | 這個行程的 namespace：一行一個 `bind`／`mount`，最後一行是 `cd 目前目錄`，可以拿去重建 | — |
| `fd` | 大家可讀 | 第一行是目前目錄；之後一行一個開著的檔（編號、讀寫、裝置、qid、位移、開啟時的路徑） | — |
| `segment` | 大家可讀 | 一行一個記憶體區段 | — |
| `text` | 只讀 | 開它等於開這個行程的執行檔 | — |
| `mem` | 擁有者 | 行程的記憶體，位移＝虛擬位址 | 行程在 Stopped 時才能寫 |
| `regs`、`fpregs`、`kregs`、`proc` | 擁有者 | 暫存器與核心裡的行程結構（跟機器有關的二進位） | 前兩個可寫 |
| `profile`、`syscall` | 擁有者 | 取樣統計、系統呼叫追蹤（`syscall` 手冊沒寫，原始碼裡有） | — |

幾件跟 aos 有關的性質：

- 每個 `/proc/n` 的擁有者（stat 的 uid）就是那個行程的使用者；`ctl`、`mem`、`note` 這幾個檔的權限照「行程的預設權限」（預設 0640，`proc.c:1371`），對檔做 wstat 可以改它（`devproc.c:463-508`）。也就是說「誰能控制這個行程」是用檔的權限位元表達的。
- 行程一死，目錄立刻不見；別人手上還握著的 fid，下一次操作就回 `process exited`。做法是把 pid 放在 qid 的版本號裡，對不上就拒絕（`devproc.c:133-146`、`377`、`717`）。
- 例外：異常死掉的行程會停在 Broken 狀態，`/proc/n` 整個留著給除錯器看，直到有人對它的 ctl 寫 `kill`（`ps(1)`、`kill(1)` 的 `broke`）。
- 正常結束的行程只留下一筆 wait 紀錄，交給父行程（放在**父行程**的 `wait` 檔裡）。
- `ps` 是一支讀 `/proc/*/status` 與 `args` 再排版的普通程式（`ps.c:64-88`）；`kill`、`stop`、`start` 是各 5 行左右的 rc 腳本。

### 2.7 `ctl` 收哪些字、寫回來代表什麼（`proc(3)`、`devproc.c:1299-1476`）

| 字 | 做什麼 | 寫回來代表 |
|---|---|---|
| `stop` | **暫停**行程 | **真的停了**：寫的人會卡住，直到它進入 Stopped 或死掉（`devproc.c:1201-1226`、`1396`） |
| `start` | 讓 Stopped 的行程繼續 | 已放行；它不是 Stopped 就回錯 |
| `waitstop` | 不動它，只是等它停 | 它停了 |
| `startstop` | 放行，再等它下一次停 | 它又停了 |
| `kill` | **結束**行程 | **只是收到**：行程下一次進出核心時才死（`devproc.c:1330-1344`） |
| `hang`／`nohang` | 設／清「下次 exec 完先停住」的記號 | 記號設好了 |
| `pri n`、`fixedpri n` | 設基礎優先權（要調到比一般高，得是主機擁有者） | 設好了 |
| `wired n` | 綁在第 n 顆處理器 | 設好了 |
| `close n`、`closefiles` | 關掉它的第 n 個／全部開著的檔 | 關了 |
| `private`、`noswap` | 之後誰都讀不到它的記憶體／不准換出 | 設好了 |
| `trace`、`profile`、`event` | 追蹤與取樣的開關 | 設好了 |
| `period`、`deadline`、`cost`、`sporadic`、`yieldonblock`、`admit`、`expel` | 即時排程的參數；`admit` 會做「排不排得進去」的測試 | 設好了；`admit` 測不過就回錯、附原因 |

（即時排程那幾個字，手冊與原始碼列的略有出入；表裡照手冊。）

文法（`parse.c`，所有裝置的 ctl 檔共用這一份）：**一次 write＝一句**；去掉結尾的一個換行；用空白切欄。寫錯了都是「這次 write 失敗、原因是一句字串」：

| 情況 | 回的字串 |
|---|---|
| 空的 | `empty control message` |
| 不認得的字 | `unknown control message "…"`（引號裡是原訊息） |
| 參數個數不對 | `wrong #args in control message "…"` |
| 狀態不對（例如對沒停的行程寫 start） | `bad process or channel control request` |
| 行程已經死了 | `process exited` |
| 沒權限、或對象是核心自己的行程 | `permission denied` |

### 2.8 /srv、namespace、exportfs／import、factotum、Styx

- **/srv**（`srv(3)`）：佈告欄。行程把一個開著的連線（通常是一條講 9P 的管線的一端）貼成 `/srv/名字`——建這個檔、把檔案描述符的編號寫進去。別人 open 它就拿到同一條連線，通常接著 `mount /srv/名字 /某處`。貼的人不在了，這個檔還在；刪掉才算撤下。
- **每個行程自己的 namespace**（`bind(1)`、`fork(2)`、`namespace(6)`）：每個行程（群組）有自己的一張「名字指到哪」的表。`bind 新 舊`＝讓舊名字也指到新的那個東西；`mount /srv/x 舊`＝把一條 9P 連線的樹接在舊名字上；加 `-a`／`-b` 是疊成 union 目錄（幾個目錄疊成一個，照順序找），加 `-c` 才准在裡面建檔。`rfork` 決定子行程跟父行程共用這張表（預設）、複製一份（RFNAMEG）、還是從空的開始（RFCNAMEG）；RFNOMNT 之後不准再 mount。開機時照 `/lib/namespace` 建，裡面就有 `bind #p /proc`、`bind -c #s /srv`、`mount -a /srv/factotum /mnt`。
- **exportfs／import**（`exportfs(4)`、`import(4)`）：exportfs 把自己 namespace 的一塊用 9P 送出去（它是轉手的伺服器）；`import 機器 /proc` 把遠端的那一塊接進本機。手冊裡的例子 `srvfs broke /mnt/term/proc` 就是把一份 /proc 貼出去讓別人遠端除錯。
- **factotum**（`factotum(4)`）：每個使用者一個的「鑰匙管家」，本身也是擺出檔（`rpc`、`ctl`、`proto`…）的普通行程，貼在 `/srv/factotum`。9P 的 auth 只留了一個位子（afid 那個檔），真正的認證對話由程式在 afid 與 factotum 的 `rpc` 檔之間轉手，密碼不進應用程式（`auth(2)` 的 `auth_proxy`）。
- **Styx**：Inferno 系統對同一套協議的叫法，現行版本跟 9P2000 一樣（Inferno `intro(5)`）。

### 2.9 用 rc 殼操作的樣子

示意，沒在真的 Plan 9 上跑；語法照 `rc(1)`、`proc(3)` 與 `/rc/bin/kill`、`stop`、`slay`、`start` 四支腳本的內容，最後一行的字樣照 `echo.c:34-35` 與 `parse.c`。

```rc
ps                              # 讀 /proc/*/status 印成表
cat /proc/123/status            # 那筆固定寬度的紀錄
echo stop > /proc/123/ctl       # 暫停；這行回來時它已經停了
echo start > /proc/123/ctl      # 繼續
echo kill > /proc/123/note      # 客氣地請它結束（它可以接下來、收尾）
echo kill > /proc/123/ctl       # 強制結束（它接不到、擋不了）
kill myprog | rc                # kill 只「印出」上面那種指令，接給 rc 才真的做
echo hangup > /proc/123/notepg  # 送給它整個 note 群組
cat /proc/123/wait              # 卡住，直到 123 的某個子行程結束，印出 pid、時間、結束訊息
cat /proc/123/ns                # 它眼中的世界：一行一個 bind／mount
ls -lm /proc/123                # -m：每個檔最後是誰改的
import kremvax /proc            # 把另一台機器的 /proc 接到本機，之後 ps 看到的是那台的行程
echo bogus > /proc/123/ctl      # 印出：echo: write error: unknown control message "bogus"
```

### 2.10 實測：同一件事在線上長什麼樣

我寫了一個玩具 9P2000 伺服器（擺出 `ctl`、`status`、`wait`、`_metainfo` 四個檔，掛在一個 unix socket 上）與一個玩具用戶端。重跑：`python3 ~/.aos/scratch/aos-proc-arch-1125/07/exp/run.py`（純標準庫；跑完自己收掉伺服器、刪 socket）。節錄實際輸出：

```
# echo stop > ctl
  -> Twalk    tag=2      22 bytes  fid=0 newfid=1 names=['ctl']
  <- Rwalk    tag=2      22 bytes  nwqid=1
  -> Topen    tag=3      12 bytes  fid=1 mode=1
  <- Ropen    tag=3      24 bytes
  -> Twrite   tag=4      28 bytes  fid=1 offset=0 data=b'stop\n'
  <- Rwrite   tag=4      11 bytes  count=5
  -> Tclunk   tag=5      11 bytes  fid=1
  <- Rclunk   tag=5       7 bytes
# echo bogus > ctl      (a word the proc does not know)
  <- Rerror   tag=12     40 bytes  ename='unknown control message "bogus"'
# echo start > ctl, twice (second one: wrong state)
  <- Rwrite   tag=13     11 bytes  count=6
  <- Rerror   tag=14     47 bytes  ename='bad process or channel control request'
# stat status           (what 9P itself tells about a file)
   {'name': 'status', 'mode': '0o444', 'dir': False, 'qid': (0, 2, 2), 'mtime': 1795579919, 'length': 45, 'uid': 'toyproc', 'gid': 'toyproc', 'muid': 'alice'}
# cat wait &  ;  echo kill > ctl   (the read on wait gets no reply until the proc dies)
  -> Tread    tag=27     23 bytes  fid=6 offset=0 count=4096   <- no reply yet
  -> Twrite   tag=28     28 bytes  fid=1 offset=0 data=b'kill\n'
  <- Rwrite   tag=28     11 bytes  count=5
  <- Rread    tag=27     27 bytes  count=16
     (tag 27 was the blocked read on wait) data=b"1 0 0 0 'killed'"
# echo stop > ctl after death
  <- Rerror   tag=29     23 bytes  ename='process exited'
```

看得到的事：`echo stop > ctl` 是走、開、寫、關 4 來 4 回，共 137 bytes；`Rwrite` 就是「收到」；被拒是 `Rerror` 帶一句話；stat 裡 `muid` 自動記下最後一個下控制的人（alice）、版本號從 0 變 2；讀 `wait` 的那個請求先懸著，等 `kill` 之後才回，兩個回覆靠 tag 分得清。程式大小：伺服器 189 行、用戶端 112 行（不算空行；一次只服務一個連線、沒做認證）。

## 3. 對新介面的含意

### 3.1 逐條對「定了的」

| 定了的 | Plan 9 原樣怎麼做 | 判定 |
|---|---|---|
| 介面基於 9P；能擺出這套的就是 aos proc；aos-loop／daemon 退成普通實作 | 「介面＝一夾檔的名字與語意，誰擺出來都算」是 Plan 9 的中心思想。連 /proc 都有第二個實作：`snapfs` 把存下來的行程快照擺成 /proc 的樣子、跟活的行程並排，除錯器照用（`snap(4)`）。 | 照搬（思想） |
| 9P 自己有的（stat 之類）照 9P；`ctl`、`status` 純文字；`_metainfo` 照 aos 的 json | Plan 9 全是純文字或二進位，沒有 json。 | stat、ctl、status 照搬；`_metainfo` 是延伸 |
| `ctl` 吃純文字；寫回來＝收到，做完沒看 `status` | 名字與「寫一句純文字」都一樣。但 Plan 9 是逐字而定：`stop`、`waitstop` 等到做完才回來，`kill` 只是收到；不合法的當場回錯。 | 形式照搬；「一律只代表收到」是 aos 把規則簡化成一條 |
| `status` 一行一個「名稱: 值」；目前只給 status；以後多給別的檔 | Plan 9 也叫 status，但是 12 欄靠位置認的固定寬度紀錄。「以後多給別的檔」正是 Plan 9 的做法（args、fd、ns、segment 各一個檔，各有各的格式）。 | 名字照搬；**格式是 Linux 式，不是 Plan 9 式** |
| token 用量 proc 自己報、放自己的目錄；kernel 的帳在 kernel 的目錄；daemon 不管帳 | 行程的用量（六個時間、記憶體）也放在它自己的 status 裡，而且分「自己的」與「子孫的」兩組；各伺服器的統計放各自的樹（例 `/net/tcp/stats`）。 | 放法照搬；token 這個量是延伸 |
| daemon＝Linux 與 aos 之間的橋，也是 aos proc，多一個 procs 夾，每項連到那個 proc 自己的目錄 | Plan 9 沒有這一層：/proc 是核心一個人回答全部。最像的是 `rio`（一個行程替每個視窗擺一個子目錄）與 /srv（大家把自己的連線貼在同一個夾）。 | 延伸，見 3.2 |
| kernel＝普通 aos proc | Plan 9 的核心不是行程；但「系統服務＝擺出檔的普通行程」到處都是（factotum、plumber、rio，連檔案系統都是）。 | 照搬（思想），對到的是 Plan 9 的使用者層伺服器 |
| `proc` 與 `procs` 兩個名字指同一處 | 一個 bind 的事。9P 裡「這兩個是同一個東西」的講法是回同一個 qid。 | 照搬得到 |
| 入口給根 daemon 的 PID；`AOS_ROOT`；走 `/proc/<PID>/cwd` | Plan 9 找服務靠 /srv 裡的名字，不靠 PID。但 `rio` 把自己貼成「使用者名＋pid」，再用環境變數 `$wsys` 告訴它底下的行程（`rio(4)`）——跟 `AOS_ROOT` 帶 PID 是同一招。 | 延伸；有前例 |
| stack＝活著的 proc 的身體；`/proc/<PID>` 就是它 | `/proc/n` 正是這個：目錄在＝行程在，裡面的 `mem` 就是它的記憶體，一死就沒。 | 照搬 |
| 要留的放 `procs/<名>/persist`；位置 proc 自己說（`settings`），daemon 可給預設 | Plan 9 的 /proc 裡完全沒有「留下來的」；要留的就寫到檔案伺服器上的普通檔。「我的東西在哪」最像的是 `ns`（它看到的世界）與 `fd` 的第一行（它站在哪）。 | 延伸 |
| 活著走 unix socket；掛了問 daemon／kernel 信箱在哪，改寄信 | 活著：寫它的 `note`，或跟它擺出來的檔講話。死了：寫不進去（`process exited`），沒有信箱這回事。 | 活著那半照搬得到；掛了改寄信是延伸 |
| 問信箱時要不要順手叫醒：daemon 的可選設定 | `plumber`（訊息轉送站）有一模一樣的開關：規則寫 `plumb client 指令`＝沒人在聽就把程式叫起來、訊息先留著等它來拿；寫 `plumb start 指令`＝叫起來但訊息丟掉（`plumb(6)`）。`listen` 也是有人連進來才起對應的服務程式（`listen(8)`）。 | 延伸；有前例 |

Plan 9 的檔在 aos 裡最像什麼（推論，給寫規格的人對照用）：

| Plan 9 | aos 裡最像的 |
|---|---|
| `ctl` | aos-loop 的 ctl 視窗（pause、resume、stop） |
| `status` | state 視窗，加上 daemon 表的 phase |
| `note` | 插話、打斷：短、不排隊、送給身體本身，身體可以接也可以不接 |
| `notepg` | 對一個 daemon 底下全部（shutdown、sleep） |
| `wait`（放在父行程的夾裡） | daemon 表上那一列消失與它的 reason；「等子做完」 |
| `ns`、`fd` 的第一行 | `settings`（東西放哪、站在哪） |
| `text` | 定義夾（知識庫說的「原始碼」，`proto8/knowledge/aos/world.md:12`） |
| `mem`、`regs`、`segment` | 身體內部：history、queue、session |
| Broken 狀態 | phase 是 stopped、留著 reason 與現場（`proto8/knowledge/aos/status.md:12`） |

### 3.2 「核心替大家回答」與「每個 proc 自己回答」的差別帶來什麼

| 事情 | Plan 9（核心回答） | aos（各自回答） | 所以 |
|---|---|---|---|
| 行程卡死時 | 核心照樣答 status、照樣執行 stop／kill | 沒人讀它的 ctl，status 讀不到或是舊的 | 要有第二級：對 daemon 下的強制手段（daemon 握有 Linux PID，可以發信號）。Plan 9 自己也分兩級：`kill` 腳本寫 `note`（客氣），`slay` 腳本寫 `ctl`（強制；`kill(1)` 叫它 "a surer, if heavy handed, kill"）。 |
| 死了以後 | 目錄消失；父行程從自己的 wait 檔拿到「pid、用掉的時間、結束訊息」；異常死的先停在 Broken 給人看 | 身體消失，status 與 token 用量跟著沒 | 死因要落在 daemon 那邊（今天 daemon 表的 reason 欄就是這個角色）；要看現場的東西（歷史的尾巴、錯誤輸出）得在 persist。 |
| 說的話可不可信 | 核心說的，行程騙不了 | 自己報的 | 「活著沒、吃多少記憶體」以 Linux 的 `/proc/<PID>/status` 為準；aos 的 status 只講 aos 這一層的事。兩個同名的 status 各有分工，不是重複。 |
| 列出全部 | `ls /proc` 只問一個回答者，一定回得來 | daemon 列名字，細節要一個個去問 | 列表工具對每個 proc 要有時限；或 daemon 自己的表留一行摘要（今天的表就有 phase、reason）。 |
| 誰在問 | 核心知道每個請求是哪個使用者，照檔的權限位元擋 | 每個 proc 得自己認人 | unix socket 上可以向核心問對方的 PID（`SO_PEERCRED`，`unix(7)`）；FUSE 的每個請求也帶呼叫者的 PID（`/usr/include/linux/fuse.h:959-969`）；核心的 9p 只分得出 Linux 帳號。歸 [15](15-權限過去的規劃對照新模型.md)。 |
| 長得一不一樣 | 一份核心程式，格式不會走樣；所有 ctl 檔共用同一個切字函式，連錯誤字串都一樣 | 很多種實作 | 要一頁規格、一支驗收腳本、每種語言一份共用的小函式（切 ctl 的字、排 status 的行）。 |
| 誰來回答 | 行程什麼都不用做 | 每個 proc 得有一個隨時答得了話的部分 | 推論：常駐、不做重活的 aos-loop 很適合當「替身體回答」的那個，等於在 aos-loop 這一層重現 Plan 9 核心的角色。細節歸 [01](01-aos-loop現況.md)。 |

`procs/<名>` 怎麼「連過去」：9P 裡沒有 symlink，也沒有「請改問另一台」這種訊息；Plan 9 是靠**看的人**自己的 namespace 把別人的樹 mount 進來。推論：Linux 的 symlink（11-25 實測那招）反而比 Plan 9 的做法更合用：登記一次、所有人都看得到、daemon 不必轉手。代價是它只在「路徑由 Linux 核心來走」時有效（普通檔，或掛載之後）。

### 3.3 「基於 9P」的三個層次

| | (a) 只學長相，底下是普通檔 | (b) socket 上真的講 9P，不掛載 | (c) 掛成檔案系統 |
|---|---|---|---|
| 怎麼讀寫 | cat／echo，任何語言的 open | 要一支會講 9P 的小工具或函式庫（plan9port 的 `9p read acme/$winid/body` 那種） | cat／echo |
| 寫 ctl 回來代表 | 字進了檔；沒人保證看到 | Rwrite＝proc 收下了 | write 回來＝proc 收下了（前提：沒開回寫快取） |
| 被拒的原因 | 當場回不來，只能事後看 status | Rerror 一句話 | **只剩錯誤碼**，那句話掉了（3.6） |
| 讀了會等的檔 | 沒有（用 inotify 或輪詢） | 有（伺服器晚點回；不等了就 flush） | 有（cat 卡住；按中斷就取消——核心的 9p 會替你送 flush：`linux/net/9p/client.c:730-736`） |
| 知道它死了 | 要另外定（`/proc/<PID>/cwd` 那條路斷掉；或看 mtime） | 連線斷了＝死了 | 讀寫回錯；殘留的掛載點要有人卸 |
| muid、版本號 | 沒有 | 有 | 沒有 |
| 現有工具（Read、ls、json_get、index_view） | 全部照用 | 看不進去 | 全部照用 |
| 一支 20 行的 sh 能當 proc 嗎 | 能 | 不能，要帶 9P 函式庫 | 不能 |
| 跨機器 | 靠共用的檔案系統 | 同一套協議改走 TCP | 掛遠端的 |
| 要什麼權限 | 不用 | 不用 | FUSE 不用（靠 fusermount3）；核心的 9p 要 root |
| 要寫多少（估，推論；實數歸 [09](09-FUSE與9P實作可行性.md)） | 幾乎不用：定格式，加一份小函式 | 每種語言一份伺服器：玩具 189 行，堪用的估 400～800 行；小工具 150～250 行。伺服器還得自己顧「同時好幾個人連進來、有人斷線要清掉他的 fid」（在 Plan 9 是核心代勞，plan9port 另外寫了 `9pserve` 補這塊） | 手刻 FUSE 比 9P 重（估 800～1500 行）而且只有 Linux 能用；或只寫一支「9P 轉 FUSE」的橋，所有 (b) 的實作共用（plan9port 的 `9pfuse` 就是這樣） |
| 最大的代價 | 「收到」與錯誤都要另外定憑據；閒著時得輪詢 | cat／echo 不能用，跟「眼前都是檔」相違 | 掛載點的生老病死、快取要調、錯誤那句話掉了、每次存取多一趟進出核心 |

現成的對照：plan9port 在 Unix 上三層都做了。它的每個服務是一個講 9P 的 unix socket，全部放在一個夾裡（預設 `/tmp/ns.$USER.$DISPLAY`）；平常用 `9p` 小工具讀寫；想要 cat 就用 `9pfuse`，或 `mount -t 9p -o trans=unix` 交給核心掛（`p9p intro(4)`、`p9p 9p(1)`、`p9p 9pfuse(4)`、Linux 9p 文件的 Usage 一節）。

補一句：(b) 永遠不會單獨存在。要先找到那個 socket，而「誰在、socket 在哪」還是靠 (a) 式的普通檔與 symlink（daemon 的 procs 夾）。所以實際的形狀是「外圈（誰在）用普通檔，內圈（跟某一隻講話）用 9P」，這也正是使用者說的「如果proc活著，那我們就直接走unix socket了」。

### 3.4 三個層次能不能同時成立

能，條件是把規格分成兩半：

- **語意一份**：有哪些名字、每個檔的內容長怎樣、「交一句話給 ctl」「讀出整份 status」是什麼意思。
- **接法三份**：同一個動作在普通檔、9P、掛載上各怎麼做，「收到」各看什麼。

而且語意只能規定三層都做得到的事（推論）：

1. ctl 一行一句；一次只交一行。（普通檔沒有「一次 write」的界線，9P 與掛載有，取交集。）
2. 「收到」要有一個看得到的憑據（例如 status 裡一行「已收幾句」）；活的接法額外保證「寫回來就是收到」。
3. 被拒的原因要有讀得到的地方；9P 的接法額外在 Rerror 帶同一句話。
4. status 要小到一次讀得完（否則分兩次讀會拼到前後兩個時刻）。9P 一則訊息有上限：Linux 核心預設 128K，Plan 9 預設 8192＋24 bytes（`devmnt.c:19`）；保持在幾 KB 內最保險。
5. 屬性只依賴 mtime、length、mode（3.5）。
6. 讀了會等的檔列為選配。
7. 「活著沒」用路徑走不走得到、或 socket 連不連得上來判，不靠檔的內容。

再加兩支通用的轉接程式，一個實作只要做一層，別的層次就有了：「把一個普通夾用 9P 送出去」（(a) 變 (b)，Plan 9 世界的 u9fs、exportfs 就是做這件事）與「把 9P 掛成檔案系統」（(b) 變 (c)，9pfuse）。

### 3.5 stat 裝不下的放哪；stat 哪些欄位對 aos 有用

9P2000 的 stat 沒有自由欄位（.u 的 `extension` 是給 symlink 與裝置號用的，Linux 還拿它塞連結數）。Plan 9 對「想講更多」的一貫答案是**再擺一個檔**。所以：

| aos 想講的 | 去哪 |
|---|---|
| 一句話說明、屬性（副作用、冪等…） | `_metainfo`（已定）。列表時由上一層的 index 帶出來——index 的規矩本來就是「X 的說明寫在 X 的上一層」。細節歸 [12](12-_metainfo、index與proc目錄.md)。 |
| token 用量 | 自己目錄裡一個檔，或 status 的幾行（已定）。 |
| 現在怎樣、在做什麼 | `status`。 |
| 東西放哪（persist、信箱） | `settings`。 |

Linux 上唯一接近「stat 的延伸欄位」的是延伸屬性（xattr）。實測這台 ext4 與 tmpfs 都能設 `user.aos.description`；但 9P2000 沒有它、cp 與 git 預設會弄丟、agent 的工具看不到，不建議當主路。

stat 的欄位對 aos 的用處：

| 欄位 | 可以拿來表示 | 三層都拿得到嗎 |
|---|---|---|
| mtime | 「最後有動靜」：status 的 mtime＝最後一次狀態變動，ctl 的 mtime＝最後一次收到控制。`ls -lt procs/` 就是「誰最近有動靜」的排行 | 都有。(b) 只到秒；(c) 走 FUSE 時核心會把屬性快取一段時間（libfuse 預設 1 秒，`mount.fuse3(8)`），要設成 0 才即時 |
| length | 「有沒有東西可讀」：Plan 9 的 wait 檔就是 length 大於 0 表示有紀錄。信箱、佇列類的檔可以照用；status 給真實長度 | 都有。(c) 走 FUSE 時不開 direct_io，read 不一定會問到伺服器（`mount.fuse3(8)`）；長度填 0 的合成檔因此可能讀不到（後半句憑記憶，歸 09） |
| mode | 誰能讀寫：ctl 不給讀、status 大家可讀 | 都有；但全部 agent 同一個 Linux 帳號時，(a)(c) 擋不了誰 |
| uid | 這隻 proc 是誰的 | (b) 是字串，可以直接放 aos 的名字；(a)(c) 是 Linux 的數字帳號，大家都一樣 |
| muid | 誰最後寫的：ctl 的 muid＝最後一個下控制的人，等於不花力氣的留底 | **只有 (b)**。核心的 9p 把它丟掉（`linux/fs/9p/vfs_inode.c:1144-1189`）；FUSE 的屬性沒有這一欄（`/usr/include/linux/fuse.h:253-270`） |
| qid 的版本號 | 「變了沒」不用讀內容就知道，比秒級的 mtime 細 | 只有 (b) |
| qid 的唯一編號 | 同名但重起過＝新編號，握著舊的人認得出「不是同一隻了」 | (b) 有；(a)(c) 是 inode 編號，大致可用 |
| 獨佔位元 | 一次只准一個人開（協議自帶的鎖） | 只有 (b) |

結論（推論）：介面只依賴 mtime、length、mode；muid 與版本號當加分，有就用。

### 3.6 「寫 ctl 回來＝收到」與「錯誤怎麼回」在 9P 上天生怎麼表達

使用者原話是「1.寫ctl回來，算是收到。」。9P 的規矩是每個請求恰好一個回覆：成功的 R，或 Rerror。寫 ctl 就是一個 Twrite，四種結局各有明確的意思：

| 結局 | 意思 |
|---|---|
| `Rwrite(count)` | 伺服器收下了這幾個 bytes。要不要等事情做完才回，是伺服器自己的規矩（Plan 9 的 stop 等、kill 不等）；使用者定的是「收下就回」。 |
| `Rerror("…")` | 沒收，附一句原因。慣例不超過 127 bytes（`ERRMAX` 是 128）；太長可以截，手冊說它「只是參考」。 |
| 一直沒回 | 還在等，這是合法的。不想等就送 Tflush，規則很精確：Rflush 之前先到的回覆算數，否則當作沒送過（`flush(5)`）。所以「我等到逾時了，那句到底收到沒」有確定的答案。 |
| 連線斷了、還沒回 | 不知道。所以 ctl 的字最好是「再送一次也無害」的。 |

寫伺服器的人看到的也是這樣：Plan 9 的函式庫只有一個 `respond(請求, 錯誤字串)`，成功就給空的（`9p(2)`）。

同一件事在三層：

| | 「收到」 | 被拒的原因 |
|---|---|---|
| (a) 普通檔 | 要另外看憑據；寫得進去不算數 | 只能事後看 status |
| (b) 直接講 9P | Rwrite | Rerror 的那句話，原封不動 |
| (c) 核心的 9p | write 回來（沒開快取時它等到 Rwrite 才回：`linux/fs/9p/vfs_file.c:416-426`） | 預設的 .L 只有錯誤碼；舊版本的字串被核心拿去查一張固定的表換成錯誤碼，查不到的一律變成 526 號並記一行核心日誌（`linux/net/9p/client.c:539-567`、`linux/net/9p/error.c`） |
| (c) FUSE | write 回來（預設同步；憑記憶） | 回覆的標頭只有一個數字（`/usr/include/linux/fuse.h:971-975`） |

所以「9P 的錯誤是一句字串」這個好處，在 Linux 上只有 (b) 拿得到。Plan 9 自己在類似處境也是多擺一個檔：`/net/tcp/n/err`「存著出錯的原因」（`ip(3)`）。

## 4. 邊緣狀況

- **`stop` 這個字**：Plan 9 的 stop 是暫停（start 回來）、kill 才是結束；aos 今天 stop 是結束、pause／resume 是暫停。字表歸 [18](18-ctl、status、settings的候選寫法.md)，但「照搬 Plan 9 的字」會撞到這個。
- **寫 ctl 會不會卡住**：Plan 9 的 stop 會（寫的人在 ps 裡顯示成 Stopwait）。aos 定了「回來＝收到」，回答的那部分就不能等身體把事做完；身體正在一個很長的回合裡時由誰回，是 3.2 最後一列的問題。
- **一次 write 兩行**：`printf 'a\nb\n' > ctl` 是一次 write。Plan 9 只去掉最後一個換行，會把它當成一句帶參數的話而回錯。
- **`echo x > ctl` 帶「清空」旗標**：Linux 的殼用 `>` 開檔會要求清空；掛載時伺服器得收下、不當成錯。9P 的 open 有這個位元，「只能附加」的檔照規矩忽略它（`open(5)`）。
- **名字與值的限制**：9P 的名字不能有 `/` 與 NUL；status 一行一筆，值裡就不能有換行。Plan 9 對帶空白的欄位是用單引號括起來。
- **懸空的登記**：Plan 9 的 /srv 有一樣的毛病（貼的人死了、檔還在）。它的解法是協議裡的 ORCLOSE：開檔時加這個旗標，關掉就刪，而行程一死核心會替它關。Plan 9 的函式庫貼 /srv 時就是這樣做，而且貼完故意不關那個檔（`lib9p/srv.c:831-853`）——登記跟行程的生死綁在一起。aos 用 symlink 登記沒有這種自動收的機制，要 daemon 收屍時刪。Linux 上最接近的是抽象 unix socket（行程一死名字自動消失，`unix(7)`），但它不在檔案系統裡、走不了路徑。
- **巢狀深度**：用「symlink 指到 `/proc/<PID>/cwd`」的走法，一條路最多穿 19 層 `procs/<名>`，第 20 層回 `ELOOP`（實測，見下；Linux 一條路最多跟 40 次連結，`path_resolution(7)`，每層用掉 2 次）。9P 的 walk 一次最多 16 段，但可以分次走，沒有總上限。
- **token 的「子孫合計」**：Plan 9 把子孫的時間跟自己的分開記，子行程結束時併進父行程。token 用量遲早也會有「自己的」與「底下的」兩個數；先記著。
- **快取會偷走「收到」**：掛載時若開回寫快取，write 回來時伺服器還沒看到那句話。規格的掛載接法要寫明不准開。
- **note 沒人接會死**：Plan 9 裡外面送來的 note，行程沒登記處理函式就直接結束。aos 若學 note 做「插話」，要定沒人接時怎麼辦。
- **認證只是一個位子**：9P 的 auth 只留了位置、沒規定內容，attach 的名字是自己報的。同一台機器上問核心對方是誰就夠；跨機器才需要另一套（歸 [15](15-權限過去的規劃對照新模型.md)、[20](20-送訊息兩條路的細節.md)）。

<details><summary>巢狀深度的重跑程式（純標準庫，在一個空的暫存夾裡跑）</summary>

```python
import os, errno
pid = os.getpid()                       # 這個行程站在目前的夾，所以 /proc/<pid>/cwd 就是這個夾
open("status", "w").write("phase: running\n")
for n in range(1, 40):                  # hop0 -> /proc/pid/cwd/hop1 -> ... -> status，共 n 跳
    for i in range(n):
        if os.path.lexists("hop%d" % i): os.unlink("hop%d" % i)
        os.symlink("/proc/%d/cwd/%s" % (pid, "hop%d" % (i + 1) if i + 1 < n else "status"), "hop%d" % i)
    try:
        open("/proc/%d/cwd/hop0" % pid).read()
    except OSError as e:
        print("hops=%d -> %s" % (n, errno.errorcode[e.errno])); break
```

輸出：`hops=20 -> ELOOP`

</details>

## 5. 要問使用者的

**題 1：「基於 9P」要落到哪一層？**

- a. 只學長相：檔名、純文字、屬性的意思照 9P；底下是普通檔；unix socket 上講一個自訂的小協議。
- b. 長相照 9P，而且 proc 的 unix socket 上真的講 9P2000（只用其中九種訊息）；普通檔照樣算一種合格的實作；掛載以後再說。
- c. 一開始就要掛成檔案系統，cat／echo 直接能用。
- 推薦 b。理由：socket 本來就定了要有，在上面講 9P 就同時得到「寫回來＝收到」「錯誤一句話」「讀了會等」，以後要掛載只差一支大家共用的橋。（socket 上講什麼的細節歸 [20](20-送訊息兩條路的細節.md)。）

**題 2：落檔的實作，「寫 ctl 回來＝收到」怎麼算？**（普通檔永遠寫得進去，寫回來不代表有人看到。）

- a. 介面多定一個看得到的憑據：status 裡一行「已收到第幾句」；活的接法額外保證寫回來就是收到。
- b. 落檔的也算收到：寫得進去就算（跟寄信一樣是「交到了」），有沒有人處理一律看 status。
- c. 規定 ctl 一定要有活的回答者；落檔的實作要配一個常駐的代答者。
- 推薦 a。理由：只多一行，三種接法都給得出來；今天 `ctl.json` 的 seq 就是這個東西的 json 版。

**題 3：ctl 被拒的原因放哪？**（直接講 9P 時是 Rerror 那句話；掛載後只剩錯誤碼；普通檔連錯誤碼都沒有。）

- a. status 裡一行：上一句被拒的 ctl 與原因。
- b. 另外擺一個 `err` 檔（Plan 9 的 `/net/tcp/n/err` 是這樣）。
- c. 寫完從同一個開著的 ctl 讀回這次的結果（每個開的人各看各的，不會互蓋；普通檔做不到）。
- 推薦 a。理由：跟「做完沒看 status」「目前只給 status」一致；多人同時下控制會互蓋的問題，真的遇到再加 c。

**題 4：proc 卡死、不回 ctl 時的強制手段歸誰？**

- a. 兩級都寫進介面：客氣的寫 proc 自己的 ctl；強制的寫它 daemon 的 ctl，由 daemon 用 Linux 信號做。
- b. 介面只管 proc 自己的 ctl；卡死了怎麼辦是各個 daemon 實作自己的事。
- c. 所有 ctl 一律先經過 daemon，由它轉。
- 推薦 a。理由：Plan 9 就是兩級（note 客氣、ctl 的 kill 強制），而「daemon 是 Linux 與 aos 之間的橋」正好是握有 Linux 手段的那一個；c 會讓每一句話都得經過 daemon。

## 6. 沒查到／沒把握的

- Plan 9 的例子（2.9）沒在真的 Plan 9 上跑；這台沒有 Plan 9，也沒有 plan9port。查的是第四版（貝爾實驗室／Plan 9 Foundation 那一支），9front 等後來的分支有增減，沒查。
- 掛載那一層我一樣都沒實跑：核心的 9p 要 root；FUSE 歸 09。3.6 表裡 (c) 的兩列，核心 9p 是讀原始碼得來的，FUSE 那列除了標頭的欄位（查過本機標頭檔）以外是憑記憶。
- Linux 的行號是上游 v6.6 的；這台跑的是微軟的 6.6.114 分支，沒逐行對。
- 仍憑記憶、沒找到原文的：FUSE 上長度填 0 的合成檔不開 direct_io 會讀不到；FUSE 的 write 預設同步、伺服器死了回什麼錯。
- 行數都是估的（3.3 那一列），唯一實測的是玩具的 189＋112 行。玩具只處理一個連線、沒做認證、沒做 create／remove／wstat。
- 9P2000.u 只有一份草稿，好幾節是 TODO；實際行為以各家實作為準，我只看了 Linux 的。
- 沒查：9P 在 unix socket 上跟一個自訂的行協議比，實際延遲差多少；Windows 那一側的 9P 伺服器（WSL 用的）怎麼回錯誤。
