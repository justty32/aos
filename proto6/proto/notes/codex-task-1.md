# codex 任務書 1：proto6 第一段原型（daemon 啟動＋登記＋tick 一次）

你在 git repo `/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4df97cfbb8f29bc4`。規格在 `proto6/spec/`（中文）。你要在 `proto6/proto/` 從零寫一個能跑的最小原型。

## 硬規則

1. **只准新增／修改 `proto6/proto/` 底下的檔案。** 不准改 spec、notes、其他任何目錄。
2. **不准 git commit、不准 git add、不准 push。** 我（隊長）會驗收後自己 commit。
3. 語言 Python 3.9+，**只准標準函式庫**。不要用 asyncio、dataclass 花招、metaclass、裝飾器魔法；結構寫得像之後能直接翻成 C++11／C99（明確的 fork/exec、fd、poll 或執行緒、簡單類別與函式）。`subprocess` 可用，但要能看出對應的 fork/exec 步驟。
4. 不准用 sudo、不准要求 root。這台是 Manjaro，一般使用者、cgroup v2、systemd --user 有委派（`systemd-run --user --scope -p Delegate=yes` 可用）。
5. 測試用 `unittest`，全部要綠：`cd proto6/proto && python3 -m unittest discover -s tests -v`。需要真 cgroup 委派的測試，條件不成立就 `skipTest("原因")`，不准失敗。
6. 測試不能依賴檔名排序代表時間先後；不能 sleep 固定長時間賭時序，要輪詢加逾時（上限幾秒）。
7. 總工時目標 40 分鐘內。做不完的，照「回報格式」寫在「留下一輪」。
8. 撞到 spec 講不清楚或互相矛盾的地方，**不要改 spec**，寫進 `proto6/proto/notes/spec-gaps.md`，每條：`## G-n．<條號> 一句話標題`，下面三行「卡在哪」「原型暫時怎麼做」「建議問使用者什麼」。這份很重要，請認真記，至少把本任務書「已知洞」那幾條也寫進去。

## 要讀的 spec（依序）

- `proto6/spec/daemon.md`：B-601、B-603（只做啟動清舊 cgroup）、B-605（全部）
- `proto6/spec/protocol/README.md`：P-002、P-004、P-005、P-006、P-010
- `proto6/spec/protocol/daemon/startup-and-ipc.md`：P-101、P-103（P-102 只做「無 helper 模式」）
- `proto6/spec/protocol/daemon/registration.md`：P-104、P-105、P-106、P-115
- `proto6/spec/protocol/daemon/provision-and-runner.md`：P-109、P-110、P-111（P-107 只讀「daemon 開格前自己建框（不寫上限）」那句）
- `proto6/spec/base/inst.md`：全篇，但**指示詞（`$ref`/`$env`/`$at` 等取值指示詞）這一輪不做**
- `proto6/spec/protocol/node.md`：P-200、P-202、P-203、P-204、P-205（P-206 以後不做）
- `proto6/spec/tick.md`：B-602、group 與 needs、git 提交與還原
- `proto6/spec/cli/README.md`、`proto6/spec/cli/commands.md` 的 daemon／node 表、`proto6/spec/cli/mapping-and-alias.md`
- schema：`proto6/spec/protocol/schemas/daemon-config.schema.json`、`daemon-rpc.schema.json`、`daemon-registration.schema.json`、`daemon-runner-report.schema.json`、`node-inst.schema.json`、`node-tasks.schema.json`、`common.schema.json`；範例在 `proto6/spec/protocol/examples/daemon/`、`examples/node/`

## 範圍（要做的）

### 目錄

```
proto6/proto/
  README.md            怎麼跑、做了什麼、還沒做什麼（用繁體中文，白話）
  bin/aos              CLI 入口（#!/usr/bin/env python3，可執行）
  bin/aos-runner       P-109 runner
  bin/aos-tick         P-203 tick
  aosproto/            共用程式（套件）
  tests/               unittest
  notes/spec-gaps.md
```
bin 腳本自己把 `proto6/proto` 加進 sys.path，不需安裝。daemon 開 runner 時用同目錄的 `bin/aos-runner` 絕對路徑（不靠 PATH）；inst 的 `argv[0]` 若是 `aos-tick`，照 PATH 找 —— 測試與 README 裡把 `proto6/proto/bin` 加進 PATH。

### 1. `aos daemon start --config F [--create-cgroup]`（alias `aos daemon --config F`）

- 讀設定：照 P-101 表與 daemon-config schema 手寫驗證（不要依賴 jsonschema）；拒絕未知欄位、重複 key（`object_pairs_hook`）。設定錯回 **2**。`create_cgroup:true`（或 `--create-cgroup`）而沒寫 `cgroup_root` 也回 2（見已知洞 1）。
- **自檢（B-605）**：Linux kernel ≥ 5.14（解析 `os.uname().release` 前兩段數字）、Python ≥ 3.9、`git --version` ≥ 2.35、cgroup v2 可用（`/proc/self/mounts` 有 `cgroup2` 掛載點）。不合 → stderr 說明、回 **125**。把「比版本」寫成可注入的純函式，單元測試餵假版本。
- **cgroup 子樹（B-605 通用規則）**：
  - 子樹路徑＝`cgroup_root`；省略就用 daemon 自己的 cgroup（`/proc/self/cgroup` 的 `0::` 行＋cgroup2 掛載點）。
  - 「準備好」＝資料夾存在；資料夾與 `cgroup.procs`、`cgroup.subtree_control`、`cgroup.threads` 對目前帳號可寫；而且 daemon 自己目前就在這棵子樹裡（自己的 cgroup 路徑等於或位於子樹之下，按路徑元件比，不用字串前綴）。
  - 不準備好：沒開 create → 125；開了 create → `mkdir` 建 `cgroup_root`，建不了 → 125；建好後仍須符合「準備好」（daemon 不在裡面時，嘗試把自己寫進去；失敗 → 125 並說明原因是 cgroup v2 需對共同上層有寫權）。已存在就不重建。
  - 通過後：daemon 把自己搬進子樹下的葉框 `<子樹>/daemon`；node 的框：頂層 node 是 `<子樹>/n-<sha256(node_id) 前 16 hex>`，子 node 的框放在其 parent 的框之下（同一命名法）；本 node 的 tick 程序放在 `<node 框>/tick` 葉框。once 放在 **parent 的框**之下的 `once-<hash>` 葉框。命名是原型自訂，記到 spec-gaps。
  - 這一輪**不寫任何資源上限**、不動 `subtree_control`。
- **測試用假 cgroup**：加一個隱藏旗標 `--x-fake-cgroup DIR`（README 標明只給測試用）。開了之後：cgroup2 掛載點與「daemon 自己的 cgroup」都當作 DIR，所有 cgroup 動作走一個 FakeCgroup 後端：建框就是 mkdir＋建空的 `cgroup.procs` 等檔；搬程序就是在 `cgroup.procs` 追加 PID 一行；「框是否全空」＝框及子框 `cgroup.procs` 裡列的 PID 沒有一個還活著（`os.kill(pid, 0)`）；`cgroup.kill` 就是對還活著的列出 PID 送 SIGKILL（並寫 `1` 到 `cgroup.kill` 檔留紀錄）。真後端（RealCgroup）用真檔案。兩者同一介面。
- **啟動清舊（B-603 的一小部分）**：開任何新格前，掃子樹下所有 node 框（`n-*`、`once-*`、`tick` 葉），只要還有程序：先對它們送 SIGTERM，等 `shutdown_grace_ms`（預設 2000），再寫 `cgroup.kill`，輪詢確認全空才往下；清不掉 → 125。
- **socket**：`socket_path` 父目錄不存在就建（0750）；取同目錄 `daemon.lock` 的非阻塞 flock，拿不到 → 125（有別的 daemon）；持鎖後可刪殘留 socket；bind 後 chmod 0660。`state_dir` 不存在就建；寫 `state_dir/daemon.pid`、`state_dir/helper.pid`（內容 `none`）。stdout 印一行 `helper_pid=none` 並 flush。
- **無 helper 模式**（P-102/B-303）：通用 user＝`common_user`（有寫就解析成 UID；若不等於目前 UID → 設定錯 2），沒寫就是目前 UID。所有 node 的 inst `user` 都必須解析到通用 user，否則該格 launch_failed（UserNotGranted／user_not_granted）。
- **頂層**：照 `roots` 登記（`node_id` 必須是資料夾且有 inst，照 P-010；找不到 → 2），`owner_uid`＝該 root inst 的原始 `user` 解析結果（省略＝通用 user），必須在 `identity_grant` 內（按 UID 比，名稱先解析）；不合 → 2。啟動後每個 root 自動排一格（B-603）。
- **停機（最小版）**：SIGINT／SIGTERM → 不再開新格、對在跑的 tick 框送 SIGTERM、等 grace、`cgroup.kill`、確認全空、刪 socket 與兩個 pid 檔、回 0；清不空回 125。**不寫 state.json**（下一輪）。

### 2. IPC（P-103／P-104～106／P-115）

- Unix stream、一行一個 JSON-RPC、LF 結尾、單行上限 262144 bytes（超過回一次 invalid_request 後關連線）。回應沿用請求 id；取不到合法 id 時 `id:null`。錯誤照 P-005／P-111：保留碼＋`data:{code,retryable}`；業務錯 -32000。
- 身分只看 `SO_PEERCRED` 的 uid（`struct.unpack('3i', sock.getsockopt(SOL_SOCKET, SO_PEERCRED, 12))`）。
- 授權：寫成純函式 `authorize(peer_uid, method, target, registry)`，照 P-103 表（owner 或可信註冊鏈上任一祖先的 owner）。單元測試直接餵不同 uid 測 forbidden。
- 要做的 method：`daemon.info`、`node.register`、`node.unregister`、`node.wake`、`node.pause`、`node.resume`、`node.show`、`node.ls`（含 limit／after_node_id 分頁，按 node_id UTF-8 bytes 排）。其他 method（`node.provision`、`daemon.attention.*`）回 -32601。
- `node.register`：照 P-104。只接非頂層；`parent_id` 必須已登記；新成員的 `identity_grant` 必須是 parent 額度的子集（按 UID）；inst 的原始 `user` 必須在新額度內；`once:true` 不能帶 `interval_ms`；once 的目標可以是單檔 inst。相同內容重送回成功且不改狀態；內容不同照 P-104（這輪簡化：不同就回 `busy` 或 `registration_conflict`，擇一並記 gap）。新登記不自動跑。
- `node.wake`：照 P-105，running 時合併成一個 pending；paused 只記 pending。
- `node.pause`／`node.resume`：照 P-105（resume 只開閘，pending 或到期才跑）。
- `node.unregister`：阻止新格、等目標與已登記子樹全空（必要時 TERM → grace → cgroup.kill）、刪登記。
- `node.show`／`node.ls`：照 P-106 全部欄位（`boot_id`、`cgroup:{path,limits}`——這輪 limits 回 `{}` 或讀到的值，記 gap——、`last_tick` 六欄）。once 跑完解除後保留 `registered:false` 紀錄。
- `boot_id`：每次啟動用 `uuid.uuid4()`。

### 3. 開格（daemon 端）

- 每個 node 同時最多一格（B-602）；定期 node 依 `interval_ms`（從登記完成／上次收尾算）；wake 提前。
- 開格：`last_tick.started_at_ms` 記下、outcome=running；確保 node 框存在（不存在就建，不寫上限）；開一條 status pipe；fork/exec `bin/aos-runner --inst-fd N --target <node_id> --authorized-uid <owner_uid> --status-fd M`，**在子程序 exec 前把自己寫進 tick 葉框的 cgroup.procs**（寫 `0` 或自己的 PID），runner 的 stdin/stdout 為 /dev/null，stderr 收進 `<node>/.aos/attention/` 以外的診斷位置（資料夾 node：`<node>/.aos/runner-stderr.log`；once 單檔：不收，丟 /dev/null；記 gap）。inst fd 傳「daemon 讀到的原始 bytes」的唯讀 fd（可用 pipe 或 memfd；說明對應 C 的哪個 syscall）。
- 收尾：wait runner、讀 status pipe 一行 JSON、確認框全空（不空就 cgroup.kill 再確認）；依 P-106 填 last_tick（completed／launch_failed／unknown）。
- 非 once 的 runner 回報 exit_code 3 或 125、或沒有可信回報：設 `paused:true`，在 `<node>/.aos/attention/` 寫一個 JSON 事項（格式簡單就好，檔名用 `daemon-<boot_id>-<序號>.json`；記 gap），寫不出就 stdout 警告一行。
- once：跑一格後自動解除，保留 `registered:false` 紀錄；runner 回報 started:false 或 daemon 拒絕啟動時，在 inst 旁寫 `<inst 檔名>.err`（P-110，`{version:1,node_id,error}`，error 用小寫 code），不覆蓋既有檔。

### 4. `aos-runner`（P-109／P-110＋inst 第 1 版）

- argv：`aos-runner --inst-fd N --target /abs --authorized-uid UID --status-fd N [--stderr /abs] [--timeout-ms N]`；用法錯回 2。
- 從 inst fd 讀 bytes；再照 P-010 用 target 讀一次原來源，bytes 不同 → 125（UserMismatch 或 ReadFailed，記 gap）。
- inst 驗證與錯誤代號照 inst.md（`_metainfo`、`user`、`argv`、`stdin`/`stdout`/`stderr`/`exit`/`cwd`/`envs`、選項 inherit/append/mkdir/merge/clear 及衝突規則）。**遇到任何 `$` 開頭 key 的物件（取值指示詞）且不是 `$opt` 選項** → 125，代號 `DirectiveUnsupported`（原型自訂，記 gap 為「這輪沒做」）。
- `user` 解析成 UID，必須等於 `--authorized-uid`，否則 125 `UserNotGranted`。
- base 照 P-010；`cwd` 預設 base。子程式 `setsid`、依 envs 疊環境（不注入 AOS_*）、argv[0] 照 PATH 找。127／126 規則、signal → 128+N、`exit` 檔寫十進位＋LF 並 fsync 檔案與父目錄。timeout：對整組 TERM、2 秒後 KILL。
- status fd 寫一行 JSON（`daemon-runner-report` 形狀），只寫一次，子程式 exec 前關掉這個 fd。前置失敗 `{"started":false,"exit_code":125,"error":{"code":"...","message":"..."}}`，並在 stderr 印 `代號: 白話`。
- runner 的 exit code 與回報一致。

### 5. `aos-tick`（P-203／P-204／P-205，最小版）

- `aos-tick [--node DIR]`；省略用 cwd；DIR 必須是 git repo 根（`git rev-parse --show-toplevel` 等於它）。
- 鎖：`$(git rev-parse --absolute-git-dir)/aos/tick.lock` 非阻塞 flock，拿不到回 75；格首看到 `aos/tick-blocked` 回 125；repo 沒有初始 commit 回 125。
- 格首把受管工作區回到 HEAD（`git reset --hard -q HEAD` ＋ `git clean -fdq`（不加 -x，不碰 ignored））。
- 讀 `.aos/tasks.json`，照 P-202 驗證（`_metainfo`、id 唯一且符合 ID 規則、kind 順序 system→kernel/agent→custom、group 連續、needs 只指向前項、不准 `user`），錯 → 2、一項都不跑。
- 依序跑：每項當 inst 跑（**直接複用 runner 的 inst 解析與執行函式**，不要另寫一套；base＝node 根；不切 UID），環境加 `AOS_NODE_DIR`、`AOS_TICK_LOCK_FD`（鎖 fd 繼承給任務）。
- group／needs 照 tick.md：組內全成功 → `git add -A` ＋ `git -c core.hooksPath=/dev/null commit -q --no-verify -m "aos-tick group <first>..<last>"`（無 diff 不 commit）；失敗 → 還原到組開始的 HEAD（reset --hard ＋ clean -fd）。依賴失敗組的組跳過。
- 結束碼：0／1／2／3／75／125 照 P-203。commit／還原失敗 → 寫 `aos/tick-blocked`（UTF-8 原因）、回 3。
- 不做 outbox／收件／summary／published.json。

### 6. CLI（`bin/aos`，照 spec/cli 的 argv 與 stdout 格式）

要做的指令（含 alias）：
- `aos daemon start --config F [--create-cgroup]`、`aos daemon --config F`
- `aos daemon info --socket S [--json]` → `boot_id=…`
- `aos node new N [--tasks F]`（alias `aos new`）：建資料夾、`git init`、寫 `.aos/inst.json`（`{"argv":["aos-tick"]}`）、`.aos/tasks.json`（有 `--tasks` 就複製並驗證，否則空 tasks）、P-200 的 `.gitignore`、初始 commit；stdout `created N; initial_commit=<oid>; tasks=<項數>`。目標已存在 → 2。不做 `--template`、`--user`、`--socket`、`--agent-config`（用了回 2 並說明未實作）。
- `aos node register T --parent N --identity-grant F [--interval-ms M | --once] [--yes] --socket S [--json]` → `registered T (not woken)`
- `aos node unregister T [--yes] --socket S [--json]` → `unregistered T`（沒 `--yes` 時從 stdin 問 y/n，stdin 不是 tty 且沒 --yes → 125）
- `aos node wake T --socket S [--json]` → `wake accepted T`
- `aos node pause N --socket S [--json]` → pause 後輪詢 node.show 直到 running:false，印 `paused N; running=false`
- `aos node resume N --yes --socket S [--json]` → 這輪**不做 P-210 驗證與提交**，只送 IPC，印 `resume accepted N`（記 gap／還沒做）
- `aos node show T --socket S [--json]`、`aos node ls [--node T ...] --socket S [--json]`（人看的格式要把「已解除 once」「未啟動」「還在跑」「結果不明」分開）
- `aos node tick N` → exec `aos-tick --node N`
- `aos inst run [T] [--timeout-ms M] [--stderr F] [--json]`（alias `aos run`）→ 用目前 UID 跑 runner
- 短形 alias：`aos ls/show/new/register/unregister/wake/pause/resume/tick/run`
- `--daemon-config F` 取代 `--socket S`：讀設定裡的 socket_path。
- 失敗代稱與結束碼照 H-002（IPC：2 參數錯、125 前置、1 拒絕／斷線；stderr 印代號與白話）。`--json` 印原始 RpcResponse 一行。
- 其他 53 條指令不做；打了回 2 並印「原型未實作」。

## 必須有的測試（全綠或有理由 skip）

1. 版本比較純函式：kernel 5.13 → 失敗、5.14 → 過；git 2.34 → 失敗；Python 3.8 → 失敗。
2. 設定驗證：config.minimal.valid.json、config.create-cgroup.valid.json 過（改成測試用路徑後）；config.version.invalid、config.create-cgroup-no-root.invalid、未知欄位、重複 key → 回 2。
3. cgroup 準備檢查（假 cgroup 目錄）：子樹不存在且沒 create → 125；子樹不存在、開 create → 建起來並通過；子樹存在但 daemon 不在裡面（用注入的「自己的 cgroup 路徑」測）→ 125。
4. 授權純函式：owner 可、祖先 owner 可、無關 uid → forbidden；daemon.info／node.ls 任何人可連。
5. **端到端（假 cgroup）**：用 `aos node new` 建頂層 node R（tasks：一個 custom 任務 `sh -c 'echo hi > out.txt'`）與子 node C（任務寫 `result.txt`）；寫 config（roots=[R]、socket 在暫存目錄）；背景開 `aos daemon start --config ... --x-fake-cgroup DIR`；等 stdout 出現 `helper_pid=none`；輪詢 `aos node show R` 到 last_tick.outcome=completed、exit_code=0，且 R 的 git log 有 `aos-tick group` commit、`out.txt` 已提交；`aos node register C --parent R --identity-grant <檔> --yes`；`aos node show C` 的 last_tick 為 null；`aos node wake C`；輪詢到 completed；C 的 `result.txt` 已提交；`aos daemon info` 兩次同一 boot_id；`aos node ls` 看得到 R 與 C；最後送 SIGTERM，daemon 回 0、socket 與 pid 檔消失。
6. once：登記一個單檔 inst（`user` 寫一個不存在的帳號名，例如 `aos-no-such-user`）→ wake → 產生 `<檔名>.err`、`node.show` 顯示 registered:false、outcome=launch_failed、exit_code=125。
7. 停格：非 once node 的任務讓 tick 回 3（例如在 git dir 放 `aos/tick-blocked` 使 tick 回 125 也行）→ daemon 設 paused:true 並在 `.aos/attention/` 留一個檔。
8. runner 單元：inst 各欄位與選項、錯誤代號、exit 檔、127/126、signal 128+N、timeout、未授權 user → 125 不寫 exit。
9. tick 單元：壞任務表 → 2 且不跑；group 失敗還原不 commit；needs 指向失敗組 → 跳過；鎖被占 → 75；tick-blocked → 125。
10. **真 cgroup（可 skip）**：`shutil.which("systemd-run")` 存在且 `systemd-run --user --scope -p Delegate=yes --quiet true` 成功時，用 `systemd-run --user --scope -p Delegate=yes -- aos daemon start --config ...`（不給 cgroup_root）跑一次第 5 條的前半（R 跑完一格），並確認 R 的 tick 葉框在真 cgroup 下被建立；否則 skip 並寫明原因。
11. 啟動清舊（假 cgroup）：預先在假 node 框的 cgroup.procs 放一個活著的 `sleep 60` PID，啟動 daemon 後該程序被收掉（先 TERM）才開格。

## 已知洞（先寫進 spec-gaps.md，實作中再加）

1. P-101／B-605：`--create-cgroup` 從 CLI 開、設定沒寫 `cgroup_root` 時該回 2（用法／設定錯）還是 125（初始化失敗）？P-101 只說「開了卻建不了」是 125。原型：回 2。
2. B-605／P-107：node 框、tick 葉框、once 葉框、daemon 葉框的**命名與樹形**沒定；node id 是任意長路徑，不能直接當 cgroup 名。原型：`n-<sha256 前 16>` 巢狀在 parent 框下、`tick`／`once-<hash>` 葉框。
3. B-605：「cgroup_root 省略就用 daemon 自己的 cgroup」，但 daemon 又要「搬進子樹下的一個葉框」—— 自己的 cgroup 如果還有別的程序（例如手動 `systemd-run --scope` 開的 shell），搬走後父框並非空，之後若要開 controller 會撞「no internal process」。原型：這輪不開 controller 所以不撞；記下來。
4. P-109：runner 的 stderr「由 daemon 收集為 node 診斷」，但收到哪裡沒定。原型：資料夾 node 寫 `<node>/.aos/runner-stderr.log`（覆寫）。
5. P-105：自動停格寫 `.aos/attention/` 的**檔名與格式**要看 ops P-601，這輪沒實作 ops。原型：簡單 JSON。

## 回報格式（寫進 -o 指定的輸出檔，也就是你最後一則訊息）

```
## 做了什麼
- 條列檔案與功能
## 測試
- 指令、總數、過幾個、skip 幾個（逐條寫 skip 原因）
## spec-gaps
- 共幾條，列標題
## 留下一輪
- 沒做完或偷懶的地方
```
