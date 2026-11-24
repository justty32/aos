# aos-sandbox — 把一個函數關起來跑

← [cmd](../../../docs/05-commands.md)｜設計與決定：[thinking 2026-10-24-sandbox](../../../../thinking/2026-10/24/sandbox/README.md)｜試驗場 `~/code/try/sandbox/`（11-15 已刪）

`aos-sandbox - 照一份設定把 prog 關進沙箱再跑`（使用者 10-24「linux權限和沙箱可以開始做了，藉助s6那套」）。

```
aos-sandbox [--dry-run] [--] CONFIG prog [args...]
```

它不常駐：排好一條 s6 式的 chain-loading（每支改一下行程狀態就 exec 成剩下的），exec 下去就走了。結束碼、stdin、stdout、stderr 都是 prog 的（被訊號停＝128＋N）。

```
[s6-softlimit -a … -d … -t …]   上限（設定有寫才接）
[s6-setuidgid 帳號]        root 身分層；非 root 改成 sudo -n -k /usr/local/bin/s6-setuidgid 帳號，放上限之前
bwrap --unshare-all …      看得到哪些路徑、能不能連網（一定接；不用 root）
  -- prog args...
```

兩層：**身分**（s6，要先有帳號；非 root 帳號走 sudo NOPASSWD）＋**命名空間**（bwrap，免 root）。上限是 s6-softlimit（免 root）。

## 設定（一份 JSON 物件；全選填；不認得的 key 忽略）

| key | 值 | 做什麼 | 沒寫 |
|---|---|---|---|
| `user` | `帳號`、`uid:gid` 或 `sub:N` | 帳號：root 跑＝`s6-setuidgid`；不是 root＝前面自動接 `sudo -n -k /usr/local/bin/s6-setuidgid 帳號`（要有 root/setup.sh 的 NOPASSWD sudoers）；sudo 不准＝`UserBad`，不會不換身分就跑；`uid:gid` 只准 root；`sub:N` 照舊接 `aos-asuser --env-all sub:N --`（[aos-asuser](../asuser/README.md)） | 不換 |
| `base` | 路徑陣列 | 系統唯讀底 | `/usr /bin /sbin /lib /lib64 /etc` 裡存在的 |
| `commands` | 指令名陣列 | 照 PATH 找到，所在資料夾唯讀看得到（例 `aos-exec`）；真位置在 `<家>/bin/<名>`、旁邊有 `<家>/lib/aos/` 的＝aos 的命令，**整個家**（`AOS_HOME` 有設＝它，沒設＝命令所在的家）唯讀綁（`bin lib include templates knowledge …` 都在裡面；路徑規則路-7，[11-17 路徑規則](../../../../thinking/2026-11/17/路徑規則/04-規則草稿.md)），同一個家只綁一次 | 沒有 |
| `ro` | 路徑陣列 | 唯讀看得到；跟 `rw` 巢狀時**深的那條說了算**（`rw: [repo]`＋`ro: [repo/.git]`＝repo 可寫、`.git` 唯讀；反過來 `ro: [repo]`＋`rw: [repo/sub]` 也行；11-13 線修 T32） | 沒有 |
| `rw` | 路徑陣列 | 可寫看得到（`ro`、`rw` 混在一起照路徑深淺排、淺的先綁；同一條兩邊都列＝可寫）；列了 `$AOS_STACK` 而它不在＝先建（[tool-cells-lazy](../../../../thinking/2026-11/11/tool-cells-lazy.md)：`aos-tools call` 不先建工具小格），其他路徑不在＝`PathMissing` | 沒有 |
| `net` | 布林 | 能不能連網 | `false`（只有沙箱自己的 loopback） |
| `mem_mb`、`cpu_s`、`procs`、`file_mb`、`files` | 正整數 | `s6-softlimit` 的 `-a`＋`-d`（`mem_mb`；不用 `-m`：它連堆疊上限一起設，aos-exec 一開執行緒就失敗）、`-t`、`-p`、`-f`、`-o` | 不限 |
| `env` | 環境變數名陣列 | 只帶這幾個進去（外面有設的才帶；bwrap `--clearenv`＋`--setenv`）；**明列 `env` 就是整份取代預設清單，不是往預設上加**——要預設那幾個就自己一起列 | `PATH`、`LANG`、`LC_ALL`、`LC_CTYPE`、`TZ`、`PYTHONDONTWRITEBYTECODE`、`PYTHONIOENCODING` 與 aos 的六個（`AOS_ENTRY`、`AOS_WS`、`AOS_STACK`、`AOS_CF`、`AOS_CD`、`AOS_CO`）、hub 型的 `AOS_DAEMON`、`AOS_LLM_KERNEL`（N-63 ③ 子 process 預設繼承）、`AOS_KERNEL`、`AOS_CLOCK`（同一條；使用者 11-06 選項框「預設補上」）、`AOS_HOME`（路-7：綁家、放行這一個變數）；外面沒設的照樣不帶；只帶變數、不綁它指的路徑（要看得到就自己列進 `ro`／`rw`）；API key 一律不帶，要就明寫 |

`sub:N`（N＝1～60000，不准前導 0）是在 user ns 裡換成 uid N，對到真 subuid「起點＋N－1」；aos-sandbox 只換主群組（G＝N），`limits.groups` 的多群組由 daemon 段 3（C++）處理，aos-asuser 今天只收一個 `--group`。
bwrap 在這個 user ns 裡照開（[06 X28](../../../../thinking/2026-11/13/kernel-limits-plan/06-試驗紀錄.md)），仍由 bwrap 清環境。
工作區的每層祖先都要給「別人」x（可穿越）權限，換成 subuid 才走得到。

非 `sub:` 的 user 只收最長 32 字的帳號名（`^[a-z_][a-z0-9_-]*[$]?$`）或數字 `uid:gid`；其他格式算設定壞掉。非 root 的乾跑也會查 passwd，帳號不存在、uid／gid 為 0、或使用 `uid:gid` 都是 `UserBad`。真正執行前用同一條 `sudo -n -k` 跑系統的 true 預檢；`-k` 忽略快取密碼，只准 NOPASSWD 規則放行。sudo 放最前面，後面才設 s6-softlimit 上限；乾跑不預檢。

非 root 走 sudo 時，`bwrap`、`s6-softlimit`、prog 本身、設定檔所在的資料夾，以及 `commands`、`ro`、`rw` 的路徑都必須讓 aos-run 走得到、讀得到、跑得動（系統路徑或 `/srv/aos-run` 底下）；`/home/<我>` 是 700 時進不去，`~/.local/bin` 這類路徑也不行，不會自動補 ACL。

**env 白名單的值會出現在 sudo 的指令列紀錄裡**：bwrap 的 `--setenv KEY VALUE` 在 argv 裡，所以機密不要列進 `env`。

- **沒列到的路徑一律看不到**（白名單）；`/proc`、`/dev`、空的 `/tmp` 一定有。
- **能寫的只有 `rw` 列的與 `/tmp`**（11-13 線修 T36）：所有綁定之後把沙箱的根 `/` 改成唯讀（bwrap `--remount-ro /`），寫到沒綁的地方（例 `$HOME`、別的定義夾）＝`Read-only file system`、指令失敗，不再默默寫進沙箱的暫存根、退 0、主機上卻沒檔。`/tmp` 照舊可寫，但它是沙箱自己的、跑完就沒了。
- **設定檔所在的資料夾自動唯讀看得到**（11-13 線修 T34）：工具的 `_entry` 寫 `["aos-sandbox", "_metainfo.json#/sandbox", "aos-exec", "inner"]`，`inner` 是相對工具夾的；以前 `ro` 改寫成絕對路徑、漏了工具夾，就報 `EntryMissing entry not found: inner (relative paths count from /: /inner)`。已被某條 `ro`／`rw` 蓋到（同一條或在它底下）就不另綁（在 `rw` 裡的照舊可寫）。所以**別把祕密放在沙箱設定旁邊**。`inner` 指到的地方（例 `py/tools/base/shell`）照舊要列進 `ro`。綁進來的路徑在沙箱裡是同一個位置；相對路徑從 cwd 算。路徑是符號連結的，沙箱裡做同一條連結再綁它指到的地方。
- **`commands` 列了 aos 的命令＝整個家唯讀看得到**（路徑規則路-7）：家裡的 `thinking/`、`docs/`、`py/`、`cpp/` 也一起看得到、寫不進去，所以**別把祕密放在家裡**。家在 `commands` 這段就綁好、比 `ro`／`rw` 早：`ro`／`rw` 列了家的上層（例 `rw` 的工作區包著家）時，家被那條蓋過、跟著它可寫（同以前綁 `<家>/lib` 的做法）。**家是哪個**（使用者 11-18 選項框「AOS_HOME 有設就用它」）：`AOS_HOME` 有設＝綁它指的家；沒設才認命令的真位置（`<家>/bin/<名>` 的那個 `<家>`）。`AOS_HOME` 有設但不像家（裡面沒有 `install.py` 或沒有 `bin/`，判準比照 `env.sh` 的 `EnvBad`）＝`EnvBad` 錯、退 1，不默默退回認命令位置。`commands` 沒列 aos 的命令就不綁家，也不檢查 `AOS_HOME`（它只是照 `env` 帶進去的變數）。aos 的命令來自 `AOS_HOME` 以外的另一個家＝只綁它自己的資料夾、不綁它的家，stderr 多一行 `aos-sandbox: warning: …`（那個命令在沙箱裡多半起不來；正常 `source $AOS_HOME/env.sh` 之後 PATH 上的 aos 命令都在 `$AOS_HOME/bin`，碰不到）。
- 設定檔可以寫 `檔#/指標`（例 `_metainfo.json#/sandbox`）；值可以用 `{"$env": 名, "$path": 接後面, "$prefix": 接前面}`（不解 `$ref`）。
- `--dry-run`：不跑，印出那一條 argv（一行 JSON）。
- **`cpu_s` 是 CPU 時間**（`s6-softlimit -t`，到了收 SIGXCPU、退 152），跟單子的 `timeout_ms`、庫的 bash 的 `timeout_s` 那種**牆鐘時間**不同種：`sleep` 一整天不吃 CPU、`cpu_s` 擋不到；要限總時間用叫它那格的 `timeout_ms`。
- **能不能用 LLM kernel＝看不看得到信箱**（使用者 10-24「就是看他能不能存取檔案啊」，[紀錄 S14、S17](../../../../thinking/2026-10/24/sandbox/README.md)）：不另設開關。預設看不到（信箱沒列進 `rw`）；要用就 `rw` 列信箱 `{"$env": "AOS_LLM_KERNEL", "$path": "/requests"}`（`AOS_LLM_KERNEL`＝llm kernel 的 stack、信箱固定在它的 `requests/`；**只綁信箱、不綁整個 stack**：stack 裡還有 kernel 的定義與 `kernel.json`）、`env` 帶 `AOS_LLM_KERNEL`（預設的 `env` 就有；自己寫 `env` 時要列）。綁了信箱的上層資料夾也等於給了信箱（寫什麼就做什麼）。換帳號（`user`／身分層）跑時，寫不寫得進由信箱的擁有者、群組、權限位決定：[root/setup.sh](root/setup.sh) `--mailbox 信箱`。
  寄得進去之後，沙箱外的 llm kernel [`py/tools/aos/kernel_llm`](../../../tools/aos/kernel_llm/README.md) 用它自己的身分與環境、跑它自己定義裡的 endpoint 函數（信裡只帶請求、不帶單子）——關在裡面的程式只能寄請求、挑 kernel 登記過的代號，改不了端點與金鑰。

**設定壞了＝當沒寫：不套沙箱、直接跑 prog**（使用者 11-12 晚，回沙箱設定寫壞時怎麼辦，甲＝也略過、不關沙箱照跑、跟其他格一致：「甲，出事自己負責」；[N-69](../../../../docs/NORMS/10-基礎設施-定義與工作區/11-N-69.md)「全是觀點、參考用」）。stderr 印一行 `aos-sandbox: warning: sandbox config ignored, running unsandboxed: 原因`，prog 照 PATH 找、stdin／stdout／結束碼照舊是它的；`--dry-run` 印的就只有 prog 那條。算「壞」的：檔讀不了、不是 JSON、指到的不是物件、`#` 後面不是 `/`、某個 key 型別不對（`net` 不是布林、上限不是正整數、`user` 不是字串、路徑／指令／`env` 不是字串陣列）、裡面有 `$ref`、`$env` 指的變數沒設。**不算壞、照舊是錯的**：設定不在（檔不在、`#/` 指不到＝`CfgMissing`）、環境做不到（列的路徑不在＝`PathMissing`；bwrap、s6、`commands` 列的指令不在＝`CommandMissing`；非 root 的帳號／sudo 身分檢查不通過＝`UserBad`）。所以沙箱不是保證：要確定有關住，看 stderr 有沒有那行 warning。

錯：stderr 一行 `aos-sandbox: error: 代號 原因`、退 1——`ArgumentsBad`、`FlagUnknown`、`CfgMissing`（檔不在、`#/` 指不到）、`PathMissing`、`CommandMissing`（PATH 上沒有 bwrap、s6-*、`commands` 列的）、`UserBad`（非 root 的帳號或 sudo 檢查不通過）、`EnvBad`（`commands` 有 aos 的命令、`AOS_HOME` 有設卻不像家）。exec 之後的結束碼都是 prog 的（被訊號停＝128＋N）：**退非 0 時 stderr 有 `aos-sandbox: error:` 這行＝我錯；沒有＝下層（s6／bwrap／prog）的碼**（stdio-unify R8）。`--help`＝英文說明到 stdout、退 0。

## 怎麼接

寫在**叫的那一方**的 argv 最前面（函數自己關自己沒有意義）：

```json
["aos-sandbox", "sandbox.json", "aos-exec", "inner"]
```

| 例子 | 檔 | 說明 |
|---|---|---|
| shell 工具 | [examples/shell-boxed/](examples/shell-boxed) | 工具夾本身自動唯讀綁（上面 T34），`ro` 改成絕對路徑時不用再列它；庫的 shell（[py/tools/base/shell](../../../tools/base/shell)）原封不動（`inner` 捷徑）；它 import 的 aos 套件（[py/aos](../../)，裝好是 `lib/aos`）跟著 `commands` 的 aos-exec 整個家一起唯讀看得到（lib 工具共用的開頭，沒綁就起不來），外面包一層：只寫得到 `$AOS_WS` 與自己的 stack、斷網、環境照預設那幾個；`cpu_s` 120 是 CPU 時間，shell 自己的 `timeout_s`（最多 300）是牆鐘 |
| 子 agent（要碰 daemon 的工具） | [examples/subagent-boxed/](examples/subagent-boxed) | 庫的 subagent 原封不動（`inner` 捷徑；`inner` 指 subagent 之後沒重測）。`sandbox.json`（模式 1，沒有框架站）：rw 綁 `$AOS_DAEMON`（寄 ctl 信、子的 stack 要寫介面宣告的工具／腦覆蓋層）、`$AOS_WS`、`$AOS_STACK`（回信信箱在這）；整個家跟著 `commands` 唯讀看得到（範本的工具都指到 `lib/`、aos-agent 的套件在 `lib/aos/apps/agent`、本例 add 時 `def` 指的子定義 `templates/agents/agent-fsm` 都在家裡；`def` 換成家外的定義時自己列進 `ro`）；`commands` 帶 aos-exec、aos-agent、aos-post、aos-tools、aos-json；斷網。`sandbox-kernel.json`（模式 2，框架站是 procs-kernel）：daemon stack 只 ro（ctl 信箱寫不進去，信只能寄 `$AOS_KERNEL`）、rw 綁它的 `procs/`＋`$AOS_KERNEL`。兩份都明列 `env`（不帶 `AOS_LLM_KERNEL`），列了 `AOS_KERNEL`、`AOS_CLOCK`、`AOS_HOME`（範本的工具路徑寫 `{"$env": "AOS_HOME", …}`，沒帶進沙箱就解不開；未實測）。沒寫上限（這台公司 WSL 沒有 s6）。實測見 [no-pid 13](../../../../thinking/2026-11/05/no-pid/13-P5實作結果.md) |
| claude／codex CLI | [examples/cli-tool.json](examples/cli-tool.json) | 要連網、要寫自己的設定資料夾；擋的是「讀寫工作區以外」；環境只帶 `PATH`、`HOME`、`TERM`、語系、aos 的六個與 `AOS_HOME`（登入靠 `~/.claude`、`~/.codex` 裡的檔；用環境變數給 key 的話自己加進 `env`） |
| agent 當工具 | [examples/agent.json](examples/agent.json) | 斷網、信箱綁進來（`rw` 的 `$AOS_LLM_KERNEL/requests`，只綁信箱；腦只能經信箱用 aos-llm 問）；`commands` 帶 aos-post、aos-tools（agent-fsm 的 wait／act 要用；它們都在同一個家的 `bin/`，所以整個家跟著唯讀綁）、環境另帶 `AOS_LLM_KERNEL`、`AOS_HOME`（端點、模型、金鑰都在 kernel 那邊的 `kernel.json`，agent 看不到）。沙箱有自己的行程編號也行：kernel 認寄信的人看信裡 `sender.flock` 的檔案鎖、不看 pid（紀錄 S15） |

**要碰 daemon 的工具（subagent、agents_ctl、self_tools、self_history、do_task）綁這兩樣**：`AOS_DAEMON`（rw；模式 2 改成 `AOS_KERNEL` 的 `requests/`＋daemon stack 唯讀，再加 rw 它的 `procs/`——子的 stack 要寫得進去）（[no-pid P5](../../../../thinking/2026-11/05/no-pid/13-P5實作結果.md)）。另外兩件要注意：
- **叫它的那隻 agent 的定義資料夾也要 ro 綁**：self_tools 會讀父的定義（父的 `interfaces.json`、宣告的 llm 設定檔），看不到時報 `InterfaceMissing`；self_history、do_task 經 `aos-agent history` 也要讀它的 `interfaces.json`（找 history 檔；do_task 不讀 llm 設定、不生子）。定義放哪沒有環境變數可指，範例沒寫，自己在 `ro` 加上。
- **daemon 的 stack 放在工作區裡（例 `ws/.stack`）時，綁 `AOS_WS` 就已經把整台 daemon 綁進去了**——連 shell-boxed 這種葉工具也寫得到 ctl 信箱。要真的關住，daemon 的 stack 別放在工作區裡。
- **照起手範本用 `-w .` 掛 agent（工作區＝整棵樹）時，沙箱關不住樹的控制台，這是使用者自己承擔的風險**（使用者 11-18 晚：「好，沙箱這個基本上是使用者要自己承擔的風險吧。」，[sbx-fix-1118](../../../../thinking/2026-11/18/sbx-fix-1118.md)）：樹裡的根 stack（daemon 信箱）、llm kernel 的 stack 與定義、各隻的定義都在工作區裡，綁 `AOS_WS` 就一起可寫——沙箱裡的工具看得到 daemon 的表、能對別隻說話、改得到 kernel 與自己的定義，還能 `ctl add` 叫 daemon 在**沙箱外**再開一隻（11-18 家機實測）。要隔得乾淨就給它專用的工作夾（例 `mkdir work && aos-agent -d .stack ctl add -w work agents/ann`），或放樹外的專案夾。

## 要 root 的那半

[root/setup.sh](root/setup.sh)：預設乾跑（只印指令），`sudo sh proto8/py/aos/apps/sandbox/root/setup.sh --apply` 才做——把 s6 四支放進 `/usr/local/bin`、建系統帳號 `aos-run`、開 `/srv/aos-run`、加一條 sudoers（只准「換成 aos-run」）。
**在 `/srv/aos-run` 底下開資料夾**（11-14 線限 sbroot 驗收踩到的）：跑 setup.sh 的人（我）不在 `aos-run` 群組裡。群組外的人對目錄 chmod，kernel 會清掉 setgid 位，之後新建的檔變成我自己的群組，`aos-run` 就讀不到；我也不能把檔 chgrp 到 `aos-run`。所以 `/srv/aos-run` 底下**只 mkdir、不 chmod**，讓子目錄沿用 setgid 帶下來的 `aos-run` 群組；umask 022 建出來是 2755，要讓 `aos-run` 寫的那層再加 `chmod g+w`（群組留著，只有那層的 setgid 會掉）。把自己加進 `aos-run` 群組（`sudo usermod -aG aos-run 我`，重新登入後生效）之後，就不會有這個問題。這層的接法：不是 root 時 aos-sandbox 自己接 `sudo -n -k /usr/local/bin/s6-setuidgid 帳號`，不用手動拼 `--dry-run` 印出的那條（驗收紀錄 [kernel-limits-1114](../../../../thinking/2026-11/14/kernel-limits-1114.md)）。
`setup.sh --mailbox 信箱 [--apply]`：只做讓 aos-run 寫得到某個 kernel 信箱——擁有者＝我（跑 kernel 的人）、群組 `aos-run`、2770，四格加預設 ACL（閘門建的信、kernel 寫的回信兩邊都讀寫得到，不看 umask）；信箱要放在 aos-run 走得到的地方（例 `/srv/aos-run/requests`）。不讓寫＝`chmod 700 信箱`。
另外三個旗標換預設值（不讀環境變數）：`--me 名`（我＝跑 kernel 的人，預設 `$SUDO_USER` 或自己；測試在假 root 裡給數字）、`--s6-bin 路徑`（s6 的 bin，預設試驗場 `/home/<我>/code/try/sandbox/s6-root/bin`）、`--runner 名`（跑不信任函數的帳號與群組，預設 `aos-run`）；repo 現行沒有 `SetupFlagsTest`，乾跑旗標需手動核對。從 repo 根跑以下指令（不帶 `--apply`，只印不執行），確認輸出採用指定的 s6 路徑、使用者與 runner；乾跑不讀取 s6 執行檔，示例的 `--s6-bin` 路徑不必存在：

```sh
sh proto8/py/aos/apps/sandbox/root/setup.sh --me "$(id -un)" --s6-bin /tmp/pf-line5-impl-check/s6/bin --runner aos-pf-line5-check
```

## 需要

`bwrap`（bubblewrap）、`python3`；設定寫了上限或 `user` 才要 s6（`s6-softlimit`；root 身分層的 `s6-setuidgid`、`s6-applyuidgid` 照 PATH 找；非 root 另需 sudo 與固定 `/usr/local/bin/s6-setuidgid`）。這台 Arch 的官方庫沒有 s6，試驗場自己編了一份到 `~/code/try/sandbox/s6-root/bin`（11-15 已刪，要用得重編）（skalibs 2.16.0.0、execline 2.10.0.0、s6 2.15.1.1，skarnet.org 原始碼）。

**搬不走的那半**：帳號、sudoers、`/srv` 下的配置與 bind 的主機路徑都屬於這台機器；搬完先改 bind 路徑，再重跑 [root/setup.sh](root/setup.sh)（先乾跑，核對後 `--apply`；信箱另帶 `--mailbox`），不會因複製 image 自動重建。
