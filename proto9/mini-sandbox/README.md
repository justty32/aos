最小的沙箱原型（11-27 家機）：底層就是一行 `systemd-run --user --scope`（CPU、記憶體、行程數上限）加 `unshare -UrmpnC`（自己的 user／mount／PID／網路／cgroup namespace），上面可選疊一隻網路 kernel（兩層 netns：pasta 接外網、nft 白名單與總量、tc 頻寬）與切 uid 的選項；檔案、IPC、`/run/user` 等其他全部漏給 Linux。驗收兩次全過、pi `--fake` 經網路 kernel 跑通四個工具。

# mini-sandbox（11-27，家機 Manjaro 6.18）

← [proto9](../README.md)｜使用者定的：[pi沙箱-1127](../../proto8/thinking/2026-11/27/pi沙箱-1127.md) 定了的第 10 條｜依據（不進 git，家機）：`~/.aos/scratch/proto9-smallproto-1127/net-report.md`（最小底層與網路模組調查）、`uid-report.md`（切 uid 調查）、給使用者看的 `report.html`｜旁邊那一版：[pi-sandbox](../pi-sandbox/README.md)（從零組天空、seccomp、`/llm`，跟這版並存、不被取代）

我自己定的標【擬】。

## 結論先講

- **pi 在裡面會怎樣**：它是 uid 0（對到外面的你本人），看得到、寫得到你所有的檔；`ps` 只看得到自己那幾隻；CPU、記憶體、行程數有上限，而且它**改不掉**這些上限；沒裝網路 kernel 時只有 `lo`，什麼都連不到；裝了就只連得到白名單上的 ip:port，速度與總量有上限，規則它拆不掉，它還能自己再開一層沙箱。
- **但它一行就能整個跳出去**：`/run/user/1000` 沒蓋（使用者選的，見「漏掉的」第 3 條）。這次實測：`systemd-run --user` 這支指令在沙箱裡反而失敗，可是同一個請求直接經 D-Bus（`busctl --user call … StartTransientUnit`）送出去就成功，起出來的行程在你本人的網路、不在沙箱的 cgroup 裡（沒有 CPU／記憶體上限）。
- **驗收跑兩次都全過**：`SUMMARY ok (31 PASS, 0 FAIL, 4 info, 41s)`，兩次一模一樣；pi `--fake` 經網路 kernel 跑完 read、write、edit、bash 四個工具；跑前跑後沒留下行程、scope、netns、測試伺服器。
- **pasta 家機沒裝**：從官方原始碼 tag `2026_10_02.cba3570` 編在 `~/.aos/scratch/proto9-mini-1127/passt/`（不進 repo）。正式用要裝套件：Arch／Manjaro `pacman -S passt`、Ubuntu `apt install passt`。
- **新發現（調查報告沒寫的）**：上傳整形不能讓 tbf 丟封包，丟一個就重送三成、慢到五分之一，所以上傳的佇列開深（1 秒）；沙箱結束後它的 netns 可能還被沒關完的連線拖著，veth 要由網路 kernel 主動拆。細節在下面「網路 kernel」。

## 三層長什麼樣

```
你（外面，uid 1000，本來的網路）
│
├─ 網路 kernel（可選，net_kernel.py，一直開著）
│    外層 A：自己的 user ns（0→你，1..65536→你的 subuid）＋自己的 netns
│      ├─ pasta 接到 A，在 A 裡開出 aosnet0（接外網；本機的服務預設連不到）
│      ├─ nft：白名單、總量、計數；tc：上傳整形在 aosnet0、下載整形在每條 vpN
│      └─ vp0 ══veth══╗
│                     ║
└─ mini.py 起的那一行   ║
     systemd-run --user --scope（cpu、mem、pids 上限）
       [nsenter --user=<A>]   ← 有網路 kernel 時才有：沙箱生在 A 的 user ns 底下
         unshare -UrmpnC --fork --mount-proc
           裡層 B：自己的 user／mount／pid／net／cgroup ns
             eth0 ═══════════╝（網路 kernel 拉進來的）
             mini.py --inside（只做：等網路接好、把 lo 開起來）
               [setpriv --reuid=N …]   ← uid N≥1 時才有
                 env -i …  你的指令（pi）
```

用使用者 11-27 的說法：「後一層就是運行在前一層給出的環境裡，環境套環境」——網路 kernel 是外面那層，沙箱生在它的 user namespace 裡，所以碰不到它的規則；不裝網路 kernel，就是 `unshare -n` 的空網路（只有 `lo`）。

### 誰起誰、veth 誰拉

1. 你先起網路 kernel：`net_kernel.py` 用 `unshare --user --net` 開外層 A（有 subuid 就順便把 1..65536 對到你的 subuid，切 uid 才用得到），在 A 裡跑一隻小 holder（root，管 `ip`、`nft`、`tc`）；再起 `pasta … <holder 的 PID>` 接進 A。規則載好後在它的夾裡開 `ctl`（unix socket）、寫宣告與狀態檔。
2. `mini.py` 看設定的 `net` 指到哪個夾，讀那個夾的 `.aos/interfaces/aos/net/kind`（要是 `veth`）與 `ctl`，問 `info` 拿到 A 的 PID。
3. `mini.py` 在自己的暫存夾（`$XDG_RUNTIME_DIR/aos-mini-*`，跑完刪）開一個只收一次的 `gate.sock`，然後跑那一行：`systemd-run … nsenter --user=/proc/<A>/ns/user --preserve-credentials unshare -UrmpnC … mini.py --inside --gate gate.sock -- …`。
4. 沙箱裡第一支程式（`mini.py --inside`）連 `gate.sock` 說「好了」；外面的 `mini.py` 從連線的對方憑證拿到它在外面的 PID，叫網路 kernel `attach`。
5. 網路 kernel 的 holder：`ip link add vpN type veth peer name eth0 netns /proc/<PID>/ns/net`，兩頭配位址（`10.77.N.1/30`、`.2/30`）、開 `lo`、設預設路由、在 vpN 掛下載整形。回「好」。
6. `mini.py --inside` 收到「好」才 `exec` 你的指令。它結束＝PID namespace 結束＝那條 veth 由網路 kernel 拆掉。

`ctl` 只收「不在任何沙箱裡」的呼叫者（對方的 user namespace 要跟網路 kernel 外面那隻一樣）：pi 從裡面連得到這個檔（檔案沒遮），但它的請求會被拒（驗收 `ctl_refused_inside`）。

## 怎麼跑

```
cd proto9/mini-sandbox
python3 mini.py cfg.json                    # 照設定跑；退出碼照傳（被訊號殺＝128+N，OOM＝137）
python3 mini.py cfg.json -- sh -c 'id'      # 換掉設定裡的 argv
python3 mini.py cfg.json --dry-run          # 只印組出來的那一行
python3 mini.py cfg.json --print            # 先把那一行印到 stderr 再跑
python3 mini.py --give-back ~/some/dir      # uid N 寫的檔還給你（見「切 uid」）

python3 net_kernel.py --dir ~/net1 --config net.json [--pasta PATH]   # 起網路 kernel（前景跑，Ctrl-C 收）
python3 net_kernel.py --dir ~/net1 --config net.json --dry-run        # 只印 holder、pasta、tc 指令與 nft 規則

python3 accept.py                           # 驗收（約 40 秒；--no-pi 不跑 pi，--pasta PATH，--keep 留下暫存夾）
```

`--dry-run` 的樣子（沒網路、uid 0）：

```
systemd-run --user --scope --quiet --collect --unit mini-t-2114095.scope -p CPUQuota=20% -p MemoryMax=100M -p MemorySwapMax=0 -p TasksMax=30 unshare -UrmpnC --fork --kill-child --mount-proc /usr/bin/python3 -I …/mini.py --inside -- env -i HOME=/home/lorkhan LANG=C.UTF-8 LOGNAME=lorkhan MINI_UNIT=mini-t-2114095.scope PATH=/usr/local/bin:/usr/bin:/bin TERM=tmux-256color USER=lorkhan sh -c 'id; …'
```

有網路 kernel 時多 `nsenter --user=/proc/<A>/ns/user --preserve-credentials`，`--inside` 後面多 `--gate …/gate.sock`；`uid: 1` 時 `-UrmpnC` 換成 `-U --map-user=0 --map-users=1:100000:65536 --map-group=0 --map-groups=1:100000:65536 -mpnC`（有網路 kernel 時是 `1:1:65536`，因為 A 已經把 1.. 對到 subuid 了），`env -i` 前面多 `setpriv --reuid=1 --regid=1 --clear-groups --inh-caps=-all --bounding-set=-all --no-new-privs`。

跟調查報告那一行比多了三樣【擬】：`--kill-child`（`unshare` 死了就把裡面的 1 號也殺掉）、`--collect`＋`--unit mini-<名>-<PID>.scope`（scope 有固定的名字、結束一定收掉）、`mini.py --inside` 這一小段（等網路、開 `lo`）。

### 收掉

`mini.py` 收到 SIGTERM／SIGINT／SIGHUP 時：先 `systemctl --user kill` 把同一個訊號送給整個 scope，5 秒後還在就殺 `unshare`（`--kill-child` 再把沙箱的 1 號 SIGKILL，整個 PID namespace 跟著結束）。原因：`unshare --fork` 等孩子時把 SIGTERM／SIGINT 擋著；沙箱的 1 號對沒裝處理函式的訊號（例如 `sleep` 收 SIGTERM）不理。`mini.py` 自己被 SIGKILL 的話，沙箱照跑到結束。

## 設定欄位（`mini.py` 的 json）

| 欄位 | 預設 | 意思 |
|---|---|---|
| `argv` | 必填 | 要跑的指令（字串陣列）；命令列 `-- …` 可蓋掉 |
| `name` | `mini` | 只用在 scope 名字 `mini-<name>-<PID>.scope`；英數、`-`、`_` |
| `cwd` | 叫 `mini.py` 時的目錄 | 指令從哪裡開始跑 |
| `env` | `PATH`、`LANG=C.UTF-8`，外加你的 `HOME`、`USER`、`LOGNAME`、`TERM`【擬】 | 裡面看到的環境變數全部就這些（`env -i`），另外一定多一個 `MINI_UNIT`＝自己的 scope 名【擬】（cgroup namespace 把路徑藏起來了，要查自己的上限時用） |
| `cpu` | 不限 | `"20%"`（一顆核的 20%）、`"150%"`；寫數字會補 `%` |
| `mem` | 不限 | `"100M"`、`"2G"`；有寫就一起設 `MemorySwapMax=0`（不然超過時先吃 swap、不會馬上被砍） |
| `pids` | 不限 | 整個沙箱同時最多幾隻行程／執行緒（`TasksMax`） |
| `net` | `"none"` | `"none"`＝只有 `lo`；或一個網路 kernel 的夾（裡面有 `.aos/interfaces/aos/net/`） |
| `uid` | `0` | `0`＝你本人；`N≥1`＝外面看是你的 subuid 起點＋N−1（家機 `100000`） |

## 網路 kernel（`net_kernel.py`）

### 設定（json）

| 欄位 | 預設 | 意思 |
|---|---|---|
| `allow` | `[]` | 白名單，一筆 `{"to": "1.1.1.1" 或 "10.0.0.0/8", "port": 443 或 "8000-8100", "proto": "tcp"｜"udp"}`；只收 IPv4 |
| `host_ports` | `[]` | 放行本機（外面 `127.0.0.1`）的哪幾個 port，例 `[4000]`（LiteLLM）；pi 用 `host_addr:port` 連 |
| `host_addr` | `169.254.77.1`【擬】 | pi 那邊用來指「本機」的位址（交給 pasta 的 `--map-host-loopback`） |
| `down`／`up` | 不限 | 下載／上傳頻寬，`"16mbit"`（＝2 MB/s）、`"8mbit"`；單位 bit／kbit／mbit／gbit |
| `quota` | 不限 | 總量（上下行加起來，含封包表頭），位元組或 `"12mb"`（1000 進位） |
| `max_attach` | `1`【擬】 | 同時能接幾個沙箱；頻寬每條各算、總量大家共用 |
| `subnet` | `10.77.0.0/16`【擬】 | veth 兩頭的位址從這裡切，每個沙箱一段 `/30` |
| `status_interval` | `1` 秒 | 狀態檔多久更新一次 |
| `burst` | 自動 | tbf 的 burst（位元組），預設 max(64 KiB, 每秒量÷50) |

**pasta 怎麼叫**（`--dry-run` 印得出來）：`pasta --config-net -q -f -4 -m 1500 -T none -U none -t none -u none -I aosnet0 --no-map-gw <A 的 PID>`；有 `host_ports` 時 `--no-map-gw` 換成 `--map-host-loopback 169.254.77.1`。
- `-T none -U none`：pasta 預設會把「本機只聽 127.0.0.1 的 port」全部接進來（調查實測連得到 LiteLLM 4000），關掉。
- `-t none -u none`：pi 開的 port 不會被開到你主機上。
- `--no-map-gw`：pasta 預設把「連到閘道 IP」轉成連你本機，關掉；要放行本機某個 port 時，才換成一個專用位址（`--map-host-loopback`），再由 nft 只放那幾個 port。
- `-m 1500`：pasta 的介面預設 MTU 65520，tbf 的 burst 比一個封包小時整條卡死。
- `-4`：只走 IPv4【擬】；`inet` 規則表照理也管 IPv6，但沒測，乾脆不給 v6。

**nft 規則**（外層 A，表名 `inet aosnet`）：從 `vp*` 進來的新連線只有白名單（與 `host_addr` 的那幾個 port）放行，其他回 `admin-prohibited`（pi 看到「No route to host」，馬上失敗）；放行與回程的封包兩個方向都先經過同一個 `quota`，超過就丟；從 `vp*` 打 A 自己一律丟（`to_outer`）；往 `aosnet0` 出去的做 masquerade。每條白名單一個具名計數器。完整規則用 `--dry-run` 看。

**tc**：上傳在 `aosnet0`（A 往 pasta）掛 tbf、佇列 1 秒；下載在每條 `vpN`（A 往沙箱）掛 tbf、佇列 200 毫秒。
- **上傳的佇列為什麼開 1 秒（這次量到的）**：200 毫秒時上傳 2 MB 有時 2 秒、有時 5～13 秒，tbf 只丟了 1～3 個封包，卻多送了三成的位元組；開到 1 秒後連續 7 次（含一次 10 MB）都 0 丟、0.97～1.00 MB/s。推測原因：上傳那條 TCP 的另一頭是 pasta 自己（它把連線接下來再從你主機送出去），漏一個封包後面的都要重送；所以寧可排隊、不要丟。代價是上傳卡滿時延遲最多多 1 秒。
- 下載的另一頭是沙箱自己的 Linux，丟幾個封包它處理得好，200 毫秒就準（1.96 MB/s，設 2.00）。

**veth 由網路 kernel 拆**：沙箱結束後，它的 netns 有時會被還沒關完的連線拖住（例如總量用完卡著的下載），veth 一直在，下一個沙箱就因 `max_attach` 接不上（第一輪驗收撞到）。現在 holder 記住每條 vpN 接的是哪隻行程（PID＋啟動時間），那隻不在了就 `ip link del`，每秒查一次、接新沙箱前也查一次。

### 宣告與狀態檔（在 `--dir` 那個夾）

| 位置 | 內容 |
|---|---|
| `.aos/interfaces/aos/net/kind` | `veth`（給你一條 veth 進你自己的 netns，規則在另一頭） |
| `…/ctl` | `ctl`（以夾起算的 socket 路徑） |
| `…/protocol` | `json-lines`：一行 json 進、一行出；`{"op":"info"}`、`{"op":"attach","pid":N}` |
| `…/allow` | 一行一條：`tcp 1.1.1.1/32 443` |
| `…/host_addr`、`…/host_ports` | `169.254.77.1`；一行一個 `tcp 4000`（沒放行時兩個都是空檔） |
| `…/down`、`…/up`、`…/quota` | `16mbit`、`8mbit`、`12000000`（不限＝空檔） |
| `…/max_attach`、`…/ipv6`、`…/dns`、`…/status` | `1`；`no`；`only if allowed above (by ip and port 53)`；`status` |
| `.aos/interfaces/aos/description` | 一行英文：這隻 kernel 是什麼 |
| `status`（資訊，不是宣告） | `state`、`updated`、`attached`、`quota_bytes`／`quota_used`／`quota_left`、`up`／`down`／`denied`／`to_outer` 的封包數與位元組、每條白名單 `allow.N: tcp 1.1.1.1/32 443 new_connections 3 bytes 180`、`host.N: …`；每秒從 `nft -j list table inet aosnet` 讀出來重寫，收掉時寫 `state: stopped` |

宣告「每個參數一個小檔」照 [pi-sandbox](../pi-sandbox/README.md) 的 `llm_kernel.py` 寫 `aos/llm` 的風格；欄位名與內容都是【擬】。

**DNS**：只放 IP 白名單時，查網域也被擋（沒放 53）。pi 讀的是你主機的 `/etc/resolv.conf`（檔案沒遮），家機寫 `192.168.1.1`，要查網域就把 `{"to":"192.168.1.1","port":53,"proto":"udp"}` 加進白名單；DNS 本身也能拿來偷偷送資料出去（調查報告第 2 節）。

## 切 uid（選項，預設關）

`uid: N`（N≥1）時，沙箱的 user namespace 多對一段 subuid（`newuidmap`，不用 root），`setpriv` 換成 N、清掉附加群組（不清的話你的 wheel 等群組只是顯示成 nobody，權限照算）、丟掉所有 capability、設 `no_new_privs`。外面看是 `100000+N−1`。有網路 kernel 時，外層 A 已經把 1..65536 對到你的 subuid，沙箱在 A 裡面再對一次 `1:1:65536`（A 裡面叫 `newuidmap` 實測可以）。

pi 在裡面會怎樣：你的家目錄是 700，它整個進不去（連 `mini.py`、`probe.py` 都碰不到，所以驗收用 `/usr` 底下的 `sh`、`curl`）；600 的檔讀不到；所有人都能讀的檔照讀；殺不了、調不了你的行程；`/run/user/1000` 也進不去（uid-report 2.1），所以「漏掉的」第 3 條在 uid N 時是關著的（這次沒在 mini 裡量）。

要讓它在某個夾工作，三個配套（uid-report 2.2、2.3，都不用 root）：

1. **工作夾先 setfacl**，pi 和你兩條都加進預設 ACL：`setfacl -R -m u:100000:rwx,d:u:100000:rwx,d:u:1000:rwx <夾>`，路上每一層夾也要讓 100000 能進（`setfacl -m u:100000:x ~ …`；你的家目錄是 700，這等於開一個口，自己判斷）。
2. **收尾把檔還給你**：pi 用 0644 建的檔你改不動（ACL 的 mask），跑 `python3 mini.py --give-back <夾>`（＝`unshare --user --map-user=0 --map-users=1:100000:65536 … -- chown -R 0:0 <夾>`）。
3. **git 的 safe.directory**：兩邊都會報 dubious ownership；pi 那邊在 `env` 加 `GIT_CONFIG_COUNT=1`、`GIT_CONFIG_KEY_0=safe.directory`、`GIT_CONFIG_VALUE_0=<夾在裡面的路徑>`。

## 驗收（`accept.py`、`probe.py`）

`accept.py` 在外面起兩個測試伺服器（`127.0.0.1` 上隨機 port，一個會被放行、一個永遠不放行）、三隻網路 kernel（K1 白名單＋頻寬＋總量；K2 不放行本機；K3 給 pi），每一項起一個 mini 沙箱跑 `probe.py` 的一個小指令（或 curl、sh），印 `名字 PASS|FAIL|info 說明`。外網的兩項先在外面試 `https://1.1.1.1/`，外面不通就記 info 跳過，本機測試伺服器那幾項照跑（沒外網時的備案）。

| 項目 | 怎麼量 | 兩次的結果（11-27 家機） |
|---|---|---|
| `cpu_quota` | `cpu 20%`，忙迴圈 3 秒，CPU 時間÷牆上時間 | 0.199、0.2 |
| `mem_oom` | `mem 100M`，要 300 MB | 吃到 80 MB 被砍，退出碼 137 |
| `pids_max` | `pids 30`，一直 fork | 第 28 隻 fork 失敗（EAGAIN） |
| `cgroup_ns_C` | 寫自己 scope 的 `memory.max`、在旁邊開新 cgroup 搬過去 | `/proc/self/cgroup` 是 `0::/`；改上限 `Operation not permitted`、搬家 `No such file or directory` |
| `no_host_procs` | 數 `/proc` | 只看到自己 1 隻，看不到 accept 的 PID |
| `no_net_only_lo` | 沒網路 kernel | 介面只有 `lo`；連 1.1.1.1:443 `Network is unreachable` |
| `exit_code_passed` | `exit 7` | 7 |
| `declaration` | K1 宣告檔 | 跟設定一致 |
| `net_ifaces` | K1 | `eth0`、`lo` |
| `allowed_external_open` | `https://1.1.1.1/` | 301 |
| `denied_external_8888`、`denied_external_port80` | `https://8.8.8.8/`、`http://1.1.1.1/` | `000` |
| `allowed_host_port_open` | `169.254.77.1:<放行的 port>` | 通 |
| `host_port_not_listed`、`litellm_4000_closed` | 本機沒放行的 port、LiteLLM 4000（外面確實在聽） | `No route to host` |
| `own_lo_is_not_host` | 沙箱的 `127.0.0.1:<放行的 port>` | `Connection refused`（那是沙箱自己的 lo） |
| `gateway_not_host` | 閘道 `192.168.1.1:<放行的 port>` | `No route to host` |
| `outer_ns_closed` | 外層 A 的 `10.77.0.1:22` | 逾時（丟掉） |
| `ctl_refused_inside` | 從裡面對 `ctl` 要 `attach` | `Refused only callers outside any sandbox may use ctl` |
| `rules_out_of_reach` | 裡面 `nft flush ruleset`（成功，退出碼 0），再連沒放行的 port | 照樣 `No route to host` |
| `nested_unshare_ok` | 裡面 `unshare -Urn` | 成功，裡面那層 uid 0、只有 `lo` |
| `uid1_net`、`uid1_none` | `uid 1`（有／沒有網路 kernel） | 裡面 `id -u`＝1；讀 600 的檔 `Permission denied`；外面看 scope 裡的行程 uid 有 `100000`（另一個 `1000` 是 `unshare` 本身）；有網路時放行的 port 通 |
| `down_rate` | 下載 4 MB，設 16mbit | 1.96 MB/s、1.96 MB/s |
| `up_rate` | 上傳 2 MB，設 8mbit | 0.99、1.00 MB/s |
| `status_matches` | 狀態檔 `quota_bytes`＝宣告＝設定；used＋left＝總量；這 6 MB 讓 used 漲多少 | 12000000；漲 6227550、6248670（多出來的是表頭與 ACK） |
| `quota_cut` | 要 30 MB | 拿到 5464472、5444536 就斷（當時剩 5764052、5742970）；下一個連線逾時；`quota_left 0` |
| `default_no_host_map_gw`、`…_addr` | K2 沒放行本機，nft 白名單**故意**放行閘道與 `169.254.77.1` 的那個 port | 一個被真的路由器拒、一個逾時：pasta 不轉到本機 |
| `pi_fake` | 見下 | DONE |
| `cleanup` | 跑前跑後比：這次的行程（mini、net_kernel、pasta、probe、llm_kernel）、它們握著的 netns、`mini-*` 的 systemd 單元、`$XDG_RUNTIME_DIR/aos-mini-*`、兩個測試伺服器的 port | 什麼都沒留 |

info（漏掉的，照實量、不算失敗；兩次一樣）：

| 項目 | 量到的 |
|---|---|
| `leak_systemd_user` | 裡面 `systemd-run --user` 失敗：`Failed to connect to user scope bus via local transport: No data available`（推測：`-C` 之後 `/proc/self/cgroup` 只剩 `/`，systemd 的指令判斷不出你是哪個使用者；沒查證）。**但 D-Bus 是通的**（`busctl --user list` 有 195 行），改用 `busctl --user call org.freedesktop.systemd1 … StartTransientUnit` 送同一個請求就成功：起出來的服務 netns 是你主機的 `net:[4026531833]`（沙箱的是另一個）、cgroup 在 `app.slice/mini-leak-*.service`（不在 mini 的 scope 底下，沒有 CPU／記憶體／行程數上限）。這次是在**有網路 kernel** 的沙箱裡做的，所以白名單、頻寬、總量也一起被繞過。驗收跑完把它 `systemctl --user stop` 掉 |
| `leak_ssh` | `~/.ssh` 列得出 4 筆、`id_ed25519` 讀得到（只讀 64 位元組，不印內容） |
| `leak_ipc_shared` | 裡面的 IPC namespace 跟外面同一個 `ipc:[4026531839]` |
| `leak_run_user` | `/run/user/1000` 看得到 25 筆，`systemd/private` 在 |

### pi `--fake`

照 [pi-sandbox](../pi-sandbox/README.md) 的做法：外面起 `llm_kernel.py --fake`（劇本腦，不叫模型），因為 pi 只會講「HTTP 到某個網址」，`accept.py` 在外面 `127.0.0.1:<port>` 開一個小轉接接到腦的 unix socket；K3 只放行這一個 port（`host_ports`），pi 的 `models.json` 的 `baseUrl` 寫 `http://169.254.77.1:<port>/v1`。pi 在 mini 沙箱裡（`mem 2G`、`pids 512`、`HOME` 指到暫存夾、`cwd` 是小專案），用你本機 fnm 的 node 與 pi 套件（檔案沒遮，直接用）。

結果兩次都是：`DONE`、`stopReason stop`、工具 read、write、edit、bash 都成功、`hello.txt` 是 `pinecone`、`config.ini` 改成 `level = high`、pi 的 5 輪＝腦的帳本 5 行、K3 的 `host.0` 記到 1 個新連線。

坑：pi 的 stdin 是一條不會關的管子時，它會一直等（把 stdin 當成多的提示），第一次跑卡到逾時；`accept.py` 給它 `/dev/null`。

## 漏掉的（使用者 11-27：「3.甲，剩下都按照推薦。反正就給他漏」）

照 net-report 第 1 節「漏掉之後 pi 做得到什麼」，這版全部照漏：

1. **讀你所有的檔**：`~/.ssh` 私鑰（這次實測讀得到）、各種 token、瀏覽器資料、LiteLLM 設定裡的金鑰。
2. **寫和刪你所有的檔**：改 repo（包括 `.git`、`AGENTS.md`、git hooks）、`~/.bashrc`；在 `~/.config/systemd/user/` 放一個服務，你下次登入它就在沙箱外面跑。
3. **整個跳出去：`/run/user/1000` 這個口**。pi 在裡面摸得到 systemd --user 與 D-Bus，叫 systemd 替它起一隻新行程，那隻就在沙箱外面：**你本人的網路（網路 kernel 的白名單、頻寬、總量全部不算數）、不在 mini 的 cgroup 裡（CPU、記憶體、行程數上限全部不算數）**——前兩層的限制都被繞過。這次實測：`systemd-run --user` 那支指令在沙箱裡會失敗，但直接經 D-Bus（`busctl`）送同一個請求就成功，所以「指令失敗」不代表口是關的。它也能從外面那隻 `nsenter` 進網路 kernel 的外層、把規則清掉（理論上，沒試）。**這是使用者知情後選的，原話「3.甲，剩下都按照推薦。反正就給他漏」，不再勸。**（之後使用者補了「3.這個，就做成一個kernel吧」：把蓋 `/run/user/<uid>` 做成可裝可不裝的檔案遮蔽 kernel、預設裝不裝還沒定——見 pi沙箱-1127 第 10 條；**這版沒做**。）
4. **D-Bus session bus**：能叫桌面上的程式；你的密碼庫如果開著，可能拿得到密碼（沒試）。
5. **其他用檔案路徑連的 socket**：X11、Wayland（看畫面、送按鍵）、PipeWire（麥克風）、`$SSH_AUTH_SOCK`（叫你的 ssh-agent 幫它簽）、docker.sock（若你在 docker 群組）；網路 kernel 的 `ctl` 也連得到，但請求會被拒。只有 abstract socket 因為自己有 netns 連不到外面。
6. **IPC 跟外面相通**（這次實測同一個 namespace）：SysV 共享記憶體、號誌、訊息佇列、POSIX mqueue、`/dev/shm`。
7. **vsock**：沒有 seccomp 擋，WSL2 上就是連到 Windows 那一邊，netns 管不到（這次沒量）。
8. **所有系統呼叫都能用**：io_uring、keyctl、userfaultfd 等；Linux 核心本身的洞能打到的面變大。
9. **看行程**：有 PID namespace，看不到也殺不到你其他行程（這次實測只看到自己）——這條擋住了。
10. **腦（LLM）**：沒有 `/llm`，pi 只能經網路打 LiteLLM；它讀得到金鑰，網路 kernel 只能限位元組總量，限不了次數或金額。
11. **擋得住的**：裡面的 sudo 這類 setuid 程式沒作用；pi 自己調不高上限（要有 `-C`，這次實測）；網路 kernel 的規則從裡面拆不掉（這次實測）。

這次多看到的：

12. **磁碟讀寫速度、磁碟空間**：使用者帳號的 cgroup 只拿得到 cpu、memory、pids，這兩樣管不了。
13. **網路 kernel 的 `ctl` 連得到**：檔案沒遮，pi 連得上這個 socket，但 `info`、`attach` 都會被拒（它不在外面的 user namespace）；只要第 3 條那個口開著，它從外面起的那隻就不會被拒，能 `attach`、甚至進外層 A。
14. **`mini.py` 被 SIGKILL 時沙箱照跑**：`unshare` 與裡面的程式不在 `mini.py` 底下收。

## 四題的決定（使用者 11-27 下午，經 main 轉述；全文在 pi沙箱-1127 第 10 條）

1. **甲**：底層＝`systemd-run --user --scope -p CPUQuota= -p MemoryMax= -p MemorySwapMax=0 -p TasksMax= unshare -UrmpnC --fork --mount-proc <指令>`，一定要 `-C`。→ `mini.py`。
2. **甲**：網路模組＝兩層 netns，外層 pasta 接外網、nft 與 tc 設在外層，pi 在裡層，veth 接起來；做成可選的 kernel，不裝就沒網路。→ `net_kernel.py`。
3. **甲**：`/run/user/1000` 不蓋，全部漏掉（見上面第 3 條；後來補的「做成 kernel」這版沒做）。
4. **甲**：切 uid 做成選項、預設關。→ `uid`。

## 我擬的（【擬】）

- 夾名 `mini-sandbox`、檔名 `mini.py`／`net_kernel.py`／`probe.py`／`accept.py`；`mini.py --inside`、`--give-back`、`--print`。
- 那一行多的 `--kill-child`、`--collect`、`--unit mini-<名>-<PID>.scope`、`mini.py --inside`；`env` 的預設、多給 `MINI_UNIT`；收訊號時「整個 scope 送一次、5 秒後殺 `unshare`」。
- 網路 kernel 的設定欄位與預設（`host_addr 169.254.77.1`、`subnet 10.77.0.0/16`、每個沙箱一段 `/30`、`max_attach 1`、`status_interval 1`、burst 的算法）；只做 IPv4（pasta `-4`）；tap 名 `aosnet0`、veth 名 `vpN`／`eth0`；上傳佇列 1 秒、下載 200 毫秒。
- 總量算上下行加總、含表頭；用完是丟封包（連線卡住、新連線逾時），不是回拒絕。
- 宣告 `aos/net` 的欄位名與內容（`kind veth`、`protocol json-lines` 等）、狀態檔的格式；`ctl` 只收不在沙箱裡的呼叫者；`gate.sock` 放在 `$XDG_RUNTIME_DIR/aos-mini-*`。
- 驗收的門檻：CPU 比 0.15～0.25；頻寬設定值的 ±25%；6 MB 的流量讓 quota 漲 6.0～6.6 MB；用完時拿到的量跟剩下的差 10%＋100 KB 以內。

## 跟任務書不一樣的地方

- **`systemd-run --user` 那條漏洞換了一個量法**：任務書寫「`systemd-run --user` 從裡面起的行程跑出沙箱」；實測這支指令在 `-C` 的沙箱裡失敗，同一個請求改走 `busctl` 才成功。驗收兩種都試、兩種結果都印。
- 那一行多了 `--kill-child`、`--collect`、`--unit` 與一小段 `mini.py --inside`（理由見上）；有網路 kernel 時前面多 `nsenter --user=<A>`。
- 上傳整形的 tbf 佇列是 1 秒，不是調查報告的 200 毫秒（理由見上）。

## 沒驗的

- **公司 WSL（Linux 6.6、Ubuntu）全部沒跑**：那台有沒有 pasta（要 `sudo apt install passt`）、nft 與 tc 的模組在 user namespace 裡能不能自動載入、`newuidmap` 在 A 裡面行不行，都不知道；WSL2 上 vsock 直接通 Windows（第 7 條）。
- **IPv6**：pasta 用 `-4`，A 與 B 都沒有 v6 位址（B 的 eth0 只有 `fe80::` 本地位址）；`inet` 表照理也管 v6，沒測。
- 第 3 條從外面那隻 `nsenter` 進網路 kernel 外層清規則：理論上做得到，沒試。
- 密碼庫經 D-Bus 拿不拿得到密碼、X11／Wayland／PipeWire／ssh-agent：沒試。
- `max_attach` 大於 1（好幾隻沙箱共用一隻網路 kernel、共用總量）：沒測。
- UDP 白名單、port 範圍、CIDR：程式會轉成 nft，沒有專門的驗收項。
- 長時間上傳（10 MB 以上）只手動試過一次（10 MB、0.97 MB/s、0 丟）。
- 真的模型：沒叫（任務書不要）。pi 經網路 kernel 直接打 LiteLLM 4000（`host_ports: [4000]`）照理就通，沒試。
- 使用者後來補的：`/run/user` 檔案遮蔽 kernel、`--kernels` 依名字疊 kernel、「試層疊」（同一種 kernel 疊兩層、換順序）——這版都沒做。網路 kernel 跟沙箱的關係已經是「環境套環境」（沙箱生在網路 kernel 的 user namespace 裡），但「網路 kernel 疊網路 kernel」沒試。

## 暫存與清理

- pasta 編在 `~/.aos/scratch/proto9-mini-1127/passt/`（官方 `git clone https://passt.top/passt`、`git checkout 2026_10_02.cba3570`、`make`；GPL-2.0+，只當另外的程式呼叫，沒抄進 repo）。`accept.py` 沒給 `--pasta` 又在 PATH 上找不到時用這一份。
- 驗收的暫存在 `~/.aos/scratch/proto9-mini-1127/accept/`，全過就刪（`--keep` 留著）。
- 用到 nft、tc、veth 時 Linux 會自動載入幾個核心模組（`nft_quota`、`sch_tbf`、`veth` 等），卸掉要 root，重開機就沒了，沒有害處。

## 檔案

| 檔 | 是什麼 |
|---|---|
| `mini.py` | 讀設定、組那一行、跑、退出碼照傳；`--inside`（沙箱裡第一支）、`--give-back`（uid N 的檔還給你） |
| `net_kernel.py` | 網路 kernel：外層 netns＋pasta＋nft＋tc、`ctl`、宣告、狀態檔；`--holder` 是它在外層裡的那一半 |
| `probe.py` | 驗收在沙箱裡跑的小指令（cpu、mem、pids、cgroup、procs、tcp、get、put、curl、ns、leaks、ctl、read） |
| `accept.py` | 驗收：測試伺服器、三隻網路 kernel、每項一個沙箱、pi `--fake`、跑前跑後比對 |
