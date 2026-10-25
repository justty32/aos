# sandbox — 把一個函數關起來跑（aos-sandbox）

← [proto8](../../README.md)｜設計與決定：[thinking 2026-10-24-sandbox](../../thinking/2026-10-24-sandbox.md)｜測試 `proto8/tests/test_sandbox.py`｜試驗場 `~/code/try/sandbox/`

`aos-sandbox - 照一份設定把 prog 關進沙箱再跑`（使用者 10-24「linux權限和沙箱可以開始做了，藉助s6那套」）。

```
aos-sandbox [--dry-run] [--] 設定檔 prog [args...]
```

它不常駐：排好一條 s6 式的 chain-loading（每支改一下行程狀態就 exec 成剩下的），exec 下去就走了。結束碼、stdin、stdout、stderr 都是 prog 的（被訊號停＝128＋N）。

```
[s6-softlimit -a … -d … -t …]   上限（設定有寫才接）
[s6-setuidgid 帳號]        身分（設定有寫 user 才接；要 root）
bwrap --unshare-all …      看得到哪些路徑、能不能連網（一定接；不用 root）
  -- prog args...
```

兩層：**身分**（s6，要先有帳號、要 root）＋**命名空間**（bwrap，免 root）。上限是 s6-softlimit（免 root）。

## 設定（一份 JSON 物件；全選填；不認得的 key 忽略）

| key | 值 | 做什麼 | 沒寫 |
|---|---|---|---|
| `user` | `帳號` 或 `uid:gid` | `s6-setuidgid` 換身分（只有 root 能用） | 不換 |
| `base` | 路徑陣列 | 系統唯讀底 | `/usr /bin /sbin /lib /lib64 /etc` 裡存在的 |
| `commands` | 指令名陣列 | 照 PATH 找到，所在資料夾唯讀看得到（例 `aos-exec`） | 沒有 |
| `ro` | 路徑陣列 | 唯讀看得到 | 沒有 |
| `rw` | 路徑陣列 | 可寫看得到（最後綁，可以蓋在 `ro` 裡面） | 沒有 |
| `net` | 布林 | 能不能連網 | `false`（只有沙箱自己的 loopback） |
| `mem_mb`、`cpu_s`、`procs`、`file_mb`、`files` | 正整數 | `s6-softlimit` 的 `-a`＋`-d`（`mem_mb`；不用 `-m`：它連堆疊上限一起設，aos-exec 一開執行緒就失敗）、`-t`、`-p`、`-f`、`-o` | 不限 |
| `env` | 環境變數名陣列 | 只帶這幾個進去（外面有設的才帶；bwrap `--clearenv`＋`--setenv`）；寫了就只照它，不再加預設那幾個 | `PATH`、`LANG`、`LC_ALL`、`LC_CTYPE`、`TZ`、`PYTHONDONTWRITEBYTECODE`、`PYTHONIOENCODING` 與 aos 的六個（`AOS_ENTRY`、`AOS_WS`、`AOS_STACK`、`AOS_CF`、`AOS_CD`、`AOS_CO`）；API key 一律不帶，要就明寫（10-24） |

- **沒列到的路徑一律看不到**（白名單）；`/proc`、`/dev`、空的 `/tmp` 一定有。綁進來的路徑在沙箱裡是同一個位置；相對路徑從 cwd 算。路徑是符號連結的，沙箱裡做同一條連結再綁它指到的地方。
- 設定檔可以寫 `檔#/指標`（例 `_metainfo#/sandbox`）；值可以用 `{"$env": 名, "$path": 接後面, "$prefix": 接前面}`（不解 `$ref`）。
- `--dry-run`：不跑，印出那一條 argv（一行 JSON）。
- **`cpu_s` 是 CPU 時間**（`s6-softlimit -t`，到了收 SIGXCPU、退 152），跟單子的 `timeout_ms`、庫的 bash 的 `timeout_s` 那種**牆鐘時間**不同種：`sleep` 一整天不吃 CPU、`cpu_s` 擋不到；要限總時間用叫它那格的 `timeout_ms`。
- **能不能用 LLM kernel＝看不看得到信箱**（使用者 10-24「就是看他能不能存取檔案啊」，[紀錄 S14、S17](../../thinking/2026-10-24-sandbox.md)）：不另設開關。預設看不到（信箱沒列進 `rw`、`AOS_KERNEL` 不在預設的 `env`）；要用就 `rw` 列 `{"$env": "AOS_KERNEL"}`、`env` 列 `AOS_KERNEL`。綁了信箱的上層資料夾也等於給了信箱（寫什麼就做什麼）。換帳號（`user`／身分層）跑時，寫不寫得進由信箱的擁有者、群組、權限位決定：[root/setup.sh](root/setup.sh) `--mailbox 信箱`。
  寄得進去之後，沙箱外的 aos-kernel-llm 會用它自己的身分照信跑單子——關在裡面的程式寄得到任何單子，kernel 那邊要寫 `accept`（[aos-kernel-llm](../../impls/aos-kernel-llm/README.md)：只跑名單裡的單子、環境用 kernel 自己的）才擋得住；這條是 Linux 權限管不到的，暫留（紀錄 S18）。

錯：stderr 一行 `aos-sandbox: 代號 原因`、退 1——`ArgumentsBad`、`FlagUnknown`、`CfgMissing`（檔不在、`#/` 指不到）、`CfgBad`、`PathMissing`、`CommandMissing`（PATH 上沒有 bwrap、s6-*、`commands` 列的）、`UserBad`（要換身分卻不是 root）。

## 怎麼接

寫在**叫的那一方**的 argv 最前面（函數自己關自己沒有意義）：

```json
["aos-sandbox", "sandbox.json", "aos-exec", "inner"]
```

| 例子 | 檔 | 說明 |
|---|---|---|
| 自我改進 | [examples/self-improve.json](examples/self-improve.json) | 放進交辦工作區當 `sandbox.json`：run 格與 try_run 都把被改的函數關起來（只看得到這次的暫時複本＋工作區、斷網、只帶 `PATH`、語系幾個環境變數、1 GB、60 秒 CPU）。工作區沒放時 self-improve 預設用自己的 [sandbox.json](../../demo/self-improve/sandbox.json)（同這份、少了要 s6 的上限；10-24 定） |
| bash 工具 | [examples/bash-boxed/](examples/bash-boxed) | 庫的 bash（[lib/base/bash](../../lib/base/bash)）原封不動（`inner` 捷徑），外面包一層：只寫得到 `$AOS_WS` 與自己的 stack、斷網、環境照預設那幾個；`cpu_s` 120 是 CPU 時間，bash 自己的 `timeout_s`（最多 300）是牆鐘 |
| claude／codex CLI | [examples/cli-tool.json](examples/cli-tool.json) | 要連網、要寫自己的設定資料夾；擋的是「讀寫工作區以外」；環境只帶 `PATH`、`HOME`、`TERM`、語系與 aos 的六個（登入靠 `~/.claude`、`~/.codex` 裡的檔；用環境變數給 key 的話自己加進 `env`） |
| agent 當工具 | [examples/agent.json](examples/agent.json) | 斷網、信箱綁進來（`rw` 的 `$AOS_KERNEL`；腦只能經信箱用 aos-gate 問）、環境另帶 `AOS_KERNEL`、`AOS_BRAIN_URL`、`AOS_BRAIN_MODEL`（不帶 key）；kernel 那邊寫 `accept`。沙箱有自己的行程編號也行：kernel 認寄信的人看信裡 `sender.lock` 的檔案鎖、不看 pid（紀錄 S15） |

## 要 root 的那半

[root/setup.sh](root/setup.sh)：預設乾跑（只印指令），`sudo sh proto8/extras/sandbox/root/setup.sh --apply` 才做——把 s6 四支放進 `/usr/local/bin`、建系統帳號 `aos-run`、開 `/srv/aos-run`、加一條 sudoers（只准「換成 aos-run」）。
`setup.sh --mailbox 信箱 [--apply]`：只做讓 aos-run 寫得到某個 kernel 信箱——擁有者＝我（跑 kernel 的人）、群組 `aos-run`、2770，四格加預設 ACL（閘門建的信、kernel 寫的回信兩邊都讀寫得到，不看 umask）；信箱要放在 aos-run 走得到的地方（例 `/srv/aos-run/mailbox`）。不讓寫＝`chmod 700 信箱`。這段在假 root 裡有測（`tests/test_sandbox.py` 的 `MailboxPermTest`）。

## 需要

`bwrap`（bubblewrap）、`python3`；設定寫了上限或 `user` 才要 s6（`s6-softlimit`、`s6-setuidgid`、`s6-applyuidgid`，都照 PATH 找）。這台 Arch 的官方庫沒有 s6，試驗場自己編了一份到 `~/code/try/sandbox/s6-root/bin`（skalibs 2.16.0.0、execline 2.10.0.0、s6 2.15.1.1，skarnet.org 原始碼）。
