把 pi coding agent 關進 aos-daemon 的一隻 proc、腦只經 `/llm` 的正式版（最小方案第 3 節 #3～#6，11-27 家機）：llm kernel（可以疊）、`/llm/relay` 小轉接、起 pi 的小工具 `aos-pi`、驗收腳本與跟 srt、Codex 的對照；配上新的 aos-daemon（每隻自己一份 IPC namespace、擋 vsock）後，`--fake` 兩種疊法全過。

# pi-sandbox（11-27，家機 6.18）

← [proto9](../README.md)｜方案：最小方案報告（家機 `~/.aos/scratch/proto9-minplan-1127/report.md`，不進 git）第 1、3、5、7 節｜原型：[pi-sandbox-1127](../experiments/pi-sandbox-1127/README.md)（這裡是它搬正，原型夾沒動）｜使用者定的：[pi沙箱-1127](../../proto8/thinking/2026-11/27/pi沙箱-1127.md) 第 1～8 條與「天空的佈局」｜daemon：[aos-daemon](../cpp/aos-daemon/README.md)（這件的 #1、#2 與 vsock 在那邊改，同一批交）｜對照表：[compare.md](compare.md)

我自己定的標【擬】。

## 結論先講

- **pi 在裡面會怎樣**：它是一個住在 `/home/pi` 的普通使用者，工作夾在 `~/work`。在 `~/work` 與 `/tmp` 讀、寫、改檔、跑 shell 都正常；寫別的地方得到 `Read-only file system`；找你的 `~/.ssh`、repo 得到「沒有這個檔」；上網失敗；改 `~/work/.git` 失敗；想事情只能經 `/llm`，被數次數、被限模型，用完就拿到 429。
- **四個工具在 `~/work` 都通**：`--fake` 跑兩次、真模型（`chatgpt-gpt-6-luna-nothink`）跑一次，都是 read、write、edit、bash 全過、`stopReason stop`。真模型那次 5 次請求、10.8 秒。
- **kernel 疊 kernel 對得上**：疊兩隻時，pi 看到幾則回覆＝上面那隻帳本幾行＝下面那隻帳本幾行（5＝5＝5）；上面那隻用完時 pi 敲了 4 次門（它自己會重試 3 次），全被上面拒，下面那隻 **0 次**。
- **驗收的必過項全過**（配上新 daemon 之後）。第一次跑時（舊 daemon）有三項沒擋：SysV 共享記憶體、POSIX 訊息佇列（當時沒開 IPC namespace）與 **vsock**（新發現：`net none` 只隔開 IP 網路，vsock 不分 network namespace，pi 的 shell 連得到外面在 vsock 上聽的程式）。aos-daemon 補上每隻自己一份 IPC namespace，內建擋單也加了 `socket(AF_VSOCK)`（srt、Codex 也這樣擋）。重跑之後三項都擋住了。
- **跑前跑後沒留東西**：行程、掛載、cgroup、systemd 單元、SysV、mqueue 每次都比對過，乾淨。
- **跟 srt、Codex 比**：檔案這塊 aos-pi 最緊（srt、Codex 照設計整台主機唯讀看得到，`~/.ssh` 讀得到）；IPC 現在 aos-pi 與 Codex 擋、srt 沒擋；vsock 三邊都擋；開巢狀 user namespace 只有 srt 擋。表在 [compare.md](compare.md)。

## 怎麼跑

```
cd proto9/pi-sandbox
python3 aos_pi.py ~/some/project "Fix the failing test" --model chatgpt-gpt-6-luna-nothink        # 真的：外面要有 LiteLLM 127.0.0.1:4000
python3 aos_pi.py ~/some/project "say hi" --model x --fake                                          # 不花錢：腦照劇本答
python3 aos_pi.py ~/some/project "..." --model M --stack 2 --limit 10                               # 疊兩隻 llm kernel
python3 aos_pi.py ~/some/project "and now add a test" --model M --continue                          # 接著上一次的對話講
python3 accept.py --fake                                                                            # 驗收（約 10 秒，一隻、疊兩隻都跑）
python3 accept.py --model chatgpt-gpt-6-luna-nothink --limit 10 --stacks 2                          # 驗收叫真模型（最多 10 次）
python3 compare.py --out /tmp/table.md                                                              # 同一支 probe 放進 aos-pi、srt、Codex
```

`aos-pi`（指令名照慣例是 `aos-pi`，檔是 `aos_pi.py`；這版沒做指令入口【擬】）做的事：

1. 起一台沒有 init 的 aos-daemon（`daemon.json` 是 `{}`），之後全部從外面寫它的 `ctl`。
2. 起 llm kernel：一隻（`llm-0`，有網路，上游是 LiteLLM），或 `--stack N` 疊 N 隻（`llm-0` 有網路；`llm-1`…沒網路，上游是下面那隻吐的夾）。pi 看到的是最上面那隻。
3. 照標準佈局起 pi：`pi --mode json --thinking off --provider aosllm --model M "<交代>"`，前面套 `/llm/relay`。
4. 等 pi 做完。**判做完看 json 事件**：最後一則 assistant 訊息的 `stopReason` 是 `stop`、而且有 `agent_settled` 才算 DONE；不看退出碼（pi 被拒光了也退 0）。
5. 印結果：DONE／NOT DONE、用了哪些工具、最後一句、每隻 kernel 這次收了幾次、還剩多少額度、pi 那隻的 `locks`、daemon 的警告（`status` 的 `landlock_warning` 與 stderr 的 warning 行）。
6. 收掉：對 daemon 送 SIGTERM（沒有 init 時它把底下全部 SIGKILL）。

參數：`--limit`（pi 能用幾次，預設 20）、`--stack`、`--lower-limit`（下面幾隻的額度，預設 `--limit` 的兩倍【擬】）、`--name`（沙箱名，預設 `pi`）、`--sandbox-root`（預設 `~/.aos/sandbox`）、`--continue`、`--git-rw`（不把 `.git` 蓋成唯讀）、`--timeout`（預設 600 秒）、`--fake`／`--fake-script`、`--upstream`、`--daemon`、`--node`／`--pi`。沒做完退 1、stderr 一行 `aos-pi: error: NotDone …`。

要有：`proto9/cpp/aos-daemon/build/bin/aos-daemon`（`accept.py` 找不到會先 `make`）；fnm 的 node v24.14.1 與 `@earendil-works/pi-coding-agent` 1.5.2；user namespace、subuid、systemd --user（daemon 本來就要的）。

## 天空每一筆（`aos_pi.py` 的 `pi_sky()`）

| pi 看到的 | 實體 | 唯讀／可寫 | 為什麼 |
|---|---|---|---|
| `/` | daemon 給的空 tmpfs | 唯讀 | 根是管它的那一方（aos-pi）的地方 |
| `/.aos/interfaces/aos/description` | `<run>/sky/.aos/` | 唯讀 | 管它的那一方的宣告，一行英文，見下 |
| `/usr` | 主機的 `/usr` | 唯讀 | node 要的 libc、bash、python3、curl |
| `/bin`、`/lib`、`/lib64` | 照主機：是 symlink 就放同樣的 symlink（家機三個都是指到 `usr/…`），是夾就唯讀綁進來 | 唯讀 | 動態連結的載入器、`#!/bin/sh` |
| `/dev` | daemon 的 `dev`（null、zero、full、random、urandom） | 唯讀 | 子行程的 stdin／stdout |
| `/etc/passwd` | `<run>/sky/passwd`，一行 `pi:x:0:0:pi:/home/pi:/bin/bash` | 唯讀 | 讓 `whoami`、git 知道「我是 pi、家在 `/home/pi`」；`/etc` 其他都沒有 |
| `/opt/node/bin/node` | fnm 的 node（只綁這一個檔） | 唯讀 | pi 的執行環境 |
| `/opt/pi` | pi 的套件夾 | 唯讀 | pi 本身 |
| `/tmp` | tmpfs 256m | 可寫 | pi 的 bash 工具長輸出會存暫存檔 |
| `/llm` | 最上面那隻 kernel 吐的夾 | 唯讀 | 腦的唯一出口：`sock`、`relay`、`status`、`.aos/interfaces/aos/llm/` |
| `/home/pi` | 外面 `~/.aos/sandbox/<名字>/home/` | 可寫 | 家目錄；pi 的 `~/.pi`（設定、對話紀錄）在這；**不自動清**，要清自己刪 |
| `/home/pi/work` | 你給的工作夾（真檔） | 可寫 | pi 動的就是你的檔 |
| `/home/pi/work/.git` | 工作夾的 `.git` | 唯讀 | 蓋在上面的一層：擋「pi 放 git hook、你下次 commit 在外面執行」；`--git-rw` 關掉；工作夾沒有 `.git` 就不放 |

另外（proc 設定，不是天空）：`HOME=/home/pi`、`USER=pi`、`PATH=/opt/node/bin:/usr/bin:/bin`、`PI_OFFLINE=1` 等三個、`cwd /home/pi/work`、`net none`、`memory.max 2G`、`pids.max 512`、其他鎖照 daemon 預設（Landlock 自己一個、內建 seccomp、沒有特權、`no_new_privs`）。**不給 `/proc`**（給了讀得到外面整台的連線表）。帳號是你本人（daemon 裡的 uid 0），pi 寫的檔在外面就是你的檔。

每次起來 aos-pi 會**重寫** `~/.pi/agent/models.json`、`settings.json`（provider 指到 `http://127.0.0.1:8787/v1`、假金鑰、`retry.baseDelayMs 500`）【擬】；其他 pi 自己寫的（`auth.json`、`sessions/`）留著。`<run>` 是 `~/.aos/sandbox/<名字>/run/`：這次的設定與 log，留到下一次開工才清【擬】。

## `.aos` 宣告

| 位置（pi 看到的） | 誰寫 | 內容 |
|---|---|---|
| `/.aos/interfaces/aos/description` | aos-pi | `/ belongs to aos-pi, the side that runs you (read-only). Only your home /home/pi (your work dir is ~/work, its .git is read-only) and /tmp are writable. There is no network: the model is reached only through /llm (see /llm/.aos/interfaces/aos/llm).` |
| `/llm/.aos/interfaces/aos/llm/kind` | llm kernel 起來時自己寫 | `socket` |
| `…/path` | 同上 | `sock`（以 `/llm` 起算） |
| `…/protocol` | 同上 | `http/1.1` |
| `…/api` | 同上 | `openai-completions`（`POST <base>/chat/completions`） |
| `…/base` | 同上 | `/v1` |
| `…/models` | 同上 | 收的模型，一行一個；別的 403 |
| `…/status` | 同上 | `status`（狀態檔的位置） |
| `…/relay` | 同上 | 第一個字是轉接的位置（`relay`），後面是用法：`node <dir>/relay --llm <dir> --port N [-- CMD ARGS...]`【擬：一行裡「位置＋用法」】 |
| `/llm/.aos/interfaces/aos/description` | 同上 | `llm kernel: the only way to the model here; counts and caps requests` |
| `~/.aos` | 沒人寫 | 沒有＝pi 沒宣告任何東西，合法 |

`/llm/status`（資訊，不是宣告）：`requests_used`、`requests_limit`、`models`、`upstream`（`fake`／網址／`kernel <夾>`）。

## llm kernel（`llm_kernel.py`，只用 Python 標準庫）

- 在它吐的夾裡開 `sock`（HTTP over unix socket），寫上面那份宣告、`status`，把 `relay.js` 放成 `relay`（夾裡本來就有、又沒有來源時留著原本的）。
- **上游兩種**：`--upstream http(s)://…/v1`（LiteLLM），或 `--upstream /某個夾`＝另一個有 `aos/llm` 宣告的夾：讀它的 `kind`、`protocol`、`api`、`path`、`base`（每次請求都重讀，下面那隻重起也接得上【擬】），連它的 socket。下面那隻不收某個模型時，起來就 stderr 警告一行。這樣 kernel 吃 `/llm`、吐 `/llm`，可以一直疊。
- 規矩照原型【擬】：模型不在名單 → 403、不算次；用完 → 429、不送出去；送出去**之前**先把次數加一寫進額度檔（中途當掉也算）；`--fake` 照劇本答、不算次、但到上限照樣拒。帳本 `ledger.jsonl` 一次請求一行（`sent`／`fake`／`refused`＋原因／`upstream_error`），記對方在 daemon 那層的 PID。
- 上面那隻轉給下面、下面回 429 或 403 時，上面那隻已經算了一次（它送出去了）【擬】。
- 疊的時候：最下面那隻 `net host`、其他 `net none`；下面那隻吐的夾唯讀綁進上面那隻的 `/up`。上面那隻的天空裡只有自己的程式、自己的夾、`/up`。
- 輸出照三扇門：stderr 只有 `llm-kernel: error: 代號 原因` 與 `llm-kernel: warning: …`；起來的那行在 stdout。

## `/llm/relay`（`relay.js`）

原型的 `launch.mjs` 搬過來，改成由 kernel 放進它吐的夾：pi 只會講「HTTP 到某個網址」，relay 在 pi 自己的 loopback（`net none` 每隻一個）聽 8787、每個連線接到宣告裡的 socket，再把 pi 當孩子起起來、用它的退出碼結束。它讀 `/llm/.aos/interfaces/aos/llm/` 找 socket，`kind`／`protocol`／`api` 不對就拒。寫成 CommonJS，因為放進夾裡時沒有副檔名，node 把沒有副檔名的檔當 CommonJS 跑。換別的「只會講 HTTP」的 agent 也能用：`node /llm/relay --llm /llm --port N -- 它的指令`。備案是 socat（找輪子報告第 4 件）。

## 驗收（`accept.py`、`probe.sh`）

`accept.py` 一個模式做這些（`--stacks 1,2` 兩個模式都跑）：

1. 做一個小專案（`NOTES.md`、`config.ini`、`test_app.py`，`git init` 後 commit 一次）。
2. 在外面擺好要試著碰的東西：一個外面的夾、一個 unix socket（路徑）、一個 abstract socket、一個 vsock 監聽、一塊 SysV 共享記憶體、一個 POSIX 訊息佇列、自己的 PID。
3. 起 daemon 與 kernel，在**跟 pi 一樣的天空**（多綁一個 `/opt/probe`）跑 `probe.sh`，不叫模型；每項 `want`／`got` 比對。
4. pi 做四步小事（read `NOTES.md`、write `hello.txt`、edit `config.ini`、bash 跑 `python3 test_app.py`），檢查工作夾的結果與 `stopReason`。
5. 對帳：pi 的 assistant 訊息數＝最上面那隻帳本行數；每隻送出去的＝下面那隻帳本行數。
6. 把最上面那隻的額度檔寫成用完，再叫 pi 一次：pi 要 NOT DONE、最上面那隻全拒、下面每隻 0 次。
7. 收掉後比對：這支 daemon 的行程、我們的 kernel／relay／pi／probe、run 夾底下的掛載、我們那幾個 cgroup 夾與 systemd 單元、SysV、`/dev/mqueue`（只看「多出來的」，因為旁邊可能有別人在跑 aos-daemon 的測試）。

`probe.sh` 不知道我們的佈局，路徑全從環境變數給（`PROBE_WORK`、`PROBE_GIT`、`PROBE_RO`、`PROBE_OUTSIDE`、`PROBE_SECRETS`、`PROBE_LLM_SOCK`…，說明在檔頭），所以同一支也拿去 srt、Codex 跑。測項照 Codex（`codex-rs/linux-sandbox` 的 `tests/suite/sandbox.rs`、`seccomp.rs`、`linux_run_main_tests.rs`）與 srt（`test/sandbox/` 的 `integration`、`mandatory-deny-paths`、`write-through-links`、`pid-namespace-isolation`、`seccomp-filter`、`seccomp-vsock-block`、`linux-nested-userns`）的測試照意思重寫，**沒抄程式碼**，每一項行尾註明出處（檔名＋測試名）；兩邊都沒有的（讀 `/etc/shadow`、TIOCSTI、SysV、mqueue、abstract socket、ptrace 兄弟）註 `own`。

必過項（`accept.py` 的 `MUST`，任務書列的）：寫工作夾要通；寫 `/`、`/.aos`、`/llm`、`/usr`、`/etc`、外面的夾、`.git`（hook、新檔、config）、經 symlink 寫出去要擋；讀 `~/.ssh`、repo、`~/.pi/agent/auth.json`、工作夾在外面的真路徑、`/etc/shadow`、經 symlink 讀要擋；沒有 `/proc`；連外網（DNS、https、IP、`/dev/tcp`、ping、ssh、vsock）要擋；繞過 `/llm`（外面的 LiteLLM、api.anthropic.com）要擋、經 `/llm/sock` 要通、不准的模型要被拒；外面的 unix socket、abstract socket、SysV、mqueue 要擋；碰外面的 PID 要擋。其他（hardlink、mknod、setuid、ptrace、`process_vm_writev`、io_uring、TIOCSTI、`no_new_privs`、特權、巢狀 user namespace、mount、umount）照印、記成 info、不算失敗。

### 結果（11-27 家機）

| 那次 | 結果 |
|---|---|
| `accept.py --fake`，新 daemon（main-alt 合進後重跑） | `SUMMARY ok`：一隻、疊兩隻的必過項全過，`net_vsock` 是 `socket(AF_VSOCK): EPERM`，`ipc_sysv_shm` 是 `shmat: EINVAL`，`ipc_posix_mq` 是 `mq_open: ENOENT`；`cleanup: ok` |
| `accept.py --fake` 第 1 次，舊 daemon（約 10 秒） | `SUMMARY FAILED 6`：一隻、疊兩隻各三項——`net_vsock`、`ipc_sysv_shm`、`ipc_posix_mq`；其他必過項全過；四個工具 PASS、DONE；對帳 MATCH；用完時下面 0 次；`cleanup: ok` |
| `accept.py --fake` 第 2 次，舊 daemon | 同上，一模一樣 |
| `accept.py --model chatgpt-gpt-6-luna-nothink --limit 10 --stacks 2`（真模型一次，舊 daemon） | `SUMMARY FAILED 3`（同樣三項）；pi 5 次請求、10.8 秒、四個工具全過，最後一句 `Created hello.txt with pinecone and changed config.ini to level = high. python3 test_app.py output: ALL TESTS PASSED`；`llm-1` 送 5＝`llm-0` 收 5（都 200，token 約 2.7k～2.9k 一次、合計約 1.4 萬）；用完時 pi 敲 4 次、`llm-0` 0 次；`cleanup: ok` |

info 那幾項在 aos-pi 都擋住，只有 `unshare_userns` 是通的（見下）。

## 發現（給 aos-daemon）

1. **vsock 穿過 `net none`**（必過項；**已補**，aos-daemon 內建擋單加了這條【擬】，見 [vs-codex-srt](../cpp/aos-daemon/vs-codex-srt.md)）：Linux 的 vsock 不分 network namespace，家機有 `vsock_loopback` 模組，外面 `bind((VMADDR_CID_ANY, port))` 監聽，沙箱裡 `connect((1, port))` 就連上了。外面有在 vsock 上聽的服務（VM 管理程式之類）時，pi 的 shell 碰得到它們。srt（`seccomp-vsock-block`）與 Codex（`seccomp.rs` 的 `deny_vsock`）都在 seccomp 擋 `socket(AF_VSOCK)`。做法：`socket`／`socketpair` 的第一個參數是 `AF_VSOCK` 就回 EPERM。
2. **SysV、mqueue**：舊 daemon 沒擋；新 daemon 每隻自己一份 IPC namespace 之後擋住了。
3. **巢狀 user namespace 開得起來**（info）：`unshare(CLONE_NEWUSER)` 在 aos-pi、Codex 裡都成功，srt 擋。aos-daemon README 寫明內建擋單「不擋開 namespace 與 mount」（為了以後疊 daemon）。開了只是在自己的天空裡再分一層，碰不到外面；但它讓核心裡更多程式碼被沙箱碰到（核心的洞那條，最小方案第 4 節第 10 條）。要不要擋由使用者定。

## 漏給 Linux 的（照最小方案第 4 節，這版都沒變）

1. 工作夾是真檔：pi 能把 `.git` 以外的檔全改壞或刪掉；救回來靠 git。
2. pi 留在工作夾的檔（Makefile、`package.json` 的 script、`AGENTS.md`）之後被你在外面執行或被別的 agent 讀：沙箱管不到，要你自己看 diff。
3. pi 讀得到的都會經 `/llm` 送到模型供應商：祕密不要放進工作夾。
4. 磁碟寫滿：工作夾與家目錄沒有配額；`/tmp` 有 256m 上限。
5. CPU 與磁碟讀寫速度不設上限；記憶體 2G、行程數 512 有。
6. 看得到還有誰在跑：照 PID 知道 daemon 與 kernel 在不在、讀它們的 nice（只有一隻 pi 時沒差）。
7. 同一個帳號：pi 能調小 daemon 能開的檔案數、改 llm kernel 的優先權（家機擋得住訊號，`ptrace` 也擋住了，見 probe）。
8. 跑什麼程式不管：`/usr` 整個唯讀放進去，curl、python、gcc 都跑得了，只是沒網路。
9. 主機名看得到；時間、快取這類側通道不管。
10. Linux 核心本身的洞：不是虛擬機的沙箱都一樣。
11. llm kernel（最下面那隻）是唯一有網路的：它讀得到 pi 送的一切，要寫得小、上游寫死。
12. 家目錄跨次留著：pi 能改自己的 `~/.pi`，影響下一次開工（`models.json`、`settings.json` 每次會被 aos-pi 重寫，其他的留著）。

## 跟最小方案不一樣的地方

- `relay` 那行宣告寫成「位置＋用法」一行（方案只說「宣告多一行說它在哪、怎麼用」）【擬】。
- `relay.js` 改成 CommonJS（放進夾裡沒副檔名），參數多收「不帶 `--`＝只轉接、不起程式」。
- `/bin`、`/lib`、`/lib64` 照主機：symlink 就放 symlink、夾就唯讀綁（方案寫「唯讀」；家機三個都是 symlink，公司 WSL 沒試）。
- 驗收多了 vsock、abstract socket、經 symlink 寫出去、`.git` 新檔等測項（抄 Codex、srt 的）。
- 疊兩隻時「用完」是直接把最上面那隻的額度檔寫成用完再叫 pi（不靠剛好用光），這樣真模型那次也不多花錢。
- pi 的 `retry.baseDelayMs` 設 500（預設 2000），額度用完時重試 3 次只要約 3.5 秒【擬】。
- 方案說的「兩台各跑一次」：只跑了家機；公司 WSL 沒跑。
- `aos-daemon` 那邊的改動與 `make test`、`channels-1127` 重跑，記在 [aos-daemon README](../cpp/aos-daemon/README.md)。

## 我擬的（【擬】）

- 檔名與指令名：`aos_pi.py`（指令名 aos-pi，沒做入口）、`llm_kernel.py`、`relay.js`、`fake_brain.py`、`daemon_ctl.py`；沙箱名預設 `pi`、根預設 `~/.aos/sandbox`。
- `/.aos/interfaces/aos/description` 的英文句子；`/etc/passwd` 那一行（uid 0、shell `/bin/bash`）。
- `--lower-limit` 預設 `--limit` 的兩倍；額度用完的規矩、上面算了下面拒的那次照算。
- 每次重寫 pi 的 `models.json`、`settings.json`；`<run>` 夾留到下一次才清；同名沙箱同時跑兩次沒擋（會撞）。
- 驗收的必過與 info 怎麼分。

## 沒驗的

- 公司 WSL（Linux 6.6）：都沒跑。
- 真模型那次是在舊 daemon 上跑的；新 daemon 只跑了 `--fake`（新 daemon 只多擋東西，pi 用到的路沒變）。
- `--continue` 只用 `--fake` 看過（第二次的請求帶了上一次的 4 則訊息），真模型沒試。
- `.git` 唯讀時 pi（真模型）的反應：probe 量到寫入是 `Read-only file system`，pi 自己撞到會怎麼說沒試。
- 長輸出（bash 工具把全文存到 `/tmp`）、互動模式、RPC 模式：沒試。
- Codex 的 `network.unix_sockets`（准某個 socket）：沒驗，所以對照表上 Codex 的 `llm_sock_models` 是擋住。
- kernel 重起時上面那隻或 relay 接不接得上新的 socket：照理接得上（每次都重讀宣告、重連），沒測。

## 檔案

| 檔 | 是什麼 |
|---|---|
| `aos_pi.py` | aos-pi：標準佈局 `pi_sky()`、起 daemon／kernel／pi、判做完、印結果、收掉 |
| `daemon_ctl.py` | 沒有 init 的 aos-daemon 的小用戶端：起、寫 `ctl`、讀 `procs/<名>/`、等死、停 |
| `llm_kernel.py` | llm kernel：unix socket 上的 HTTP、`aos/llm` 宣告、額度與帳本、上游是網址或另一個 `aos/llm` 夾 |
| `fake_brain.py` | `--fake` 的劇本腦 |
| `relay.js` | kernel 放成 `/llm/relay` 的小轉接 |
| `probe.sh` | 不依賴佈局的探測：一行一項 `名 want got 說明`，出處寫在行尾 |
| `accept.py` | 驗收：probe、四個工具、對帳、用完、留下什麼 |
| `compare.py` | 同一支 probe 放進 aos-pi、srt、Codex，印對照表 |
| [compare.md](compare.md) | 對照文件：三邊設定與表 |
