這份是試驗 12 的總覽：沙箱、aos-asuser、aos-share 各自要額外裝什麼、在公司 WSL 上有什麼限制，整理自 09、10、11 與實機檢查，沒有新實測。
← [目錄](README.md)

使用者原話（11-18）：「你剛剛跟我說的沙箱、asuser/share這些，麻煩也弄進教學」

出處簡稱：09＝[09](09-aos-sandbox限制資源.md)、10＝[10](10-aos-asuser.md)、11＝[11](11-aos-share.md)、檢＝[沙箱隔離-實機檢查](../沙箱隔離-實機檢查.md)。標「實測」「預期，未實測」「推的」的，照來源原樣，沒有升級。

## 結論

- 這台已經有的：bwrap，所以沙箱擋資料夾、擋網路現在就能用（09、檢，實測）。
- 這台沒有的：s6、`newuidmap`／`newgidmap`、`setfacl`／`getfacl`，以及 `aos-run` 帳號那一整套（10、11）。
- 最省事：`sudo apt install uidmap acl`，補上 aos-asuser 與 aos-share；沙箱自己的記憶體、CPU 時間上限另外要 `s6`（見下表）。
- 這些 sudo 指令都要你自己跑，我沒跑過、裝好後的行為都是預期，未實測（10、11）。

## 要裝什麼

| 功能 | 靠什麼 | 這台有沒有 | 怎麼補 |
|---|---|---|---|
| 沙箱限資料夾與網路 | bwrap | 有 `/usr/bin/bwrap`（10、檢） | 不用補 |
| 沙箱自己的 `mem_mb`／`cpu_s` | `s6-softlimit`（套件 `s6`） | 沒有，會 `CommandMissing`（09、10） | `sudo apt install s6`；裝完要確認 `s6-softlimit` 在 PATH 上，再用 `aos-sandbox --dry-run 設定 true` 看（09「沒驗的」，未實測） |
| 沙箱換成 `aos-run` 帳號 | s6、系統帳號 `aos-run`、sudoers 規則、`/srv/aos-run` | 四樣都沒有（10） | 裝 s6 後跑 repo 的 `setup.sh`，要 sudo；`--s6-bin /usr/bin` 是推的，裝完先 `ls /usr/bin/s6-setuidgid`（10，未實測） |
| aos-asuser（`sub:N`，沙箱的 `"user": "sub:N"` 也靠它） | `newuidmap`／`newgidmap`（套件 `uidmap`） | 沒有；`/etc/subuid` 已有 `100000:65536`（10） | `sudo apt install uidmap` |
| aos-share | `setfacl`／`getfacl`（套件 `acl`）；驗證要換身分，所以也要 `uidmap` | `setfacl` 沒有；ext4 支援 ACL（11） | `sudo apt install acl uidmap` |

一行補完 asuser 與 share：

```sh
sudo apt install uidmap acl
```

`aos-run` 那條另外要（10，未實測）：

```sh
sudo apt install s6
sh $AOS_HOME/py/aos/apps/sandbox/root/setup.sh --s6-bin /usr/bin          # 乾跑，先看要做什麼
sudo sh $AOS_HOME/py/aos/apps/sandbox/root/setup.sh --s6-bin /usr/bin --apply
```

小提醒：`aos-asuser` 的 `--dry-run` 也要 `newuidmap` 在 PATH，沒裝就看不到對照表（10）。`aos-share check` 不靠 getfacl，現在就能用（11，實測）。

## 不裝東西的替代路

| 想限制 | 做法 | 出處與狀態 |
|---|---|---|
| 記憶體、CPU 時間 | 掛 agent 時加 `aos-agent ctl add --limits '{"mem_mb":2048,"cpu_s":600}' …`；daemon 自己 setrlimit，不需 s6 | 09，實測：2048 MB 下 claude 照跑、要 3 GB 的程式 `MemoryError`；`cpu_s=30` 時吃滿 CPU 的程式 30 秒被收（退 152） |
| CPU 百分比 | 外面包 `systemd-run --user --scope -p CPUQuota=50%` | 09，實測可行（6 秒只吃到 2.9 秒 CPU），**不是內建**，沒有設定欄位 |
| CPU 核心數 | 外面包 `taskset -c 0,1` | 09，實測可行，**不是內建** |

寫法要注意（09）：`systemd-run` 要包在 `aos-sandbox` **外面**（沙箱裡沒有 systemd 連線）。`--limits` 只收 `mem_mb cpu_s procs file_mb files mem_total_mb procs_total user`，寫 `net`、`ro` 會 `ArgumentsBad`。`cpu_s` 是每個行程各自累計，不是整隻 agent 的總額。

## WSL 上的限制

| 限制 | 說明 | 出處與狀態 |
|---|---|---|
| 開網路的沙箱 DNS 不通 | `/etc/resolv.conf` 是連到 `/mnt/wsl/resolv.conf` 的連結，沙箱沒綁。要在 `ro` 多寫 `"/mnt/wsl/resolv.conf"`；範例 `cli-tool.json` 沒寫，照抄會連不上 | 檢 C、09，實測 |
| 關網路時 eca-claude 動不了 | `net:false` 時 claude 連不到 API，問話 150 秒沒回，約 3 分鐘後 `CliFailed … EAI_AGAIN`，進冷卻重試。eca-claude 只能開網路，靠 `ro`／`rw` 擋檔案 | 09，實測 |
| `AllowedCPUs` 沒效 | 使用者那層 systemd 沒拿到 cpuset 控制器（只有 `cpu memory pids`），核心數請用 `taskset` | 09，實測 |
| 家目錄 750 | 換成 subuid 後走不進 `~`；`~/aos-home/bin`、工作區、`claude` 都在家目錄底下。沙箱加 `user: sub:N` 真跑 agent 時**推測會失敗，沒實測**。正式用要放 `/srv` 之類，或自己決定給 `~` 加一條 `u:100004:x`。`aos-share` 分享 `~` 底下的東西會警告且讀不到（預期） | 10、11；`/srv` 的 `install -d` 指令是 11 標的「推的」 |
| `setup.sh` 照 Arch 寫 | 預設 `--s6-bin` 是 `~/code/try/sandbox/s6-root/bin`（這台沒有）；註解叫人用 AUR；`useradd --shell /usr/bin/nologin`，Ubuntu 的 nologin 在 `/usr/sbin/nologin` | 10 |
| aos-agent 說「daemon 沒活著」要等 | WSL2 的 pid 命名空間讓「daemon 沒活著就馬上說」失效，要乾等 30 秒 | 使用者 11-18 裁：維持現狀（不在上面四份來源裡，由頂層指示補入） |

## 跟 WSL 無關但會踩到的

| 項目 | 說明 | 出處與狀態 |
|---|---|---|
| 設定檔寫壞整個不關 | 型別寫錯（例 `"net": "no"`）只印一行 `aos-sandbox: warning: sandbox config ignored, running unsandboxed`，程式照跑、看得到 `~/.ssh`。要看 stderr 有沒有那行。這是使用者 11-12 裁的規則 | 檢 F、09，實測 |
| 起手範本的沙箱碰得到 daemon 的 stack | 範本的 `-w .` 讓樹（含 `.stack/`）成為工作區：實測沙箱能 `aos-daemon-ctl ls`、對 `ann` 說話、往 llm kernel 的 `requests/` 寫檔。**尚未裁怎麼處理**。目前教學的做法是工作區放樹外面（例 `~/aos-ws`） | 檢 A、09 |
| 不認得的鍵直接忽略 | 例 `cpu_percent` 寫了等於沒寫，連 warning 都沒有，容易以為有限制 | 09，實測 |
| `net:true` 碰得到主機 127.0.0.1 | 開網路就是跟主機共用網路，連主機只聽 127.0.0.1 的服務也碰得到 | 檢 B、09，實測 |

來源之間的矛盾：沒有發現。

## 裝好之後去哪看步驟

| 想做的 | 看哪份、哪一節 |
|---|---|
| 沙箱資料夾、網路、記憶體、CPU 時間、CPU 百分比與核心數 | [09](09-aos-sandbox限制資源.md)「步驟」與「四種一起上」；裝了 s6 後的驗法在「沒驗的」 |
| 關網路時會怎樣 | 09「關網路時 eca-claude 怎樣」 |
| aos-asuser 換身分、`aos-run` 帳號 | [10](10-aos-asuser.md)「要使用者自己用 sudo 跑的」與「裝好之後預期的操作」 |
| aos-share 套樣板、體檢、收回 | [11](11-aos-share.md)「裝好後的主線」 |
| 沙箱隔離的整體檢查（A～F） | [沙箱隔離-實機檢查](../沙箱隔離-實機檢查.md) |
