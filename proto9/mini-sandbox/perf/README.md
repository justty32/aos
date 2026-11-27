perf/ 是 mini-sandbox 與 pi-sandbox 的效能量測腳本：一個入口 `bench.py`，選要量哪幾項，印一行一筆的 JSON（附機器、Linux 版本、commit、時間）和一張人看的表；量出來的數字整理在 [../PERF.md](../PERF.md)。

# perf：量效能的腳本（11-27）

← [mini-sandbox](../README.md)｜數字與解讀：[PERF.md](../PERF.md)

從 11-27 兩份調查的 scratch 腳本（家機 `~/.aos/scratch/kernel-scale-1127/`、`~/.aos/scratch/kernel-files-1127/`）整理來的，不再依賴 scratch 的路徑。只用 Python 標準庫，另有一支小 C 程式 `lat.c`（有 `cc` 就當場編進暫存夾；沒有就改用 Python 計時，紀錄裡 `"timer": "python"`）。不用 root。我自己定的標【擬】：子命令名、欄位名、暫存夾 `/tmp/aos-perf-*`、scope 名 `aos-perf-cg-<PID>.scope` 與 `mini-perf-<PID>.scope` 都是【擬】。

## 怎麼跑

```
cd proto9/mini-sandbox/perf
python3 bench.py --quick                              # 小量版，家機約 6 秒（mini 只疊 cg、mask 各 1、5 層）
python3 bench.py                                      # 完整版（不含 mountmax、fusehang）
python3 bench.py all                                  # 全部
python3 bench.py fs overlay                           # 只量這幾項
python3 bench.py mini --kinds cg,mask,llm --layers 1,5,10
python3 bench.py --out ~/perf.jsonl pisandbox         # JSON 一行一筆接在檔尾，表印到 stdout
python3 bench.py --dir ~/tmp fs                       # 暫存夾放在別的檔案系統（磁碟 vs tmpfs，bind 的速度不一樣）
```

- 沒給 `--out`：JSON 印到 stdout，表印到 stderr；給了 `--out`：JSON 接在那個檔尾，表印到 stdout。
- 每一筆都有 `time`（UTC）、`load1`（量的時候的負載，別人同時在跑東西時數字會飄）、`bench`、`case`、`n`、`quick`、`host`（`cpu`、`cpus`、`kernel`、`os`、`wsl`、`commit`（工作樹有改動就加 `+dirty`）、`python`）。不記主機名與使用者名。
- 某一項失敗不會停掉其他項，那一筆會有 `error`。
- 跑完把暫存夾刪掉（`--keep` 留著）。它起的行程、掛載、scope 都在結束前收掉；只 kill 自己記下的 PID（rofiles-fuse 會自己變背景程式，用「在自己那個 mount namespace 裡、名字是 rofiles-fuse」找出 PID）。

## 子命令

| 名字 | 量什麼 | 怎麼量 | 對到 scratch 的哪支 | `--quick`／完整 |
|---|---|---|---|---|
| `fs` | 靜態蓋法 bind、tmpfs、`/dev/null`、唯讀、bind＋唯讀掛 N 條：掛的時間、每條、讀掛載表、開檔（沒掛的、跨過 bind 的、被換掉的深檔）、stat、找不存在的檔、之後再開一層 `unshare -Urm true` | 每組一個新的 `unshare -Urm`；`lat.c` 量 | `bench_bind.py`、`run_bind.py`、`setup.sh` | N＝0、100、1000／0、10、100、1000、5000 |
| `overlay` | overlayfs 疊 K 層唯讀：掛的時間、每個檔第一次開、重複開、找不存在 | `unshare -Urm`，舊的 mount API、相對路徑 | `bench_ov.py` | K＝0、1、5、20／再加 2、100、500、501（501 應該 `EINVAL`） |
| `mountmax` | 一直 bind 到 `mount-max` 拒絕：幾條、錯誤原文、每條多久、那時開檔與讀掛載表、`umount -l` 全卸 | `unshare -Urm`，掛載點在一塊 tmpfs 裡 | `wall.py`、`mounts.py` 的撞牆那段 | 預設不跑，點名或 `all` 才跑（約 1 秒、吃約 50 MB） |
| `flat` | 一層一層（每層一支精簡 python＋新的 user+mount ns＋一條 tmpfs）vs 攤平（一支 python 一次掛 N 條）；最後都多開 pi 那一層，試 pi 拆不拆得掉 | `layer.py` | `layer.py`、`flat.py` | 一層一層 1、10／再加 30；攤平 10、1000 |
| `fuse` | 開檔、stat：一般檔、bind、Python FUSE（快取 0、1 秒）、rofiles-fuse（C，有裝才量）；內容改了看不看得到；Python 服務的記憶體 | `unshare -Urm`，`pyfuse.py` 自己 `mount(2)`，不用 fusermount3 | `bench_fuse.py`、`pyfuse.py` | 2000／5000 次 |
| `fusehang` | FUSE 服務卡住時，讀的人 SIGTERM、SIGKILL 殺不殺得掉、別人 stat 會不會卡、服務死後怎樣 | `unshare -Urm` | `hang.py` | 預設不跑，點名或 `all` 才跑（約 8 秒） |
| `sock` | unix socket 一問一答（服務每次重讀一個小檔） | 兩端都 Python | `sockrtt.py` | 5000／20000 次 |
| `userns` | user、PID namespace 能疊幾層，撞牆的錯誤原文；另印 `max_user_namespaces`、`mount-max`、這裡的 `cgroup.max.depth`、能用的控制器 | 一層層 `unshare`＋寫 id 對照，丟掉的子行程 | `userns_depth.py` | 一樣 |
| `cgdepth` | cgroup 疊 N 層、每層開 cpu／memory／pids 並設上限：建每層、fork、碰記憶體、scope 與整台的核心記憶體 | `systemd-run --user --scope -p Delegate=yes` 裡，不開 namespace | `cgdepth.py` | N＝1、100／1、100、1000 |
| `mini` | `mini.py --kernels` 疊 N 層某種 kernel：起到最裡層、scope 記憶體、常駐行程、RSS、cgroup 深度、pi 位置的 stat／開檔／列目錄／fork／執行／碰記憶體（`inner.py`）、問腦（llm）、小檔與上下傳（net）、收掉要多久 | kernel 設定當場生在暫存夾、`MINI_KERNELS_PATH` 指過去；預設 `--no-auto-mask`（`--auto-mask` 打開） | `run.py`、`bench.py`、`gen_kernels.py`、`srv.py`；net 那段 scratch 是另外內嵌的，這裡補進來了 | `--kinds`（cg、mask、mix、llm、net，預設 cg,mask）`--layers`（預設 1,5／1,5,10） |
| `pisandbox` | pi-sandbox（aos-daemon）那條路：起 daemon、起 llm kernel、起一隻 proc（最小天空與 pi 的整片天空）、經 1、2 隻 llm kernel 與 `/llm/relay` 問一次、收掉 daemon、整套到 pi 第一個請求 | 用 `proto9/pi-sandbox` 的 `aos_pi.Sandbox`、`daemon_ctl`，一律 `--fake`，不碰 mini | （scratch 沒有，這次新寫的） | proc 5／20 次、請求 30／200 次、整套 1／3 次 |

## 要有什麼

- 都要：Linux、Python 3（家機 3.14）、util-linux 的 `unshare`、沒被關掉的 user namespace。
- `cgdepth`、`mini`：systemd --user（`systemd-run --user --scope`）。`mini` 另要 mini 本身要的東西（見 [README](../README.md)），net 要 pasta、nft、tc。
- `fuse`、`fusehang`：`/dev/fuse`；rofiles-fuse 沒有就少那兩行。
- `pisandbox`：`proto9/cpp/aos-daemon/build/bin/aos-daemon`（沒有就那一筆寫 error，自己先 `make`）、fnm 的 node 與 pi 套件（找法跟 `aos_pi.py` 一樣；沒有就整套那筆寫 error）。
- `lat.c`：有 `cc`／`gcc`／`clang` 就用，沒有就 Python 計時（數字會大約 1 µs，只能看相對）。
- 公司 WSL：照理都能跑（Linux 6.6、有 systemd --user），**還沒試**。

## 注意

- `mini` 會開很多 namespace、scope 與（net）pasta；別人在跑 mini 的測試時，先只用小量（例 `--kinds cg,mask --layers 1,5`）。net 一層一層真開到 17 層、其他到 33 層會撞牆卡住（[PERF](../PERF.md)「已知的毛病」）；腳本在等不到最裡層時會用 `cgroup.kill` 收掉**自己那個** scope（`mini-perf-<PID>.scope`），每次最多等 300 秒。
- 量的時候別人在跑東西，數字會飄；看 `load1`。
- `fs` 的速度跟暫存夾在哪個檔案系統有關（`tree_fs` 欄）：家機 `/tmp` 是 tmpfs，F 那份報告的測試樹在 ext4 上。
- 會在 repo 留下 `__pycache__` 的寫法都關掉了（`-B`、`PYTHONDONTWRITEBYTECODE`）。

## 沒搬的

- `mounts.py` 的「同一個 user ns 裡一層層開 300 層 mount ns」：`fs` 的「之後再開一層 `unshare -Urm true`」量的是同一件事的一層，沒搬整段。
- `copysim.py`（宣告夾每層整份抄）：它直接 import mini 的 `nest`，七題實作會改這塊，等改完再看要不要搬。
- `flatprobe.py`（cg 10 層 vs 攤平 1 層的 cpu／pids／mem 實際限制）、`order.py`、`lockcheck.py`：量的是「對不對」不是「快不快」，留在 scratch。
- `explain.py`：effective＋blame 的示意，七題實作會做真的。
- 網路模組（N 那份報告的 `systemd-run`＋`pasta`＋nft＋tc 手下指令）：沒寫成腳本，`mini --kinds net` 量的是 mini 的 net kernel。

## 檔案

| 檔 | 是什麼 |
|---|---|
| `bench.py` | 入口：選子命令、暫存夾、JSON 與表 |
| `common.py` | 共用：機器資訊、紀錄、計時、`mount(2)`、`lat.c` 的包裝 |
| `lat.c` | C 寫的開檔／stat 延遲（中位數、p90、p99） |
| `fsbench.py` | `fs`、`overlay`、`mountmax`、`flat` |
| `layer.py` | `flat` 用的一層（精簡 python，像一支小 kernel） |
| `dynbench.py` | `fuse`、`fusehang`、`sock` |
| `pyfuse.py` | 純 Python 的最小 FUSE 服務 |
| `nsbench.py` | `userns`（含 `limits`）、`cgdepth` |
| `minibench.py` | `mini` |
| `inner.py` | 在 pi 的位置跑的那支（被抄進暫存夾） |
| `pisandbox.py` | `pisandbox` |
