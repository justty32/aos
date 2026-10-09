本線在 `cd544440` 找到 **5 條：A 類 2 條、B 類 3 條**。最重要的是 LiteLLM 金鑰跨 tick 遺失，以及 compact 無法接收 llmcall 已交付的退出碼 4。
全程唯讀、無網路／LLM 呼叫；兩項接點用純記憶體 mock 核對，另實跑三個無副作用的 CLI 參數案。以下寫檔重現腳本未在本沙箱執行，供隊長核對。
入口盤點為 **31 支：17 支列入 error_path、12 支未列、2 支封存**；未重審 kernel 內部。

### NEW-xmod-1〔A／up→tick→brain→llmcall，高〕文件要求的 LiteLLM 金鑰在任務啟動時被丟掉

- 契約：`proto7-2/modules/up/ADVANCED.md:38`：「別處設 `AOS7_LITELLM_URL`，要金鑰設 `AOS7_LITELLM_KEY`」。
- 程式：
  - `proto7-2/lib/aos7_task.py:317`：「`if not k.startswith("AOS7_") or k.startswith("AOS7_TEST_")`」，移除金鑰與端點；`:321` 只補核心六個變數。
  - `proto7-2/modules/up/aos7_up.py:44` 建立設定，`:46` 保存 `litellm_url`，沒有金鑰接續機制。
  - `proto7-2/modules/up/aos7_up_brain.py:187` 複製已過濾的環境，`:190` 只補回 URL。
  - `proto7-2/packs/llmcall/aos7_llmcall_litellm.py:65`：「`key = os.environ.get("AOS7_LITELLM_KEY")`」；有值才加 Authorization。
- 已知限制的延伸：`proto7-2/notes/decisions-2026-10-09.md:39` 已記 K1 白名單及 AUDIT／SUBROOT 副作用；本條新增後果是 **up 文件承諾的需驗證端點無法使用**。
- 重現：攔住程序啟動，只檢查真正交給 runner 的環境；不連網、不呼叫 AI。

```bash
T=$(mktemp -d /tmp/astra8-xmod-key-XXXX)
export T
PYTHONDONTWRITEBYTECODE=1 python3 -B - <<'PY'
import os, sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path("proto7-2/lib").resolve()))
import aos7_task as task

root = Path(os.environ["T"])
node = root / "n"
node.mkdir()
ctx = SimpleNamespace(root=str(root), node=str(node), fnode=str(node),
                      round=1, node_id="n")
incoming = {
    "PATH": os.environ["PATH"],
    "AOS7_LITELLM_KEY": "astra8-test-only",
    "AOS7_LITELLM_URL": "http://example.invalid/v1",
}
with patch.object(task, "env_with_bin", return_value=incoming), \
     patch.object(task.subprocess, "Popen") as launch, \
     patch.object(task, "read_json", return_value=None):
    task.start_in_slot(ctx, {"name": "brain", "mode": "once",
                            "argv": ["true"]}, "brain", 1)
    env = launch.call_args.kwargs["env"]
    print("KEY_PASS =", "AOS7_LITELLM_KEY" in env)
PY
rm -rf "$T"
```

- 預期／推斷實際：依 up 契約，金鑰應有傳到 llmcall 的有效管道；實際 `KEY_PASS = False`，且 brain 無補回機制。環境過濾已用無寫入 mock 實測；需要金鑰的端點將收到沒有 Authorization 的請求。
- 修法：在 up／任務啟動接面提供明確的金鑰傳遞機制，保留核心身分變數的隔離，並補一個帶驗證資訊的離線接點測試。

### NEW-xmod-2〔A／compact→llmcall，中〕退出碼 4 的完整摘要被拒收，同一 pending 重跑仍卡住

- 契約：
  - `proto7-2/packs/llmcall/ADVANCED.md:46`：「4｜已交付但帳未清：usage 未知（pending）或超出預留（overrun）」。
  - `proto7-2/notes/blueprint-errors.md:19`：「不用重送；對帳」。
  - `proto7-2/modules/compact/ADVANCED.md:51`：「整理中斷會留 pending，下次 now／watch 先接完」。
- 程式：
  - `proto7-2/modules/compact/aos7_compact.py:376`：「`if reply.returncode:`」，`:377` 一律轉成「摘要沒拿到：llmcall 退出 …」、退出 3；`:378` 才讀交付結果。
  - `proto7-2/packs/llmcall/aos7_llmcall.py:79`：`pending`／`overrun` 回 4；`:250`～`:253` 已有 receipt 時重印並回相同結果。
  - `proto7-2/modules/compact/ADVANCED.md:99` 也寫「非 0 不拿半張回條」，與 llmcall 對 4 的完整交付定義衝突。
- 重現：用符合交付接面的本機替身回傳 4，不啟動 llmcall 或 AI。

```bash
T=$(mktemp -d /tmp/astra8-xmod-compact-XXXX)
export T
PYTHONDONTWRITEBYTECODE=1 python3 -B - <<'PY'
import json, os, subprocess, sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path("proto7-2/modules/compact").resolve()))
import aos7_compact as c

node = Path(os.environ["T"])
(node / "notes").mkdir()
journal = node / "notes/journal.jsonl"
original = "".join(json.dumps({"text": f"已完成工作 {i}"}) + "\n"
                   for i in range(10))
journal.write_text(original)
(node / "compact.json").write_text(json.dumps({
    "files": ["notes/journal.jsonl"], "keep_recent": 1,
    "llm": {"gateway": "fake", "reserve": 1}
}))

def delivered(argv, **kwargs):
    receipt = {"outcome": "answered", "billing": "overrun",
               "text": "十件工作的完整摘要", "used": 2, "overrun": 1}
    body = json.dumps(receipt)
    Path(argv[argv.index("--out") + 1]).write_text(body)
    return subprocess.CompletedProcess(argv, 4, body, "")

with patch.object(c.subprocess, "run", side_effect=delivered):
    for attempt in (1, 2):
        rc = c.main(["now", str(node), "--force"])
        print("attempt", attempt, "rc", rc,
              "pending", (node / "compact/pending.json").exists(),
              "unchanged", journal.read_text() == original)
PY
rm -rf "$T"
```

- 預期／推斷實際：應使用完整摘要完成整理，另提示帳務問題；推斷兩次都是 `rc 3 pending True unchanged True`。拒收 4 的分支已用純記憶體 mock 實測。特別是 overrun 已保存 receipt，照原樣重跑仍回 4，不能靠重試解除。
- 修法：接受 llmcall 的 0／4，再驗證交付內容；4 另外留下對帳提醒，1／2／3 分別處理。

### NEW-xmod-3〔B／統一錯誤路徑與入口覆蓋，中〕未列入口沒有明確豁免，仍與「全 aos 共用」契約衝突

- 契約：
  - `proto7-2/notes/blueprint-errors.md:17`：用法錯退 2。
  - 同檔 `:35`：「`--help` …退出 0」；`:41`：「『不知道』不能降成 0 或升成 1」。
  - 同檔 `:57`：「每包…壞參數退 2 且 stderr 一行…」。
- 程式：
  - `proto7-2/tests/core/test_error_path.py:107`～`:108` 只讀清單，`:113` 起依清單生成測試；沒有入口盤點／漏列檢查。
  - `proto7-2/modules/tools/aos7_ctl.py:162`：「`return 0 if e.code == 0 else 1`」；`:183`～`:185` 捕獲 `Unknown` 仍回 1。
  - `proto7-2/packs/adapt/aos7_adapt.py:529` 使用原生 argparse，錯誤保留多行 usage。
  - `proto7-2/packs/usage/bin/aos7-usage:8`～`:9` 不分參數，stderr 印轉址後退出 1；相對的 llmdiag stub 有獨立 help 分支。
- 重現：

```bash
T=$(mktemp -d /tmp/astra8-xmod-entry-XXXX)
P="$PWD/proto7-2"
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "$T/home" "$T/slot"
printf '{' > "$T/slot/birth.json"
(
  cd "$T"
  export HOME="$T/home"
  python3 -B "$P/bin/aos7-ctl" --no-such-option
  printf 'ctl bad rc=%s\n' "$?"
  python3 -B "$P/bin/aos7-ctl" task "$T/slot" kill
  printf 'ctl unknown rc=%s\n' "$?"
  python3 -B "$P/packs/adapt/bin/aos7-adapt" --no-such-option
  printf 'adapt bad rc=%s\n' "$?"
  python3 -B "$P/packs/usage/bin/aos7-usage" --help
  printf 'usage help rc=%s\n' "$?"
)
rm -rf "$T"
```

- 預期／推斷實際：
  - `ctl bad`：預期 2、一行；實測 1、兩行。
  - `ctl unknown`：依統一契約預期 3；推斷 1。
  - `adapt bad`：退出 2 正確，但實測 stderr 兩行，沒有契約要求的處理建議。
  - `usage help`：預期 0、stdout 說明；實測 1、stderr 轉址。
  - `ctl Unknown→1` 是既有行為（`notes/problems.md:314` 已記），本條報的是**今天統一契約與驗收範圍漏接**，不是重報舊實作。
- 修法：把所有現役入口納入清單；凍結核心、包裝器退出碼透傳與轉址 stub 各自明列豁免，其餘補齊統一錯誤介面。

入口逐一盤點如下，路徑相對 `proto7-2/`：

```text
列入  bin/aos7-tick
未列  bin/aos7-tock
未列  bin/aos7-daemon
未列  bin/aos7-run
未列  bin/aos7-ctl
未列  bin/aos7-wait-tock
未列  bin/aos-exec
未列  modules/audit/aos7-audit
未列  modules/subd/aos7-subd
列入  modules/compact/aos7-compact
列入  modules/diag/aos7-diag
列入  modules/events/aos7-events
列入  modules/llmdiag/aos7-llmdiag
列入  modules/mail/aos7-mail
列入  modules/metrics/aos7-metrics
列入  modules/routines/aos7-routines
列入  modules/skills/aos7-skills
列入  modules/up/aos7-up
列入  modules/wfnode/aos7-wfnode
未列  packs/adapt/bin/aos7-adapt
列入  packs/author/bin/aos7-author
列入  packs/author/bin/aos7-gates
列入  packs/budget/bin/aos7-budget
列入  packs/kernel/bin/aos7-kernel
列入  packs/llmcall/bin/aos7-llmcall
列入  packs/prompt/bin/aos7-prompt
未列  packs/step/bin/aos7-step
未列  packs/step/bin/aos7-step-result
未列  packs/usage/bin/aos7-usage
封存  archive/llmdiag/aos7-llmdiag
封存  archive/usage/bin/aos7-usage
```

### NEW-xmod-4〔B／error_path 檢查器，中〕「不留檔」驗收看不到 HOME 寫入，也不檢查 help 的目錄變動

- 契約：
  - `proto7-2/notes/blueprint-errors.md:17`：退出 2「什麼都沒動」。
  - `proto7-2/tests/README.md:37`：壞參數驗收「不留檔」。
- 程式：
  - `proto7-2/tests/core/test_error_path.py:30`～`:31` 快照只有 `os.walk(tmp)` 下的名稱及 mtime。
  - 同檔 `:33` 繼承環境，只移除 AOS 變數，沒有隔離 HOME／XDG。
  - 同檔 `:52`：「`if tag == "bad" and snap() != before:`」；help 即使寫 cwd 也不比較。
  - 因此「fixture 路徑不得逃出 tmp」（`:25`）只約束建測資，沒有約束或監測被測入口。
- 重現：兩個故意違規的入口，分別在 help 寫 cwd、壞參數寫 HOME；所有路徑仍限制於本次 `$T`。

```bash
T=$(mktemp -d /tmp/astra8-xmod-checker-XXXX)
export T
PYTHONDONTWRITEBYTECODE=1 python3 -B - <<'PY'
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path("proto7-2/tests/core").resolve()))
import test_error_path as ep

root = Path(os.environ["T"])
home = root / "home"
home.mkdir()
os.environ["HOME"] = str(home)
tempfile.tempdir = str(root)

source = '''
import os, sys
from pathlib import Path
mode = MODE
if "--help" in sys.argv:
    if mode == "help_cwd":
        Path("unexpected-write").write_text("help wrote")
    print("aos7-probe 用法")
    sys.exit(0)
if mode == "bad_home":
    (Path(os.environ["HOME"]) / "unexpected-write").write_text("bad wrote")
print("aos7-probe: 參數錯。例：--help", file=sys.stderr)
sys.exit(2)
'''
for mode in ("help_cwd", "bad_home"):
    entry = root / (mode + ".py")
    entry.write_text(source.replace("MODE", repr(mode)))
    row = {"name": "aos7-probe", "entry": str(entry),
           "exempt": {"unsure": "此探針只測副作用"}}
    # 保留檢查器的暫存目錄供觀察；最後由 bash 刪除整個 T。
    with patch.object(ep.shutil, "rmtree"):
        print(mode, "issues =", ep.problems(row, ep.TOP))
print("writes =", sorted(str(p.relative_to(root))
                         for p in root.rglob("unexpected-write")))
PY
rm -rf "$T"
```

- 預期／推斷實際：至少 `bad_home` 應被「不留檔」驗收判失敗，help 的副作用也應可被發現；推斷兩者均為 `issues = []`，但 `writes` 同時列出 HOME 與 help 工作目錄的檔。
- 修法：將 HOME／XDG／暫存位置放入受監測沙箱，help 與 bad 都比較副作用；快照至少納入內容與 mode，另明確說明監測不到的範圍。

### NEW-xmod-5〔B／錯誤契約資料表，低〕「現狀退出碼」表仍保留改碼前的 3／4／5 定義

- 契約：`proto7-2/notes/blueprint-errors-items.json:5`：「改完的包把 change 清空、現狀欄改成新值」；`proto7-2/notes/blueprint-errors.md:9` 仍將此表作為逐包退出碼查詢入口。
- 程式／對照：
  - 表 `:67`～`:69` 仍列 author `3=conflict、4=unknown、5=full`。
  - `proto7-2/packs/author/aos7_author.py:53` 已是：
    「`CODES = {None: 0, "invalid": 2, "conflict": 1, "unknown": 3, "full": 1}`」。
  - 表 `:154` 仍稱 mail 的 2 包含 OSError；`proto7-2/modules/mail/aos7_mail_cli.py:140` 已回 3。
  - 表 `:162` 仍稱「up（設計中）」。
- 重現：純靜態查詢，不建檔。

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B wf/tools/tabledb.py \
  proto7-2/notes/blueprint-errors-items.json find pack=author
PYTHONDONTWRITEBYTECODE=1 python3 -B wf/tools/tabledb.py \
  proto7-2/notes/blueprint-errors-items.json find pack=mail
rg -n 'CODES =|return 3|up（設計中）' \
  proto7-2/packs/author/aos7_author.py \
  proto7-2/modules/mail/aos7_mail_cli.py \
  proto7-2/notes/blueprint-errors-items.json
```

- 預期／推斷實際：查詢「現狀」應得到已上線定義；實際仍得到遷移前的碼義與待改清單，容易把 author 的 3 解讀成確定衝突、4 解讀成 unknown。
- 修法：同步現狀欄及 `change`；若要保留遷移前盤點，改標歷史快照並移出現行契約導航。

### 看過但沒問題

- error_path 現有三組豁免：tick 凍結介面、metrics 量尺、llmdiag 轉址，理由仍成立；沒有 skip 列。
- kernel 已列入 error_path，上一輪報告的 E5 缺項已修。
- brain→llmcall 明確區分 3，並接受 0／4（`aos7_up_brain.py:196`～`:211`）。
- skills→llmcall 接受 0／4，保留 1／2／3 並轉述帳未清提醒（`aos7_skills.py:220`～`:235`）。
- author 的主要 LLM 提案路徑接受 0／4，3 對應 unknown（`aos7_author_llm.py:113`～`:115`）。
- mail→events ack 只有成功才更新本地確認游標；失敗保留待重試（`aos7_mail_ack.py:63`～`:76`）。
- kernel 的控制接面直接寫帶原 run／id 的 `ctl.json`，不是透過 `aos7-ctl` 的退出碼判定。
- metrics 讀取真實的巢狀 request／reply／usage；diag 的 budget inflight 讀取位置與 budget 寫者一致。
- INDEX、modules README 對 usage／llmdiag 封存與轉址的描述一致；run_all 的預設搜尋不含 archive。
- layer-interfaces 明列為舊 commit 的調查紀錄，未將其中舊缺口當成本輪新發現。

### 沒看完

- 未逐一完成所有子命令、權限故障與中斷窗口的退出碼矩陣；以上不代表其餘錯誤路徑全通過。
- 原子寫、flock、暫存清理、JSON 讀錯及名稱編碼的全庫重複實作比對未完成，沒有提出 C 類結論。
- metrics／diag 的所有壞檔形狀與跨預算組合未窮舉；README 所列 1216 項未重新計數或執行。
- 本文涉及建檔的重現腳本仍待隊長實跑；未進行真人新手試用或需驗證端點的真傳輸測試。