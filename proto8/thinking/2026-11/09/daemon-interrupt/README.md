# 2026-11-09 daemon 真正的中斷（daemon-interrupt；規劃＋使用者裁定（11-09）：做成 `aos-daemon-ctl poke`；施工結果見 05）

← [2026-11-09](../README.md)｜細節：[01 現況與實測](01-現況與實測.md)、[02 三條路](02-三條路.md)、[03 衝突與邊緣](03-衝突與邊緣.md)、[04 方向題與結論](04-方向題與結論.md)、[05 施工結果](05-施工結果.md)

## 使用者原話（11-09，逐字）

> 對了，daemon這塊，目前是super loop事，每次循環檢查一次，這沒有真正的所謂中斷。我有個想法，如果要做真正的interrupt，那有幾條路，第一種是吃到特定訊號SIG*後，去讀特定檔案。第二種是開一個socket檔案給人寫，並且我們提供相關指令。第三種是走plan9路線，將/proc映射過去

補充（同日，經頂層轉述，逐字；規劃的前提）：

> 這種中斷，就先不考慮可遷移性了。就是說，早前有定過：與linux或底層相關的各種麻煩事都盡量讓daemon作處理與隔斷，讓aos proc能夠盡量享有純粹抽象。所以這套中斷我覺得同樣是做為橋樑，aos體系下，第一優先考慮使用的仍是super loop，第二優先，也就是真的有緊急需求，才走這套。並且這套希望是可選的。

「早前有定過」那條是使用者 11-05 晚說的「所有牽涉到linux原生行程的機制，都以daemon爲界面，而daemon所擔任的，就是橋梁，並且盡量將各類東西暴露爲檔案」（[no-pid](../../05/no-pid/README.md)），落在 [CONCEPTS 附錄1 名詞](../../../../docs/CONCEPTS/附錄1-名詞.md) daemon 條的 11-06 註、[C-04](../../../../docs/CONCEPTS/01-設計理念/01-C-01～C-48.md)、[C-83 ②](../../../../docs/CONCEPTS/01-設計理念/09-C-83.md)（11-06 改成「建議」），以及 [lib 規則 11](../../../../lib/docs/01-分層等/02-規則5a至11與引用.md)。使用者 10-30 也提過 plan9：「純粹的寫檔案、讀檔案……這一塊我們aos好像沒有用到，之後可以考慮。不過這個感覺只能一對一？多對一的話就得用上鎖了。」（[map-review 01](../../../2026-10/30/map-review/01-使用者原文.md)）

## 使用者裁定（11-09，逐字）

> 先做訊號就好，然後只做一個指令：aos-daemon-ctl ring，這需要daemon在自己的stack寫有自己的pid，然後這個指令透過這個pid去傳送訊號，傳送之後daemon會立即讀檔。ring有選項，可以指定這次是否算做一次完整loop的exec(也就是類似提前讓他做一次cycle)，或是只是讓他單純吃ctl，或是吃ctl+信箱。ring這個名字感覺不太好，幫我想想是否有其他名字。可以順手擋掉SIGUSR1/2。其他指令不動。這些都可以再討論。clock我要再仔細看看。

> 那就poke。指令用--all/--ctl/--mail...，預設只吃--ctl。pid被別的程式重用...這是使用者自己要承擔的風險，但我們確實也會做一些護欄，就是你說的這些。剩下的你說的都OK。clock我繼續看

兩句之間頂層提、使用者回「剩下的你說的都OK」的：pid 用 daemon 已寫在自己 state.json 的 `pid`／`started_at_ticks`／`boot_id`，不另開檔；送之前比對 `/proc/<pid>/stat` 的 starttime 與 `/proc/sys/kernel/random/boot_id`，三者都對上才送，否則報 daemon 不在；跨帳號／沙箱送不出去（EPERM）就回錯、不改走別路；連 poke 多下合併成一次；身體跑到一半被 poke 不中斷身體，跑完立刻補看；這是對「其他人不碰 pid」（N-17 的 11-06 改讀）開的例外，要寫進條文。

## 裁定後的做法（結論）

- **只做訊號、只有一個寄件人**：`aos-daemon-ctl [--daemon D] poke [--ctl|--mail|--all]`（三者互斥、預設 `--ctl`）；先開 pidfd、比 starttime 與 boot_id、再用 pidfd 送。對不上／不在＝`DaemonMissing`，EPERM 等送不出去＝`PokeFailed`，都退 1；成功不印、退 0；state 窗關著＝`StateMissing`。
- **三個訊號**：`SIGRTMIN+1`＝ctl、`+2`＝mail、`+3`＝all；daemon 在 state.json 寫穩定欄 `poke: {"ctl": N, "mail": N, "all": N}`，寄件人只照這欄送、沒這欄就拒（`PokeFailed`）。排隊的訊號醒來一次全取出、取最強的模式做一次。
- **三種模式**：`--ctl`＝立刻跑一圈讀 ctl.json、procs_ctl、對表、寫窗，這圈不認領信箱、不跑身體；`--mail`＝再加信箱；`--all`＝提前一整圈（含身體，不管 interval 到了沒；`max` 照算）。平常的 super loop 圈完全不變，poke 只是提早叫醒。身體跑到一半（含內嵌單子 `run_inline`）不打斷，跑完才補看。
- **SIGUSR1／SIGUSR2 一律擋住**（不再把 daemon 打死）；子行程起來前遮罩還原成 daemon 擋之前的樣子（aos-util `restore_signals`），身體、子項照常收得到這些訊號。
- **只有 aos-daemon 與這支指令懂訊號**：proc 與其他 aos 程式照舊只寫檔；aos-loop 不接 poke（引擎只多一個通用掛鉤 `wake_`／`woke`，aos-loop 不設）；其他子命令不動。條文：[N-17 的 11-09 例外](../../../../docs/NORMS/05-基礎設施-窗/06-N-17.md)。
- **跟 04 推薦的差別**：使用者選了**訊號**而非 socket（04 題 1 推薦 socket 當預設鈴）；指令叫 **poke**（使用者原提 ring）；**不做 daemon.json 的 `interrupt` 開關**（04 細節 2、3：開了才在 state 宣告），改成 daemon 一律宣告 `poke` 欄；寄件人從各口加 `--urgent`（04 題 3、細節 4）改成**獨立的 `poke` 子命令**，`aos-post send`、`py/daemon_ctl` 的寄信函式不加旗標；04 題 4（擋 SIGUSR1／2）照推薦，但改成不論有沒有人用 poke 都擋；04 的搶占（細節 7）、daemon 叫子項（細節 8）、socket 與 plan9 都沒做。

## 結論（白話；裁定前的規劃）

- **現況**：daemon 閒著時每圈最多睡 1 秒，寫 ctl 平均約 130 毫秒才被看到（最慢 1 秒，暫停中 0.7 秒）；SIGINT／SIGTERM 會馬上叫醒。**真正沒有中斷的地方在「跑身體」那段**：loop（或 daemon 自己的身體）跑一次身體的整段期間完全不看 ctl，身體是一次 LLM 呼叫就是幾分鐘。另外現在對 daemon 送 SIGUSR1 會**直接把它殺掉、子項留成孤兒**。→ [01](01-現況與實測.md)
- **三條路都做成「門鈴」**：鈴只叫 daemon「現在就看一次檔」，指令照舊寫 ctl.json／procs_ctl.json／信箱；鈴丟了就等下一圈（最多 1 秒），多響了只是多看一眼。proc 端只多一個 `--urgent` 旗標，不碰訊號、socket、FUSE。開關是 daemon.json（loop.json 同）的選填 key `interrupt`，沒寫＝跟現在一樣。開了就在 state 窗宣告「我接哪種鈴、在哪」，寄件人照公開窗決定要不要響。→ [02](02-三條路.md)
- **三條路比較**：①訊號最省事，但寄件人要讀 pid、對 /proc、`kill()`，直接撞 no-pid，沙箱裡與跨帳號都送不出去；**只適合 daemon 叫自己的子項**（daemon 本來就管子的 pid）。②Unix socket 只看檔案權限，沙箱、跨帳號都通、不碰 pid，改動中等；要注意 socket 路徑有 108 字元上限、`/mnt/c` 這類掛載上建不起來。③plan9 路線最像「全是檔案」（daemon 用 FUSE 掛一個 `live/` 資料夾，寫它就是呼叫），但最重，daemon 卡住時所有碰 `live/` 的人（連 `ls`、`git add`）一起卡住，當掉還留殭屍掛載。→ [02](02-三條路.md)、[03](03-衝突與邊緣.md)
- **搶占**（身體跑到一半也叫得到）三條路共用一套：第一版只在「身體是一支程式」那條路做（`run_folder`），鈴聲期間讀到的 `stop` 立刻把 SIGTERM 轉給身體，`pause` 等身體跑完才生效；身體是內嵌單子的那條路只喚醒、不搶占。→ [02 § 搶占](02-三條路.md#三條路共用搶占)
- **方向題 4 題**（推薦）：①先做哪條（推薦②socket 當預設鈴；①只用在 daemon 叫子項；③排後）②鈴還是通道（推薦鈴）③預設響不響（推薦寄件人明說 `--urgent`）④開關關著時要不要順手擋 SIGUSR1／SIGUSR2（推薦擋）。→ [04](04-方向題與結論.md)

規劃流程照 [user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)：opus 收集＋在 /tmp 複本實測 → fable 一次性規劃 → opus 補邊緣（路徑 108 字元、drvfs、子項 unblock 寫死三訊號、①只限父叫子）。
