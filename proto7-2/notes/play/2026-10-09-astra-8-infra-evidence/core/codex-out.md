本線收斂出 5 條：A 類 3 條、B 類 2 條；最值得先驗的是倒數落盤故障後仍開回合，重起可能超跑整份額度。  
受測 HEAD 為 `cd544440`。全程未寫檔、未連網；只執行無寫入的解析與記憶體故障注入。以下涉及臨時檔與 daemon 的完整重現腳本尚未實跑，實際結果明列為推斷。  
已排除既知 once_retry 窗口、槽控制檔互蓋界線與 kernel 內部舊發現。

### NEW-core-1〔A／daemon，中〕倒數存檔失敗仍開回合，重起可超跑整份額度

- 契約：`proto7-2/spec.md:81`「開回合前若有倒數，先在 paused.json 記 `owe`」；`proto7-2/spec.md:14`「先寫證據再動作」；`proto7-2/notes/decisions-2026-10-09.md:74`「不確定時寧可少跑不多跑」。
- 程式：`proto7-2/lib/aos7_daemon.py:173` 存檔失敗後 `self.owe.pop(nid, None)`，`:175` 只記錯、不向外傳；`proto7-2/lib/aos7_daemon_timeline.py:245` 呼叫 `mark_owe(...)` 後，`:252` 直接執行 tick。關回合後存檔再失敗也只記錯（`aos7_daemon.py:196`）。
- 已知限制的延伸：決策檔 `:76` 列的是中途 resume／舊 tick 交接造成「多一回合」。此案倒數在啟動前已落盤，兩回合都關完，故障期間卻完全沒有扣款證據；額度 N 可重跑 N，並非只多一回合。
- 重現：

```bash
T=$(mktemp -d /tmp/astra8-core-XXXX)
export T PYTHONDONTWRITEBYTECODE=1
python3 -B - <<'PY'
import json, os, pathlib, subprocess, sys, time

t = pathlib.Path(os.environ["T"])
root = t / "root"
(root / ".aosd").mkdir(parents=True)
(root / "n/.aos").mkdir(parents=True)

def put(path, obj):
    path.write_text(json.dumps(obj))

def read(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}

put(root / ".aosd/nodes.json", {"nodes": {"n": {}}})
put(root / ".aosd/paused.json",
    {"paused": {}, "steps": {"n": {"k": 2}}})
put(root / "n/.aos/tasks.json", {"tasks": []})
put(root / "n/.aos/timeline.json", {"interval_ms": 50})

hook = t / "hook.py"
hook.write_text("""
import errno, os, signal
writes = 0
closed = 0
def inject(op, path):
    global writes
    if op == "write" and os.path.basename(path) == "paused.json":
        writes += 1
        if writes > 1:  # 啟動時保存成功；之後持續 EIO
            raise OSError(errno.EIO, "astra8 paused write")
def test_point(name):
    global closed
    if name == "round-closed-before-steps":
        closed += 1
        if closed == 2:
            os.kill(os.getpid(), signal.SIGKILL)
""")

cmd = [sys.executable, "-B", "proto7-2/bin/aos7-daemon", str(root)]
env = dict(os.environ)
env.pop("AOS7_TEST_HOOKS", None)
processes = []
try:
    with (t / "daemon.log").open("w") as log:
        first = subprocess.Popen(
            cmd, env=dict(env, AOS7_TEST_HOOKS=str(hook)),
            stdout=log, stderr=log)
        processes.append(first)
        try:
            first.wait(timeout=8)
        except subprocess.TimeoutExpired:
            first.kill()
            first.wait()
        print("first_round =", read(root / "n/.aos/round.json").get("round"))
        print("saved =", read(root / ".aosd/paused.json"))

        second = subprocess.Popen(cmd, env=env, stdout=log, stderr=log)
        processes.append(second)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            row = read(root / ".aosd/status.json").get("nodes", {}).get("n", {})
            if row.get("phase") == "paused":
                break
            if second.poll() is not None:
                raise RuntimeError("second daemon exited; inspect daemon.log")
            time.sleep(.05)
        else:
            raise RuntimeError("did not pause")
        print("final_round =", read(root / "n/.aos/round.json").get("round"))
finally:
    for p in processes:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
PY
rm -rf "$T"
```

- 預期／推斷實際：照契約，證據寫不進去時停止開新回合，恢復後累計不超過 2 回合。推斷目前印出 `first_round = 2`、磁碟仍是 `steps={"n":{"k":2}}` 且沒有 owe；重起後 `final_round = 4`。
- 修法：`mark_owe` 未落盤就退避、不 tick；結算失敗保留待提交狀態，成功落盤前不開下一回合。

### NEW-core-2〔A／指示詞解析，低〕A9-03 修補漏掉超長前導零，承諾接受的索引仍會崩潰

- 契約：`proto7-2/notes/decisions-2026-10-09.md:73`「前導零索引維持舊行為（照收）」；`proto6/spec/inst.md:37` 解析驗證失敗應印「代號: 白話」、回 125。
- 程式：`proto7-2/lib/aos_directives.py:223` 用 `len(tok.lstrip("0"))` 檢長度，卻仍執行 `int(tok)`；`:226` 又轉換一次原字串。`proto7-2/lib/aos_inst.py:99` 只包裝 `DirectiveError`，原始 `ValueError` 會逸出。
- 與舊案區別：A9-03 原案是超長且越界的索引；此案索引數值就是 0，依本專案明定語意應接受。無寫入的 `load_obj` 探針已確認：普通 `0` 成功、4301 個 `9` 回具名錯誤、4301 個 `0` 漏出 `ValueError`。
- 重現：

```bash
T=$(mktemp -d /tmp/astra8-core-XXXX)
export T PYTHONDONTWRITEBYTECODE=1
python3 -B - <<'PY'
import json, os, pathlib
p = pathlib.Path(os.environ["T"]) / "inst.json"
p.write_text(json.dumps({
    "arr": ["/bin/true"],
    "argv": [{"$ref": "", "$at": "/arr/" + "0" * 4301}]
}))
PY
PYTHONINTMAXSTRDIGITS=4300 \
  python3 -B proto7-2/bin/aos-exec "$T/inst.json"
printf 'rc=%s\n' "$?"
rm -rf "$T"
```

- 預期／推斷實際：預期解析成 `/bin/true`，退出 0。推斷 CLI 實際 traceback，末尾為 `ValueError: Exceeds the limit (4300 digits)...`，退出 1。
- 修法：將去前導零後的字串（空時用 `"0"`）轉換一次，範圍判定與取值共用該整數。

### NEW-core-3〔A／tools，中〕aos7-ctl 寫入故障直接 traceback，尚未接上統一錯誤路徑

- 契約：`proto7-2/notes/blueprint-errors.md:18` 讀寫故障退 3；`:25` 人話錯誤固定一行；`:17` 參數錯退 2。工具包的寫檔職責見 `proto7-2/modules/tools/README.md:17`。
- 程式：`proto7-2/modules/tools/aos7_ctl.py:162` 把 argparse 的非零退出一律轉 1；`:167` 直接呼叫 `daemon_ctl`，其 `:94` 的 `write_json` 沒有 OSError 邊界。task／add 分支也只捕捉 `Unknown`（`:183`、`:197`）。
- 重現：

```bash
T=$(mktemp -d /tmp/astra8-core-XXXX)
export T PYTHONDONTWRITEBYTECODE=1

python3 -B proto7-2/bin/aos7-ctl --not-an-option
printf 'bad-args rc=%s\n' "$?"

# 對真 CLI main 的寫入邊界注入 EIO；不依賴 chmod 或執行者權限。
python3 -B - <<'PY'
import errno, os, sys
from unittest.mock import patch
sys.path[:0] = [
    "proto7-2/modules/tools", "proto7-2/modules/control", "proto7-2/lib"
]
import aos7_ctl
with patch.object(aos7_ctl, "write_json",
                  side_effect=OSError(errno.EIO, "astra8 write failure")):
    sys.exit(aos7_ctl.main(["daemon", os.environ["T"], "register", "n"]))
PY
printf 'write-error rc=%s\n' "$?"
rm -rf "$T"
```

- 預期／推斷實際：預期壞參數退 2；EIO 退 3、stderr 一行 `aos7-ctl: 不確定：…`。壞參數退 1 已實測；記憶體注入已確認 OSError 逸出，完整腳本推斷退 1 並印 traceback。`tests/error_path.json` 目前未列 ctl，因此一致性驗收沒有涵蓋此入口。
- 修法：在 ctl CLI 邊界統一處理參數錯、Unknown 與 OSError，並補進 error_path 驗收清單。

### NEW-core-4〔B／events，中〕讀者把 I/O 故障當成功，局部契約與全域錯誤規則矛盾

- 契約：`proto7-2/notes/blueprint-errors.md:41`「不知道不能降成 0」，且讀不了檔仍退 0 的唯一豁免是 metrics。
- 相反的局部契約：`proto7-2/modules/events/ADVANCED.md:51` 將 read 定義為「讀完（errors／gaps 仍列在結果）」退 0，3 僅用於舊 `--ack`。
- 程式：`proto7-2/modules/events/aos7_events_read.py:57` 捕捉 OSError 後只加 `file_unreadable`；`:180` 印 JSON，`:181` 無條件 `return 0`。
- 重現：

```bash
T=$(mktemp -d /tmp/astra8-core-XXXX)
export T PYTHONDONTWRITEBYTECODE=1
python3 -B proto7-2/modules/events/aos7-events pub \
  --events "$T/events" --create --node n \
  --kind hello --event-id e1 --payload '{}'

python3 -B - <<'PY'
import errno, os, sys
from unittest.mock import patch
sys.path[:0] = ["proto7-2/modules/events", "proto7-2/lib"]
import aos7_events_read as reader

events = os.path.join(os.environ["T"], "events")
original = open
def fault(path, *args, **kwargs):
    if os.fspath(path) == os.path.join(events, "obs.active.jsonl"):
        raise OSError(errno.EIO, "astra8 read failure")
    return original(path, *args, **kwargs)

with patch("builtins.open", fault):
    sys.exit(reader.main(["--events", events]))
PY
printf 'read rc=%s\n' "$?"
rm -rf "$T"
```

- 預期／推斷實際：預期保留 JSON 診斷，同時退 3、stderr 說明讀取不確定。推斷實際 `records=[]`、`errors=[{"kind":"file_unreadable",…}]`，卻退 0、stderr 空白；同一分支已用無寫入注入確認。
- 修法：把 I/O／state 不可讀與正常 retention gap 分流，前者退 3 並補人話；同步修改 ADVANCED 的退出碼表。

### NEW-core-5〔B／events，低〕超大事件退 2，卻已建立目錄、鎖與 state

- 契約：`proto7-2/notes/blueprint-errors.md:17` 退出 2「什麼都沒動」；`proto7-2/modules/events/ADVANCED.md:50` 將 `too_large` 歸退出 2，`:87` 保證「用法錯不寫」。
- 程式：`proto7-2/modules/events/aos7_events_store.py:284` 先拿會建目錄與鎖檔的 `locked`（`proto7-2/lib/aos7_fs.py:197`、`:199`）；`:287` 先恢復；直到 `aos7_events_store.py:231` 才判大小，且 `:232` 明確 `write_json(path, st)` 後回 `too_large`。`modules/events/spec.md` 的 append 節也明寫「dup、too_large、full 保存恢復後 state」，與全域規則不一致。
- 重現：

```bash
T=$(mktemp -d /tmp/astra8-core-XXXX)
export T PYTHONDONTWRITEBYTECODE=1
python3 -B - <<'PY'
import json, os, pathlib, subprocess, sys
events = pathlib.Path(os.environ["T"]) / "events"
p = subprocess.run([
    sys.executable, "-B", "proto7-2/modules/events/aos7-events",
    "pub", "--events", str(events), "--create", "--node", "n",
    "--kind", "big", "--event-id", "big-1",
    "--payload", json.dumps("x" * 65536)
], capture_output=True, text=True)
print("rc =", p.returncode)
print(p.stdout.strip())
print(p.stderr.strip())
print("files =", sorted(x.name for x in events.iterdir())
      if events.exists() else [])
PY
rm -rf "$T"
```

- 預期／推斷實際：預期退 2 且 `events/` 不存在。推斷實際退 2、`why="too_large"`，但留下 `state.json`、`state.json.lock`；事件本身沒有追加。
- 修法：將 CLI 可判定的大小拒絕提前至建立目錄／鎖之前，並對齊保存端與退出 2 的副作用契約。

### 看過但沒問題

- A9-01：仍在 reaping 且沒有時間線時恢復 missing，清除回收義務前不開新線。
- K 系列：runner 尚未完成啟動時保留 kill 請求；unregister 的回收義務先落盤。
- events 保存端：append／ack／recover 共用鎖；輪替後先保存 state，再寫新 active；12 檔為清理完成後上限，原子寫暫存檔例外已有文件。
- history A9-02：歧義舊檔先封存 `.v1`，撞名加流水號，標記完成後不再逐回合封存。
- control：先加釘槽 once 再送綁 run 的 kill；tasks 表鎖內重讀 birth。
- once_retry：鎖內重讀 birth 已加入；鎖後槽重用窗口屬已列明的至少一次限制。
- subd／audit：子根以 realpath 判界；audit 的 busy 改為 thread-local；豁免路徑限制在自身 node 內。
- wait-tock：輪詢不寫檔，舊 run 通知不當新通知。
- kernel 接點：kill 帶原 run／id，核心回條保留原請求欄位；不改殺新 run。
- up 安裝：現版是 budget-llm、brain、compact、routines 四個 keep 任務，與 ADVANCED 一致；kernel 明文要求另外安裝。

### 可疑未證

- kernel 檢查 ctl 空缺至實際写入之間存在競態，但核心明列不同寫者互蓋不保證，tools 也明寫覆蓋既有請求；目前不另編號，需先釐清是否要提供跨寫者仲裁契約。

### 沒看完

- 未逐一審遍歷史測試與長跑範例。
- 未實跑 SIGKILL／EIO／多寫者壓力矩陣；上述臨時目錄腳本待可寫環境核對。
- kernel 內部規則、brain／llmcall 業務恢復依分工未重審。