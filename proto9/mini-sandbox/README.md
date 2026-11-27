最小的沙箱原型（11-27 家機）：底層就是一行 `systemd-run --user --scope`（CPU、記憶體、行程數上限）加 `unshare -UrmpnC`（自己的 user／mount／PID／網路／cgroup namespace），上面可選疊網路 kernel（兩層 netns：pasta 接外網、nft 白名單與總量、tc 頻寬）與切 uid；第二段（11-27 晚）加了照名字嵌套的 `mini.py --kernels`（每個 kernel 是一支包裝程式，替內層設好環境再在裡面起下一層：cgroup、網路、檔案遮蔽、uid），檔案遮蔽 kernel 蓋掉 `/run/user/<uid>` 就關住經 D-Bus 跳出去那條路；第三段（11-27 夜，使用者六題都照推薦）把 kernel 設定搬到 `$AOS_HOME/kernels/`、`--kernels` 改逗號分隔、裝了上限／網路／llm kernel 自動加遮蔽，並把 llm kernel 做成嵌套的一層（pi 沒網路也經 socket 問得到腦，被記帳、限模型、限次數）；第四段（11-27 深夜，使用者三題都照推薦）定下 llm kernel 也觸發自動遮蔽、額度每次跑重算（要累計寫 `state`），網路 kernel 寫在 llm kernel 裡面又放行它的上游時 mini 直接拒絕起來；其他照舊全部漏給 Linux。舊驗收 31 項、層疊實測 22 項、llm 嵌套驗收 11 項都兩次全過，真模型跑過一次。

# mini-sandbox（11-27，家機 Manjaro 6.18）

← [proto9](../README.md)｜使用者定的：[pi沙箱-1127](../../proto8/thinking/2026-11/27/pi沙箱-1127.md) 定了的第 10 條｜依據（不進 git，家機）：`~/.aos/scratch/proto9-smallproto-1127/net-report.md`（最小底層與網路模組調查）、`uid-report.md`（切 uid 調查）、給使用者看的 `report.html`｜旁邊那一版：[pi-sandbox](../pi-sandbox/README.md)（從零組天空、seccomp、`/llm`，跟這版並存、不被取代）

我自己定的標【擬】。

## 結論先講

**第四段（11-27 深夜，kernel 設定檔格式說明第 07 節三題都照推薦；細節在「第四段：三題怎麼做」）**

- **llm kernel 也觸發自動遮蔽**：使用者定（第 1 題甲），程式本來就這樣（`AUTO_MASK_FOR` 含 `llm`），沒改。
- **llm 額度每次跑都重算**：使用者定（第 2 題甲），程式本來就這樣；要累計就在設定寫 `state`，用法與坑寫在「llm kernel」的「`state`：額度要累計時」。這次新加一個驗收項實測累計真的接得上（`e_state_carries`）。
- **網路 kernel 寫在 llm kernel 裡面、又放行它的上游，mini 直接拒絕起來**（第 3 題甲，以前只印警告）：例 `aos/llm/litellm-luna,aos/net/base-litellm-proxy`，`mini.py` 退出碼 2、一行英文錯誤講清楚是哪兩個 kernel、怎麼改；在起任何東西之前就擋（沒有 scope、行程、`/tmp/aos-mini-*`），`--dry-run` 也一樣報錯。反過來寫（網路在前）照常起。
- **pi 在裡面會怎樣**：寫錯的那種疊法根本起不來，pi 不會偷偷多一條直連 LiteLLM 的路；其他照第三段。
- **驗收各一次全過**：見「第四段：三題怎麼做」最後。

**第三段（11-27 夜，六題照推薦做；細節在「第三段：六題怎麼做」與「llm kernel」兩節）**

- **pi 在裡面會怎樣**：`mini.py --kernels aos/base-low,aos/llm/fake -- …pi…` 這樣寫，pi **沒有網路**（只有 `lo`），**卻問得到腦**：它照 `$AOS_ENV` 的宣告找到 llm kernel 的 socket，用 kernel 放的 `relay` 把自己的 `127.0.0.1:8787` 接過去。每一次都記進帳本、只准列出來的模型（別的回 403）、次數用完回 429；外面的 LiteLLM 4000 試了三條路（`127.0.0.1`、`169.254.77.1`、本機的 `192.168.1.104`）都連不到；帳本與額度檔它看不到也改不到。
- **真模型跑了一次**：`chatgpt-gpt-6-luna-nothink`，額度上限 10 次，pi 用了 5 次、15.5 秒，read、write、edit、bash 全過，帳本 5 行都是 200，約 1.4 萬 token。
- **六題都照推薦**（使用者 11-27 晚：「都先按照推薦，我還在外面爽玩」）：kernel 設定搬到 `$AOS_HOME/kernels/`（repo 的 `proto8/kernels/`）；內層寫鬆照樣起、取較緊的、印警告；沒寫 `--kernels` 就什麼都不裝；llm kernel 是一層包裝程式了；`--kernels a,b,c` 逗號分隔；裝了資源上限或網路 kernel 時 mini 自動在最裡面加 `aos/mask/run-user`、印一行說加了，`--no-auto-mask` 關掉。
- **跟推薦不完全一樣的一點**（當時【擬】，第四段使用者定保留）：llm kernel 也會觸發自動遮蔽——不遮的話 pi 經 D-Bus 叫 systemd 起一隻沙箱外的行程，那隻在你本人的網路裡、直接連 LiteLLM，llm kernel 的次數與模型限制就白設（實測 `e_no_auto_mask_llm_only` 跳得出去）。
- **驗收各兩次全過**：`accept.py` 31 項（沒改）、`stack_test.py` 22 項（多了「只寫 cg 時自動遮蔽、加 `--no-auto-mask` 時跳得出去」兩項）、新的 `llm_test.py` 11 項（加真模型那次 12 項）；跑完沒留下行程、scope、netns、測試伺服器、transient unit、`/tmp/aos-mini-*`。

**第二段（11-27 晚，嵌套與檔案遮蔽，細節在下面「嵌套」以後各節）**

- **pi 在裡面會怎樣**：`mini.py --kernels aos/base-low,aos/net/base-litellm-proxy,aos/mask/run-user -- pi …`（第三段起是逗號；當時是空格）這樣寫，pi 就住在三層 kernel 的最裡面：CPU、記憶體、行程數有上限、只連得到外面的 LiteLLM、`/run/user/1000` 是一個空夾；**這次經 D-Bus 也跳不出去了**（`busctl` 回「連不上」），遮蔽它拆不掉（`umount` 回 Invalid argument）。不裝遮蔽 kernel 就跟第一段一樣，一行跳出去（這次又量了一次）。
- **每個 kernel 都是一支包裝程式**：`kernel1 [參數] -- kernel2 [參數] -- … -- pi`，每一支替後面設好環境，然後在那個環境裡起下一支（跟 `unshare`、`nsenter`、`setpriv` 同一種形狀）。寫在前面的是外層，後面的是它的住戶。
- **疊起來只會更緊**：同一種疊兩層，Linux 本身就取較緊的那個（cgroup 是一層層往下算、網路是封包要先過內層再過外層）；內層寫得比外層鬆，實測照樣被外層擋住，內層 kernel 起來時印一行警告。pi 在沙箱裡自己再起一個 mini，也鬆不過外面那層。
- **只有一種疊法會出事：uid 不是最後一個**。切了 uid 之後，後面的 kernel 讀不到你家目錄裡的程式，起不來（退出碼 2，pi 沒跑），不會「少一層照跑」。
- **層疊實測兩次都全過**：`stack_test.py` 20 項（含 pi `--fake` 經 base＋net＋mask 跑完四個工具）；舊的 `accept.py` 31 項照樣兩次全過。

**第一段（11-27 下午）**

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

## 嵌套：`mini.py --kernels`（第二段，11-27 晚）

### 使用者的比喻與規則

使用者 11-27 的原話（照序）：「試試看層疊」「到時候的用法，或許可以是這樣：aos daemon ctl add --kernels aos/base-low aos/net/base-litellm-proxy aos/bases/extra-1 $AOS_HOME/templates/fsm-agent/gpt」「…你知道janet嗎，他有setdyn…又像是lua的srt metatable一層一層合併...不太對，因為後一層會需要使用前一層的東西，所以應該是嵌套set」「應該說，後一層就是運行在前一層給出的環境裡，環境套環境」。

- **Janet 的 `with-dyns`**：在一段程式外面包一層「這一段裡某個設定是什麼」，裡面的程式去讀，拿到的是離它最近那層包的值；包好幾層就是一層套一層。這裡一樣：每個 kernel 替它裡面那一段設好環境，裡面再包一層，就是在這個環境裡再設一次。
- **跟 Lua metatable 一層層合併不一樣的地方**：後一層不是跟前一層「合併設定表」，而是**真的跑在前一層的環境裡**——它的行程在前一層的 cgroup 裡、它看到的網路是前一層給的網路、它看到的檔案是前一層遮過的檔案。所以它用得到前一層的東西，也鬆不過前一層。
- **誰是住戶**：每個 kernel 是前一層的住戶；pi（agent）是最裡層的住戶。**寫在前面的＝外層**（使用者已確認）。
- **內層不能比外層鬆**（11-27 定的 1甲：不擋在裡面再開沙箱）：這版不是靠 kernel 自律，是 Linux 本身就這樣算——cgroup 上限一層層往下取最緊、封包要先過內層的規則再過外層的、從外層抄來的掛載在內層是鎖住的。內層寫得比外層鬆，只是寫了沒用（起來時印一行警告）。

### 長什麼樣

```
python3 mini.py --kernels aos/base-low,aos/net/base-litellm-proxy,aos/mask/run-user -- pi …
組出來的那一行（--dry-run 印得出來；{…} 是各自那份設定）：
systemd-run --user --scope … -p Delegate=yes --                         ← mini.py：外面那個 scope（沒有上限）
  python3 -I cg_kernel.py   --name aos/base-low                --json {…} --
  python3 -I net_kernel.py  --name aos/net/base-litellm-proxy  --json {…} --
  python3 -I mask_kernel.py --name aos/mask/run-user           --json {…} --
  python3 -I -c "$(cat leaf.py)" stage1 --env-json {…} --               ← 最裡那步（不是 kernel，一定有）
  pi …
```

每一支只看自己的參數，`--` 後面整串原封不動當成「下一個要跑的指令」，設好環境就在裡面跑它。

| 程式 | 替內層做什麼 | 自己留著嗎 | 宣告給內層 |
|---|---|---|---|
| `cg_kernel.py` | 在自己的 cgroup 底下開子 cgroup `k-<PID>`、設 cpu／memory（含 swap 0）／pids 上限、搬進去；開新的 user＋mount＋cgroup namespace（內層看自己是 `/`、改不了這些上限、搬不出去），重掛一份 `/sys/fs/cgroup` | 不留（換成下一支） | `aos/cgroup/`：`cpu`、`mem`、`pids`（跟外層宣告比過、取較緊的）、`asked`（自己寫的） |
| `net_kernel.py`（`--json` 時是包裝模式） | 外層 netns＋pasta＋nft＋tc（跟第一段一樣）；用 `nsenter --user=<外層>` 加 `unshare --user --net` 起下一支，把 veth 拉進它的 netns，好了才放行；自己這幾隻搬進 cgroup `k-net`、下一支放 `in` | 留著（顧 pasta、每秒寫狀態檔），下一支結束才收、退出碼照傳 | `aos/net/`（欄位同第一段，少 `ctl`、`protocol`、`max_attach`） |
| `mask_kernel.py` | 開新的 user＋mount namespace，把設定的路徑蓋掉（見下面「檔案遮蔽 kernel」） | 不留 | `aos/mask/paths`：外層蓋過的也抄進來，一行一條 |
| `uid_kernel.py` | 開新的 user namespace，`setpriv` 換成 uid N、清掉附加群組、丟掉所有 capability、`no_new_privs` | 不留 | `aos/uid/`：`uid`、`outside`（外面看是哪個 id） |
| `leaf.py`（最裡那步） | pi 自己的 user／mount／PID／cgroup namespace 與新的 `/proc`；外層沒宣告 `aos/net` 就給一個只有 `lo` 的空網路；`env -i` 換成乾淨的環境變數 | `unshare` 在外面等 pi | 不宣告；把 `AOS_ENV` 交給 pi【擬】 |

`leaf.py` 用 `python3 -I -c "<整份原始碼>"` 跑（不是讀檔），因為切成 uid N 之後它讀不到你家目錄裡的檔；它也不 import 這個夾的別的檔。

**為什麼是這個形狀**（「每支都是包裝程式、`--` 串下去」）：

1. **這就是 Linux 本來的做法**：`unshare`、`nsenter`、`setpriv`、`env`、`systemd-run` 本身就是「設好一樣東西，再執行後面的指令」，這種一支接一支 exec 下去的串法叫 chain loading，daemontools、s6、execline 都這樣做（只借形狀，沒抄程式）。每一支不用知道後面是誰。
2. **「後一層跑在前一層的環境裡」自動成立**：下一支就是在前一支設好的 namespace、cgroup 裡被起來的，不用另外傳什麼。
3. **一支一件事**：換順序＝換 `--kernels` 的順序；同一種寫兩次就是兩層。
4. 想過的另一種：「一個主程式讀全部設定、一次設好」（第一段的 `mini.py cfg.json` 就是）——做不到「後一層用前一層的東西」（例如內層網路 kernel 的 pasta 要跑在外層給的網路裡），pi 也不能在裡面用同一套再疊一層。第一段那種用法照樣留著（`accept.py` 測的就是它）。

### 每層怎麼知道外層給了什麼：`$AOS_ENV`【擬】

- 一個環境變數 `AOS_ENV` 指到一個夾，夾裡的 `.aos/` 就是「到這一層為止，外面給了什麼」：
  - `.aos/interfaces/aos/<種類>/<欄位>`：每個欄位一個小檔（照第一段網路 kernel 的寫法）；
  - `.aos/kernels`：從外到內一行一層，例 `cgroup aos/base-low`、`net aos/net/base-litellm-proxy`；
  - `.aos/host_uid`、`.aos/host_subuid`：你在外面的 uid 與 subuid 範圍（mini.py 在最外面寫一次）。
- **每一層做三件事**：讀 `$AOS_ENV`（外層給的）→ 抄一份成自己的夾、加上（或蓋掉）自己這一種的宣告 → `AOS_ENV` 改指自己的夾，再起下一層。外層的夾不動。所以內層讀到同一種的宣告，就是離它最近那層的——跟 `with-dyns` 裡讀到最裡那層的值一樣。遮蔽 kernel 例外：它把外層蓋過的路徑一起抄進來，因為外層的遮蔽在內層一樣有效。
- **實際有人讀的**：最裡那步看有沒有 `aos/net`，決定要不要給空網路；cgroup kernel 讀外層的 `aos/cgroup`，比自己鬆就警告；網路 kernel 讀外層的 `aos/net`——自己的 `host_ports`（「外面那台機器的某個 port」）翻成「到外層 `host_addr` 的白名單」，總量比外層大就警告；遮蔽 kernel 讀 `host_uid` 換掉 `{uid}`；uid kernel 讀 `host_subuid` 算外面看是哪個 id。
- **為什麼是「環境變數指一個夾」，不是 `/.aos`**：根目錄是你主機的，不用 root 開不了 `/.aos`（要整片天空自己組，那是 pi-sandbox 那一版）；普通程式不看這個變數就什麼事都沒有，合「普通程式什麼都不用知道」（pi沙箱-1127 第 5 條）。
- **夾放在哪**：`/tmp/aos-mini-*/`（mini.py 開、跑完刪），每層一個 `<第幾層>-<種類>-<PID>/`，網路 kernel 的狀態檔 `status` 也在它那一層的夾裡。不放 `$XDG_RUNTIME_DIR` 是因為切成 uid N 之後進不了 `/run/user/1000`（700），最裡那步就讀不到宣告。遮蔽 kernel 若蓋到這個夾，會在蓋子上留一個洞（宣告寫 `hole`）讓內層看得見。

### 名字去哪找（第三段，使用者定第 1 題）

- `aos/base-low` → 先在 `$MINI_KERNELS_PATH`（冒號分隔的夾，可不設）裡找 `aos/base-low.json`，再找 `$AOS_HOME/kernels/aos/base-low.json`；第一個找到的算。兩個都沒設：`mini: error: KernelNotFound kernel aos/base-low: nowhere to look (set AOS_HOME, …)`，退出碼 2，什麼都沒跑。名字本身像路徑（`/`、`./`、`~` 開頭或 `.json` 結尾）就直接讀那個檔。
- 一個名字＝一份 json：`{"description": "…", "program": "cg_kernel.py", "config": {…}}`。
- **`program` 怎麼寫才在兩處都對**【擬】：只寫檔名（`cg_kernel.py`、`llm_kernel.py`）＝mini 自己的程式，就是跟 `mini.py` 同一夾的那支；所以同一份 json 放在 `proto8/kernels/`、測試的暫存夾、或 `$AOS_HOME` 被抄到 repo 外，都指到「正在跑的那份 mini」旁邊的程式。寫了 `/` 的照路徑走：`$變數`、`~` 先展開，相對路徑從那份 json 所在的夾算（例 `"$AOS_HOME/../proto9/mini-sandbox/cg_kernel.py"` 也行）。
- 原本 `proto9/mini-sandbox/kernels/` 拿掉了，不留後備（避免兩份對不上）；測試用的 `t/…` 照舊寫在暫存夾、用 `MINI_KERNELS_PATH` 指過去，`aos/…` 讀這份 repo 的 `proto8/kernels/`（測試自己把 `AOS_HOME` 設成這份 repo 的 `proto8`）。

| 名字（`$AOS_HOME/kernels/` 底下） | 是什麼 |
|---|---|
| `aos/base-low` | cgroup：CPU 一顆核的 20%、記憶體 512M（不准用 swap）、行程＋執行緒 64 |
| `aos/base-high` | cgroup：200%、4G、1024 |
| `aos/net/base-litellm-proxy` | 網路：只放行外面 `127.0.0.1:4000`（LiteLLM；裡面用 `169.254.77.1:4000` 連），下載 16mbit、上傳 8mbit、總量 200 MB。**注意**：跟 llm kernel 一起用時，pi 會繞過 llm kernel 直接連 LiteLLM（mini 會印警告），見「llm kernel」 |
| `aos/mask/run-user` | 檔案遮蔽：`/run/user/<你的 uid>` 蓋成空夾（裝了上限／網路／llm kernel 時 mini 自動加這份） |
| `aos/mask/ssh` | 檔案遮蔽：`~/.ssh` 蓋成空夾（示範再多蓋一個路徑） |
| `aos/uid/1` | 切 uid：裡面是 uid 1（外面是你第一個 subuid）；要放最後 |
| `aos/llm/fake` | llm kernel，劇本腦、不叫模型：模型 `fake-model`、一次跑 50 次；第一句有 `four steps` 就照劇本叫 read、write、edit、bash（驗收那件小事），其他答 `FAKE OK` |
| `aos/llm/litellm-luna` | llm kernel，上游是這台的 LiteLLM `127.0.0.1:4000`：只准 `chatgpt-gpt-6-luna-nothink`、一次跑 10 次；要放在網路 kernel 外面 |

使用者例子裡的 `aos/bases/extra-1` 不知道指什麼，沒做（`aos/mask/ssh` 是「再多一層」的示範）。

### 怎麼跑

```
cd proto9/mini-sandbox
python3 mini.py --kernels aos/base-low,aos/net/base-litellm-proxy -- pi …   # 自動在最裡面加 aos/mask/run-user
python3 mini.py --kernels aos/base-low,aos/mask/run-user,aos/uid/1 -- sh -c id   # uid 一定放最後
python3 mini.py --kernels aos/base-low,aos/llm/fake -- …                       # 見「llm kernel」怎麼起 pi
python3 mini.py -- sh                      # 沒寫 --kernels：一個都不裝，只有最裡那步（沒網路、沒上限、檔案全漏）
python3 mini.py --no-auto-mask --kernels aos/base-low -- sh   # 不要自動加遮蔽（/run/user 照漏）
python3 mini.py --dry-run --kernels … -- …   # 只印組出來的那一行（自動加的那層也印得出來）
python3 mini.py --print --kernels … -- …     # 先把那一行印到 stderr 再跑
# 其他選項：--name N（scope 叫 mini-<N>-<PID>）、--cwd D；網路 kernel 要 pasta：MINI_PASTA=<路徑>，沒設找 PATH
# kernel 名字去 $MINI_KERNELS_PATH、$AOS_HOME/kernels 找（見上）
python3 stack_test.py                       # 層疊實測（約 100 秒；--no-pi、--pasta PATH、--keep）
python3 llm_test.py                         # llm 嵌套驗收（約 35 秒；--model M 多跑一次真模型、--no-pi、--keep）
```

退出碼照傳（被訊號殺＝128+N，OOM＝137）。收到 SIGTERM／SIGINT／SIGHUP：整個 scope 送同一個訊號，5 秒後還在的整個 scope 送 SIGKILL。pi 自己在裡面跑 mini 時沒有 scope（見下），改送給自己那個 process group。

### cgroup 怎麼分（為什麼內層鬆不過外層）

Linux 的 cgroup v2 有一條規矩：開了控制器（cpu、memory、pids）往下分的 cgroup，自己不能直接放行程。所以每一層都把自己搬進一個子夾、讓「根」空著。實際跑起來（`systemd-cgls` 看到的，base＋net＋mask＋pi）：

```
mini-<名>-<PID>.scope         ← mini.py 開的（Delegate=yes，沒有上限；裡面的人才能自己分）
└─ k-<PID>                    ← cgroup kernel 的上限設在這
   └─ inner                   ← 它給內層的 cgroup namespace 根（內層看是 /）
      ├─ k-net                ← 網路 kernel、holder、pasta
      └─ in
         ├─ wait              ← 最裡那步的 unshare 在這裡等
         └─ sb                ← pi 的 cgroup namespace 根
            └─ agent          ← pi
```

- 上限一層層往下算：子夾寫 500M、祖先是 200M，實際就是 200M（Linux 算的，實測見下表 b_cg_*）。
- 內層改不了自己 namespace 根的上限（`Operation not permitted`），也搬不出根（第一段 `cgroup_ns_C` 量過）。
- pi 在 `/sys/fs/cgroup` 看到自己的 `memory.max` 是 `max`（上限掛在它看不到的祖先上）；要知道自己的上限，讀 `$AOS_ENV/.aos/interfaces/aos/cgroup/`。
- 每層要重掛一份 `/sys/fs/cgroup`，不然它看到的還是整台的樹、找不到自己：直接掛會 `EBUSY`（同一個 cgroup2 掛在同一點上），所以先蓋一小塊 tmpfs、在裡面掛、再 bind 過去（這次試出來的）。
- pi 自己再起 mini（沙箱裡開沙箱）時，它的 cgroup 裡還有 pi 的其他行程，cgroup kernel 就在 namespace 根底下開一個兄弟夾 `k-<PID>`（還在外層的上限底下）；在最外面（主機的 cgroup namespace）不准這樣做，免得開到別人的 slice 去。這些空夾等外層結束時跟著 scope 一起收。

## 檔案遮蔽 kernel（`mask_kernel.py`）

使用者 11-27：「啊，3.這個，就做成一個kernel吧」——蓋 `/run/user/<uid>` 不寫死在底層，做成可裝可不裝的 kernel。

| 設定欄位 | 預設 | 意思 |
|---|---|---|
| `paths` | `[{"path": "/run/user/{uid}", "how": "tmpfs"}]` | 要蓋的路徑；`{uid}`＝你外面的 uid、`{home}`＝家目錄；不存在就跳過（宣告寫 `absent`） |
| `paths[].how` | `tmpfs` | `tmpfs`：蓋成空夾（1 MB，pi 寫得進去，沙箱結束就沒了）；`null`：用 `/dev/null` 蓋一個檔；`ro`：原地唯讀 |
| `keep` | 無 | 蓋掉的夾裡要留著看得見的路徑；`$AOS_ENV` 所在的夾一定留 |

- **pi 在裡面會怎樣**：`/run/user/1000` 是一個空夾，systemd --user、D-Bus session bus、Wayland、PipeWire 的 socket 都不見了；`systemd-run --user` 與 `busctl --user call … StartTransientUnit` 都回「No such file or directory」，**跳不出去**（實測 a_base_mask 等 6 種疊法）。不裝就跟第一段一樣跳得出去（a_none、a_base、a_base_net 這次又量到 `busctl rc 0`）。
- **pi 拆不掉**：遮蔽做在外層的 mount namespace，pi 在更裡面一層（它自己的 user namespace），Linux 把從外層抄來的掛載鎖住；`umount2(…, MNT_DETACH)` 回 `Invalid argument`（實測）。
- **還漏的**（這個 kernel 預設只蓋這一個夾）：其他檔案全漏（`~/.ssh` 可以加 `aos/mask/ssh`）；`~/.config/systemd/user/` 寫得進去，你下次登入時那個服務會在沙箱外面跑；IPC 跟外面同一個；`$SSH_AUTH_SOCK` 不在 `/run/user` 底下時照樣連得到。
- **坑**：家機的 fnm（node 版本管理）把每個殼的 node 放在 `/run/user/1000/fnm_multishells/…`，`PATH` 裡若是那條路，遮掉之後 pi 就找不到 node。要寫真實路徑（`~/.local/share/fnm/node-versions/…`；pi-sandbox 的 `aos_pi.find_node()` 本來就找真實路徑，所以 `d_pi_fake_stack` 沒事）。
- 預設裝不裝：**使用者定（第 6 題乙）**：裝了 cgroup 或網路 kernel（另加 llm kernel：第四段使用者定第 1 題甲）時 mini 自動在最裡面加；什麼都沒裝時不加；`--no-auto-mask` 關掉。見「第三段」。

## 層疊實測（`stack_test.py`）

`stack_test.py` 在外面起三個測試伺服器 A、B、C（`127.0.0.1` 隨機 port），照名字找 kernel（第三段起：`MINI_KERNELS_PATH=<暫存>/kernels` 放測試用的 `t/…`，`aos/…` 從 `AOS_HOME=<這份 repo>/proto8` 的 `kernels/` 找；`--kernels` 用逗號），每種疊法起一個沙箱跑 `probe.py check`（一次量很多樣，原始碼用 `-c` 傳進去，uid 1 也跑得動），最後比對跑前跑後。測試用的 kernel：`t/base`＝20%／200M／40 隻；`t/net-ab`＝放行 A、B，總量 5 MB；`t/net-a-2mb`＝只放 A、2 MB；`t/net-ac-10mb`＝A、C、10 MB；`t/cg-tight`＝20%／200M／30；`t/cg-loose`＝80%／500M／100。

**a. 不同 kernel 疊、只裝幾個、換順序**（數字是兩次的值，一樣只寫一個）

| 項目 | 疊法（前面＝外層） | 量到的 | pi 在裡面會怎樣 |
|---|---|---|---|
| `a_none` | 不裝（第三段起是真的沒寫 `--kernels`：`mini.py -- …`） | 只有 `lo`；`busctl` 成功；uid 0、600 的檔讀得到；沒有自動加遮蔽 | 看不到別人的行程、沒網路，但沒有任何上限，一行就跳出去 |
| `a_base` | base（第三段：mini 自動加遮蔽） | CPU 0.2；記憶體到 190 MB 被砍；fork 到第 38 隻失敗；只有 `lo`；stderr 有「added aos/mask/run-user」；`busctl` 回 Failed to connect；`umount` 回 Invalid argument | 有上限、改不掉、跳不出去（第二段時這一項是跳得出去） |
| `a_base_no_auto_mask` | base，加 `--no-auto-mask`（第三段新加） | 上限同上；沒加遮蔽；`busctl` 成功（rc 0） | 有上限，但一行就跳出去、上限白設（＝第二段的 `a_base`） |
| `a_base_net` | base、net（第三段：自動加遮蔽） | 上限同上（記憶體到 140 MB 就砍）；A 通、C `No route to host`；pasta 在 `k-<PID>/inner/k-net`（上限裡面）；自動加遮蔽、`busctl` 失敗、`umount` 回 Invalid argument | 只連得到 A、跳不出去；pasta 跟網路 kernel 吃掉 pi 約 50～60 MB 額度 |
| `a_base_net_no_auto_mask` | base、net，加 `--no-auto-mask`（第三段新加） | 同上，但 `busctl` 成功 | 只連得到 A，但一行就跳出去、白名單也白設 |
| `a_base_mask` | base、mask | 上限同 `a_base`；`busctl` 回 No such file；`umount` 回 Invalid argument | 有上限、跳不出去、拆不掉遮蔽；沒網路 |
| `a_base_mask_uid` | base、mask、uid | 再加：`id -u`＝1、600 的檔 `Permission denied`（記憶體 190、180 MB 被砍） | 同上，而且進不了你的家目錄 |
| `a_all` | base、net、mask、uid | 四樣同時成立 | 有上限、只連得到 A、跳不出去、是 uid 1 |
| `a_mask_outermost` | mask、base、net、uid | 同 `a_all` | 跟 `a_all` 一樣：遮蔽放最外面也行 |
| `a_net_outermost` | net、base、mask、uid | 同 `a_all`，但記憶體到 190 MB 才砍；pasta 在 `/k-net`（**上限外面**） | 跟 `a_all` 一樣，差別是網路 kernel 吃的資源不算在 pi 的額度裡 |
| `a_mask_inside_net` | base、net、mask | 同 `a_base_net`＋跳不出去、`umount` 回 Invalid argument | 遮蔽放在網路 kernel 裡面也一樣有效 |
| `a_uid_before_mask` | base、uid、mask | 退出碼 2：`can't open file …/mask_kernel.py: Permission denied`；指令沒跑 | **出事的疊法**：起不來（不會少一層照跑） |
| `a_uid_before_net` | base、uid、net | 同上（`net_kernel.py` 讀不到） | 同上 |

**b. 同一種疊兩層**

| 項目 | 疊法 | 量到的 | pi 在裡面會怎樣 |
|---|---|---|---|
| `b_net_in_net_tighter` | 外：A、B、5 MB；內：A、2 MB | A 通；B `No route to host`；要 4 MB，拿到 1901064、1901144 位元組就斷 | 只連得到兩層都准的 A，總量照較小的 2 MB |
| `b_net_in_net_looser` | 外：A、B、5 MB；內：A、C、10 MB | A 通；C 連不到（外層擋）；要 8 MB，拿到 4795216、4790404 位元組就斷（之前沒用過這隻的總量）；內層網路 kernel 起來時印兩行警告 | 內層寫鬆了沒用：C 照樣連不到、5 MB 照樣斷 |
| `b_cg_in_cg_looser` | 外 20%／200M／30；內 80%／500M／100 | CPU 0.2；190 MB 砍；fork 到第 28 隻失敗；內層 cgroup kernel 印三行警告（「… applies」） | 照外層的上限 |
| `b_cg_in_cg_tighter` | 反過來 | 一樣（0.2、190 MB、28） | 照內層的上限（還是兩層中較緊的） |
| `b_mask_on_mask` | `aos/mask/run-user`、`aos/mask/ssh` | 跳不出去；`~/.ssh/id_ed25519` No such file；宣告兩行（`tmpfs /run/user/1000`、`tmpfs /home/…/.ssh`） | 兩樣都看不到 |

**c. 沙箱裡再開沙箱（pi 自己跑 `mini.py --kernels …`）**

| 項目 | 外層 → 內層 | 量到的 | pi 在裡面會怎樣 |
|---|---|---|---|
| `c_mini_in_mini_looser` | 外：`t/cg-tight`、mask、`t/net-ab` → 內：`t/cg-loose`、`t/net-ac-10mb` | `.aos/kernels` 五行（外三內二；第三段起六行：內層的 mini 也自動加了遮蔽）；CPU 0.2；記憶體到 80 MB 就砍（外層 200M 還算進內層那幾隻 kernel 與 pasta）；fork 到第 18 隻失敗；A 通、B 不通（內層沒放）、C 不通（外層擋）；跳不出去 | 裡面那層只會更緊；寫鬆的部分全部無效 |
| `c_mini_in_mini_bare` | 同上外層 → 內層不裝 kernel | 上限照外層；A、B 通（**沿用外層的網路**）、C 不通；跳不出去 | 跟外層一樣緊（沒網路宣告不是「沒網路」，是「照外層」） |

**d. pi**：`d_pi_fake_stack`——pi `--fake` 經 `t/base-pi`（200%／2G／512）、`t/net-pi`（只放行腦的轉接 port）、`aos/mask/run-user` 跑完 read、write、edit、bash 四個工具，`hello.txt` 是 `pinecone`。**pi 在裡面照常工作**。

`cleanup`：跑前跑後比這次的行程（含 subuid 的）、它們握著的 netns、`mini-*` 的 systemd 單元（含跳出去起的那隻）、`/tmp/aos-mini-*` 與 `$XDG_RUNTIME_DIR/aos-mini-*`、三個測試伺服器的 port，什麼都沒留。

第三段兩次：`SUMMARY ok (22 PASS, 0 FAIL, 0 info, 102s)`、`(22 PASS, 0 FAIL, 0 info, 103s)`（上表的數字是這兩次的，跟第二段一樣的就沒改）。

## 做不到或出事的（第二段）

1. **uid 只能放最後**：切了之後，後面的 kernel 讀不到你 700 的家目錄裡的程式，也寫不了 cgroup 的檔（擁有者是你本人）。實測起不來、退出碼 2、指令沒跑（fail closed）。最裡那步不受影響（用 `-c` 帶原始碼）。要讓 uid 放中間，得把 kernel 程式裝到大家讀得到的地方（例如 `/usr/local/lib/aos/`），那要 root 或另外安排。
2. **網路 kernel 在 cgroup kernel 外面時，pasta 不算進上限**（`a_net_outermost`）：不是錯，是兩種選擇——網路 kernel 放裡面，pasta 吃的 CPU／記憶體算 pi 的（pi 能用的少約 50～60 MB）；放外面，pi 用滿額度，但 pasta 不受限。
3. **網路 kernel 疊網路 kernel 時，「本機」的意思變了**：對內層來說，「外面那台機器」是外層的沙箱，所以內層的 `host_ports` 被翻成「到外層 `host_addr` 的白名單」，pi 一樣用 `169.254.77.1:<port>` 連；外層的子網已經用了 `10.77.0.0/16`，內層自動改用 `10.78.0.0/16`（往上找沒用過的）。
4. **pi 在裡面再起 mini 時沒有 systemd scope**：它在自己的 cgroup namespace 裡（加上遮蔽時連 systemd 都連不到），所以不開 scope、cgroup 用兄弟夾；收行程改送 process group，這條路**沒測**。
5. **內層沒寫網路 kernel ≠ 沒網路**：外層宣告了 `aos/net`，內層最裡那步就沿用那個網路（`c_mini_in_mini_bare`）。一樣緊，不會更鬆；要更緊就在內層也放一個網路 kernel。
6. **宣告夾 pi 改得到**：`/tmp/aos-mini-*` 是你本人的檔，pi（uid 0＝你）寫得進去。宣告只在每層起來時讀一次，之後改了沒有作用；但網路 kernel 的狀態檔 `status` 也在那裡，pi 可以改它來騙看狀態的人（不影響規則本身）。要擋得在 pi 那層之前用唯讀掛載蓋住，這版沒做。
7. **這次找到並修好的**：網路 kernel 起的時候先把 SIGTERM 設成「忽略」，被忽略的訊號會一路傳給它起的內層，pi 那層的 `sh` 就連 `trap` 都設不上（POSIX 規定），結果收不到 SIGTERM、被 5 秒後的 SIGKILL 殺掉（退出碼 137 而不是自己的 3）。改成起內層前先換成「轉送」。另外第一版收訊號只殺 `systemd-run` 起的那一支（後來 exec 成網路 kernel），最裡那步的 `unshare` 跟 pi 留在 scope 裡沒死；改成 5 秒後對整個 scope 送 SIGKILL。

## 第三段：六題怎麼做（使用者 11-27 晚「都先按照推薦，我還在外面爽玩」）

| 題 | 使用者定的 | 這版怎麼做 | pi 在裡面會怎樣 |
|---|---|---|---|
| 1 | kernel 設定放 `$AOS_HOME/kernels/<名字>.json` | 示範設定搬到 repo 的 `proto8/kernels/`；找法 `$MINI_KERNELS_PATH` → `$AOS_HOME/kernels/`；兩個都沒設就清楚報錯；`proto9/mini-sandbox/kernels/` 拿掉（見「名字去哪找」） | 一樣；差在你去哪裡改設定 |
| 2 | 內層寫鬆：照樣起、取較緊的、印一行警告 | 本來就是這樣（`b_cg_in_cg_looser`、`b_net_in_net_looser` 量的）；llm 疊 llm 也照這樣：內層的次數比外層多、或模型外層不收，就印警告 | 受較緊的那層限制 |
| 3 | 沒寫 `--kernels`：什麼都不裝 | `mini.py -- 指令` 就是一個都不裝（只有最裡那步）；`--kernels ''` 也一樣；`a_none` 改成真的不寫 `--kernels` | 沒網路、看不到別人的行程，但沒上限、檔案全漏、一行就跳出去 |
| 4 | llm kernel 改成嵌套的 kernel | `llm_kernel.py`（mini 這邊一份，pi-sandbox 的沒動），見下一節 | 沒網路也問得到腦，被記帳、限模型、限次數 |
| 5 | `--kernels` 逗號分隔 | `--kernels a,b,c`；也收 `--kernels=a,b`，寫兩次會接起來【擬】；舊的空格寫法拿掉了（`--kernels a b --` 回 `unknown option 'b'`） | 一樣，差在打字 |
| 6 | 裝了資源上限或網路 kernel 時自動加 `aos/mask/run-user` | 加在**最裡面**（有 uid kernel 時在它前面，因為 uid 要最後）；stderr 印一行 `mini: added aos/mask/run-user innermost (… --no-auto-mask leaves /run/user/1000 open)`；已經有蓋 `/run/user/<uid>` 的遮蔽 kernel 就不加；`--no-auto-mask` 關掉【擬】；llm kernel 也觸發（第四段使用者定） | 有上限時就跳不出去；其他檔案照漏 |

**第 6 題為什麼加在最裡面**：遮蔽做在哪一層都擋得住 pi（第二段 `a_mask_outermost`、`a_mask_inside_net` 都量過），差別只在外層 kernel 自己看不看得到 `/run/user`。放最裡面＝推薦乙說的「在它們裡面」：外層那幾隻（網路 kernel 顧 pasta 的、llm kernel 的 proxy）是你信得過的程式，照舊；被關的只有住在最裡面的 pi 和它再開的東西。pi 從裡面拆不掉（`umount` 回 Invalid argument，`a_base`、`a_base_net` 量的）。`aos/mask/run-user` 那份 json 找不到時，用內建的同一份設定（`/run/user/{uid}` 蓋成空夾）。第一段的 `mini.py cfg.json` 用法沒有自動加（那條路本來就沒有遮蔽 kernel，`accept.py` 照舊量漏洞）。

**llm kernel 也觸發自動遮蔽**（當時【擬】、跟推薦字面不同；第四段使用者定保留）：推薦乙只寫「cgroup 或網路」，理由是「不然那兩個形同虛設」；llm kernel 同理——不遮的話，pi 經 D-Bus 叫 systemd 起一隻沙箱外的行程，那隻在你本人的網路裡，直接連 LiteLLM，次數與模型限制都白設（`e_no_auto_mask_llm_only` 實測跳得出去）。使用者 11-27 深夜定保留（第四段第 1 題甲）。

## 第四段：三題怎麼做（使用者 11-27 深夜「都先按照推薦」）

題目在 kernel 設定檔格式說明（家機 `~/.aos/scratch/kernel-format-1127/report.html`，不進 git）第 07 節；原話「都先按照推薦」經 main-alt 的任務書轉來。三題都選甲（推薦）：

| 題 | 使用者定的 | 這版怎麼做 | pi 在裡面會怎樣 |
|---|---|---|---|
| 1 | llm kernel 也觸發自動加遮檔案 kernel | 程式本來就這樣（`mini.py` 的 `AUTO_MASK_FOR` 是 `cgroup`、`net`、`llm`），沒改；以前標【擬】的地方改成使用者定 | 只裝 llm kernel 時也經 D-Bus 跳不出去（`e_auto_mask_llm_only`） |
| 2 | llm 額度每次跑都重算，跑完就清；要累計就在設定寫 `state` | 程式本來就這樣，沒改；用法與坑寫進「llm kernel」的「`state`：額度要累計時」（含同時跑兩隻共用一個 `state` 會算錯）；加一項驗收 `e_state_carries` | 一樣；額度檔它碰不到 |
| 3 | 網路 kernel 放行了 llm kernel 上游的 port、又寫在 llm kernel 後面（內層）時，直接拒絕起來 | `mini.py` 找完名字、**起任何東西之前**就查（自動遮蔽之前，也在 `--dry-run` 印那一行之前）；寫錯就印一行錯誤、退出碼 2；沒有 scope、行程、`/tmp/aos-mini-*`。以前的警告拿掉了 | 寫錯的疊法起不來，pi 不會多一條直連上游的路 |

**第 3 題的錯誤長這樣**（家機實跑）：

```
$ mini.py --kernels aos/llm/litellm-luna,aos/net/base-litellm-proxy -- true
mini: error: KernelOrderBad aos/net/base-litellm-proxy (net kernel) lets 127.0.0.1:4000 through (its host_ports), and it sits inside aos/llm/litellm-luna (llm kernel), whose upstream is http://127.0.0.1:4000/v1: the agent could reach the upstream directly, around the llm kernel's count and model list. Put aos/net/base-litellm-proxy before aos/llm/litellm-luna in --kernels (outside it), or take port 4000 out of its host_ports. Nothing was started.
```

**怎麼算「放行了上游」**：llm kernel 的 `upstream` 是 `http(s)://位址:port/…`，它後面（內層）任何一個網路 kernel——

- 上游是 `127.0.0.1`／`localhost`（本機）：那個網路 kernel 的 `host_ports` 含這個 port（寫成數字、字串、`"3990-4010"` 範圍、`{"port": …}` 都算）。
- 上游是別的 IP【擬，任務書只講 port】：那個網路 kernel 的 `allow` 有一條 tcp 規則，`to` 蓋到這個位址、`port` 蓋到這個 port。錯誤訊息改說 `its allow list`。
- 上游寫主機名（例 `api.example.com`）：沒有位址可比，不查【擬】。
- 好幾對都寫錯時只印第一對，後面加 `(and N more like it)`【擬】；錯誤代號 `KernelOrderBad`【擬】。
- `net,llm,net` 這種（llm 夾在兩個網路 kernel 中間）內層那個放行了上游也一樣拒絕：照理 llm kernel 已經把內層的網路切掉、那個網路 kernel 本來就連不出去，拒絕不會少掉什麼，規則單純【擬】。

**沒擋的**：上游是本機的對外位址（例 `http://192.168.1.104:4000`）而內層網路 kernel 放行 `host_ports: [4000]`——LiteLLM 若聽 `0.0.0.0`，兩條路通到同一個伺服器，mini 比不出來；用 `127.0.0.1` 寫上游就查得到。

**驗收**（`llm_test.py` 新加四項，`stack_test.py`、`accept.py` 沒改）：

| 項目 | 疊法 | 結果（11-27 家機） |
|---|---|---|
| `e_order_refused` | `t/llm-up-a,t/net-a`（llm 的上游＝測試伺服器 A 的 port，網路 kernel 放行 A） | 退出碼 2、錯誤行有 `KernelOrderBad` 與兩個名字；指令沒跑（標記檔沒出現）；跑前跑後比對沒有新的行程、netns、`mini-*` 單元、`/tmp/aos-mini-*` |
| `e_order_refused_dry` | 同上，加 `--dry-run` | 同上（`--dry-run` 也報錯、stdout 沒印那一行） |
| `e_order_net_first` | `t/net-a,t/llm-up-a`（網路在前） | 照常起、退出碼 0、指令跑了 |
| `e_state_carries` | `t/llm-keep`（上限 3、寫 `state`）與 `t/llm-fresh`（上限 3、沒寫） | 每次問 2 次、各跑兩次：有 `state` 第二次 `200、429`、額度檔 `{"used": 3, "limit": 3}`；沒寫兩次都 `200、200` |

跑了兩輪（第二輪先 unset 所有 `AOS_*`），兩輪數字一樣：`accept.py` `SUMMARY ok (31 PASS, 0 FAIL, 4 info, 41s)`、`stack_test.py` `SUMMARY ok (22 PASS, 0 FAIL, 0 info, 103s)`、`llm_test.py`（不叫真模型）`SUMMARY ok (15 PASS, 0 FAIL, 0 info, 40s)`；跑完沒留下行程、scope、netns、`/tmp/aos-mini-*`、測試伺服器。

## llm kernel（`llm_kernel.py`，第三段）

使用者定第 4 題：llm kernel 也改成跟 mini 的 kernel 同一種包裝程式（`llm_kernel … -- 下一層`）。程式是 mini 這邊一份：HTTP 的部分照 [pi-sandbox](../pi-sandbox/README.md) 的 `llm_kernel.py` 抄過來改，`fake_brain.py` 原樣抄、`relay.js` 抄過來改兩處（見下）；pi-sandbox 的檔都沒動。

### 它做什麼

`llm_kernel.py --name aos/llm/fake --json {…} -- 下一支…`：

1. 讀 `$AOS_ENV`（外層給了什麼），開自己的宣告夾 `/tmp/aos-mini-*/<第幾層>-llm-<PID>/`。
2. 在那個夾開 `sock`（unix socket 上的 HTTP，講 OpenAI 的 chat completions）、放 `relay`（node 小轉接）、寫 `status`，宣告 `.aos/interfaces/aos/llm/`。
3. **proxy 留在它自己這一層跑**（同一支行程的一條執行緒），把下一支起在新的 user＋mount namespace 裡；起之前先把自己的帳本夾蓋成空的（在網路 kernel 裡面時再給下一支一個新的空網路，見下）。
4. 下一支結束 → stderr 印一行帳（`llm-kernel: aos/llm/fake: 5 answered (fake), 0 refused, 0 upstream errors; 5 of 50 used`）→ 收掉 socket → 退出碼照傳。

### 設定（kernel json 的 `config`）

| 欄位 | 預設 | 意思 |
|---|---|---|
| `upstream` | 外層的 llm kernel | `"fake"`＝劇本腦（不叫模型）；`http(s)://…/v1`（例 LiteLLM）；一個有 `aos/llm` 宣告的夾的絕對路徑；不寫（或 `"outer"`）＝用外層宣告的 llm kernel（llm 疊 llm） |
| `models` | 必填 | 准的模型，一個或一串；別的回 403 |
| `limit` | 必填 | 這一次最多幾次請求；用完回 429 |
| `fake_script` | 無 | 劇本（跟 pi-sandbox 一樣：`[{"when": 第一句裡有的字, "steps": [{"tool":…,"args":…} 或 {"text":…}]}]`），直接寫在設定裡 |
| `state` | 這次跑的暫存夾（跑完刪；第四段使用者定） | 帳本 `ledger.jsonl` 與額度檔 `budget.json` 放哪；要讓額度跨好幾次累計就寫一個夾，見下面「`state`：額度要累計時」 |

規矩照 pi-sandbox【擬】：模型不在名單 → 403、不算次；用完 → 429、不送出去；送出去**之前**先把次數加一寫進額度檔；帳本一次請求一行（`fake`／`sent`／`refused`＋原因／`upstream_error`）。**跟 pi-sandbox 不一樣的一點**【擬】：劇本腦也算次數，這樣「用完被拒」不叫模型也試得出來。不轉送 `Authorization`（pi 只有假金鑰）。

### `state`：額度要累計時（第四段使用者定第 2 題甲）

不寫 `state`＝**每次跑都重算**：帳本與額度檔放在這次跑的 `/tmp/aos-mini-*/…-llm-<PID>.state/`，跑完跟著刪，下次從 0 開始。要讓好幾次共用一個額度（例「這隻 pi 今天總共 200 次」），在 kernel 的 `config` 寫一個夾：

```json
{"program": "llm_kernel.py",
 "config": {"upstream": "http://127.0.0.1:4000/v1", "models": ["chatgpt-gpt-6-luna-nothink"], "limit": 200,
            "state": "~/.aos/llm-state/{name}"}}
```

- `~` 會展開、`{name}` 換成 kernel 的名字（`/` 換成 `-`，例 `aos-llm-litellm-luna`）；夾不在就建（權限 700）。跑完不刪。
- 夾裡兩個檔：`budget.json`（`{"used": 已用, "limit": 上限}`）、`ledger.jsonl`（一次請求一行，一直往後加）。要歸零就刪 `budget.json`。
- **上限只會往下調**：起來時取「額度檔裡的上限」和「設定的 `limit`」較小的那個寫回去。所以之後把 `limit` 改大**不會生效**，要自己改或刪 `budget.json`；改小馬上生效。
- **同時跑兩隻共用同一個 `state` 會算錯**：每隻 llm kernel 各自「讀額度檔、加一、寫回去」，兩支程式之間沒有鎖；兩隻同時送請求時可能都讀到同一個數字，結果少算（實際送出去的比 `used` 多，可能超過上限）。帳本兩隻會交錯寫進同一個檔，行數大致對，但不保證。要同時跑就給每隻一個自己的夾（`{name}` 不夠分，同一個名字的兩隻還是同一個夾）。
- pi 碰不到這個夾：llm kernel 起內層前把它蓋成空的（見「擺在疊的哪裡」第 3 條），pi 改不到額度。
- 實測（`e_state_carries`）：上限 3、每次問 2 次、連跑兩次，有寫 `state` 時第二次回 `200、429`、額度檔 `{"used": 3, "limit": 3}`；沒寫時兩次都 `200、200`。

### 宣告（`.aos/interfaces/aos/llm/`，每個欄位一個小檔）

| 檔 | 內容 |
|---|---|
| `kind`、`protocol`、`api`、`base` | `socket`、`http/1.1`、`openai-completions`、`/v1`（跟 pi-sandbox 一樣） |
| `path` | socket 的**絕對路徑**【擬】（pi-sandbox 寫相對於宣告夾；mini 的宣告會被一層層抄進內層的夾，相對路徑就對不上了） |
| `models`、`limit` | 准的模型一行一個；次數上限（內層的 llm kernel 讀來比、寫鬆就警告） |
| `status` | 狀態檔的絕對路徑（`requests_used`、`requests_limit`、`models`、`upstream`） |
| `relay` | 第一個字是轉接的絕對路徑，後面是用法（同 pi-sandbox 的寫法） |
| `network` | `unchanged: …` 或 `cut: …`（見下）【擬】 |
| `description` | 一行英文：這隻 kernel 是什麼 |

### pi 怎麼用

pi 只會講「HTTP 到某個網址」，所以跟 pi-sandbox 一樣在它前面套 relay：relay 在 pi **自己的** `127.0.0.1:8787` 聽，每個連線接到宣告的 socket，再把 pi 當孩子起起來。mini 這份 relay 改了兩處：沒給 `--llm` 時讀 `$AOS_ENV`；宣告的 `path` 可以是絕對路徑。pi 的 `~/.pi/agent/models.json` 的 `baseUrl` 寫 `http://127.0.0.1:8787/v1`、`apiKey` 寫假的。驗收裡起 pi 的那一行：

```
mini.py --kernels aos/base-low,aos/llm/fake -- env PATH=<node 的夾>:/usr/bin:/bin HOME=<pi 的家> \
  sh -c 'exec node "$(cut -d" " -f1 "$AOS_ENV/.aos/interfaces/aos/llm/relay")" --port 8787 -- "$@"' \
  sh <pi 的 cli.js> --mode json --thinking off --provider aosllm --model fake-model "<交代>"
```

### 擺在疊的哪裡、為什麼 pi 繞不過

**推薦擺法：llm kernel 寫在網路 kernel 前面（外層）**，例 `aos/base-low,aos/llm/litellm-luna`（pi 沒網路）或 `aos/base-low,aos/llm/litellm-luna,<只放行別的東西的網路 kernel>`：

```
你（主機的網路）
└─ cgroup kernel（上限；llm 的 proxy 也算在裡面）
   └─ llm kernel：proxy 在這層，用這層的網路（主機的）連 127.0.0.1:4000
      sock 在 /tmp/aos-mini-*/2-llm-<PID>/sock
      └─ [新的 user＋mount namespace：帳本夾蓋成空夾]
         └─ （可選）網路 kernel：只放行它白名單上的
            └─ aos/mask/run-user（mini 自動加）
               └─ 最裡那步 → pi：自己的網路（空的，或網路 kernel 給的）
                  relay 在 pi 自己的 127.0.0.1:8787 → sock
```

pi 繞不過它，靠這幾件（都有驗收項）：

1. **pi 的網路不是 proxy 那層的網路**。沒有網路 kernel 時，最裡那步給 pi 一個只有 `lo` 的空網路；網路 kernel 在 llm kernel 裡面時，pi 在網路 kernel 給的網路裡，只到得了白名單上的。實測連 LiteLLM 4000 三條路都不通：`127.0.0.1:4000` 回 Connection refused（那是 pi 自己的 `lo`）、`169.254.77.1:4000` 回 Network is unreachable／No route to host、本機的 `192.168.1.104:4000` 回 unreachable／逾時（`e_nonet_probe`、`e_net_probe`）。
2. **llm kernel 在網路 kernel 裡面時（`net,llm` 這種寫法）也一樣**：這時 proxy 用的是網路 kernel 給的網路，內層要是沿用，pi 就跟 proxy 連得到同樣的地方；所以 llm kernel 給內層一個新的空網路、把內層宣告裡的 `aos/net` 拿掉（宣告寫 `network: cut`），上游寫 `127.0.0.1:P` 時自動換成網路 kernel 的 `host_addr`（跟網路 kernel 疊網路 kernel 的 `host_ports` 同一種翻法），網路 kernel 沒放行 P 就警告。實測 `e_llm_inside_net`：pi 只有 `lo`、連不到網路 kernel 放行的 A，腦照樣問得到。缺點：這種寫法下，llm kernel 裡面再放網路 kernel 就沒有對外的路（pasta 在空網路裡），pi 什麼都連不到（關著，不會變鬆）。
3. **帳本與額度檔 pi 碰不到**：pi 是 uid 0＝你本人，照理寫得到你的檔；所以 llm kernel 起內層前，在新的 mount namespace 把帳本夾蓋成空的 tmpfs，pi 在更裡面拆不掉（跟遮蔽 kernel 同一種「鎖住的掛載」）。實測 pi 看到那個夾是空的，往裡寫 `budget.json` 只寫在蓋子上，外面的額度檔沒變（`e_budget_429`）。
4. **llm 疊 llm 時繞不過內層那隻**：內層的上游是外層宣告的 socket；內層起它的內層前，把外層的 socket 用 `/dev/null` 蓋掉。pi 在 `/tmp/aos-mini-*` 找得到外層 socket 的路徑，連過去回 Connection refused，只能經內層（`e_llm_on_llm`）。
5. **D-Bus 那個口**：mini 自動加的 `aos/mask/run-user` 關住（llm kernel 也觸發，見上）。
6. **mini 看得到的寫錯直接拒絕起來**（第四段使用者定第 3 題甲；以前只印警告）：llm kernel 的上游是本機某個 port、而它裡面的網路 kernel 又放行同一個 port（例 `aos/llm/litellm-luna,aos/net/base-litellm-proxy`），pi 就能直接連上游、不被記帳；`mini.py` 在起任何東西之前報錯、退出碼 2，見「第四段：三題怎麼做」。

還漏的（照「反正就給他漏」）：pi 讀得到 LiteLLM 設定裡的金鑰（檔案全漏），只是沒網路送不出去；pi 改得到 `$AOS_HOME/kernels/*.json`（例如把 `limit` 改大），下一次起的時候才生效；宣告夾與 `status` pi 改得到，只騙得到它自己與看狀態的人（同第二段「做不到」第 6 條）。

## llm 嵌套驗收（`llm_test.py`，第三段）

`llm_test.py` 在外面起一個測試伺服器 A，`AOS_HOME` 設成這份 repo 的 `proto8`、`MINI_KERNELS_PATH` 指暫存夾的 `t/…`。要讀帳本的那幾項，用 `t/…`＝把 `aos/llm/fake` 抄一份、只加 `state` 夾（或改 `limit`）；`t/net-a`＝只放行 A 的網路 kernel。pi 用本機 fnm 的 node 與 pi 套件（檔案沒遮），`--fake` 的劇本就是 `aos/llm/fake` 裡那份。

| 項目 | 疊法 | 三次的結果（兩次 `--fake`、一次加真模型；11-27 家機） |
|---|---|---|
| `e_nonet_probe` | `aos/base-low,aos/llm/fake`（不加網路） | 只有 `lo`；經 socket 問腦 200；LiteLLM 4000 三條路都不通；A 不通；自動加遮蔽、跳不出去 |
| `e_pi_nonet` | 同上 | pi DONE（3.2 秒，CPU 只有 20%）、四個工具全過、`hello.txt` 是 `pinecone`、`level = high`；pi 5 輪＝kernel 答了 5 次 |
| `e_net_probe` | `aos/base-low,<llm>,t/net-a`（llm 在網路 kernel 外面） | `eth0`、`lo`；A 通；LiteLLM 4000 不通（`169.254.77.1` No route、本機位址逾時）；問腦 200、帳本 1 行 |
| `e_pi_net` | 同上 | pi DONE（6.4～6.6 秒）、四個工具全過；帳本 5 行＝pi 5 輪 |
| `e_budget_429` | `t/llm-two`（上限 2） | 三次請求回 200、200、429；不准的模型 403；帳本 `fake、fake、budget、model`；外面的額度檔 `{"used": 2, "limit": 2}`；pi 那邊看帳本夾是空的，寫進去的沒影響外面 |
| `e_pi_used_up` | `aos/base-low,t/llm-used`（額度檔先寫成用完） | pi NOT DONE，錯誤 `429 … request budget used up (3 of 3)`；帳本 4 行（pi 1 次＋自己重試 3 次）全是 `refused budget` |
| `e_llm_inside_net` | `t/net-a,<llm>`（llm 在網路 kernel 裡面） | pi 只有 `lo`、A `Network is unreachable`、問腦 200；內層看到的宣告只有 `llm`、`mask`（沒有 `net`）；`network cut` |
| `e_llm_on_llm` | `t/llm-outer`（上限 3）、`t/llm-inner`（上限 10，上游＝外層） | 四次請求 200、200、200、429；內層帳本 4 行（最後一行是外層回的 429）、外層 `fake×3、refused`；內層印警告（比外層鬆）；pi 直接連外層 socket 回 Connection refused |
| `e_auto_mask_llm_only` | `aos/llm/fake` | mini 自動加遮蔽；`busctl` 回 Failed to connect |
| `e_no_auto_mask_llm_only` | 同上，加 `--no-auto-mask` | 沒加；`busctl` 成功（rc 0）＝跳得出去 |
| `e_pi_real`（`--model` 才跑） | `aos/base-low,t/llm-real`（`aos/llm/litellm-luna` 加 `state`，上限 10） | `chatgpt-gpt-6-luna-nothink`：DONE、15.5 秒、四個工具全過、5 次請求都 200、約 14232 token；最後一句 `Completed all four steps. test_app.py reports: ALL TESTS PASSED.` |
| `cleanup` | 跑前跑後比 | 行程、netns、`mini-*` 單元、`/tmp/aos-mini-*`、`$XDG_RUNTIME_DIR/aos-mini-*`、測試伺服器都沒留 |

三次：`SUMMARY ok (11 PASS, 0 FAIL, 0 info, 34s)`、`(12 PASS, 0 FAIL, 0 info, 48s)`（加真模型）、`(11 PASS, 0 FAIL, 0 info, 33s)`。

第四段加了四項（`e_order_refused`、`e_order_refused_dry`、`e_order_net_first`、`e_state_carries`），表與結果在「第四段：三題怎麼做」。

## 第二段問的六題（使用者 11-27 晚都選推薦，做法見「第三段：六題怎麼做」）

原話：「都先按照推薦，我還在外面爽玩」（經 main 轉述，記在 [pi沙箱-1127](../../proto8/thinking/2026-11/27/pi沙箱-1127.md) 定了的第 10 條最後一點）。下面是當時的題目，原樣留著；選的是標「推薦」的那個。順序誰在外層已確認（前面＝外層），不再問。

1. **kernel 的名字去哪裡找**
   - 甲（推薦）：`$AOS_HOME/kernels/<名字>.json`（跟 `knowledge/`、`templates/` 同一層），另外可用環境變數加別的夾、或直接寫路徑。pi 在裡面會怎樣：都一樣，差在你去哪裡改設定。
   - 乙：放在 agent 範本底下（`templates/fsm-agent/gpt/kernels/…`），每個範本自己帶。pi 一樣；同一份 base-low 會在很多範本裡各抄一份。
   - 丙：每個 kernel 一個夾（設定＋程式＋說明，像 agent 定義夾）。pi 一樣；最整齊，但現在只有四支程式，夾比內容多。
2. **同名設定／內層想放寬時怎麼辦**
   - 甲（推薦，現在的做法）：照取兩層較緊的，內層放寬無效、起來時印一行警告。pi 在裡面會怎樣：受較緊的那層限制。
   - 乙：內層比外層鬆就報錯、不起。pi 一樣受限，差在寫錯時是起不來還是只有警告。
3. **沒寫 `--kernels` 時預設是什麼**
   - 甲（推薦）：什麼 kernel 都不裝，只有最裡那步。pi 在裡面會怎樣：看不到別人的行程、沒網路，但沒有任何上限，檔案全漏，一行就跳出去。
   - 乙：預設 `aos/base-low`。pi 有上限，但不裝遮蔽時上限照樣能一行繞過。
   - 丙：預設 `aos/base-low aos/mask/run-user`。pi 有上限、跳不出去、沒網路。
4. **跟 `/llm`、`.aos` 宣告怎麼接**
   - 推薦：pi-sandbox 的 llm kernel 也改成同一種包裝程式（例 `aos/llm/<名>`）：它在自己的環境裡開 `/llm` socket、宣告 `.aos/interfaces/aos/llm/`（現在已經是這個格式），內層照 `$AOS_ENV` 找到 socket；socket 放在宣告夾旁邊，遮蔽 kernel 自動留洞。pi 只會講 HTTP，還要那個小轉接（pi-sandbox 的 `/llm/relay`）。pi 在裡面會怎樣：不用網路 kernel 也問得到腦，而且只問得到這一個。
   - 另一個小點：pi 現在拿得到 `AOS_ENV`【擬】。不給的話，pi 不知道外面給了它什麼（普通程式本來就不用知道）；給的話，懂 aos 的程式才找得到 `/llm` 這類介面。
5. **跟 proto8 `aos-daemon-ctl add` 的參數衝不衝突、`--kernels` 怎麼擺**：現有旗標是 `--name --ws --stack --def --limits --auto-restart --reply-to --timeout-s --ws-json --stack-json --path-json`，`--kernels` 不撞名；但 `add … XXX [-- ARGS]` 的 XXX 是位置參數，草圖 `--kernels a b c XXX` 會分不清名字到哪裡結束。
   - 甲：`--kernels` 吃到下一個選項為止，XXX 用 `--def`／`--path-json` 給。
   - 乙（推薦）：逗號分隔一個參數 `--kernels aos/base-low,aos/net/base-litellm-proxy XXX`，最接近草圖、不會吃掉 XXX。
   - 丙：可重複的 `--kernel NAME --kernel NAME XXX`。
   - pi 在裡面會怎樣：三種都一樣，差在打字。另外 `--limits`（aos-sandbox 的上限）跟 cgroup kernel 重疊：疊起來一樣取較緊的、不會打架；要不要收掉 `--limits` 另外再說。
6. **檔案遮蔽 kernel 預設裝不裝**
   - 甲：不裝（使用者先前傾向，照「反正就給他漏」）。pi 在裡面會怎樣：一行就跳出去，cgroup 與網路 kernel 都白設（這次 a_base、a_base_net 又量到）。
   - 乙（推薦）：只要裝了 cgroup 或網路 kernel，就自動在它們裡面加 `aos/mask/run-user`（不然那兩個形同虛設）；兩個都沒裝時不加。pi 有上限時就跳不出去；其他檔案照樣全漏。
   - 丙：一律裝。pi 永遠連不到 systemd --user、D-Bus、Wayland、PipeWire。

## 漏掉的（使用者 11-27：「3.甲，剩下都按照推薦。反正就給他漏」）

照 net-report 第 1 節「漏掉之後 pi 做得到什麼」，這版全部照漏：

1. **讀你所有的檔**：`~/.ssh` 私鑰（這次實測讀得到）、各種 token、瀏覽器資料、LiteLLM 設定裡的金鑰。
2. **寫和刪你所有的檔**：改 repo（包括 `.git`、`AGENTS.md`、git hooks）、`~/.bashrc`；在 `~/.config/systemd/user/` 放一個服務，你下次登入它就在沙箱外面跑。
3. **整個跳出去：`/run/user/1000` 這個口**。pi 在裡面摸得到 systemd --user 與 D-Bus，叫 systemd 替它起一隻新行程，那隻就在沙箱外面：**你本人的網路（網路 kernel 的白名單、頻寬、總量全部不算數）、不在 mini 的 cgroup 裡（CPU、記憶體、行程數上限全部不算數）**——前兩層的限制都被繞過。這次實測：`systemd-run --user` 那支指令在沙箱裡會失敗，但直接經 D-Bus（`busctl`）送同一個請求就成功，所以「指令失敗」不代表口是關的。它也能從外面那隻 `nsenter` 進網路 kernel 的外層、把規則清掉（理論上，沒試）。**這是使用者知情後選的，原話「3.甲，剩下都按照推薦。反正就給他漏」，不再勸。**（之後使用者補了「3.這個，就做成一個kernel吧」：第二段做了，見「檔案遮蔽 kernel」；第三段使用者定「裝了上限或網路 kernel 就自動加」，`--no-auto-mask` 或什麼 kernel 都不裝時這一條照舊。）
4. **D-Bus session bus**：能叫桌面上的程式；你的密碼庫如果開著，可能拿得到密碼（沒試）。
5. **其他用檔案路徑連的 socket**：X11、Wayland（看畫面、送按鍵）、PipeWire（麥克風）、`$SSH_AUTH_SOCK`（叫你的 ssh-agent 幫它簽）、docker.sock（若你在 docker 群組）；網路 kernel 的 `ctl` 也連得到，但請求會被拒。只有 abstract socket 因為自己有 netns 連不到外面。
6. **IPC 跟外面相通**（這次實測同一個 namespace）：SysV 共享記憶體、號誌、訊息佇列、POSIX mqueue、`/dev/shm`。
7. **vsock**：沒有 seccomp 擋，WSL2 上就是連到 Windows 那一邊，netns 管不到（這次沒量）。
8. **所有系統呼叫都能用**：io_uring、keyctl、userfaultfd 等；Linux 核心本身的洞能打到的面變大。
9. **看行程**：有 PID namespace，看不到也殺不到你其他行程（這次實測只看到自己）——這條擋住了。
10. **腦（LLM）**：沒有 `/llm`，pi 只能經網路打 LiteLLM；它讀得到金鑰，網路 kernel 只能限位元組總量，限不了次數或金額。（第三段：裝了 llm kernel 時，pi 沒網路也經 socket 問得到腦，次數、模型被管；見「llm kernel」。）
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
- 第二段：`--kernels` 的寫法與「吃到 `--` 為止」；每支 kernel 的參數 `--name N --json CFG -- 下一支…`；`AOS_ENV`、`.aos/kernels`、`.aos/host_uid`、`.aos/host_subuid`；宣告夾放 `/tmp/aos-mini-*/<第幾層>-<種類>-<PID>/`；`MINI_KERNELS_PATH`、`MINI_PASTA`；名字的 json 格式（`description`、`program`、`config`）與 `kernels/` 底下的示範名字（`aos/base-high`、`aos/mask/ssh`、`aos/uid/1` 是我加的）；cgroup 夾名 `k-<PID>`、`inner`、`k-net`、`in`、`wait`、`sb`、`agent`；scope 加 `Delegate=yes`；內層比外層鬆時印警告、不報錯；網路 kernel 包裝模式的子網自動往上找、`host_ports` 翻成外層 `host_addr` 的白名單；遮蔽 kernel 的 `{uid}`、`{home}`、`keep`、`hole`、tmpfs 1 MB；最裡那步的 cgroup 排法、把 `AOS_ENV` 交給 pi；層疊實測的門檻（CPU 0.15～0.25、記憶體 200M 時 190 MB 以內被砍、2 MB 總量時拿到 1.5～2.0 MB、5 MB 時 4～5 MB）。

- 第三段：`program` 只寫檔名＝mini 自己的程式、寫了 `/` 才當路徑（`$變數`、`~` 展開、相對 json 的夾）；找名字是 `$MINI_KERNELS_PATH` 先、`$AOS_HOME/kernels` 後；`--kernels=a,b` 與寫兩次 `--kernels` 接起來；`--no-auto-mask` 這個名字、自動遮蔽加在最裡面（uid 之前）、找不到 json 時用內建的；`llm_kernel.py` 的設定欄位（`upstream` 的四種寫法）、劇本腦也算次數、宣告的 `path`／`status`／`relay` 寫絕對路徑、`limit`、`network` 兩個新欄位；在網路 kernel 裡面時給內層新的空網路、把 `aos/net` 拿掉、上游 `127.0.0.1` 換成 `host_addr`；帳本夾用 tmpfs 蓋、上游 socket 用 `/dev/null` 蓋；relay 預設讀 `$AOS_ENV`、聽 8787；`aos/llm/fake`（劇本寫在設定裡、50 次）、`aos/llm/litellm-luna`（10 次）兩個示範名字；`llm_test.py` 的測項與門檻。

## 跟任務書不一樣的地方

- **`systemd-run --user` 那條漏洞換了一個量法**：任務書寫「`systemd-run --user` 從裡面起的行程跑出沙箱」；實測這支指令在 `-C` 的沙箱裡失敗，同一個請求改走 `busctl` 才成功。驗收兩種都試、兩種結果都印。
- 那一行多了 `--kill-child`、`--collect`、`--unit` 與一小段 `mini.py --inside`（理由見上）；有網路 kernel 時前面多 `nsenter --user=<A>`。
- 上傳整形的 tbf 佇列是 1 秒，不是調查報告的 200 毫秒（理由見上）。
- 第二段：網路 kernel 照嵌套重整成「外層、在自己的環境裡起內層」（`--json` 包裝模式），但第一段的 `ctl`＋`mini.py cfg.json` 那種用法沒拆，`accept.py` 照舊測它；層疊實測另開 `stack_test.py`，沒塞進 `accept.py`；最裡那步（`leaf.py`）不算 kernel、一定有；任務書沒提的 `aos/base-high`、`aos/mask/ssh`、`aos/uid/1` 是我加的示範；另外加了 pi `--fake` 經整疊跑一次（`d_pi_fake_stack`）。

- 第三段：自動遮蔽**llm kernel 也觸發**（任務書寫「有裝資源上限（cg）或網路（net）kernel 時」；理由見「第三段：六題怎麼做」）。
- 第三段：llm kernel 的劇本腦**也算次數**（pi-sandbox 的不算）；`state` 不寫時額度只算這一次（跑完刪）。
- 第三段：`accept.py` 沒改（它測的是第一段 `mini.py cfg.json` 的用法，不經 `--kernels`、不找名字）。
- 第三段：llm 嵌套驗收另開 `llm_test.py`（沒塞進 `stack_test.py`），真模型用 `--model` 才跑；它也跑了兩次以上（三次）。

## 沒驗的

- **公司 WSL（Linux 6.6、Ubuntu）全部沒跑**：那台有沒有 pasta（要 `sudo apt install passt`）、nft 與 tc 的模組在 user namespace 裡能不能自動載入、`newuidmap` 在 A 裡面行不行，都不知道；WSL2 上 vsock 直接通 Windows（第 7 條）。
- **IPv6**：pasta 用 `-4`，A 與 B 都沒有 v6 位址（B 的 eth0 只有 `fe80::` 本地位址）；`inet` 表照理也管 v6，沒測。
- 第 3 條從外面那隻 `nsenter` 進網路 kernel 外層清規則：理論上做得到，沒試。
- 密碼庫經 D-Bus 拿不拿得到密碼、X11／Wayland／PipeWire／ssh-agent：沒試。
- `max_attach` 大於 1（好幾隻沙箱共用一隻網路 kernel、共用總量）：沒測。
- UDP 白名單、port 範圍、CIDR：程式會轉成 nft，沒有專門的驗收項。
- 長時間上傳（10 MB 以上）只手動試過一次（10 MB、0.97 MB/s、0 丟）。
- 真的模型：沒叫（任務書不要）。pi 經網路 kernel 直接打 LiteLLM 4000（`host_ports: [4000]`）照理就通，沒試。
- （第一段寫的「`/run/user` 檔案遮蔽 kernel、`--kernels`、試層疊這版都沒做」：第二段做了。）
- 第二段沒驗的：公司 WSL；`$AOS_HOME/kernels/` 那個位置（第三段做了）；pi 在裡面跑 mini 時收訊號（送 process group）；遮蔽的 `null`、`ro` 兩種只手動試過一次（`null` 蓋的檔讀到空的、`ro` 的夾寫入回 Read-only file system、pi 改回可寫被拒、不存在的路徑宣告 `absent`），沒進 `stack_test.py`；llm kernel 改成嵌套（第三段做了）；網路 kernel 疊三層以上、`max_attach` 大於 1 的包裝模式；真的模型（第三段經 llm kernel 跑了一次）；SIGKILL 掉 mini.py 本身時（沙箱照跑，同第一段第 14 條）。
- 第三段沒驗的：公司 WSL；llm kernel 放在 cgroup kernel 外面（proxy 不算進 pi 的上限）、跟 uid kernel 一起用（pi 是 uid 1 時，fnm 的 node 在你 700 的家目錄裡跑不了；socket 已開成所有人可連，沒實測）；`net,llm,net` 這種 llm 夾在兩個網路 kernel 中間（照理內層網路 kernel 沒有對外的路）；`upstream` 寫成任意一個 `aos/llm` 夾（只測了外層宣告的那種）；`state` 跨好幾次累計（第四段補測了，見 `e_state_carries`）；真模型經 llm 疊 llm、或 llm 在網路 kernel 裡面（只跑劇本腦）；串流（pi 用的是一次回完的請求還是串流，帳本有記 `stream`，沒專門看）；llm kernel 被訊號收掉時 pi 那邊的樣子；pi 拿到 429 後的重試間隔（設 500 毫秒，照 pi-sandbox）。

## 暫存與清理

- pasta 編在 `~/.aos/scratch/proto9-mini-1127/passt/`（官方 `git clone https://passt.top/passt`、`git checkout 2026_10_02.cba3570`、`make`；GPL-2.0+，只當另外的程式呼叫，沒抄進 repo）。`accept.py` 沒給 `--pasta` 又在 PATH 上找不到時用這一份。
- 驗收的暫存在 `~/.aos/scratch/proto9-mini-1127/accept/`，全過就刪（`--keep` 留著）。
- llm 嵌套驗收的暫存在 `~/.aos/scratch/proto9-mini-1127/llm/`，全過就刪（`--keep` 留著）；第三段這幾次的輸出留在同一層的 `accept-r3.log`、`accept-r4.log`、`stack-r3.log`、`stack-r4.log`、`llm-r2.log`、`llm-r3.log`。
- 層疊實測的暫存在 `~/.aos/scratch/proto9-mini-1127/stack/`，全過就刪（`--keep` 留著）；`--kernels` 跑的時候每次開一個 `/tmp/aos-mini-*/`，跑完刪。
- 用到 nft、tc、veth 時 Linux 會自動載入幾個核心模組（`nft_quota`、`sch_tbf`、`veth` 等），卸掉要 root，重開機就沒了，沒有害處。

## 檔案

| 檔 | 是什麼 |
|---|---|
| `mini.py` | 讀設定、組那一行、跑、退出碼照傳；`--inside`（沙箱裡第一支）、`--give-back`（uid N 的檔還給你）；第二段加 `--kernels`（照名字找 kernel、串成一行、開 `$AOS_ENV`）；第三段改逗號分隔、去 `$AOS_HOME/kernels` 找、自動遮蔽、`--no-auto-mask`；第四段：網路 kernel 在 llm kernel 裡面又放行它的上游時拒絕起來（`KernelOrderBad`） |
| `net_kernel.py` | 網路 kernel：外層 netns＋pasta＋nft＋tc、`ctl`、宣告、狀態檔；`--holder` 是它在外層裡的那一半；第二段加包裝模式（`--json CFG -- 下一支`）與 `--gate`（下一支的第一步） |
| `probe.py` | 驗收在沙箱裡跑的小指令（cpu、mem、pids、cgroup、procs、tcp、get、put、curl、ns、leaks、ctl、read；第二段加 `check`＝一次量很多樣；第三段 `check` 加 `llm`：經宣告的 socket 問腦、找別的 llm socket、碰帳本夾） |
| `accept.py` | 驗收：測試伺服器、三隻網路 kernel、每項一個沙箱、pi `--fake`、跑前跑後比對 |
| `nest.py` | 第二段：kernel 共用的小工具（`KERNEL [選項] -- 下一支` 的參數、`$AOS_ENV` 的讀寫、user namespace 的對應、cgroup 的排法與重掛） |
| `cg_kernel.py` | 第二段：cgroup kernel（cpu、mem、pids 上限＋自己的 cgroup namespace） |
| `mask_kernel.py` | 第二段：檔案遮蔽 kernel（tmpfs／`/dev/null`／唯讀） |
| `uid_kernel.py` | 第二段：uid kernel（換成 uid N，要放最後） |
| `leaf.py` | 第二段：最裡那步（pi 自己的 namespace、沒網路宣告就空網路、乾淨的環境變數），用 `-c` 帶原始碼跑 |
| `llm_kernel.py` | 第三段：llm kernel（unix socket 上的 HTTP proxy、記帳、限模型、限次數；宣告 `aos/llm`；藏帳本夾；在網路 kernel 裡面時給內層空網路） |
| `fake_brain.py` | 第三段：劇本腦（從 pi-sandbox 原樣抄） |
| `relay.js` | 第三段：llm kernel 放進宣告夾的小轉接（從 pi-sandbox 抄，預設讀 `$AOS_ENV`、收絕對路徑） |
| `llm_test.py` | 第三段：llm 嵌套驗收（pi `--fake` 有／沒網路、429、繞不過、llm 在網路 kernel 裡、llm 疊 llm、自動遮蔽、`--model` 時真模型一次、跑前跑後比對）；第四段加寫錯疊法被拒、`state` 累計 |
| [`proto8/kernels/`](../../proto8/kernels/README.md) | 第三段：照名字找的 kernel 設定（`aos/base-low.json` 等；第二段在這個夾的 `kernels/`，搬過去了） |
| `stack_test.py` | 第二段：層疊實測（不同 kernel 疊、同一種疊兩層、沙箱裡開沙箱、pi `--fake`、跑前跑後比對）；第三段改逗號、加自動遮蔽兩項 |
