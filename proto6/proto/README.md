# proto6 第一段可跑原型

這一版把「daemon 啟動 → root 跑一格 → 登記子 node → wake → git 提交」接起來。用 Python 3.9+ 標準函式庫，不需安裝 Python 套件；另需 Linux 5.14+、git 2.35+、可寫的 cgroup v2 委派子樹。沒有 helper，不切 UID、不用 sudo。

所有程式與測試都在這個資料夾；沒有修改 spec，也不對外層 aos repo 做 git add／commit／push。`node new` 與 tick 會在**使用者指定的新 node repo** 建初始／group commit，這是功能本身。

## 先跑測試

在 repo 根目錄：

```sh
cd proto6/proto
export PATH="$PWD/bin:$PATH"
python3 -m unittest discover -s tests -v
```

測試資料建在本資料夾的 `.test-tmp/`，結束會收掉；不依賴檔名排序或固定長時間 sleep，等待都輪詢／select 並設逾時。git 作者由測試環境提供，不改你的 global git config。真 cgroup 案例先探測 systemd user scope，不可用才帶原因 skip；本次開發環境實際跑過真 cgroup。

## 手動跑一遍

先把 `proto6/proto/bin` 的**絕對路徑**放入 PATH。daemon 用固定絕對路徑開 aos-runner，但 inst 的 `aos-tick` 依 PATH 找。git 初始／group commit 使用你的 git 作者設定；未設定時先在適當範圍設定作者，或為本次命令提供 `GIT_AUTHOR_NAME/EMAIL` 與 `GIT_COMMITTER_NAME/EMAIL`。

以下示範用目前資料夾下的 `.demo` 放 node 與設定，socket 放短的 runtime 路徑，避免 Unix socket 108-byte 路徑限制：

```sh
# 在 proto6/proto 下
export PATH="$PWD/bin:$PATH"
mkdir -p .demo
python3 - <<'PY'
import json, os
from pathlib import Path
base = Path('.demo').resolve()
tasks = {'_metainfo': {'_type': 'aos-tasks', '_version': 1}, 'tasks': [
    {'id': 'hello', 'kind': 'custom', 'argv': ['sh', '-c', 'echo hi > out.txt']}
]}
(base / 'tasks.json').write_text(json.dumps(tasks))
config = {'version': 1, 'socket_path': '/run/user/%d/aos-proto6/d.sock' % os.getuid(),
          'state_dir': str(base / 'state'),
          'roots': [{'node_id': str(base / 'R'), 'identity_grant': [os.getuid()]}]}
(base / 'daemon.json').write_text(json.dumps(config))
(base / 'grant.json').write_text(json.dumps([os.getuid()]))
PY
aos node new "$PWD/.demo/R" --tasks "$PWD/.demo/tasks.json"
aos node new "$PWD/.demo/C" --tasks "$PWD/.demo/tasks.json"
systemd-run --user --scope -p Delegate=yes --quiet -- \
  "$PWD/bin/aos" daemon start --config "$PWD/.demo/daemon.json"
```

最後一個命令在前景執行，看到 `helper_pid=none` 後，另一個終端機（同樣設定 PATH、在 proto6/proto 下）執行：

```sh
aos daemon info --daemon-config .demo/daemon.json
aos show .demo/R --daemon-config .demo/daemon.json --json
aos register .demo/C --parent .demo/R --identity-grant .demo/grant.json \
  --yes --daemon-config .demo/daemon.json
aos wake .demo/C --daemon-config .demo/daemon.json
aos ls --daemon-config .demo/daemon.json
# 查結果：completed 是程序跑完，不保證業務成功；還要看 exit_code。
git -C .demo/R log --oneline
git -C .demo/C show HEAD:out.txt
```

wake 只是接受請求，請等 show 的 `running:false`、`last_tick.outcome:completed` 且 `exit_code:0` 後再讀提交結果。前景按 Ctrl-C，或對 `.demo/state/daemon.pid` 的 PID 送 SIGTERM，會先停新格、TERM、寬限、必要時 cgroup.kill，確認全空才正常退出並移除 socket／兩個 PID 檔。

### 只給測試用的假 cgroup

`--x-fake-cgroup DIR` 是隱藏旗標，**不提供資源隔離或安全邊界**。不用 systemd 時可測協議與排程；真部署不要開它。

```sh
python3 - <<'PY'
from pathlib import Path
from aosproto.cgroup import FakeCgroup
p = Path('.demo/fake-cgroup').resolve()
FakeCgroup(p).create(p)
PY
aos daemon start --config "$PWD/.demo/daemon.json" \
  --x-fake-cgroup "$PWD/.demo/fake-cgroup"
```

此例設定不寫 cgroup_root，所以使用假 DIR。要測自建子樹，設定 cgroup_root 為 DIR 下新目錄、加 `--create-cgroup`；沒開 create 不會偷偷建。假後端的 PID 清理與真核心仍有差異，見 G-12。

## 有哪些指令

- `aos daemon start --config F [--create-cgroup]`；`aos daemon --config F` 同義。
- `aos daemon info --socket S [--json]`。
- `aos node new N [--tasks F]`；省略 tasks 建空任務表。已存在目標回2，不提供 template/user/socket/agent-config。
- `aos node register T --parent N --identity-grant F [--interval-ms M | --once] [--yes] --socket S [--json]`。F 是 UID／帳號陣列；不自動 wake。
- `aos node unregister T [--yes] --socket S [--json]`：排空目標與子樹才解除。
- `aos node wake|pause|resume|show T --socket S [--json]`。resume 支援 --yes；pause 等到 running:false 才返回。
- `aos node ls [--node T ...] --socket S [--json]`：自動分頁，或逐筆 show。
- `aos node tick N`；`aos inst run [T] [--timeout-ms M] [--stderr F] [--json]`。

node 的上述短形（new/register/unregister/wake/pause/resume/show/ls/tick）與 `aos run` 都可用。IPC 的 `--socket S` 可換 `--daemon-config F`。unregister/resume 會確認，非互動環境加 --yes。IPC `--json` 印原始 RpcResponse；inst run 印 runner report，不能搭配合法的 inherit stdout。其餘命令／旗標回2並說原型未實作。

## 實作界線

- 原始 JSON 拒重複 key、BOM、非有限數、尾隨資料；協議物件拒未知欄位，inst 依其規則忽略額外一般欄位。
- 單執行緒 selector 處理 Unix socket；身分只取 SO_PEERCRED UID，授權沿記憶體可信 parent 鏈。
- daemon 明確 `fork → cgroup.procs → dup2/關 fd → execv`。inst 快照是 `memfd_create`、寫入、加 seal，再以 O_RDONLY 重開；等同 C 的同名 syscall/fcntl。status pipe 不傳入業務子程式。
- runner/tick 共用解析與執行函式。Popen 對應 fork/exec、dup2、close_fds、setsid；Linux subreaper 收養雙重 fork 後代，清空後才進下一項／寫 exit。timeout 先 TERM，再等2秒後 KILL。
- tick 持 git 管理目錄內同一把 flock，將鎖 fd 傳給任務；完整驗表後才跑。每組以開始時的 ignore 規則決定提交範圍，成功 commit、失敗 reset/clean；不使用 clean -x。HEAD／分支被任務換掉會擋新格並保留現場。
- daemon 的 runner 診斷用 `.aos/runner-stderr.log`；node new 會 ignore。自行準備 node 時也要 ignore 此檔，避免 tick 格首 clean 刪掉診斷。

## 還沒做

取值指示詞、root helper／切 UID、provision 動作、controller／資源上限、state.json 保存恢復、ops 正式事項、outbox／收件／summary／published.json、kernel／agent 業務命令都不在本輪。

resume **只開 IPC 閘門**，尚未做 P-210 的驗證與採用手改提交。不同內容重登一律衝突；limits 暫回 `{}`；尚不存在帳號的 identity_grant 預授未做。CLI 分頁中遇到 boot_id 改變回1要求重列。登記時 inst user 必須已存在（once 也一樣）；省略 cgroup_root 時 daemon 把原層程序都搬進 `daemon` 葉框。完整規格缺口與一次性例外見 [spec-gaps](notes/spec-gaps.md)。

假 cgroup 無法模擬核心的原子繼承與 PID 重用安全；同 UID 的惡意任務也不是本原型的隔離目標。正式驗收程序清空請以真 cgroup 為準。

## 檔案導航

| 檔案 | 負責內容 |
|---|---|
| `bin/aos`、`bin/aos-runner`、`bin/aos-tick` | 可直接執行的入口，自行設定 sys.path |
| `aosproto/common.py` | 嚴格 JSON、錯誤、UID、P-010 選檔、fsync／不覆蓋發布 |
| `aosproto/config.py` | 版本自檢、設定與登記格式、身分額度 |
| `aosproto/cgroup.py` | Real/Fake 共同介面、準備、TERM/KILL／排空 |
| `aosproto/inst.py`、`process.py` | 共用 inst 驗證、選項、程序與 exit 收尾 |
| `aosproto/runner.py`、`launch.py` | runner 入口、密封快照、daemon fork/exec、可信回報檢查 |
| `aosproto/registry.py`、`daemon.py` | 可信登記授權、生命週期、排程、socket RPC |
| `aosproto/tick.py`、`git_scope.py` | 任務表、group/needs、鎖、基線 ignore 與 git 提交 |
| `aosproto/cli.py` | CLI、alias、node new、RPC client、人讀輸出 |
| `tests/support.py` | 有逾時的輪詢、隔離 fixture、CLI/daemon 啟停 |
| `tests/test_basics.py` | 自檢、設定、cgroup 準備、授權與回報證據 |
| `tests/test_runner.py`、`test_tick.py` | 執行器、fd、exit、timeout、group 與 git 故障 |
| `tests/test_daemon.py` | 假／真 cgroup 端到端、once、排程、IPC、重啟清舊 |
| `notes/spec-gaps.md` | 本輪缺口、暫行做法與待問問題 |
