# proto4 想法筆記 §16–§19：kernel
← [索引](2026-09-08-ideas.md)｜[README](../README.md)

## 16. 名詞對齊：daemon＝cpu 的管理者、一個 inst.json＝一顆 cpu；kernel＝第一個程序（2026-09-10）

使用者原話（照錄）：

> daemon 就是 cpu 的管理者，用 daemon-ctl 登記了一個 inst.json，就相當於是登記了一個新的 cpu。在 aos 中，這就是硬體基礎，後續可能會新增更多種的 cpu 或指令集，也就是更多種類的 inst.json，或其他持續跑著的東西，但目前我們這個，就是最通用最基礎的。
>
> 好了，現在我們有了硬體，那麼操作系統的第一個程序呢？那就是 kernel，kernel 掌管所有 cpu 和行程，並且對行程做 cpu 分配和排程，同時也掌管資源分配等。在這種情況下，kernel 就是唯一能存取 daemon-ctl（與底層硬體的唯一接觸層，管理所有 cpu 的存在和使用權），還有修改所有 inst.json 的傢伙（決定 cpu 下個指令要去動哪個行程）。

整理成幾條：

- **硬體層＝daemon＋aos-run＋aos-exec**。`aos-daemon-ctl add foo.json`＝多插一顆 cpu；`rm`＝拔掉；`pause`／`resume`＝停／走。所以 §15 的 key 是 .json 路徑很自然：一個 inst.json 就是一顆 cpu 的「指令暫存器」。
- **inst.json 現在這套＝最通用最基礎的指令集**。以後可能有別種 cpu／指令集（別種格式的 inst.json，或別種「持續跑著的東西」），daemon 只管「有哪些 cpu、誰能用」，不管指令集內容。
- **kernel＝作業系統的第一個程序**，管兩件事：
  1. **cpu 與行程**：哪些 cpu 存在、每顆 cpu 下一次去跑哪個行程（排程）。
  2. **資源分配**（還沒細講）。
- **kernel 是唯一碰硬體的人**：只有 kernel 能叫 `aos-daemon-ctl`（cpu 的存在與使用權），也只有 kernel 能改 inst.json（cpu 下一條指令要動哪個行程）。其他行程不碰 ctl、不碰 inst.json。
- 跟 §7.3／§9 接得上：§9 說 daemon 是硬體、生死使用者管；§7.3 說 kernel 本身是被第一顆 cpu 每秒跑的 proc——照這裡的說法，kernel 跑起來的方式就是：使用者手動 `ctl add kernel/inst.json`（插上第一顆 cpu＝上電），之後 kernel 自己再 `ctl add` 其他 cpu。

還沒定（之後撞到再說）：kernel 自己那顆 cpu 的 inst.json 誰改（自己改自己？）；「資源」具體指什麼；行程長什麼樣（§8 的四個部分還算數嗎）。

## 17. 初步想法：kernel 管 `procs/`，每回合決定哪顆 cpu 換跑誰的 inst.json（2026-09-10）

使用者原話（照錄，自稱「初步的粗淺想法」）：

> kernel 管理某個 procs/ 資料夾，procs/ 下有很多個 .json 檔案，那些都是等待被執行的 inst.json，只是名稱不同（pid）。kernel 每回合都會去決定說，有限的 aos-daemon 管理下的 inst.json，要換成 procs 下的誰的 json。kernel 本身也是 proc，本體也是一個被 aos-daemon 持續執行的 inst.json，只是他的 inst.json 只有他自己能動，不在 procs/ 下。並且 kernel 在更換 aos-daemon 管理下的 inst.json 時，有權限可以用 aos-daemon-ctl 去暫時停止 daemon 的讀檔動作，直到 kernel 修改完 daemon 管理下的 inst.json，才會讓 daemon 繼續讀檔執行。不過其實不需要這樣啦，反正 inst.json 只有 kernel 能存取，那其實就用 rename 這個原子操作就好。

整理：

- **`procs/`＝就緒佇列**：裡面每個 `.json` 是一個等著上 cpu 的行程，檔名就是 pid。
- **cpu 的數量有限**（daemon 表上有幾筆就幾顆），kernel 每回合做排程：決定每顆 cpu 的 inst.json 換成 procs/ 裡哪一個。
- **kernel 自己**：也是 proc、也是被 daemon 持續跑的一份 inst.json，但**不放 procs/**、只有它自己能動——就是 §16 說的「上電時使用者手動插的第一顆 cpu」。
- **換指令的方式**：用 `rename` 這個原子操作就好，不用 pause/resume 去停 daemon 讀檔。（aos-run 每次跑都是「開跑那一刻」才讀那份 .json；rename 是原子的，所以 aos-run 看到的永遠是完整的舊檔或完整的新檔，不會讀到一半。）

我挖到的邊緣狀況（沒定，記著）：

1. **rename 是搬走還是換名？** 若把 `procs/123.json` 直接 rename 到 cpu 那個位置，它就離開佇列了；換下來的那份要 rename 回 `procs/`，不然行程消失。也可以是「cpu 那份永遠是 procs/ 裡某份的複本」，kernel 只 rename 複本。兩種都行，得選一個。
2. **cwd 預設會跟著搬**：inst.json 沒寫 `cwd` 時預設是「.json 所在資料夾」（§11.3），檔案 rename 到 cpu 的位置之後，預設 cwd 就變成 cpu 的資料夾、不是行程自己的家。所以 procs/ 裡的 inst.json 大概都得寫死 `cwd`（或 `$ref` 到自己家的東西時用絕對路徑），不然一搬就跑錯地方。
3. **正在跑的那次怎麼辦？** rename 只影響「下一次」開跑讀到誰；手上那次會跑完。kernel 要搶佔就得等它那次結束（或 `ctl` 砍它）。這跟 §14 pause「不保證零次」是同一件事。
4. **狀態怎麼帶著走**：換下來的行程「跑到哪了」記在哪？inst.json 是指令、不是暫存器；§8 說本體＝cwd，那狀態應該在它的 cwd 裡，換上換下都不動。這樣 rename 才夠。
5. **kernel 那顆 cpu 掛了**（inst.json 壞、每次 125）：§9 說 daemon＝硬體、使用者手動管——但 kernel 壞了誰救？`--stop-on-error` 讓它退出、daemon 把它從表拿掉，使用者看 `ls` 就知道。先這樣。

### 17.1 使用者回應（2026-09-10）

原話（照錄）：

> 因為 daemon 啟動後，接下來一定是跟著跑 kernel，所以我在想，以後可能會有一個指令，會同時啟動 daemon 和 kernel。好吧，啟動 kernel 本質上就是把 kernel 的 inst.json add 進 daemon 讓他跑，所以這就是簡單的腳本而已……之後再說。
>
> 然後 rename 這件事，這是工程問題，實作的時候自然就會知道，而且 kernel 目前只是這樣，但以後會變得比較複雜，procs/ 內的 .json 未必會是直接跟 inst.json 一樣的格式，可能還會有權限、優先級……等，目前的話可以很簡單的直接搬過去，以後就不行了。
>
> cwd 這塊，確實要寫死 cwd，不過這道檢查只在 kernel 這環做，daemon 那邊就維持原本行為。

對上面五條的處置：

- **開機一鍵**（daemon＋kernel）：就是一個腳本（起 daemon、`ctl add kernel/inst.json`），之後再說。
- **搬走還是複本**（邊緣 1）：工程問題，實作時再定。**現在直接搬過去就好**；以後 `procs/` 裡的檔案會不只是 inst.json（可能多權限、優先級等欄位），到時就不能直接搬、要由 kernel 轉成 inst.json 再放上 cpu。
- **cwd 要寫死**（邊緣 2）：對，但**這道檢查在 kernel 做**（進 procs/ 或上 cpu 前檢查有沒有寫 cwd）；**daemon／aos-run／aos-exec 維持原本行為**（沒寫 cwd 就預設 .json 所在資料夾），不加檢查。
- 邊緣 3～5 沒特別回應，照我寫的先放著。

### 17.2 我再挖的八個問題與使用者的回答（2026-09-10）

| # | 問題 | 使用者的回答 |
|---|---|---|
| 1 | 行程怎麼說「我做完了」？aos-run 會一直重跑 cpu 上那份 inst.json | 之後 kernel 變複雜時自然會有別的機制，現在不定 |
| 2 | 時間片怎麼切（跑到自己說結束／每 N 次換人）？ | kernel 自己做排程，是 kernel 的事 |
| 3 | 換人時兩次 rename 之間 cpu 上沒檔案，aos-run 剛好開跑會吃 125；開了 `--stop-on-error` cpu 就死 | 「daemon 有辦法操控 aos-run 的讀檔動作嗎？如果不行或很麻煩的話，那就把 stop on error 旗標換掉」→ 見下面我的答覆 |
| 4 | cpu 閒著放什麼（沒檔案／idle inst.json）？ | 隨便，kernel 實作細節 |
| 5 | kernel 怎麼知道哪顆 cpu 上是哪個 pid？state.json 沒有這欄 | kernel 自己記（cwd 裡一張表）；能存取 daemon 的只有 kernel，兩邊接得上就好 |
| 6 | 時限／間隔綁在 cpu（`ctl add` 時定死），不是綁行程 | kernel 處理：kernel 要能透過 ctl 改某顆 cpu 的設定；**這種設定像韌體設定／硬體特性（cpu 時脈），kernel 能改，但要小心** |
| 7 | 新行程從哪來（fork）？procs/ 只有 kernel 能寫 | 對，這就是 **syscall**：所有硬體資源都由 kernel 掌控，所以都要經過 kernel |
| 8 | kernel 每秒看一次 state.json 會漏掉中間的退出碼 | 在 daemon 和 kernel 之間開特殊協議／通道解決（之後） |

**第 3 條我的答覆**：
- daemon「操控 aos-run 讀檔」其實已經有了——`ctl pause` 就是等 aos-run 睡著再 SIGSTOP，被停住的進程不可能讀檔；`ctl resume` 放開。所以「pause → rename → resume」是可行的，但要等手上那次跑完、還多兩趟 ctl，麻煩。
- **更簡單的做法是根本不留空窗**：先 `link(cpus/0.json, procs/123.json)`（硬連結，舊的先在 procs/ 有一個名字），再 `rename(procs/456.json, cpus/0.json)`（rename 蓋過去是原子的）。任何時刻 `cpus/0.json` 都存在、內容不是舊的就是新的。這全在 kernel 那端做，daemon／aos-run 一行不用改。
- 所以 `--stop-on-error` 旗標留著（單獨用 aos-run 時有用）；cpu 要不要開它由 kernel 在 `ctl add` 時決定。用硬連結法的話開著也沒事；用直接搬的話就不要開。

定案：daemon 這層不動；第 3 條走硬連結＋rename；其餘都是 kernel 那層的事、做 kernel 原型時再定。

## 18. kernel 原型（proto4-3 `aos-kernel`）定案（2026-09-10，我提、使用者「好，去吧」）

- **家＝一個資料夾**：`inst.json`（kernel 自己那顆 cpu，只有 kernel 能動，開機＝`ctl add` 它）、`config.json`（ncpu、cpu 的 interval_ms／timeout_ms、quantum）、`procs/<pid>.json`（就緒佇列，檔名＝pid）、`procs/bad/`（退件）、`cpus/<n>.json`（每顆 cpu 一檔，daemon 的 key）、`state.json`（cpu n → pid、上去的時間、上去時的 runs）、`kernel.log`（程式自己 append）。
- **程式** `aos-kernel init DIR --ncpu N`／`tick`／`ls`，與其他四支並排放 proto4-3。
- **kernel 的 inst.json**：`{"argv":["aos-kernel","tick"],"cwd":"."}`。串流全不寫（aos-exec 開 stdout 是清空重寫，不能當 log）；envs 不寫（`AOS_DAEMON_HOME` 從 daemon 繼承下來）。
- **每回合五步**：讀自己的表 → 點 cpu（少了就放 idle 指令建檔＋`ctl add`；aos-run 死了也補回）→ 檢查佇列（沒寫 cwd 的搬 `procs/bad/`，§17.1）→ 排程（idle 且有人等→pid 最小先上；跑滿 quantum 次→搬回隊尾換人；沒人等就續跑；換檔用硬連結＋rename 不留空窗）→ 寫表寫 log 退出 0。
- **時間片用「跑幾次」算**、佇列 FIFO（pid 小先）、不做優先級。行程不會自己結束，v1 永遠輪流；要拿掉就趁它不在 cpu 上時手動刪 procs/ 的檔。
- **v1 沒有**：syscall 收件匣、改 cpu 韌體設定、daemon↔kernel 專用通道。

### 18.1 落地補記

做出來了：`proto4-3/aos-kernel`＋`aos_kernel.py`（220 行）＋`aos_kernel_tick.py`（175 行），
測試 `test/test_kernel.py` 10 條（全套從 173 條變 183 條，26.7 秒變 30.9 秒）。

我自己決定的事（一條一句）：

- **`inst.json` 的 `argv[0]` 寫 `aos-kernel` 的絕對路徑**，不靠 PATH——daemon→aos-run→aos-exec 繼承的是使用者開 daemon 時那份 PATH，寫死就不用交代環境。
- **`tick`／`ls` 都不吃參數**，家就是 cwd（跟 §18 的 `{"cwd":"."}` 對得起來）；`init` 才吃 DIR。
- **`init` 也寫一份空的 `state.json` 與 `kernel.log`**，這樣家一建好結構就是完整的。
- **`config.json` 讀不到或沒有 `ncpu` ＝這裡不是家**，`tick`／`ls` 退出 1；其餘欄位缺就吃預設。
- **一顆 cpu 只有在 daemon 表上時才排程**：剛 `ctl add` 完那回合不排，下一回合才排（`runs` 要從 daemon 那邊拿）。
- **add 失敗只影響那一顆 cpu**，不是整回合停擺；`tick` 一律退出 0，kernel 不因為外面的事死掉。
- **`cpus/n.json` 被人刪掉**＝上面那位就沒了：補一份 idle、把表上那格清成 `null`（就是 §18 說的「換成 idle」那條路）。
- **cpu 被 `ctl rm` 過再插回來，`runs` 會從 0 重數**：看到「現在的 runs 比記的 `runs_at` 小」就把 `runs_at` 重設，不然那顆 cpu 永遠換不了人。
- **佇列排除正在 cpu 上的 pid**（有人手動在 `procs/` 放同名檔時才會撞到），免得同一個 pid 被排上兩顆 cpu。
- **`state.json` 只有兩個欄位**：`{"cpus":{"0":{"pid","since","runs_at"}|null},"queue":[…]}`，`next_pid` 省掉（v1 沒有 fork）。
- **`_swap()` 的兩步都有退路**：`link` 失敗就整個不換；`rename` 失敗就把剛才那個硬連結 `unlink` 掉，回到原狀。
- **`ls` 多印一欄 `CPU_STATE`**（daemon 那筆的 `state`／「沒插上」），看 cpu 是不是真的在跑。

撞到的坑：

- **`--home` 不會傳給子孫**：daemon 用 `--home` 開的話，kernel 那層 `resolve_home()` 會退回 `~/.aos-daemon`，兩邊對不上。所以文件與測試都改用環境變數 `AOS_DAEMON_HOME` 開 daemon。
- **`procs/bad/` 在 `procs/` 底下剛好不礙事**：掃佇列只收 `*.json` 而且要是檔案，資料夾自然被濾掉。
- **硬連結那招不用善後**：`link` 之後那個 inode 有兩個名字，`rename` 蓋掉 `cpus/n.json` 這個名字之後就剩 `procs/<舊>.json` 一個，不必再 `unlink`。
- **兩顆 cpu 同一回合換人時，先換的那顆把人丟回隊尾，後換的那顆可能立刻把他撿走**（FIFO 的正常結果，但看 log 會覺得怪）。
- **`quantum` 是「那顆 cpu 跑了幾次」不是「那個行程跑了幾次」**——同一回事，因為 cpu 上只有他，但 `runs` 這個數字是 aos-run 的、不是行程的，命名容易誤會。

## 19. 上千顆 cpu 時檔案太多（之後再說）＋ `aos-kernel-boot`（2026-09-10）

使用者原話（照錄）：

> 因為我們這個 cpu 的本質，就是 linux 行程，linux 支援上千個行程一起跑，所以我們以後會有上千個 cpu。在 cpu 空閒的時候，如果 inst.json 還在，那檔案感覺會很多……你有啥想法嗎？比如 daemon 原先用檔名做標示，改成檔名＋json path，也就是我們 $ref 那樣，然後可以有 insts.json，裡面不一定要嚴格只能有一個 json object……，這個之後再說吧。
>
> 然後我覺得你要弄一個 aos-kernel-boot 指令，承襲 aos-kernel 的所有旗標，只是他把 aos-daemon &、ctl add …、kernel init，全都做了。

### 19.1 上千顆 cpu：我的想法（沒定，之後再說）

- 使用者的方向：daemon 的 key 從「檔案路徑」變成「檔案路徑＋JSON pointer」（像 `$ref` 的 `insts.json#/3`），一個 `insts.json` 裝很多顆 cpu 的指令。做得到，aos-exec 已經會解 `#/ptr`；daemon 的 key 規則改一下就好。
- 我補一個角度：**檔案不是真正的成本，進程才是**。Linux 一個資料夾放一千個小檔沒感覺；但一千支閒著的 aos-run 每秒醒來跑一次 `true`，這才是負擔。所以與其想「閒著的 cpu 的檔案放哪」，不如想「閒著的 cpu 要不要存在」：
  - **cpu 熱插拔**：kernel 只在有行程要跑時 `ctl add`，閒太久就 `ctl rm`。`ncpu` 變成上限而不是固定數。Linux 行程便宜，插拔成本低，這跟「cpu 本質是行程」正好相配。
  - 這樣閒著的 cpu 既沒檔案也沒進程；`insts.json` 那招可以留給「同時真的有上千個在跑」的時候。
- 兩招不衝突，可以都做。之後再說。

### 19.2 `aos-kernel-boot`（使用者隨即說「先不要做」，設計留著）

- 用法：`aos-kernel-boot DIR [aos-kernel init 的所有旗標] [--home H]`。一條指令把「開 daemon → kernel init → ctl add kernel 的 inst.json」做完。
- 步驟：① DIR 不存在→`init`；已經是個家（有 config.json）→沿用不重建；是別的東西→拒絕。② daemon 家＝`--home`／`AOS_DAEMON_HOME`／`~/.aos-daemon`；家裡已有活的 daemon→沿用；沒有→背景開一支 `aos-daemon`（脫離終端、stdio 進家裡的 `daemon.log`、**用環境變數 `AOS_DAEMON_HOME` 傳家**，因為 `--home` 不會傳給子孫，§18.1 的坑），等它起來（state.json 出現，最多 5 秒）。③ `ctl add DIR/inst.json`；已在表上→算成功、說一聲。④ 印出 daemon pid、家、kernel 的 key，退出 0。
- 這就是 §17.1 說的「開機一鍵＝腳本」。daemon 的生死還是使用者管（§9）：boot 只負責「沒開就開」，不負責關；關機＝`ctl stop`。

### 19.3 使用者回應：熱插拔會做；boot 的真正語意（2026-09-10）

原話（照錄）：

> 好主意，cpu 那個 aos-run 確實是這樣，這個是工程問題，後續一定會實作相關機制。
>
> 然後 boot 沒做是因為還要考慮一些狀況，比如使用者直接暫停 daemon，但 kernel 本身沒動，只要 daemon 繼續跑，那 kernel 本身是感覺不到機器停止的。還有 kernel init 這個指令通常很久才會執行一次，因為這等於是重灌操作系統的意思，但 daemon 的啟停可能會很頻繁，所以 aos-kernel-boot 的功能，我會覺得他是「看看 daemon 上有沒有 kernel 的 inst.json 在跑，沒有的話就 ctl add。然後如果連 kernel 都還沒初始化，那就報錯，提示使用者，要先灌操作系統」

整理：

- **cpu 熱插拔（§19.1）確定會做**，工程問題，之後實作。
- **三個東西的壽命不一樣**：`kernel init`＝重灌作業系統，很久一次；daemon 的啟停＝開關機，很頻繁；kernel 上 cpu（`ctl add kernel/inst.json`）＝每次開機都要做一次。§19.2 把 init 塞進 boot 是錯的。
- **boot 修正後的語意**：只做「看 daemon 上有沒有 kernel 的 inst.json 在跑，沒有就 `ctl add`」；kernel 家還沒 init → 報錯提示「先灌作業系統（`aos-kernel init`）」；不開 daemon、不 init。
- **還沒想清楚的狀況**（所以先不做）：使用者整台暫停（例如 daemon 被 SIGSTOP、或電腦睡眠）再繼續，kernel 感覺不到中間停過——它的表（since、runs_at）還是舊的，daemon 的 runs 也沒動，所以排程上大概沒事，但「上去多久」這種時間就不準。要不要讓 kernel 知道「機器停過」，之後再想。

### 19.4 `aos-kernel init` 拆成專用指令 `aos-kernel-init`（2026-09-10）

使用者：「所以 aos-kernel init 應該變成專用指令：aos-kernel-init」。因為 init＝重灌，跟每回合跑的 `tick`／給人看的 `ls` 不是同一種壽命的東西，不該擠在同一支程式的子命令裡。定案：`aos-kernel-init DIR --ncpu N [--interval-ms] [--timeout-ms] [--quantum]`；`aos-kernel` 只剩 `tick`／`ls`。以後 `aos-kernel-boot`（§19.3）也是同一系列的專用指令。

### 19.5 `aos-kernel` 本身以後＝行程跟 kernel 講話的指令（2026-09-10）

使用者：「aos-kernel 本身，會變成其他行程，和 kernel 交流的指令」。也就是 §17.2 第 7 條的 syscall 入口：行程要 fork、要資源，就叫 `aos-kernel <什麼>`，由它把請求送進 kernel 的收件匣。所以這一系列的分工是：`aos-kernel-init`＝重灌、`aos-kernel-boot`＝開機把 kernel 放上 cpu、`aos-kernel`＝行程對 kernel 的 syscall。

我的補記：照這個分法，現在 `aos-kernel tick`（kernel 自己每回合跑的）放在 syscall 指令裡就怪了，之後大概也要拆出去（例如 `aos-kernel-tick`，或 kernel 的 inst.json 直接指向另一支程式）。`ls` 倒是可以留，那是「問 kernel 現在狀況」，本來就是行程能問的事。先不動，等使用者說。

### 19.6 記下來後續考慮：機器停過、長任務被腰斬、結果沒人接（2026-09-10）

使用者原話（照錄）：

> kernel 確實應該知道機器停過，但目前沒有需求。我現在預想到的只有以後 daemon 停下了，然後比如 LLM 這種長時間任務被中途暫停，那麼 daemon 重啟後，他會怎麼做，kernel 又會怎麼做。或是說 LLM 這種長時間任務做完了，他把結果寫入了，但 daemon 因為停下了所以沒接到，又因為那是在某個 pipe 或 /tmp，重啟後也沒接到，這些邊緣情況怎麼辦。記下來後續考慮吧。

拆成三個題目，都先不做：

1. **kernel 要知道機器停過**——有需求時再做。
2. **daemon 停下時，長任務（例如一次 LLM 呼叫）跑到一半**：daemon 現在的做法是 SIGTERM 每支 aos-run、aos-run 等手上那次跑完才退（§12），所以正常關機不會腰斬；但 SIGKILL／斷電會。重啟後 daemon 的表是空的（§13：daemon 是硬體、不記憶），kernel 那邊 state.json 還寫著「cpu 0 上是 pid 3、runs_at=12」——kernel 的 tick 會重新 add cpu、runs 歸零、看到 runs < runs_at 就重設基準（§18.1），行程等於從頭再上一次。但那次跑到一半的任務本身有沒有留下半成品，是行程自己的事（§8：本體在 cwd）。
3. **長任務做完、結果寫了，但接收方不在**：結果如果走 pipe（像 status-fd）或 /tmp，daemon／kernel 不在時就丟了。方向大概是：結果一律落在行程自己的 cwd（重啟後還在），接收方重啟後去 cwd 撿，而不是靠即時通道；即時通道（§17.2 第 8 條的 daemon↔kernel 專用通道）只當加速、不當唯一來源。

### 19.7 `tick` 也拆出去：`aos-kernel-tick`（2026-09-10，使用者「你說的對，這個確實要這樣」）

定案：`aos-kernel-tick`＝kernel 的心跳，`aos-kernel-init` 產生的 inst.json 的 argv 改成 `["<絕對路徑>/aos-kernel-tick"]`；`aos-kernel` 只剩 `ls`（以後再長 syscall）。系列變成四支：`aos-kernel-init`（重灌）、`aos-kernel-boot`（開機，先不做）、`aos-kernel-tick`（心跳，daemon 叫的）、`aos-kernel`（行程叫的）。

### 19.7.1 落地補記

做出來了（§19.4＋§19.7 一起）：`proto4-3/aos-kernel-init`＋`aos_kernel_init.py`（62 行）是新的一支，`aos-kernel-tick`＋`aos_kernel_tick.py`（201 行）多了自己的命令列入口，`aos_kernel.py`（181 行）只剩家的版面（`KHome`／`here_or_die()`）與 `ls`。

- **三支的分工**：`aos-kernel-init DIR --ncpu N [--interval-ms] [--timeout-ms] [--quantum]`＝建家（很久一次）、`aos-kernel-tick`＝心跳（不吃參數，cwd 就是家，daemon 每回合叫的）、`aos-kernel ls`＝印給人看（目前只剩這一個子命令）。
- **舊的子命令被叫到就擋下來**：`aos-kernel init`／`aos-kernel tick` 都是退出碼 2、stderr 印一行提示改用 `aos-kernel-init`／`aos-kernel-tick`，不會偷偷做事（`aos-kernel init` 那次也不會建出家來）。
- **`aos-kernel-init` 寫進 `inst.json` 的 argv 換成 `aos-kernel-tick` 的絕對路徑**（`{"argv":["<絕對路徑>/aos-kernel-tick"],"cwd":"."}`），原本是 `[aos-kernel 的絕對路徑, "tick"]`；理由同 §18.1：不靠 PATH。
- **共用的東西留在 `aos_kernel.py`**：`aos_kernel_init.py` 用它的 `KHome`／`DEFAULTS`，`aos_kernel_tick.py` 用它的 `here_or_die()`／`CTL_BIN`／`IDLE_INST`，家的版面只定義一次。
- **行為沒改**，只是搬家：五步、退出碼（tick 一律 0、不是家＝1）、家的結構都跟 §18.1 一樣。
- 新增的測試：`aos-kernel init`／`aos-kernel tick` 各要退出碼 2 並提示改路；測試 183 → 185 條，全綠（約 30 秒）。

