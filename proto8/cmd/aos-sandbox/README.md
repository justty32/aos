# aos-sandbox — 把一個函數關起來跑

← [cmd](../README.md)｜設計與決定：[thinking 2026-10-24-sandbox](../../thinking/2026-10/24/sandbox/README.md)｜試驗場 `~/code/try/sandbox/`

`aos-sandbox - 照一份設定把 prog 關進沙箱再跑`（使用者 10-24「linux權限和沙箱可以開始做了，藉助s6那套」）。

```
aos-sandbox [--dry-run] [--] CONFIG prog [args...]
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
| `commands` | 指令名陣列 | 照 PATH 找到，所在資料夾唯讀看得到（例 `aos-exec`）；真位置在 `…/cmd/<名>/bin/<名>` 的，連同它們共用的 `…/py` 一起唯讀綁 | 沒有 |
| `ro` | 路徑陣列 | 唯讀看得到 | 沒有 |
| `rw` | 路徑陣列 | 可寫看得到（最後綁，可以蓋在 `ro` 裡面） | 沒有 |
| `net` | 布林 | 能不能連網 | `false`（只有沙箱自己的 loopback） |
| `mem_mb`、`cpu_s`、`procs`、`file_mb`、`files` | 正整數 | `s6-softlimit` 的 `-a`＋`-d`（`mem_mb`；不用 `-m`：它連堆疊上限一起設，aos-exec 一開執行緒就失敗）、`-t`、`-p`、`-f`、`-o` | 不限 |
| `env` | 環境變數名陣列 | 只帶這幾個進去（外面有設的才帶；bwrap `--clearenv`＋`--setenv`）；**明列 `env` 就是整份取代預設清單，不是往預設上加**——要預設那幾個就自己一起列 | `PATH`、`LANG`、`LC_ALL`、`LC_CTYPE`、`TZ`、`PYTHONDONTWRITEBYTECODE`、`PYTHONIOENCODING` 與 aos 的六個（`AOS_ENTRY`、`AOS_WS`、`AOS_STACK`、`AOS_CF`、`AOS_CD`、`AOS_CO`）、hub 型的 `AOS_DAEMON`、`AOS_LLM_KERNEL`（11-04 加，N-63 ③ 子 process 預設繼承）、`AOS_KERNEL`、`AOS_KNOWLEDGE`、`AOS_CLOCK`（11-06 加，同一條；使用者 11-06 選項框「預設補上」）；外面沒設的照樣不帶；只帶變數、不綁它指的路徑（要看得到就自己列進 `ro`／`rw`）；API key 一律不帶，要就明寫 |

- **沒列到的路徑一律看不到**（白名單）；`/proc`、`/dev`、空的 `/tmp` 一定有。綁進來的路徑在沙箱裡是同一個位置；相對路徑從 cwd 算。路徑是符號連結的，沙箱裡做同一條連結再綁它指到的地方。
- 設定檔可以寫 `檔#/指標`（例 `_metainfo.json#/sandbox`）；值可以用 `{"$env": 名, "$path": 接後面, "$prefix": 接前面}`（不解 `$ref`）。
- `--dry-run`：不跑，印出那一條 argv（一行 JSON）。
- **`cpu_s` 是 CPU 時間**（`s6-softlimit -t`，到了收 SIGXCPU、退 152），跟單子的 `timeout_ms`、庫的 bash 的 `timeout_s` 那種**牆鐘時間**不同種：`sleep` 一整天不吃 CPU、`cpu_s` 擋不到；要限總時間用叫它那格的 `timeout_ms`。
- **能不能用 LLM kernel＝看不看得到信箱**（使用者 10-24「就是看他能不能存取檔案啊」，[紀錄 S14、S17](../../thinking/2026-10/24/sandbox/README.md)）：不另設開關。預設看不到（信箱沒列進 `rw`）；要用就 `rw` 列信箱 `{"$env": "AOS_LLM_KERNEL", "$path": "/requests"}`（`AOS_LLM_KERNEL`＝llm kernel 的 stack、信箱固定在它的 `requests/`；**只綁信箱、不綁整個 stack**：stack 裡還有 kernel 的定義與 `kernel.json`）、`env` 帶 `AOS_LLM_KERNEL`（預設的 `env` 就有；自己寫 `env` 時要列）。綁了信箱的上層資料夾也等於給了信箱（寫什麼就做什麼）。換帳號（`user`／身分層）跑時，寫不寫得進由信箱的擁有者、群組、權限位決定：[root/setup.sh](root/setup.sh) `--mailbox 信箱`。
  寄得進去之後，沙箱外的 [aos-llm-kernel](../../impls/aos-llm-kernel/README.md) 用它自己的身分與環境、跑它自己定義裡的 endpoint 函數（11-04 晚起信裡只帶請求、不帶單子，`accept` 退場）——關在裡面的程式只能寄請求、挑 kernel 登記過的代號，改不了端點與金鑰（紀錄 S18 那條「寄得到任何單子」因此沒了）。

錯：stderr 一行 `aos-sandbox: error: 代號 原因`、退 1——`ArgumentsBad`、`FlagUnknown`、`CfgMissing`（檔不在、`#/` 指不到）、`CfgBad`、`PathMissing`、`CommandMissing`（PATH 上沒有 bwrap、s6-*、`commands` 列的）、`UserBad`（要換身分卻不是 root）。exec 之後的結束碼都是 prog 的（被訊號停＝128＋N）：**退非 0 時 stderr 有 `aos-sandbox: error:` 這行＝我錯；沒有＝下層（s6／bwrap／prog）的碼**（11-05 stdio-unify R8）。`--help`＝英文說明到 stdout、退 0。

## 怎麼接

寫在**叫的那一方**的 argv 最前面（函數自己關自己沒有意義）：

```json
["aos-sandbox", "sandbox.json", "aos-exec", "inner"]
```

| 例子 | 檔 | 說明 |
|---|---|---|
| shell 工具 | [examples/shell-boxed/](examples/shell-boxed) | 庫的 shell（[lib/base/shell](../../lib/base/shell)）原封不動（`inner` 捷徑），連它 import 的 [lib/tool_io.py](../../lib/tool_io.py) 一起綁唯讀（lib 工具共用的開頭，沒綁就起不來），外面包一層：只寫得到 `$AOS_WS` 與自己的 stack、斷網、環境照預設那幾個；`cpu_s` 120 是 CPU 時間，shell 自己的 `timeout_s`（最多 300）是牆鐘 |
| 小念頭（要碰 daemon 的工具） | [examples/thought-boxed/](examples/thought-boxed) | 庫的 thought 原封不動（`inner` 捷徑）。`sandbox.json`（模式 1，沒有判官）：rw 綁 `$AOS_DAEMON`（寄 ctl 信、子的 stack 要寫介面宣告的工具／腦覆蓋層；深度經啟動環境帶入）、`$AOS_WS`、`$AOS_STACK`（回信信箱在這）；ro 綁整個 `lib/`（範本的工具都指到 lib）、呼叫 `from` 或工具預設 `AOS_THOUGHT_FROM` 指的子定義（本例綁 `templates/agent-fsm`；換 `from` 時跟著換綁定）、aos-agent 的套件 `cmd/aos-agent/aos_agent`；`commands` 帶 aos-exec、aos-agent、aos-post、aos-tools、aos-json；斷網。`sandbox-kernel.json`（模式 2，判官是 procs-kernel）：daemon stack 只 ro（ctl 信箱寫不進去，信只能寄 `$AOS_KERNEL`）、rw 綁它的 `procs/`＋`$AOS_KERNEL`。兩份都明列 `env`（不帶 `AOS_LLM_KERNEL`），11-06 起列了 `AOS_KERNEL`、`AOS_KNOWLEDGE`、`AOS_CLOCK`（11-10 templates-cp 加 `AOS_HOME`：範本的工具路徑寫 `{"$env": "AOS_HOME", …}`，沒帶進沙箱就解不開；未實測）、`AOS_THOUGHT_DEPTH`、`AOS_THOUGHT_FROM`（工具登記格 `env` 可設預設子定義，相對 `$AOS_WS`），沙箱裡的 knowledge_read 照 `AOS_KNOWLEDGE` 找知識庫（庫要在綁進來的路徑裡）。沒寫上限（這台公司 WSL 沒有 s6）。實測見 [no-pid 13](../../thinking/2026-11/05/no-pid/13-P5實作結果.md) |
| claude／codex CLI | [examples/cli-tool.json](examples/cli-tool.json) | 要連網、要寫自己的設定資料夾；擋的是「讀寫工作區以外」；環境只帶 `PATH`、`HOME`、`TERM`、語系與 aos 的六個（登入靠 `~/.claude`、`~/.codex` 裡的檔；用環境變數給 key 的話自己加進 `env`） |
| agent 當工具 | [examples/agent.json](examples/agent.json) | 斷網、信箱綁進來（`rw` 的 `$AOS_LLM_KERNEL/requests`，只綁信箱；腦只能經信箱用 aos-llm 問）；`commands` 帶 aos-post、aos-tools（agent-fsm 的 wait／act 要用，11-04 晚；aos-tools 在 `cmd/aos-tools/bin/`，所以 `proto8/py` 也跟著綁）、環境另帶 `AOS_LLM_KERNEL`（端點、模型、金鑰都在 kernel 那邊的 `kernel.json`，agent 看不到）。沙箱有自己的行程編號也行：kernel 認寄信的人看信裡 `sender.flock` 的檔案鎖、不看 pid（紀錄 S15） |

**要碰 daemon 的工具（thought、agents_children、agents_ctl、self_tools）綁這兩樣**：`AOS_DAEMON`（rw；模式 2 改成 `AOS_KERNEL` 的 `requests/`＋daemon stack 唯讀，再加 rw 它的 `procs/`——子的 stack 要寫得進去）（11-06 [no-pid P5](../../thinking/2026-11/05/no-pid/13-P5實作結果.md)）。另外兩件要注意：
- **叫它的那隻 agent 的定義資料夾也要 ro 綁**：self_tools、thought 會讀父的定義（父的 `interfaces.json`、宣告的 llm 設定檔），看不到時 self_tools 報 `InterfaceMissing`，thought 也報錯（多半是 `InterfaceMissing`；11-06 起，之前不報錯、子的腦默默改用範本預設），除非叫的時候自己給 `endpoint`。定義放哪沒有環境變數可指，範例沒寫，自己在 `ro` 加上。
- **daemon 的 stack 放在工作區裡（例 `ws/.stack`）時，綁 `AOS_WS` 就已經把整台 daemon 綁進去了**——連 shell-boxed 這種葉工具也寫得到 ctl 信箱。要真的關住，daemon 的 stack 別放在工作區裡。

## 要 root 的那半

[root/setup.sh](root/setup.sh)：預設乾跑（只印指令），`sudo sh proto8/cmd/aos-sandbox/root/setup.sh --apply` 才做——把 s6 四支放進 `/usr/local/bin`、建系統帳號 `aos-run`、開 `/srv/aos-run`、加一條 sudoers（只准「換成 aos-run」）。
`setup.sh --mailbox 信箱 [--apply]`：只做讓 aos-run 寫得到某個 kernel 信箱——擁有者＝我（跑 kernel 的人）、群組 `aos-run`、2770，四格加預設 ACL（閘門建的信、kernel 寫的回信兩邊都讀寫得到，不看 umask）；信箱要放在 aos-run 走得到的地方（例 `/srv/aos-run/requests`）。不讓寫＝`chmod 700 信箱`。
另外三個旗標換預設值（不讀環境變數）：`--me 名`（我＝跑 kernel 的人，預設 `$SUDO_USER` 或自己；測試在假 root 裡給數字）、`--s6-bin 路徑`（s6 的 bin，預設試驗場 `/home/<我>/code/try/sandbox/s6-root/bin`）、`--runner 名`（跑不信任函數的帳號與群組，預設 `aos-run`）；repo 現行沒有 `SetupFlagsTest`，乾跑旗標需手動核對。從 repo 根跑以下指令（不帶 `--apply`，只印不執行），確認輸出採用指定的 s6 路徑、使用者與 runner；乾跑不讀取 s6 執行檔，示例的 `--s6-bin` 路徑不必存在：

```sh
sh proto8/cmd/aos-sandbox/root/setup.sh --me "$(id -un)" --s6-bin /tmp/pf-line5-impl-check/s6/bin --runner aos-pf-line5-check
```

## 需要

`bwrap`（bubblewrap）、`python3`；設定寫了上限或 `user` 才要 s6（`s6-softlimit`、`s6-setuidgid`、`s6-applyuidgid`，都照 PATH 找）。這台 Arch 的官方庫沒有 s6，試驗場自己編了一份到 `~/code/try/sandbox/s6-root/bin`（skalibs 2.16.0.0、execline 2.10.0.0、s6 2.15.1.1，skarnet.org 原始碼）。

**搬不走的那半**：帳號、sudoers、`/srv` 下的配置與 bind 的主機路徑都屬於這台機器；搬完先改 bind 路徑，再重跑 [root/setup.sh](root/setup.sh)（先乾跑，核對後 `--apply`；信箱另帶 `--mailbox`），不會因複製 image 自動重建。
