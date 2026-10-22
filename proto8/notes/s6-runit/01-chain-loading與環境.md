← [入口 s6-runit](../s6-runit.md)｜涵蓋：1. chain loading、2. envdir 與 `.env`｜下一份 [02-監管與重啟](02-監管與重啟.md)

# 1. chain loading：一路 exec 下去

**s6／runit 怎麼做。** execline 的一支腳本就是一條 argv，裡面是一串程式：每支只做自己那件事（改環境、換使用者、cd、動 fd），做完就 `exec` 成「argv 剩下的部分」，沒有常駐的 shell。skarnet 的文件說這叫 chain loading，也有人叫 Bernstein chaining（[execline grammar](https://skarnet.org/software/execline/grammar.html)）。runit 的 `run` 腳本通常是一行 `exec chpst -e ./env -u app ./daemon`：chpst 換使用者、設環境、上資源限制、拿鎖，然後 exec 成那支程式；它自己出錯退 100／111，否則結束碼就是那支程式的（[chpst(8)](https://smarden.org/runit/chpst.8)）。s6 那邊同樣的事拆成好幾支小程式接起來，例如 `s6-envdir ./env chpst -u app ./daemon`（[s6-envdir](https://skarnet.org/software/s6/s6-envdir.html)）。

**aos 怎麼做。** `aos-exec` 一支做完 N-59 那幾件：找入口、export `AOS_*`、cd 到 `AOS_CD`、讀 `.env`，然後 exec 入口（或行程內跑單子）。字串轉向＝交給「全新的一次 aos-exec」；`$AOS_ENTRY` 指到資料夾就走進去、一路往下，沿路每層的 `.env` 都讀。argv 陣列入口本身就是一條小鏈：`["aos-loop", {"$env": "AOS_CF"}]` 就是 aos-exec 做完自己的事、exec 成 aos-loop。aos-daemon 起子項時特別寫明「exec 成 aos-loop、pid 與啟動時間不變」——它認回子 loop（`adopt`）靠的正是 exec 不換 pid（[bin README](../../bin/README.md)）。

**兩邊一樣的地方。** 都是 exec、不 fork，所以 pid 從頭到尾是同一個，監工看到的就是真正在跑的程式；結束碼都是透明轉交（aos 的 N-43「透明轉交」對上 chpst 的「否則就是程式自己的碼」）；都不靠 sh 拼字串（對上使用者「少用 sh」）。

**可借鏡。** ①**「換使用者、資源上限、拿鎖、關 fd」不必長進 aos-exec 的旗標表**：argv 陣列入口本來就能寫 `["chpst", "-u", "app", "-l", "run.lock", "./run"]` 或前面接 `s6-envdir`，它們做完就 exec 下去，aos-exec 保持只做 N-59 那幾件——合 C-56 KISS，也合 C-04「Linux 那邊的事交給下面那層」。②**加旗標前的判準**：N-58 說旗標表以後會加。一個新旗標如果只是「改一下行程狀態再 exec」，先問能不能交給鏈上的另一支小程式。③順帶一提：skarnet 的程式分「永久錯 100／暫時錯 111」；aos 刻意不分，自己的錯一律 1（N-43，使用者「不另用 125～127」）。

**aos 刻意不同的地方。** s6 的順序寫在 argv 上、一目了然，每一步是哪支程式做的看得見；aos 把幾件事收在一支 aos-exec 裡、順序由規則固定（N-59：cd → 讀 `.env` → 挑入口），而且沿路讀哪幾份 `.env` 由資料夾結構決定、argv 上看不到。這是「資料夾＝程式」（C-68）要的：使用者 mkdir、放檔就是寫程式，不用自己排一條鏈。代價是除錯時要知道規則才推得出「這次讀了哪幾份 `.env`」。

# 2. envdir 與 `.env`

**envdir（daemontools 原版、s6-envdir、`chpst -e`）怎麼做。** 一個資料夾，一個檔一個變數：檔名＝變數名、第一行＝值（去掉行尾空白與換行，NUL 變換行）；**空檔＝把這個變數拿掉**；`.` 開頭或帶 `=` 的檔名跳過；值照字面、不展開任何東西。s6-envdir 另有 `-I`（資料夾不在就照跑）、`-f`（整份檔當值、可多行）、預設每檔只讀前 4096 bytes（[s6-envdir](https://skarnet.org/software/s6/s6-envdir.html)、[chpst(8)](https://smarden.org/runit/chpst.8)）。要用哪個 envdir 是 argv 上明寫的。

**aos 怎麼做。** 一份 `.env`，逐行 `名字=值`；只展開 `${名字}`（沒設＝錯），所以能寫 `PATH=${AOS_CD}/bin:${PATH}` 接舊值——這正是使用者要 `.env` 的主因（「主要是PATH的問題，除此之外API key也是」）；不支援引號、`export `、多行值；同名後者贏；錯只印檔名和行號、絕不印值；權限不檢查。隱式：資料夾裡有就讀，沿路每層疊上去，旗標最後蓋回；JSON 物件的 `.env` key 也算（[bin README](../../bin/README.md)、N-59 第 4 件）。

**可借鏡。** ①**拿掉一個變數**：envdir 用空檔表示「unset」；aos 的 `.env` 沒有寫法能拿掉變數（`X=` 是設成空字串），上層設了、下層一路往下拿不掉。現在沒人需要，記著就好。②**一個祕密一個檔、各自設權限**：envdir 每個變數一個檔，API key 那個檔可以單獨 `chmod 600`、甚至換擁有者——跟 C-64「用檔案是為了借 Linux 權限」同一個思路；aos 一份 `.env` 裡所有變數同一個權限。不改 aos 也做得到：入口寫成 argv 陣列、前面接 `s6-envdir secrets` 或 `chpst -e secrets`。③多行值：envdir `-f` 支援，aos 不支援；目前沒有需求。

**aos 刻意不同的地方。** envdir 的值照字面、不展開，要接舊 PATH 就得另寫一支 run 腳本；aos 選了能展開 `${名字}`，換來一份檔就搞定 PATH。envdir 是「呼叫的人指定讀哪個資料夾」，aos 是「走到哪讀到哪」（同 1. 的取捨）。另外 envdir 跳過 `.` 開頭的檔，aos 的 `.env` 本身就是 `.` 開頭——N-05 已把它列成「讀的人不讀 `.` 開頭的檔」的例外。
