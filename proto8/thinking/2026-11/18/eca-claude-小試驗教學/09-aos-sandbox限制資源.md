這份是試驗 09 的照打教學：把一隻 eca-claude agent 關進 aos-sandbox，限制它能碰的資料夾、網路、記憶體、CPU 百分比與核心數（公司 WSL 實跑，HEAD `71df48e88`）。

← [目錄](README.md)｜先讀過：[沙箱隔離-實機檢查](../沙箱隔離-實機檢查.md)（這份不重做它驗過的）

使用者原話：「9.用aos-sandbox啟動一個agent，限制其只能使用指定%數的CPU、指定數量的CPU核心、指定只能存取特定資料夾、限制網路/mem」

## 結論

| 限制 | aos-sandbox 內建？ | 這台實測 |
|---|---|---|
| 只能碰特定資料夾 | **有**（`ro`／`rw`） | 通：清單外的夾 `No such file or directory`，`ro` 讀得到寫不進（`read-only file system`），`rw` 寫得進、主機上看得到 |
| 網路開／關 | **有**（`net`） | 開：要多綁一個 `/mnt/wsl/resolv.conf` 才查得到 DNS，之後 claude 照常回答、curl 200。關：**eca-claude 動不了**（claude 自己要連 API） |
| 記憶體上限 | 有欄位 `mem_mb`，但要 s6 → 這台 `CommandMissing` | 改用 daemon 的 `--limits '{"mem_mb":…}'`（daemon 自己 setrlimit、不用 s6）：通，claude 在 2048 MB 下照跑，要 3 GB 的程式 `MemoryError` |
| CPU 時間上限 | 有欄位 `cpu_s`，同樣要 s6 | 同上改用 `--limits`：通，吃滿 CPU 的程式 30 秒被收（退 152） |
| CPU 百分比 | **沒有** | 變通：外面包 `systemd-run --user --scope -p CPUQuota=50%`：通（6 秒只吃到 2.9 秒 CPU） |
| CPU 核心數 | **沒有** | 變通：外面包 `taskset -c 0,1`：通（只看得到 0、1 號核心）。`AllowedCPUs=` 在這台**沒效** |

一句話：資料夾和網路靠 aos-sandbox；記憶體、CPU 時間靠 `aos-agent ctl add --limits`；CPU 百分比與核心數目前只能在 `_entry` 最前面自己包 `systemd-run`＋`taskset`（不是內建）。

## 步驟

前提：照 [start-eca](../../../../templates/start-eca/README.md) 抄好樹 `~/aos-home`、`claude` 登入過。每個視窗先 `cd ~/aos-home && source env.sh`。

**1. 工作區放在樹外面**（樹裡有 daemon 的 `.stack/`，工作區包著它＝沙箱碰得到 daemon，見實機檢查 A）

```sh
mkdir -p ~/aos-ws ~/data/ref && echo shared-ro > ~/data/ref/r.txt
```

會看到：沒有輸出。

**2. 在 agent 定義夾寫沙箱設定**

```sh
cat > agents/ann/sandbox.json <<'EOF'
{"commands": ["aos-exec", "aos-loop", "aos-eca-turn", "aos-mcp", "aos-tools", "aos-post", "claude"],
 "ro": [{"$env": "AOS_CLOCK"}, {"$env": "HOME", "$path": "/data/ref"}, "/mnt/wsl/resolv.conf"],
 "rw": [{"$env": "AOS_WS"}, {"$env": "AOS_STACK"},
        {"$env": "HOME", "$path": "/.claude"}, {"$env": "HOME", "$path": "/.claude.json"}],
 "env": ["PATH", "HOME", "TERM", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "PYTHONDONTWRITEBYTECODE", "PYTHONIOENCODING",
         "AOS_ENTRY", "AOS_WS", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO", "AOS_HOME", "AOS_CLOCK"],
 "net": true}
EOF
```

每條在做什麼：`commands` 的 aos 命令會把整個 `$AOS_HOME` 唯讀綁進來；`claude` 是 `~/.local/bin` 裡的連結，aos-sandbox 自己會把它指到的 `~/.local/share/claude/versions` 一起綁。`AOS_CLOCK` 不綁的話 stderr 會一直印 `no clock file …`。`/mnt/wsl/resolv.conf` 是這台 DNS 設定真正在的地方（`/etc/resolv.conf` 只是連結），不綁就查不到名字。`~/.claude`、`~/.claude.json` 是 claude 的登入檔，要可寫。

卡點：設定寫錯型別（例 `"net": "no"`）不會報錯、只印一行 `aos-sandbox: warning: sandbox config ignored, running unsandboxed`，**整個不關**；不認得的 key（例 `cpu_percent`）連 warning 都沒有、直接忽略。

**3. 讓 agent 從沙箱裡起**（daemon 用 aos-exec 在定義夾裡跑 `_entry`，所以 `sandbox.json` 寫相對路徑就好）

```sh
cp agents/ann/_entry agents/ann/_entry.orig
echo '["aos-sandbox", "sandbox.json", "aos-loop", "loop.json"]' > agents/ann/_entry
```

**4. 起根**（視窗 A，前景）

```sh
aos-tree-start root
```

會看到：`_clock`、`_sweeper` 兩行 `"phase": "running"`。

**5. 掛上 agent，順便給記憶體與 CPU 時間上限**（視窗 B）

```sh
aos-agent -d .stack ctl add -w ~/aos-ws --limits '{"mem_mb":2048,"cpu_s":600}' agents/ann
grep -E "cpu time|address space" /proc/$(aos-daemon-ctl -d .stack ls | awk '/^ann/{print $3}')/limits
```

會看到：`Max cpu time 600 601 seconds`、`Max address space 2147483648 2147483648 bytes`。`ps` 看那個 pid 是 `/usr/bin/bwrap …`＝真的在沙箱裡。

卡點：`--limits` 只收 `mem_mb cpu_s procs file_mb files mem_total_mb procs_total user`，寫 `net`、`ro` 會 `ArgumentsBad unknown key net`——它不是沙箱設定，是 daemon 的 rlimit（說明寫「the aos-sandbox keys」容易誤會）。

**6. 驗資料夾與網路**

```sh
aos-agent -d .stack --target ann say 'Run with the Bash tool, reply with raw outputs: cat ~/secret.txt; cat ~/data/ref/r.txt; echo x > ~/data/ref/w.txt; echo ok > ~/aos-ws/out.txt; curl -sS -m 8 -o /dev/null -w %{http_code} https://example.com'
aos-agent -d .stack --target ann listen --timeout-s 180
```

會看到（實跑節錄）：清單外的檔 `No such file or directory`；`shared-ro`；`read-only file system: …/w.txt`；`ok`（主機上 `~/aos-ws/out.txt` 也在）；`200`。

**7. 驗上限真的會擋**

叫它跑 `python3 -c "x=bytearray(3*1024**3)"` → `MemoryError`、`rc=1`。把 `cpu_s` 改 30 重掛（`ctl rm ann` 再 add），叫它跑 `timeout 90 python3 -c "while True: pass"` → `rc=152 after 30s`。

卡點：`cpu_s` 是**每個行程各自累計**的 CPU 時間，不是整隻 agent 的總額，也不是每秒百分比。常駐的 `aos-loop` 自己也算在內，設太小它遲早被收（實測一隻閒著的 `aos-loop` 跑 17 分鐘約用 1 秒 CPU，600 很寬；會不會撞線是推論，沒等到）。

## 四種一起上（實跑過）

`_entry` 換成這行（`systemd-run` 與 `taskset` 都會 exec 成下一支，daemon 表上的 pid 仍是 bwrap）：

```sh
echo '["systemd-run", "--user", "--scope", "--quiet", "--collect", "--unit", "aos-ann", "-p", "CPUQuota=50%", "-p", "MemoryMax=2G", "-p", "MemorySwapMax=0", "--", "taskset", "-c", "0,1", "aos-sandbox", "sandbox.json", "aos-loop", "loop.json"]' > agents/ann/_entry
aos-agent -d .stack ctl rm ann && aos-agent -d .stack ctl add -w ~/aos-ws --limits '{"mem_mb":2048}' agents/ann
P=$(aos-daemon-ctl -d .stack ls | awk '/^ann/{print $3}'); cat /proc/$P/cgroup; taskset -p $P
systemctl --user show aos-ann.scope -p CPUQuotaPerSecUSec -p MemoryMax
```

會看到：`0::/user.slice/…/app.slice/aos-ann.scope`、`affinity mask: 3`、`CPUQuotaPerSecUSec=500ms`、`MemoryMax=2147483648`。叫 agent 跑 6 秒的空轉迴圈：`[0, 1]`、`cpu 2.9 of 6s wall`；同一輪清單外的檔照樣讀不到、curl 照樣 200，claude 照常回答。`aos-daemon-ctl -d .stack shutdown` 之後 scope 變 `inactive`。

讀法：`CPUQuota=50%`＝全部加起來最多半顆核心；要「兩顆核心各跑滿」寫 `CPUQuota=200%`＋`taskset -c 0,1`。`MemoryMax` 是整隻 agent（含 claude 與它開的所有子行程）的總額，比 `mem_mb`（每個行程各自）更像「這隻 agent 最多用多少」；暫存夾實測 300M 上限下要 500M 的程式被收（退 143）。

卡點：`--unit` 名字固定，同名 scope 還在時起不來（`--collect` 讓它行程一走就清）。`-p AllowedCPUs=0-1` 在這台沒效（使用者那層的 systemd 沒拿到 cpuset 控制器，只有 `cpu memory pids`），核心數請用 `taskset`。沙箱裡沒有 systemd 的連線，所以 `systemd-run` 一定要包在 aos-sandbox **外面**。

## 關網路時 eca-claude 怎樣

`net` 改 `false` 重起：agent 照樣 running，但問它話 150 秒沒回；約 3 分鐘後 `retry.json` 記 `CliFailed … Can't reach the API server — check your internet or DNS (EAI_AGAIN)`，接著進冷卻、自己重試，`ctl stop` 要等它那輪結束（`ctl rm` 期間報 `SessionBad busy answering`）。結論：**eca-claude 這種腦在外面的 agent 不能 `net:false`**；能做的只有開網路、靠 `ro`／`rw` 擋檔案。`net:true` 等於跟主機共用網路，連主機 127.0.0.1 的服務也碰得到（實機檢查 B）。

## 發現的問題／目前做不到的（要開線補的）

1. **CPU 百分比、核心數沒有內建欄位**。若要內建，建議加在 aos-sandbox 的設定（例 `cpu_percent`→前面接 `systemd-run --user --scope -p CPUQuota=`、`cpus`→`taskset -c` 或 bwrap 前 `sched_setaffinity`），或 daemon 的 cgroup 路（`cgroup.cpp` 現在只開 `+memory +pids`，可加 `+cpu` 寫 `cpu.max`）。只是建議，沒改程式。
2. **aos-sandbox 的 `mem_mb`、`cpu_s` 綁死 s6**，這台沒有就 `CommandMissing`；同樣的事 daemon 已經用 setrlimit 做了。aos-sandbox 可以改成沒有 s6 時退用 `prlimit` 或自己 setrlimit。
3. **不認得的 key 默默忽略**（`cpu_percent` 寫了等於沒寫，連 warning 都沒有），容易以為有限制。
4. **`net` 只有全開全關**，不能「只准連 API」；`net:true` 碰得到主機 127.0.0.1。
5. **這台 DNS 要手動綁 `/mnt/wsl/resolv.conf`**，範例 `cli-tool.json` 沒寫，照抄會連不上。
6. `--limits` 的說明「the aos-sandbox keys」跟實際（只收 rlimit 那幾個）對不上。
7. 起手範本的 `-w .` 會把 daemon 的 stack 包進工作區；這份改用樹外的 `~/aos-ws` 避開。

## 沒驗的

- 裝了 s6 之後 aos-sandbox 自己的 `mem_mb`、`cpu_s`：要有 `s6-softlimit` 在 PATH 上（不用 root，自己編進 `~/` 也行），再跑 `aos-sandbox --dry-run 設定 true` 看最前面是不是 `s6-softlimit -a … -t …`，然後照第 7 步驗。
- daemon 的 cgroup 路（`daemon.json` 寫 `"cgroup": "auto"`、整棵樹用 `systemd-run --user --scope -p Delegate=yes -- aos-tree-start root` 起，`--limits` 寫 `mem_total_mb`、`procs_total`）：這份沒跑。
- 沙箱裡 agent 自己的 aos 工具（`self_ctl`、`mailbox_send` 這些要碰 daemon 的）：沒綁 `AOS_DAEMON`，多半用不了，沒試。
