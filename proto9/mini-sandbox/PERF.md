mini-sandbox 與 pi-sandbox 的效能成本總表：每種 kernel 每多一層要付多少、Linux 的層數上限、攤平前後、靜態與動態、aos-daemon 那條路，每個數字都寫了出處與怎麼重量（量測腳本在 [perf/](perf/README.md)）。

# 效能成本（11-27 家機）

← [mini-sandbox](README.md)｜量測腳本：[perf/](perf/README.md)｜使用者 11-27 晚問「有幫我記錄效能成本嗎」，這檔就是答案。

我自己定的標【擬】，照實測往外推的標【外推】。

## 先講結論（pi 在裡面會怎樣）

- **cg、mask 疊幾層，pi 開檔、列目錄、跑指令都一樣快**；只有起動每層多約 33 ms，開新行程在幾十層 cgroup 時慢約一成。
- **net、llm 每層都有一直在跑的行程**，記憶體、起動時間跟著層數加。net 疊 5 層時 pi 上傳從 26.7 掉到 5.6 MB/s；llm 每層讓 pi 問一次腦多 0.38 ms（跟真模型的秒級比起來看不出來）。
- **一層一層真開，最多約 33 層 user namespace 就撞牆**（net 一層吃 2 層，所以最多 16 層）。**七題實作後**：資源上限與遮檔案攤平，疊 100 層 0.2 秒就起好；太深的在起之前就拒絕（見最後一節「攤平後」）。
- **攤平（好幾層合成一次做）省的是起動時間和層數，不是開檔速度**：一層一層每層約 10 ms，攤平 1000 條約 21 ms；掛 0～10 萬條，pi 開一個檔都約 0.8 µs。
- **pi-sandbox（aos-daemon）那條路很輕**：daemon 起來約 8～23 ms，起一隻 proc 約 1 ms（ctl 回來）、3 ms（跑完 `/usr/bin/true`），整套（daemon＋llm kernel＋pi）到 pi 送出第一個請求約 0.3 秒，其中約 0.23 秒是 pi（node）自己起動。

## 量測環境與出處代號

**每個數字都是家機量的：** AMD Ryzen 7 9800X3D 8-Core Processor（8 核 16 緒）、Manjaro Linux、Linux 6.18.55-1-MANJARO、`/tmp` 是 tmpfs、家目錄是 ext4、Python 3.14.7。公司 WSL 一個都沒量。

下面每張表的「出處」欄用這幾個代號：

| 代號 | 是什麼 | 哪個 commit | 怎麼量的 | 現在怎麼重量 |
|---|---|---|---|---|
| **S** | 規模調查（`~/.aos/scratch/kernel-overlap-1127/scale-report.md`，腳本在 `~/.aos/scratch/kernel-scale-1127/`，家機、不進 git） | 報告沒寫；照結果檔的時間（11-27 17:48～18:00）推是 HEAD `0de8a53b8` 那時的 mini（推定） | 真的跑 `mini.py --kernels`（`run.py`＋`bench.py`），另有不開 namespace 的單獨實驗（`cgdepth.py`、`mounts.py`、`copysim.py`、`userns_depth.py`） | `perf/bench.py mini …`、`cgdepth`、`userns`、`mountmax` |
| **F** | 檔案替換調查（`~/.aos/scratch/kernel-overlap-1127/files-report.md`，腳本在 `~/.aos/scratch/kernel-files-1127/`） | 同上時段（17:48～17:54），不靠 repo 的程式 | 都在 `unshare -Urm` 裡；開檔延遲用 C 寫的 `lat.c` 量；那時另一位同時在跑規模測試，load 約 1.5 | `perf/bench.py fs overlay flat fuse fusehang sock mountmax` |
| **N** | 最小底層＋網路模組調查（`~/.aos/scratch/proto9-smallproto-1127/net-report.md`） | 11-27 13:59 前，HEAD 推是 `293269f7f`；量的是 `systemd-run`＋`unshare` 那一行，不是 mini | 手下指令 | 沒搬進 perf（見 [perf/README](perf/README.md)「沒搬的」） |
| **P** | 這次量的（`perf/bench.py`） | HEAD `e6fab894b`，工作樹 dirty：`mini-sandbox/` 的程式另一位正在改（七題實作中）；`pi-sandbox/` 與 `cpp/aos-daemon/` 沒改，daemon 是 11-27 12:48 建的那支 | `python3 perf/bench.py pisandbox`（完整版）與 `--quick`；那時家機 load 約 3～3.7（另一位在跑 mini 的驗收） | 同左 |

> 註：`S` 的 pi 那幾項（stat、開檔、fork…）是在沙箱裡用 Python 量的，含直譯器本身的成本，所以開檔是 2 µs；`F` 用 C 量，是 0.8 µs。兩邊不要直接相比，只看同一組裡「層數變多有沒有變慢」。

## 1. 每種 kernel 每多一層的成本

### 1a. 起動、記憶體、常駐行程（出處 S）

「起到最裡層」＝從叫 mini 到最裡層第一行指令跑起來。「常駐行程」＝起好之後 mini 的 scope 裡一直在跑的行程數。

| kernel | 量到的（層數：值） | 每多一層約 | 常駐行程 | pi 在裡面會怎樣 |
|---|---|---|---|---|
| 不裝 | 起到最裡層 0.11 s、scope 記憶體 2.6 MB、2 隻（sh＋unshare） | — | 2 | 基準 |
| cg | 起動 1／10／20／30／32 層：0.10／0.38／0.70／1.04／1.12 s；scope 記憶體 1.8～7.8 MB；cgroup 深度 4／22／42／62／66 | **+33 ms**、+2 層 cgroup、記憶體幾乎不加 | 2（不加） | 起來慢一點，起好之後沒有東西一直在跑 |
| mask | 1／10／20／32 層：0.11／0.38／0.69／1.06 s；記憶體 2.5～4.2 MB；掛載數 34／52／72／96 | **+31 ms**、+2 條掛載 | 2（不加） | 同 cg |
| cg、mask 交錯 | 10／20／32 層：0.44／0.80／1.23 s；記憶體 5.0／7.1／8.9 MB | +37 ms | 2 | 同上 |
| net | 1／2／3／5／10／16 層：0.26／0.43／0.68／1.02／1.96／3.04 s；scope 記憶體 51／104／146／248／484／768 MB；行程 5／8／11／17／32／51 | **+180 ms、+48 MB、+3 隻**（2 隻 python＋1 隻 pasta）；**收掉每層 +3.1 s** | 每層 3 | 疊越多越吃記憶體，關掉沙箱要等很久（3 層要 10 秒） |
| llm | 1／2／3／5／10／32 層：0.13／0.19／0.27／0.37／0.73／2.07 s；記憶體 15／28／40／65／126／391 MB | **+60 ms、+12.5 MB、+1 隻**（proxy） | 每層 1 | 見 1c |
| uid | 只能有 1 層（第二層切不了，見 [README](README.md)） | 沒量 | — | — |

**每層一支 python 要多少（出處 S，`results_python.txt`，20 次中位數）：** 空的 python 起動 5.5 ms；cg、mask、uid 要 import `nest`，13.7 ms、RSS 15 MB；llm 要 26.4 ms、RSS 24 MB。cg、mask 每層＝python 兩次＋`unshare`，跟每層 33 ms 對得上，最後都換成下一支，所以不留常駐。

**照實測外推到 1000 層【外推】（出處 S）：**
- cg／mask：起動約 33 s；cgroup 2000 層，核心記憶體約 100 MB；pi 開新行程慢到約 1.3 ms。
- net：起動約 3 分鐘、記憶體約 50 GB、收掉約 50 分鐘。
- llm：起動約 70 s、記憶體約 12.5 GB，pi 問一次腦慢 0.4 s。
- 實際上一層一層真開時 33 層就撞牆（見 1b），所以上面這些只在「攤平」之後才有意義。

### 1b. 層數上限：namespace 與其他（出處 S、F、P）

| 項目 | 值 | 出處與怎麼量 | pi 在裡面會怎樣 |
|---|---|---|---|
| user namespace 巢狀 | **從主機往下最多 33 層**，第 34 層 `unshare` 回 `ENOSPC`「No space left on device」（`man 7 user_namespaces` 寫 32，實測多一層） | S（`userns_depth.py`）、P（`perf/bench.py userns`：`new_levels_made 33`） | 外層用掉幾層，pi 自己再開沙箱就少幾層 |
| PID namespace 巢狀 | 32 層，第 33 層 `ENOSPC` | S、P（`pid 32`） | mini 每串只在最裡那步開 1 層，碰不到 |
| `max_user_namespaces` | 246988（總數，不是深度） | S、P（`limits`） | 碰不到 |
| `fs/mount-max` | 100000（每個 mount namespace 各自算） | S（`mounts.py`：第 89672 次 bind 時 ns 裡共 99999 條）、F（`wall.py`：99972 條＋原有 27 條）、P（`mountmax`：99972 條、`errno 28`） | 撞到時錯誤也是「No space left on device」，看起來像硬碟滿 |
| overlayfs 疊幾層 | 500；第 501 層 `EINVAL` | F（`bench_ov.py`） | — |
| cgroup `max.depth`／`max.descendants` | `max`（不限） | S、P（`limits`） | 只受核心記憶體與 fork 成本限制（見 1c） |
| mini 自己 | net 子網只找 `10.77`～`10.99`，最多 23 層 | S（讀 `net_kernel.free_subnet`） | user namespace 先撞到，碰不到 |

**每種 kernel 吃幾層 user namespace（S，讀程式、實測對得上）：** cg 1、mask 1、uid 1、llm 1、**net 2**，最裡那步 1（什麼都沒裝時多 1 層鎖宣告夾）。加起來不能超過 33：**cg、mask、llm 最多各 32 層，net 最多 16 層**。

**pi 在裡面會怎樣：** 外面是 `aos/base`（cg＋mask＋llm＋最裡那步＝4 層）時，pi 在裡面再開「同樣一套」的沙箱，最多約 7～8 套；外面再加 net 和 uid（共 7 層）時只剩約 4 套。【外推：算術，沒實測】

### 1c. pi 在裡面的動作會不會變慢

**檔案、行程、記憶體（出處 S，Python 量，單位見表頭）：**

| 疊法 | stat（µs） | 開檔讀（µs） | 列 `/usr/bin`（µs） | fork（µs） | 執行 `ls`（ms） | 碰 256 MB（ms） |
|---|---|---|---|---|---|---|
| cg ×1 | 0.56 | 2.01 | 633 | 401 | 0.26 | 13.9 |
| cg ×32（66 層 cgroup） | 0.54 | 2.03 | 646 | **446（+11%）** | 0.29 | 13.7 |
| mask ×32 | 0.58 | 2.05 | 648 | 410 | 0.26 | 15.0 |
| 交錯 ×32 | 0.54 | 2.00 | 635 | 420 | 0.28 | 13.2 |

**pi 在裡面會怎樣：** 疊多少層 cg 或 mask，開檔、列目錄都一樣快；開新行程在幾十層 cgroup 時慢約一成。

**單獨疊 cgroup，不開 namespace（出處 S `cgdepth.py`；P `perf/bench.py cgdepth` 重量 1、100 層）：** 每層都開 cpu／memory／pids 並設上限。

| 層數 | fork | 建每層 | scope 記憶體增加 | 整台 Slab／Percpu 增加（有雜訊） |
|---|---|---|---|---|
| 1 | 127 µs | — | 0.5 MB | — |
| 100 | 175 µs | 0.15 ms | 5.3 MB | +8 MB／0 |
| 1000 | 645 µs | 0.8 ms | 45 MB | +130 MB／+27 MB |
| 1991 | 1308 µs | 1.2 ms | 81 MB | +246 MB／+56 MB |

P 這次 1／100 層：fork 347／406 µs（量的行程比較胖，所以基準高，但一樣是「多 100 層慢約 60 µs」）、建每層 0.19／0.13 ms、scope 記憶體 +0.5／+1.1 MB。**pi 在裡面會怎樣：** 上百層 cgroup 時開新行程慢一點點；上千層時慢 5～10 倍（每次多約 0.5～1 ms），跑 `make -j` 這種大量開行程的事才感覺得到。

**單獨疊掛載（出處 S `mounts.py`，一個 namespace 裡）：** 1 萬條時 stat 0.53 µs（沒變）、讀 mountinfo 4.4 ms、複製一份 mount ns 6.4 ms；10 萬條時 stat 0.52 µs（沒變）、60 ms、73 ms。在同一個 user ns 裡一層層開 300 層 mount ns，每層 5.2 ms（那時每層要抄約 1 萬條）。

**網路（出處 S，沒設頻寬上限，量的是每多一層 pasta 的成本，MTU 1500）：**

| net 層數 | 小檔 curl 中位數 | 下載 | 上傳 |
|---|---|---|---|
| 外面直連 | 0.2～0.9 ms | 14 GB/s | 8 GB/s |
| 1 | 0.19 ms | 454 MB/s | 26.7 MB/s |
| 2 | 0.21 ms | 388 MB/s | 25.3 MB/s |
| 3 | 0.23 ms | 364 MB/s | 15.9 MB/s |
| 5 | 0.29 ms | 354 MB/s | **5.6 MB/s** |

**pi 在裡面會怎樣：** 疊 1 層 net，pi 下載仍有幾百 MB/s，上傳只剩約 27 MB/s；疊越多上傳越慢。

**網路模組有上限時準不準（出處 N，`systemd-run`＋`pasta`＋nft＋tc，不是 mini）：** 上傳 tbf 8mbit 量到 0.98 MB/s；下載 tbf 16mbit 量到 1.96 MB/s；總量 5 MB 兩次加起來剛好 5 MB 就斷；用 `police 16mbit`（直接丟封包）只跑到 0.24 MB/s，很不準。最底層那一行的上限：CPU 20% 量到 `ratio=0.20`、記憶體超過被 OOM 砍（退出碼 137）、`TasksMax=30` 時開到第 28 隻就開不出來。

**問腦（llm）：**

| 經幾層 llm kernel | pi 問一次（中位數） | 出處 |
|---|---|---|
| 1 | 0.19 ms | S（mini，從沙箱裡經 socket） |
| 2／3／5／10／32 | 0.45／0.86／1.61／3.71／12.3 ms | S |
| 1（pi-sandbox 的 kernel，從外面打它的 socket） | 0.12 ms | P |
| 2 疊（pi-sandbox） | 0.50 ms | P |

**pi 在裡面會怎樣：** 每多一層 llm kernel，問一次腦多約 0.38 ms（兩邊量的一樣）。真模型一次要幾秒，看不出來。

### 1d. `.aos` 宣告每層整份抄（出處 S）

- 實際跑 mini：暫存夾總大小 cg ×32＝15.5 KB、mask ×32＝46.3 KB；pi 看到的那份 727 B／2687 B。
- 模擬 1000 層（`copysim.py`，照 `nest.new_env`／`declare` 一層層抄，不開 namespace）：第 1000 層那份 cg 20 KB／mask 80 KB；1000 層加起來 cg 10 MB／mask 40 MB；抄的時間每層 0.33～0.45 ms，不隨層數變慢。
- **總大小是平方成長、時間是線性**；跟 python 起動的 33 ms 比可以忽略。`/tmp` 在記憶體裡，所以吃的是記憶體。
- `--dry-run` 1000 層 0.04 s，命令列 180 KB（單一參數上限 128 KB、總共 4 MB）。

## 2. 攤平前後

「攤平」＝連續好幾層同類的 kernel，在起動前先算好，合成一次做（只開一個 namespace）。

| 比什麼 | 一層一層 | 攤平 | 出處 |
|---|---|---|---|
| 純檔案層（每層＝一支精簡 python＋一個 user+mount ns＋一條 tmpfs） | **每層約 10 ms**：10 層 108 ms、30 層 312 ms | **1000 條一次掛＋pi 自己那層 ns，共 21 ms** | F（`layer.py`、`flat.py`，合成的、不是真的 `mask_kernel.py`） |
| 同上，這次重量 | 1 層 10.3 ms、10 層 72.9 ms（每層 7.3 ms） | 10 條 10.1 ms、1000 條 18.2 ms；pi 都拆不掉（`agent_could_umount False`） | P（`--quick flat`） |
| 掛 N 條靜態蓋法時 pi 開一個小檔 | — | 0 條到 10 萬條都 **0.75～0.80 µs**；P 這次（`/tmp` 是 tmpfs）0～1000 條都 0.67～0.70 µs | F（`run_bind.py`、`wall.py`）、P（`fs`、`mountmax`） |
| 掛 N 條時讀整張掛載表 | — | 1000 條 0.85 ms（`cat`）／0.38～0.72 ms（Python 讀）；10 萬條 80 ms（`cat`）／55 ms（Python 讀） | F、P |
| 掛 N 條之後 pi 再開一層沙箱（`unshare -Urm true`） | — | 1000 條 0.83 ms（P 0.87～0.94）；10 萬條 66 ms（P 77 ms） | F、P |
| cg 10 層 vs 手算攤平 1 層（cpu 90～40%、mem 400～250M、pids 80～45） | CPU 比例 0.404、fork 到第 43 隻失敗、用到 240 MB 被砍；三次牆上時間 3.68／0.67／0.75 s | **0.398、43、240 MB**；3.13／0.17／0.20 s | S（`results_flat_cg.txt`，`flatprobe.py`） |
| mask 10 層 vs 1 層蓋 10 條 | 12 個測試檔只看得到 2 個；掛載 52 條；起動 0.35 s | 一樣 2 個；43 條；**0.11 s** | S（`results_flat_mask.txt`） |
| net 3 層（頻寬各不同）vs 攤平 1 層 | 中間層總量 4 秒就被吃光，pi 只拿到 1.2～2.4 MB | 拿到約 24 MB（上限 25 MB，正確） | S（`results_flat_net*.txt`，重現 3 次） |

**pi 在裡面會怎樣：** 攤平後 pi 看到的檔案、拿到的限制完全一樣（實測），只是沙箱起得比較快、不會撞 33 層的牆，pi 也還有很多層可以自己再開沙箱。開檔速度兩邊都一樣快，因為 Linux 找路徑時不在乎掛載是哪一層掛的。

**掛的速度（F，每條）：** bind 4.0 µs（1000 條）～15.7 µs（5000 條，掛載點在磁碟上）、tmpfs 5.7～6.8 µs、`/dev/null` 1.6 µs、唯讀 4.5～17.1 µs；掛載點在 tmpfs 上時 bind 每條 1.9 µs（差在哪沒查）。P 這次（tmpfs 上，1000 條）：bind 3.6、tmpfs 5.6、null 1.9、ro 4.6 µs。

**overlayfs（F，唯讀，最底層 2000 個檔）：** 每個檔第一次被碰到時，每多一層慢約 0.3 µs：1／5／20／100／500 層 2.06／3.27／7.46／33.2／156.7 µs；碰過之後都約 1 µs。P 這次 1／5／20 層 2.44／2.83／6.09 µs。**pi 在裡面會怎樣：** 疊 20 層感覺不到；疊 500 層時 `grep -r` 掃幾萬個檔會多幾秒。

## 3. 靜態 vs 動態

| 做法 | pi 每開一次檔 | 跟 bind 比 | 要常駐行程嗎 | 服務出事時 pi 會怎樣 | 出處 |
|---|---|---|---|---|---|
| bind、tmpfs、null、唯讀（靜態） | 0.8 µs（P：0.57 µs） | 1 倍 | 不用 | 不會出事 | F、P |
| overlay（靜態） | 第一次 1～157 µs，之後 1 µs | 1～1.3 倍 | 不用 | 不會出事 | F |
| bind 一個 socket，後面接服務（Python 一問一答，服務每次重讀檔） | 開檔 0.8 µs；一問一答 **6.2 µs**（P：5.2～5.8 µs） | — | 要 | 只有用那個 socket 的程式會等，設 timeout 就好 | F（`sockrtt.py`）、P（`sock`） |
| FUSE，C（rofiles-fuse，預設快取／不快取） | **6.5／11.2 µs**（P：5.7～6.7／11.3～12.4） | 8～14 倍 | 要 | 碰到那個路徑就卡死，`kill -9` 無效 | F、P（`fuse`） |
| FUSE，Python（快取 1 秒／不快取） | **20.8／36.8 µs**（P：18.7～21.1／31.8～36.1） | 25～45 倍 | 要，約 15 MB（P：16.8 MB） | 同上 | F、P |

**服務卡住時（F `hang.py`；P `perf/bench.py fusehang` 重現）：**
- 服務收下請求後不回：讀的人停在 `request_wait_answer`，送 SIGTERM 後變成 **D 狀態**（不可中斷），**SIGKILL 也殺不掉**；只有把服務殺掉，讀的人才結束。這期間別人 `stat` 那個掛載點也一起卡住（P：2 秒後被 `timeout` 砍）。
- 服務還沒讀到請求就被暫停：SIGTERM 殺得掉。
- 服務死掉後新的讀者馬上得到 `Transport endpoint is not connected`。
- **pi 在裡面會怎樣：** 用動態的路徑，服務一卡 pi 碰到那個路徑（包括 `ls -l` 上一層、`find /`）就整個卡住，只能從外面殺服務。

**會變的資料不一定要動態（F）：** 服務一直改寫某個檔、bind 那個檔，pi 馬上讀到新內容（P 的 `content-change-seen` 也看到 `changed`）。真的要動態的只有：每次讀要當場算、要攔寫入、要逐次准不准或記帳。

## 4. pi-sandbox（aos-daemon）那條路（出處 P）

`python3 perf/bench.py pisandbox`：用 [pi-sandbox](../pi-sandbox/README.md) 的 `aos_pi.Sandbox` 與 `daemon_ctl`、`--fake`（不叫真模型、不碰 mini）。完整版每項 20 次（proc）或 200 次（請求）取中位數，整套跑 3 次；`--quick` 的數字差不到一成。報告裡原本**沒有**這組數字，這次順手量的。

| 量什麼 | 值 | 怎麼量 | pi 在裡面會怎樣 |
|---|---|---|---|
| 起 daemon | 8～23 ms | `aos-daemon`、`daemon.json` 是 `{}`，到它印出 `export AOS_DAEMON=` | — |
| 起一隻 llm kernel | 51 ms（最下面那隻）、56～67 ms（疊在上面的） | `ctl start` 到它的 `sock` 出現（python 起動佔大半） | — |
| 起一隻 proc（只有 `/usr` 等） | ctl 回來 **0.99 ms**；跑完 `/usr/bin/true` 3.2 ms | 寫 `start CONFIG` 進 `ctl`（起好才回），再看 `procs/<名>/state` | pi 每叫一次 aos 起一隻 proc，只多約 1 ms |
| 起一隻 proc（pi 的整片天空，13 筆） | ctl 回來 **1.06 ms**；跑完 3.2 ms | 同上 | 天空多幾筆幾乎不加時間 |
| 經 1 隻 llm kernel 問一次 | 0.12 ms（p90 0.20） | 從外面 POST 到它的 unix socket，假腦回答 | — |
| 經 2 隻疊的 llm kernel | 0.50 ms（p90 0.57）：**每多一隻 +0.38 ms** | 同上，打上面那隻 | 跟 mini 的 llm 每層 +0.38 ms 一樣 |
| 再經 `/llm/relay`（pi 實際走的路） | 0.62 ms（p90 0.71）：**relay 多約 0.1～0.2 ms**（`--quick` 那次 0.70 ms） | 外面起 `node relay --llm <夾> --port N`（只轉接），TCP 打它 | 問一次腦，沙箱這一段總共不到 1 ms |
| 收掉 daemon | 113 ms | SIGTERM 到它結束（沒有 init，它把底下全部 SIGKILL） | — |
| **整套：daemon＋1 隻 llm kernel 起好** | 67～78 ms | `aos_pi.Sandbox.start()` | — |
| **整套：從開始到 pi 的第一個請求** | **299～316 ms** | 同上，再起 pi（`say hi`），看 kernel 帳本出現第一行 | 按下去約 0.3 秒 pi 就在想事情了 |
| 其中 pi 起來到第一個請求 | 233～238 ms（帳本那行是回答完才寫，假腦回答不到 1 ms） | pi 那隻 proc 起動到帳本第一行（node＋pi 自己起動佔絕大多數） | 沙箱本身只佔約 70 ms |
| pi 做完（一次請求、`stopReason stop`） | 258～273 ms（從 pi 起動算） | `run_pi` 回來 | — |

**沒量：** 真模型那條（要花錢，而且秒級的模型時間會蓋掉這些）；pi 在沙箱外直接跑要多久（所以「沙箱讓 pi 起動慢多少」只能說 proc 起動那 1～3 ms）；公司 WSL。

## 已知的毛病（七題實作後：1、2、4 修好了，3 還在）

下面都是一層一層真開時量到的（出處 S）。派工說七題實作（去重、merge、攤平、effective…）會處理；修好之後用 `perf/bench.py mini …` 重量，填進下一節。

1. **【已修】撞 33 層的牆時卡死，不是乾淨報錯。**（現在起之前就算層數、超過上限直接拒絕；萬一真撞到也乾淨失敗、不留行程，見下一節與 README 第六段） cg、mask、llm 第 33 層印一行 `unshare: unshare failed: No space left on device` 後退出，但 util-linux `unshare` 的對 id 小幫手變成孤兒、一直握著 stdout，scope 收不掉，讀 mini 輸出的人會一直等（量測腳本第一次等了 211 秒）。net 第 17 層更糟：整串卡死、mini 不回來，只能 SIGKILL。**pi 在裡面會怎樣：** pi 根本沒起來，使用者只看到「卡住」，訊息還像硬碟滿了。
2. **【已修】net 疊 3 層而且各層頻寬不同時，中間那層的總量 4 秒內就被吃光**（原因查到了：pasta 一丟包就整段重送、總量在 tbf 丟之前就算；改成下載佇列 1 秒、讓 tbf 延後不丟，狀態檔多 `up_dropped`／`down_dropped`），pi 只拿到 1.2～2.4 MB（設定應該能拿約 24 MB）。重現 3 次；原因推測是被 tbf 丟掉的封包重送時被 nft quota 重複計算，沒查證。攤平成 1 層就正確。
3. **【還在】net 收掉每層約 3.1 秒，一層接一層收**（七題後重量：1／3／5／10 層 3.1／9.2／15.3／30.7 s）：1 層全程 3.33 s、3 層 9.95 s【外推：1000 層約 50 分鐘】。推測是 `Kernel.stop()` 的 `p.wait(3)` 等到逾時，沒查證。
4. **【已修】**（管理面，不是速度）cgroup 那一格寫的是最裡那層（現在有 `.aos/effective/` 與 `blame`、`--explain`，警告只印一行摘要），`cpu 40%` 其實可能是第 4 層給的；10 層印 19 行警告，上千層會淹掉畫面。

## 攤平後（七題實作之後）

出處 P2：家機（同上），11-27 晚，七題實作交件前的工作樹（基於 `e6fab894b`，交件 commit 見 git log），main-alt 跑：

```
python3 proto9/mini-sandbox/perf/bench.py --out ~/.aos/scratch/proto9-mini-1127/perf-after.jsonl mini --kinds cg,mask,mix --layers 1,5,10,32,100
python3 proto9/mini-sandbox/perf/bench.py --out ~/.aos/scratch/proto9-mini-1127/perf-after.jsonl mini --kinds llm,net --layers 1,3,5,10,32
```

| kernel | 層數 | 起到最裡層 | scope 記憶體 | 常駐行程 | pi 開檔 | pi fork | 收掉 | 跟攤平前比 |
|---|---|---|---|---|---|---|---|---|
| cg | 1／5／10／32／100 | 0.148／0.147／0.153／0.178／0.219 s | 1.9～22 MB | 2 | 2.9～3.4 µs | 241～256 µs | 0.03～0.06 s | 攤平前 32 層 1.12 s、第 33 層起不來；現在 100 層 0.22 s，cgroup 深度一律 4 |
| mask | 1／5／10／32／100 | 0.136／0.133／0.142／0.169／0.193 s | 1.5～21 MB | 2 | 2.9 µs | 238～249 µs | 0.03 s | 攤平前 32 層 1.06 s；掛載數 100 層時 232 條 |
| cg、mask 交錯 | 1／5／10／32／100 | 0.143／0.153／0.157／0.177／0.227 s | 1.9～26 MB | 2 | 2.9～3.1 µs | 249～257 µs | 0.03～0.04 s | 攤平前 32 層 1.23 s |
| llm | 1 | 0.173 s | 14.5 MB | 3 | 2.95 µs | 237 µs | 0.54 s | 問一次腦 0.21 ms。3 層以上：bench 產生的是「每層各自直通上游」的設定，現在照第 3 題**起之前就拒絕**（rc 2、0.04 s，什麼都沒起），所以量不到疊層；要量疊層得把內層寫成 `upstream: outer`（bench 還沒跟上） |
| net | 1／3／5／10 | 0.30／0.69／1.10／2.06 s | 50／151／252／448 MB | 5／11／17／32 | 2.8～3.1 µs | 235～258 µs | **3.1／9.2／15.3／30.7 s** | 起動、記憶體跟攤平前一樣（網路照舊真開）；收掉每層 3 秒的毛病**還在**（不在七題裡） |
| net | 32 | 0.05 s 就報錯（rc 2） | — | — | — | — | — | 照第 6 題「起之前算層數」：超過上限直接拒絕，不卡死、不留行程（攤平前第 17 層會整串卡死） |

**pi 在裡面會怎樣：** 資源上限和遮檔案疊 100 層，沙箱 0.2 秒就起好，pi 開檔、fork 跟 1 層時一樣；以前疊到 33 層就起不來。網路和腦照舊每層一份程式，所以疊多了照樣吃記憶體；網路收掉仍然一層 3 秒。寫得太深或兩個腦沒串起來，mini 在起任何東西之前就拒絕。

另外兩個 bug 的修法與實測（撞牆乾淨失敗、網路疊三層總量對）記在 [README](README.md) 第六段；網路疊三層總量修好後實測 pi 拿到約 23.6 MB（內層上限 25 MB），三層都 0 丟包。
