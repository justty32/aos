查 proc 目錄裡「說明自己」的幾個檔（`_metainfo`、`settings`、`status`、`interfaces.json`）與 index 怎麼分工：四個檔照「誰決定、什麼時候變」分得開，`_metainfo` 推薦原樣用定義那份，對 `procs` 做 index_view 今天不改程式就做得到；實測另外挖出三個坑（純文字檔進不了單一路徑、沙箱裡走不進 `/proc/<PID>/cwd`、先解連結的工具隔著 namespace 會讀錯檔）。

# 12　`_metainfo`、index 與 proc 目錄

← [架構規劃入口](../README.md)

寫的人：這批的第 12 隻子 agent（fable）。只讀 repo 與活樹；實驗全在 `~/.aos/scratch/aos-proc-arch-1125/12/`，起的行程都收掉了。標「推論」的是我的推論；標「例子」的是還沒有使用者的話、我舉的。需求來源是 `../../9p-proc-1125.md`，下面說「定了的」都指那一份。

## 1. 結論

1. **昨天「沒有程式照 `_metainfo` 做決定」成立，補一個精確版**：工具的 `_metainfo.json` 有四個鍵有人照做（逾時就殺、不可並行就排隊、沙箱、任意執行記帳）；agent 定義的那 9 份只有 `summary`、`cost`、`resource` 三個鍵，除了列定義時顯示那句話、檢查時要求有那句話、審視工具拿 `cost` 對實測出報告之外，沒有程式用它。daemon、kernel 的定義連這個檔都沒有，活樹的 stack 裡一份也沒有。
2. **四個檔分得開**，判準是「這個值誰決定、什麼時候會變」：`_metainfo`＝定義的作者說的，同一份定義起十隻都一樣；`settings`＝起這一隻時定的，十隻各不同、起來後不變；`status`＝這一隻自己量的，一直變；`interfaces`＝怎麼跟這個身體接（會哪些介面、檔叫什麼）。今天的欄位逐個歸屬見 3.1。
3. **proc 目錄裡的 `_metainfo` 推薦就是定義那份原樣**（動態連結），跑的時候誰都不改，這本來就是 N-69 的規定。這一隻特有的話放 `settings`，量到的放 `status`。
4. **檔名**：json 工具不看副檔名，`_metainfo` 讀寫都行；但 index_view 的天然位置、`metainfo.read`、aos-tools、defs 都只認 `_metainfo.json`（使用者 11-04 裁的「留 _、加 .json」）。兩個名字都給，一條連結就做得到，實測可用。
5. **`status`、`settings` 是純文字的話，現有的 json 工具與 `$ref` 都讀不進去**（`FileBad … is not JSON`）。單一路徑尋址走到 proc 目錄裡最常被讀的檔就斷了。
6. **對 `procs` 做 index_view 今天就做得到**：daemon 在 `procs/_index.json` 每項寫 `{"$ref": "<名>/_metainfo.json#/summary"}`。proc 死了，那一行印 `bad $ref (file not found…)`，其他行照常。缺的是內容：同一個範本起的 agent 那句話一模一樣，daemon、kernel、`_clock`、`_sweeper` 根本沒有這個檔。
7. **「每隻 agent 自己的根 index」與 mount namespace 是同一個形狀的兩層**：namespace 管「碰得到什麼」，index 管「每樣是什麼」。實測對一隻被 bwrap 關起來的行程做 `index_view /proc/<PID>/root`，直接印出它眼中的世界加描述。
8. **兩個跟沙箱有關的坑**：關進 bwrap 的行程走不進 `/proc/<外面的 PID>/cwd`（`Permission denied`），所以入口與 `procs/<名>` 連結在沙箱裡全斷；先解開連結再開檔的工具（aos-json）隔著 mount namespace 會讀到**外面**同路徑的那個檔。

## 2. 查到的事實

### 2.1 `_metainfo.json` 今天是什麼

| 問 | 答 | 出處 |
|---|---|---|
| 放哪 | 資料夾裡跟 `_entry` 並列的檔 `_metainfo.json`（不帶 `.json` 的不認）；或 JSON 物件裡的 `_metainfo` 鍵 | `proto8/docs/NORMS/10-基礎設施-定義與工作區/11-N-69.md:8`、`proto8/py/aos/metainfo.py:52-78` |
| 格式 | 一個 JSON 物件，沒有必填、不認得的鍵忽略、不加版本鍵（要改意思就換新名字） | N-69 同檔 `:10` |
| 共用的讀法 | `aos/metainfo.py` 三支：`read`（給夾、JSON 檔或 `檔#/指標`）、`timeout_ms`、`eval_cost`（純數、`{"val"}`、`{"cal": 公式}`）。只有 Python 有，C++ 那層沒有對應 | `metainfo.py:40-49,93-110,145-168` |
| 壞了 | 當沒寫：讀的人略過、提醒一句、不擋 | `metainfo.py:40-49`、N-69 `:13` |
| 會不會變 | 跑的時候誰都不改；量到的另外記在量的人那邊（`observed.jsonl`） | N-69 `:14` |
| 算不算數 | 「當然，全都是觀點，全都是參考用，出事了自行負責。」（使用者 11-12 晚）；是設計者公開給別人的聲稱，不是保證 | N-69 `:12` |
| 誰寫 | 人手寫；用 `fn` 寫的工具編譯時產、沒給的補保守預設；agent.py 編譯定義夾時寫 `summary` 加自己設的鍵、只蓋自己的鍵；`agent_def new` 記 `lineage` | `proto8/py/aos/tool_spec.py:24-26,110-121`、`proto8/py/aos/agent_spec_agent.py:278,289-298` |

**有哪些鍵、誰照它做事**（我在這台重數：git 追蹤的 `_metainfo.json` 共 95 份，數法是 `git ls-files proto8` 篩檔名後逐份讀；跟昨天蒐集 03 的數字一致）：

| 鍵 | 幾份有 | 誰讀、讀了做什麼 |
|---|---|---|
| `summary`（一句話） | 95 | `defs` 的 `ls` 顯示、`check` 要求非空（`proto8/py/tools/aos/defs/catalog.py:166-168,216-219`） |
| `timeout_ms` | 71 | act 格、aos-mcp、`mcp_tool` 到了就殺工具（`proto8/py/aos/apps/agent_fsm/act.py:150-151`、`proto8/py/aos/apps/mcp/main.py:207-208`） |
| `parallel` | 84 | aos-mcp：寫 `false` 的工具同名呼叫排隊（`proto8/py/aos/apps/mcp/serve.py:5`） |
| `sandbox` | 1 | aos-sandbox 照它套沙箱（`proto8/py/aos/apps/sandbox/main.py:4`） |
| `arbitrary_exec` | 35 | `shell_report` 記帳（`proto8/py/tools/aos/shell_report/report.py:75-76`） |
| `side_effect`、`idempotent`、`resource` | 86、84、92 | aos-mcp 換成給模型的提示，只是提示（`mcp/main.py:149-160`） |
| `cost` | 81 | `metainfo_check` 拿來跟實測比，只報告 |
| `deterministic`、`interrupt` | 85、84 | 沒有讀者 |
| `tooldef`、`index` | 1、0 | aos-tools、index_view 當「底」，外面獨立那份蓋上去（N-69 續） |
| `comfort`、`lineage` | 0、0 | 條文有，檔裡沒人寫 |

- **九軸**：九個名字（I/O 型態、生命週期、跨呼叫狀態、資源特性、可中斷性、執行保證、組合模式、環境模式、確定性）只有名字，逐軸定義不在 repo（`proto8/thinking/2026-10/11/restart/02-河堤後段.md:13`）。檔裡實際寫的軸鍵是上表那六個：`side_effect`、`idempotent`、`deterministic`、`interrupt`、`parallel`、`resource`。
- **agent 定義那 9 份**（`templates/agents/*` 6 份、`templates/starts/*/agents/ann` 2 份、`frontend/aide-def` 1 份）沒有任何軸鍵，只有 `summary`、`cost`、`resource`（agent-python 只有 `summary`）。例：`proto8/templates/agents/eca-claude/_metainfo.json` 整份是 `{"summary": "Run Claude Code as an aos agent: one turn per queue batch, answers appended to history.", "cost": {"time_ms": 60000}, "resource": ["llm"]}`。
- **daemon、kernel 沒有這個檔**：`templates/daemons/`、`templates/kernels/` 底下一份都沒有；活樹的根 daemon 定義 `~/aos-home/root`（只有 `.env`、`README.md`、`_entry`、`daemon.json`）與 llm kernel 定義 `~/aos-home/llm` 也沒有。
- **活的 stack 裡一份也沒有**：`find ~/aos-home/.stack -name "_metainfo*"` 沒有輸出。今天要知道「這隻是什麼」，得先讀 daemon 的表拿 `def` 欄，再去定義夾讀。
- **它還兼一個記號**：`defs` 把「夾裡有 `_metainfo.json`（或 `interfaces.json`）」當成「這是一份定義」（`defs/catalog.py:22-37`）。
- **照它做決定的程式，再確認一次**：`proto8/cpp` 整層搜 `metainfo` 零命中（daemon、aos-loop、aos-exec 都在這裡）；`py/tools/aos/kernel`、`kernel_llm`、`py/tools/agent/kernel_gate`、`py/aos/daemon_ctl` 也沒有命中。所以昨天那句「kernel 不讀它，aos-exec 也不讀它」成立。有執行效果的只有上表第 2～5 列（`timeout_ms`、`parallel`、`sandbox`、`arbitrary_exec`），而且全是**工具**的 `_metainfo`。對 proc 目錄要放的那一種（agent、daemon、kernel 的），「沒有程式照它做決定」完全成立。

### 2.2 `interfaces.json` 今天是什麼

- **是什麼**：資料夾「宣告自己遵守哪些介面」的檔，鍵是介面名、值是那個介面的檔在哪。全體系第二個固定名（第一個是 `_entry`），其餘檔名由它指定（`proto8/docs/NORMS/命名-續-概念搬來的檔名/01-入口-metainfo-介面-血緣.md:26-35`）。使用者 11-04 晚：「程式語言中定義class/struct的後，也會宣稱說自己繼承於/遵守於某些介面，比如golang interface之類。」
- **今天有的鍵**（`proto8/templates` 底下 19 份逐份看）：`aos-agent`（`entry` 或 `screen`、`tools`、`llm`、`llm_keys`、`history`、`system`）、最外層的 `hooks`／`hookeds`、`kernel`、`aos-ledger`、`aos-observed`、子介面 `aos-agent/screen`、`description`。**沒有 `aos-proc`**（`proto8` 除了 thinking 之外搜不到這個詞）。
- **誰讀**：aos-agent 的 `history`／`llm`／`system`／`tools`／`screen` 這些子命令照宣告找檔，定義沒宣告 `aos-agent` 就 `InterfaceMissing`（`proto8/py/aos/apps/agent/decl.py:43-48`、`proto8/py/aos/declared_files.py:6-31`）；hook（`proto8/py/aos/hook_point.py:1-6`）；量測與帳（`aos-observed`、`aos-ledger`）；`defs`（有這個檔就算一份定義，`defs/catalog.py:27`）。**跟 `_metainfo` 相反，這份是有程式照著接線的**，寫錯會壞。
- **沒宣告也收**：`aos-agent ctl add` 11-21 起沒宣告 `aos-agent` 的夾照樣掛得上，入口就是夾本身（`proto8/py/aos/apps/agent/ctl/add.py:80-87`，註解引的就是使用者那句「沒宣告的照樣跑」）。
- **stack 裡今天就有一份**：agent-fsm 的身體自己在 stack 寫 `{"aos-observed": {"file": "observed.jsonl"}}`（`proto8/py/aos/observed.py:12-22`；活樹有 110 份、內容全是這一行，例 `~/aos-home/.stack/procs/repo-aos/procs/eca-aos-sol-4/interfaces.json`）。也就是「活的那一隻自己宣告介面、宣告的檔名相對自己」已經有先例。
- **使用者說過的三句**（都跟這題有關）：
  - 11-21：「4.沒宣告的照樣跑，其他的也是，就是說，宣告這東西只是參考。」（`proto8/thinking/2026-11/21/kernel-宣告進interfaces-1121/09-使用者已答.md`）
  - 11-21：「kernel那塊，界面有分對外與對內，interfaces.json中當然兩者都可以有，只是說未來，對外的界面宣告的json，需要另外準備一份，用於讓他人存取」（同夾 `07-對外與對內.md`）
  - 11-20：「或許可以就是在stack開一個public資料夾」，選項框答「先試固定位置，沒有才寄信問」「框架放固定幾樣、其餘自己加」（`proto8/thinking/2026-11/20/aos-direct-reply-1120/06-使用者已答.md`）。**新模型裡 proc 的目錄本身就是這個「public 資料夾」**（推論）。
- **今天別的認法**（3.4 用得到）：`aos-llm ls` 認 llm kernel 是看那一列的 stack 裡是不是同時有 `endpoints.json` 與 `requests/`，明寫不猜定義名（`proto8/cpp/aos-llm/README.md:23`）；`ls`／`stat` 工具看 8 個檔名標出 aos 資料夾（`proto8/py/aos/file_summary.py:8`）。

### 2.3 index 與單一路徑

- **單一路徑** `FILE#/POINTER`：`#` 左邊是檔案系統、右邊是 JSON 裡面；json 工具全族、index_view、`$ref` 共用（`proto8/py/aos/json.py:38-58`、`proto8/py/aos/refpath.py:19-71`）。markdown 也能讀（標題、清單、`鍵: 值` 的清單項、表格），只讀不寫（`proto8/py/aos/mdpath.py:1-11`、`proto8/knowledge/aos/tools/json_get.md`）。
- **index 的天然位置只寫在一個函式**（`proto8/py/aos/index.py:31-35`）：資料夾 → `DIR/_index.json`，底下再墊一層 `DIR/_metainfo.json` 的 `index` 鍵；沒有 `_index.json` 才看 `_index.md`（`index.py:242-244`）；JSON 裡面 → `#/…/_index`。
- **一項的三種寫法**：物件 `{"description": …}`、純字串、`{"$ref": 路徑}`（解開拿到字串就當 description，`index.py:301-321`）。一項還可以帶 `index: 路徑` 指到另一份 index，只顯示、不往下讀；其他鍵 index_view 不印（`proto8/knowledge/aos/tools/index_view.md`）。
- **是視角不是事實**：不查被描述的東西在不在、不往上找、不自己去翻子夾（`index.py:5`）。
- **可以疊自己的一份**：`{"path": 節點, "index": 我自己的表}`＝天然那份為底、疊上指定那份，同名的以指定那份為準（`index.py:6`）。
- **使用者 11-12**（`proto8/thinking/2026-11/12/index.md`）：「放在天然位置的index，其實會是所謂的客觀index，而agent自己存的則是主觀。」「agent自己要記錄自己的主觀的東西，就自己想想要放哪，我們不規定。」「看的時候可以自己指定要用啥index，沒指定的話就預設用通用視角。」
- 活樹的 stack 裡沒有任何 `_index*`（`find ~/aos-home/.stack -name "_index*"` 沒有輸出）。

### 2.4 `_entry`

「跑這個資料夾時跑什麼」。範本 agent 的 `_entry` 是「把自己掛上 daemon」（`proto8/templates/agents/agent-fsm/_entry`＝`aos-agent ctl add $AOS_CD`），eca 與 daemon 的是直接起身體（`["aos-loop", "loop.json"]`、`["aos-daemon", …]`）。stack 裡沒有 `_entry` 檔，但 daemon 寫進每列小格的 `loop.json#/_entry`、`exec.json#/exec` 就是「怎麼重起這一列」（活樹的表：`"launch": {"exec": ["procs/_clock/loop.json#/_entry"]}`）。細節在 `01-aos-loop現況.md`、`02-aos-daemon現況.md`。

### 2.5 實測（公司 WSL2、核心 6.6、同一個帳號；工具用裝好的 `proto8/lib`、`proto8/bin`，環境清到只剩 `AOS_WS`）

| # | 測什麼 | 結果 |
|---|---|---|
| 1 | `json_get`／`json_ls`／`json_set` 對沒有副檔名、內容是 JSON 的 `_metainfo` | 都行（`"A toy proc that answers status."`、`ok e1/_metainfo#/note`） |
| 2 | `index_view` 看一個只有 `_metainfo`（裡面有 `index`）的夾 | `[no index] e1/_index.json does not exist…`；明講 `{"index": "e1/_metainfo#/index"}` 才印得出來 |
| 3 | `aos.metainfo.read(夾)`，夾裡只有 `_metainfo` | 回 `None`，連提醒都沒有（當沒寫） |
| 4 | 兩個名字：`_metainfo` 是指到 `_metainfo.json` 的連結 | 兩個名字都讀得到，index_view 認得；經連結 `json_set`，改到的是真檔、連結還在 |
| 5 | `json_get` 讀純文字 `status`（`phase: running` 一行一個） | `json_get: error: FileBad e1/status is not JSON`；`status#/phase` 一樣 |
| 6 | 同樣內容存成 `.md` | 沒有清單記號：整份讀得到、`#/phase` 是 `PointerMissing`。寫成清單 `- phase: running`：`#/phase` 回 `"running"` |
| 7 | aos-json 把檔當 markdown 還是 JSON | 看解開連結後的真檔名：`status.md -> status` 照樣 `is not JSON`；`alias -> status_list.md` 當 markdown（`proto8/cpp/aos-json/src/doc/file.cpp:24,65`） |
| 8 | `procs/<名>` 連到 `/proc/<PID>/cwd`，`procs/_index.json` 每項 `{"$ref": "<名>/_metainfo.json#/summary"}`，從 `/proc/<daemon PID>/cwd/procs` 做 index_view | 每隻印出自己那句話 |
| 9 | 其中一隻 `kill -9`、收屍後再看 | 那一行 `dying	bad $ref (file not found: …/dying/_metainfo.json (create it first, e.g. json_set …))`；其他行照常、退 0；連結檔還在（懸空） |
| 10 | daemon 改成自己抄一句（純 description） | 死掉那隻的那一行跟活著時一模一樣 |
| 11 | `..` 穿過 proc 連結：index 裡 `{"$ref": "alive/../marker.json"}` 對 `cat procs/alive/../marker.json` | `$ref` 讀到 daemon 的 `procs/marker.json`（照字面消掉 `..`，`refpath.py:43`）；`cat` 讀到身體真位置旁邊那一份 |
| 12 | 用 bwrap 給一隻行程一個只有 `/ws`、`/kb`、`/_index.json`（加 `/usr`）的根，從外面看 | `ls /proc/<PID>/root` 是 `_index.json bin kb lib lib64 proc usr ws`；`index_view {"path": "/proc/<PID>/root"}` 印出三行說明；它在裡面讀不到外面的檔 |
| 13 | 被關起來的行程往外讀 `/proc/<daemon PID>/cwd/status` | 共用 pid 空間：`Permission denied`；自己的 pid 空間：`No such file or directory` |
| 14 | 隔著 mount namespace，從外面經 `/proc/<PID>/cwd/_metainfo.json` 讀 | `cat` 讀到裡面那份；`json_get` 讀到**外面**同路徑那份 |
| 15 | `index_view {"path": 給的那份, "index": 自己的那份}` | `[index] e9/given/_index.json + e9/mine/root_index.json (on the same key e9/mine/root_index.json wins), 3 entries` |
| 16 | 一份 200 項的 index，每項都是 `$ref`，對每項都是純字串（機器負載約 12 時各跑三次） | `$ref`：0.50～0.69 秒；純字串：0.06～0.16 秒。每解一項 `$ref` 要起一次 aos-json（`index.py:294`） |

第 13 列的原因（憑記憶的核心規則，結果是實測的）：這台的 bwrap 不是 setuid，靠 user namespace 起沙箱；走 `/proc/<PID>/cwd` 要過 ptrace 讀權限檢查，子 user namespace 裡的行程對外面的行程過不了，反方向（外面看裡面）過得了。第 12 列的行為在本機 man 頁有寫：`proc_pid_root(5)`「It provides the same view of the filesystem (including namespaces and the set of per-process mounts) as the process itself.」

<details><summary>重跑用的指令（第 1～5、8～9、12～14 列）</summary>

```sh
# 一、乾淨環境叫一支工具（存成 t.sh；用法 ./t.sh json_get '{"path": "e1/status"}'）
P8=/home/guanyu/repo/aos/proto8
printf '%s' "$2" | env -i PATH=$P8/bin:/usr/bin:/bin AOS_WS="$PWD" python3 $P8/lib/tools/base/$1/_entry

# 二、第 1～5 列
mkdir e1 && echo '{"summary": "A toy proc that answers status.", "index": {"status": "what I am doing now"}}' > e1/_metainfo
printf 'phase: running\npid: 4242\n' > e1/status
./t.sh json_get '{"path": "e1/_metainfo#/summary"}'     # "A toy proc that answers status."
./t.sh index_view '{"path": "e1"}'                      # [no index] e1/_index.json does not exist. …
./t.sh json_get '{"path": "e1/status#/phase"}'          # json_get: error: FileBad e1/status is not JSON
```

```python
# 三、第 8、9 列（env -i HOME=$HOME PATH=/usr/bin:/bin python3 這支.py）
import json, os, signal, subprocess, tempfile, time
P8 = "/home/guanyu/repo/aos/proto8"
base = tempfile.mkdtemp(prefix="procs-index-"); root = base + "/root"; os.makedirs(root + "/procs")
def view(path):
    env = {"PATH": P8 + "/bin:/usr/bin:/bin", "AOS_WS": base}
    return subprocess.run(["python3", P8 + "/lib/tools/base/index_view/_entry"], input=json.dumps({"path": path}),
                          capture_output=True, text=True, env=env).stdout
def proc(name, summary):                          # 一隻玩具 proc：站在自己的夾，夾裡放一份 _metainfo.json
    body = "%s/bodies/%s" % (base, name); os.makedirs(body); r, w = os.pipe(); pid = os.fork()
    if pid == 0:
        os.chdir(body); json.dump({"summary": summary}, open("_metainfo.json", "w")); os.write(w, b"1")
        while True: time.sleep(60)
    os.read(r, 1); os.symlink("/proc/%d/cwd" % pid, "%s/procs/%s" % (root, name)); return pid
a, d = proc("alive", "Answers questions about the weather."), proc("dying", "Will be killed in a moment.")
os.chdir(root)                                    # 這支腳本當 daemon，站在自己的夾
json.dump({n: {"$ref": n + "/_metainfo.json#/summary"} for n in ("alive", "dying")}, open("procs/_index.json", "w"))
via = "/proc/%d/cwd/procs" % os.getpid()
print(view(via)); os.kill(d, signal.SIGKILL); os.waitpid(d, 0); print(view(via))
os.kill(a, signal.SIGKILL); os.waitpid(a, 0)
```

```sh
# 四、第 12～14 列的沙箱（D 是放了 ws/、kb/、_index.json 的暫存夾；裡面那支 sleep 的 PID 記成 P）
bwrap --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib64 /lib64 --proc /proc \
      --bind $D/ws /ws --ro-bind $D/kb /kb --ro-bind $D/_index.json /_index.json --chdir /ws sleep 60
ls /proc/$P/root ; ./t.sh index_view '{"path": "/proc/'$P'/root"}'                      # 第 12 列，在外面跑
# 第 13 列：把最後的 sleep 60 換成 sh -c 'cat /proc/<外面某支行程的 PID>/cwd/status'（再加 --unshare-pid 試一次）
# 第 14 列：多加 --dir $D/spot --bind $D/inner $D/spot --chdir $D/spot（兩個夾各放一份內容不同的 _metainfo.json），
#           在外面比 cat /proc/$P/cwd/_metainfo.json 與 ./t.sh json_get '{"path": "/proc/'$P'/cwd/_metainfo.json#/who"}'
```

</details>

## 3. 對新介面的含意

先對著「定了的」各條講一句，細節在後面各小節：

| 定了的 | 這份講到的 |
|---|---|
| `_metainfo` 照 aos 現有的（json） | 內容照 N-69、不用改（2.1）；現有的檔名是 `_metainfo.json`（3.3）；現有的規定是跑的時候不改，所以它裝不了「這一隻」與「現在」的事（3.1、3.2） |
| `status` 純文字、一行一個「名稱: 值」，目前只給這一個檔 | 今天哪些欄位該進來（3.1）；json 工具與 `$ref` 讀不進去（第 5 節第 2 題）；跟 Linux 自己的 `status` 同形（第 4 節第 5 條） |
| persist 在哪以 proc 自己說的為準，daemon 從它的目錄讀（例如 `settings`） | `settings` 就是「起來時定、每隻不同」那一格（3.1）；proc 一死就讀不到，daemon 要先抄走（第 4 節第 2 條） |
| token 用量 proc 自己報、放自己的目錄 | 是量到的，歸 `status` 或以後另一個檔，不進 `_metainfo`（N-69：實測不回寫） |
| daemon 多一個放各 proc 的資料夾；`proc`、`procs` 兩個名字 | 對它做 index_view 要什麼（3.5）；兩個名字 index_view 都走得通（3.7） |
| 支援這套的就是 aos proc | 3.4 |
| 入口是根 daemon 的 PID，從 `/proc/<PID>` 進去 | 只在大家同一個 namespace 時成立（3.6 的兩個坑） |

### 3.1 四個檔怎麼分才不重疊（題目 4）

**判準只有三問**（推論；每個值問下去只會落在一格）：

1. 同一份定義起兩隻，這個值會不一樣嗎？不會 → **`_metainfo`**（我是什麼）。
2. 會不一樣。起來之後還會變嗎？不會 → **`settings`**（我的東西放哪、起我的人交代了什麼）。會 → **`status`**（我現在怎樣）。
3. 它講的是「別人怎麼跟我接」嗎（我會哪些介面、每個介面的檔叫什麼）？→ **`interfaces`**。

| 檔 | 回答 | 誰決定內容 | 什麼時候變 | 格式 | 主要的讀者 |
|---|---|---|---|---|---|
| `_metainfo` | 我是什麼 | 定義的作者 | 定義改了才變 | JSON（定了：照現有） | kernel（使用者 11-24：「_metainfo我確實打算拿他當kernel的判斷標準」）、列表、審視的人 |
| `settings` | 我的東西放哪 | 起它的人，加上 proc 自己挑的（persist） | 起來時定，重起才變 | 沒定（使用者只提過名字） | daemon（找 persist、信箱）、要寄信的人、proc 自己的工具 |
| `status` | 我現在怎樣 | proc 自己 | 一直變 | 純文字「名稱: 值」（定了） | 人、daemon、kernel、在等它的人 |
| `interfaces` | 怎麼跟我接 | 這個身體的寫法 | 換實作才變 | JSON（現有） | 用它的工具 |

`settings` 與 `interfaces` 都在講「哪裡」，分法是：**`settings` 給錨點（東西在哪個位置，每隻不同），`interfaces` 給錨點底下的名字（哪個檔是 history，同一種身體都一樣）**。兩個接起來才是完整的路。

這個分法還順手回答了昨天 `main` 提的「`_metainfo` 的每個值要帶出處（宣稱的、量到的、誰評的）」：**出處用位置分，不用在值上加標記**（推論）。設計者宣稱的在 proc 目錄的 `_metainfo`；機器量到的在同一個目錄的 `status`（歷史的帳在 persist）；別人評的在評的人自己那邊，例如 daemon 在 `procs` 的 index 裡寫給這個孩子的那一句。kernel 要判斷時只要拿到寄件 proc 的目錄，宣稱與實測就在隔壁兩個檔。今天 kernel 不讀 `_metainfo`，N-69 寫的原因是「kernel 不讀（llm kernel 的信裡沒有單子）」；有了 proc 目錄，信裡只要認得出寄件的是哪一隻 proc 就夠了。

**歸屬表**（今天的欄位 → 新的檔）。今天的出處：`aos-agent ctl who -j`（`proto8/py/aos/apps/agent/ctl/who.py:48-49`）、`self_state`＝`ctl state` 的十一類（`ctl/state.py:16,86-311`）、aos-loop 的 `state.json`（`proto8/cpp/aos-loop/src/engine/window.cpp:322-345`）與 `state_flux.json`（`proto8/cpp/aos-loop/include/aos/loop.hpp:72-78`）、daemon 表的一列（`proto8/cpp/aos-daemon/src/child/child.cpp:356-430`）。

| 今天的欄位 | 今天在哪 | 歸哪 | 說明 |
|---|---|---|---|
| **`ctl who` 印的** | | | |
| `name` | daemon 表的鍵；agent 從裡面不知道自己叫什麼（`proto8/knowledge/aos/me.md:7`） | `settings` | 名字是 daemon 給的（`procs/<名>` 那條連結的名字）。proc 把它抄在 `settings`，別人就能核對「連結名＝它自稱的名字」 |
| `def` | 表的 `def` 欄 | `settings` | 定義**在哪**是位置；定義**說了什麼**才是 `_metainfo` |
| `ws` | 表的 `ws` 欄 | `settings` | |
| `stack` | 表的 `stack` 欄 | 不用寫 | 新的意思下 stack 就是這個目錄本身 |
| （新）`persist`、信箱位置 | 今天都在 stack 裡 | `settings` | 定了的那一條 |
| `daemon` | 讀表的人自己知道 | `settings` | 往上最近的 daemon（使用者 11-25 選的最根本的錨點，見 `06-路徑、環境變數與命名現況.md`） |
| `parent`、`notify_box` | 表的欄、啟動單子的 envs、環境變數（`proto8/py/aos/apps/agent/common.py:173-189`） | `settings` | add 時請求方寫的登記，「不是證明」 |
| **`self_state` 多出來的** | | | |
| `state`／`phase`、`paused` | 表加 `state.json` | `status` | |
| `reason`、`code`、`signal`（為什麼停） | 表 | daemon 自己的紀錄 | proc 死了目錄就沒了，這幾樣只有 daemon 答得出來 |
| `queued`、信箱幾封、history 幾則多大、`last_answer` | 現數 queue、mailbox、history | `status`（只放數字） | 內容本身在 persist |
| `tools`、`llm`、`system`、`hooks` 的內容 | 定義加 stack 的覆蓋檔 | 四個都不是 | 是設定、不是狀態，而且大；留在定義與 persist，`interfaces` 說檔名 |
| `subagents` 幾隻、上限 | 小格的帳、`subagents.json` | 幾隻進 `status`；上限是設定 | |
| `limits`（份額） | 表 | `settings` | 起來時定的 |
| 用量（記憶體、CPU、行程數）、起來多久 | 現算 Linux 的 `/proc` | `status` | 單一行程的數字 Linux 自己的 `status` 就有，aos 只需要報「整隻連子孫」的 |
| **`state.json`／`state_flux.json` 其餘** | | | |
| `pid`、`started_at_ticks`、`boot_id` | `state.json` | `status`（`pid`、起來的時間） | 這三個今天是為了「檔還在、行程沒了」時判活著；活的目錄不需要，但防 PID 被重用仍用得到起來的時間 |
| `max`、`interval_ms` | `state.json`（ctl 可改） | `status` | ctl 改、status 看 |
| `updated_at` | `state.json` | `status`，只有落檔的實作需要 | 當場回答的不需要 |
| `ctl_seq`、`responded_at` | `state_flux.json` | 只有落檔的實作需要 | 「寫 ctl 回來＝收到」之後不需要（`9p-proc-1125.md` 已寫） |
| `ctl_warning`、`mailbox_warning` 等 | `state_flux.json` | `status` | 最近一次下令或收信的問題 |
| daemon 的 `cgroup`、`group` | `state.json` | `settings` | |
| daemon 的 `poke`（叫醒用的訊號號碼） | `state.json` | `interfaces`，或消失 | 「怎麼叫醒我」是介面；走 socket 就不用 |
| **daemon 表每列其餘的欄** | | | |
| `launch`、`as_written`、`auto_restart`、`restart_on_stuck`、`stuck_after_*`、`counter_restarts`、`limit_hit`、`stop_mode` | `procs_state.json` | daemon 自己的 persist | daemon 怎麼管這個孩子，是 daemon 的事，孩子的目錄裡不放 |
| **定義裡的** | | | |
| `summary`、`cost`、`resource`、各軸鍵 | 定義的 `_metainfo.json` | `_metainfo` | 原樣 |
| 介面名與檔名 | 定義的 `interfaces.json`、stack 的 `interfaces.json` | `interfaces` | 給別人看的要另外一份（3.4） |

今天就有一處重疊可以順手收：`templates/agents/agent-python` 的 `interfaces.json#/description` 與 `_metainfo.json#/summary` 是同一句話。

### 3.2 proc 目錄裡的 `_metainfo` 是誰的話（題目 2）

用使用者的說法分三種（「靜態連結／動態連結」是 11-19 定的說法）：

| 做法 | 定義改了、行程沒重起時，proc 目錄顯示 | 別人經 proc 目錄去寫它 | 代價 |
|---|---|---|---|
| 甲　動態連結：連到定義那份（FUSE 版＝轉去讀定義） | 新的 | **會改到定義**，所有同定義的 proc 一起變（實測 4：aos-json 寫的是真檔） | 定義搬走或刪掉就懸空；定義夾裡的 `index` 鍵會被當成 proc 目錄的 index（見第 4 節第 3 條） |
| 乙　靜態連結：起來時抄一份 | 舊的（起來那一刻的） | 只改到這一隻的 | 要有人在起來時抄；之後跟定義對不上沒有人知道 |
| 丙　行程自己回答 | 它當下載入的那份 | 它自己決定收不收 | 要寫程式；內容可以每隻不同、隨跑隨變，「我是什麼」與「我現在怎樣」的界線會糊掉 |

**誰對**，看實作怎麼用定義：

- 今天的落檔實作：`loop.json` 自己寫明改了要重起（`proto8/templates/agents/agent-fsm/loop.json` 的說明「…and restart the agent」），`.env` 只在起來時讀（`proto8/knowledge/aos/definition.md:20`）；身體是每拍新起的行程（`loop.json` 的 `exec`）。推論：其餘定義檔下一拍就照新的跑，所以「行程沒重起」時，甲反而最接近實際在跑的。逐檔的重讀時機我沒驗，在 `03-agent-fsm身體與stack現況.md`、`04-eca身體與stack現況.md` 的範圍。
- 常駐、把定義載進記憶體的實作：丙最準，乙次之。
- 不管哪一種，`_metainfo` 的地位本來就是「設計者公開給別人的聲稱」。它回答的是「這種東西照設計是什麼」，不是「這一隻此刻怎樣」，後者是 `status`。

**推薦甲，規格只寫結果不寫做法**：proc 的目錄裡有一份 `_metainfo.json`，內容照 N-69，是這隻 proc 對外說的「我是什麼」；跑的時候誰都不改它（N-69 `:14` 已經這樣規定），也不收經 proc 目錄來的寫入。怎麼讓它出現在那裡是實作自己的事：落檔的用連結，外來登記的自己寫一份，FUSE 的當場答。理由有兩條既有的話：

- 使用者 11-07（N-68）：「函數自報估值，老實說，應該是函數的設計者當初給函數寫下的估值，而agent作爲函數他確實會自報估值。兩者要分清。」做丙就把兩者混在同一個檔。
- 使用者 11-25：「按照aos現有的來」。現有的就是定義旁邊那一份，跑的時候沒有人寫它。

沒有定義夾的 proc（今天的 `_clock`、`_sweeper` 的 `def` 是 `null`；以後「只登記、不起」的外來行程）只能自己寫，或者沒有。使用者 11-07 說過「不能假定永遠都有metainfo，而且我們也不該強迫」，所以**讀的人要當它可能不在**。

### 3.3 檔名（題目 3）

使用者 11-25 寫的是 `/proc/<PID>/_metainfo`，同一句說「按照aos現有的來」；現有的檔叫 `_metainfo.json`，是他 11-04 自己裁的（`proto8/thinking/2026-11/04/four-elements/06-要使用者裁的題.md:7`，第 8 題答「留 _、加 .json」；更早 10-24 的規劃是不帶副檔名的，`proto8/thinking/2026-10/24/metainfo/01-位置與格式.md:16`）。

| 誰 | `_metainfo.json` | `_metainfo` |
|---|---|---|
| `json_get`／`json_ls`／`json_set`、`$ref` | 行 | 行。它們不看副檔名，只有真檔名結尾是 `.md` 才當 markdown（實測 1、7） |
| index_view 的天然位置（`夾/_metainfo.json#/index`） | 認 | 不認（實測 2） |
| `aos.metainfo.read(夾)`（`metainfo_check` 用） | 認 | 當沒寫、不提醒（實測 3，`metainfo.py:60`） |
| aos-tools（act、aos-mcp 看到的工具特性都從它來，`proto8/py/aos/apps/tools/tooldef.py:175`）、`defs`、`ls`／`stat` 的標記、agent.py 編譯 | 認 | 不認 |
| 兩個名字都給（`_metainfo` 連到 `_metainfo.json`） | 行 | 行（實測 4；`procs`／`proc` 同一招，3.7 的例子裡 index_view 兩個名字都走得通） |

兩個名字都給做得到，代價很小：`ls` 多一行；FUSE 版多答一個名字；落檔版多建一條連結。只留 `_metainfo` 的話，上表第 2～4 列至少六處程式要改，而且跟定義夾裡的名字對不上。順帶一提：`settings` 如果是 JSON，不用副檔名現有工具也讀得到（同第一列）；如果是純文字就讀不到（實測 5）。它的格式在 `18-ctl、status、settings的候選寫法.md` 的範圍。

### 3.4 別人怎麼知道這是 aos proc（題目 5）

使用者 11-24 的原話已經給了定義：「任何linux proc，只要你能提供這些可存取的檔案佈局，如ctl/status等，那你就是aos proc」。所以要選的不是「靠什麼認」，而是「除了佈局本身，要不要再多一份宣告」。三個選項與代價：

| 做法 | 別人要做的 | 好處 | 代價 |
|---|---|---|---|
| 甲　檔在就算（讀得到 `status`、寫得進 `ctl`） | 讀一次 `status` | 就是使用者那句話；二十行 shell 也做得到；不多一個檔 | 沒有地方說「我還會什麼」。只看檔在不在會認錯：Linux 自己的 `/proc/<PID>/status` 也是「名稱:〈TAB〉值」、每個行程都有，少打一個 `/cwd` 一樣讀得到；PID 被重用時連結會指到別人。要看內容（有認得的行、`settings` 的 `name` 對得上連結名） |
| 乙　目錄裡一份 `interfaces.json` 宣告 `aos-proc` | 讀一份 JSON | 現成的機制，stack 裡今天就有一份；順便說加掛的介面（agent、kernel、帳）與檔名；介面改了意思就換新名字，不用版本號 | 多一個檔；宣告可能與實際不符（使用者 11-21：宣告只是參考）；定義夾那份帶內部檔名與指示詞，不能原樣拿來（使用者 11-21：對外的要另外一份） |
| 丙　`_metainfo` 裡加一格 | 讀 `_metainfo.json` | 不多檔 | `_metainfo` 是「不強迫寫、壞了當沒寫」的，拿來認人會靜靜失敗；「這份 inst 是哪種格式、第幾版」那種 `_metainfo` 10-12 就說不做（`proto8/thinking/2026-10/13/json-path/02-metainfo.md:16`，整理稿）；把「怎麼接」混進「我是什麼」 |

乙那一份就是使用者 11-21 說的「對外的」：檔名相對 proc 目錄、不帶指示詞、不帶內部的鍵。stack 裡今天那份 `{"aos-observed": {"file": "observed.jsonl"}}` 就是這個樣子。它要不要跟定義夾的 `interfaces.json` 同名，11-20、11-21 都還沒定。

乙還接得上一條舊原則。使用者 10-31（C-51，`proto8/docs/CONCEPTS/01-設計理念/02-C-51.md:4`）：「固定，是可以的，但建議線限縮範圍，比如只有一個檔案固定，剩下的，則都由這個檔案指定。」11-04 對 `ctl.json`／`state.json` 也選了「留 key、沒寫時預設就是這兩個名」。新介面一次固定了 `ctl`、`status`、`settings`、`_metainfo`、`procs`、`persist` 好幾個名字；`interfaces.json` 正好是 C-51 留給「其餘由它指定」的那一份，可以拿來讓這些名字「有預設、可以改」。這算不算衝突、要不要守，在 `16-過去定案與新模型的衝突檢查.md` 的範圍。

**「支援到哪一版」**：現有的規矩是不加版本鍵，只加鍵，要改意思就換新名字（N-69 `:10`）；proto8 也一律當成沒有舊版。照這兩條，答法是「看有哪些檔、`status` 有哪些行」，不是比版本號。這也是 Plan 9 的做法（憑記憶；見 `07-9P與Plan9原樣.md`）。

**推薦**：甲當定義（最少 `ctl` 加 `status`），乙當選配。`_metainfo`、`settings`、以後的 token 檔都是「有就有」。今天的程式已經是這個方向：`ctl add` 沒宣告也收，只有要靠宣告找檔的子命令才報 `InterfaceMissing`（2.2）。

### 3.5 對 `$AOS_ROOT/procs` 做 index_view（題目 6）

**今天不改 index_view 就做得到**（實測 8）。需要四樣：

1. **`procs/` 要有一份 index**。index_view 只讀 index 裡寫的字，不會自己去翻每個子夾。落檔的 daemon 在加一列、拿掉一列時寫 `procs/_index.json`；FUSE 的 daemon 當場答這個檔。
2. **每一項怎麼寫**：`{"$ref": "<名>/_metainfo.json#/summary"}`。不抄字，永遠是對面現在說的；路徑從 `procs/` 這個夾算，穿過 `procs/<名>` 連結讀到那隻 proc 的檔。代價是每一項多起一次行程：一頁 200 項約 0.5～0.7 秒，抄好的字串約 0.06 秒（實測 16）；proc 上千隻時要嘛分頁、要嘛改成抄。
3. **每隻 proc 的目錄裡要有 `_metainfo.json`、裡面有 `summary`**。今天 daemon、kernel、`_clock`、`_sweeper` 都沒有（2.1）。
4. **那句話要分得出誰是誰**。活樹 repo-aos 這台的表上，`eca-aos`、`eca-aos-kb`、`eca-aos-templates`、`eca-aos-core` 的 `def` 都是 `templates/agents/eca-claude`，照第 2 點印出來四行會一模一樣。定義的 `summary` 講的是「這一種」，不是「這一隻」。

第 4 點的三個來源：起它的人 add 時給一句、daemon 記在自己的 index（推薦）；proc 自己寫在 `settings`；或者不解，接受同種的看起來都一樣。推薦第一個，理由是「這一隻被叫來做什麼」只有起它的人知道，而且 index 的天然位置本來就是「上一層怎麼看這個節點」（使用者 11-12）。使用者自己的筆記裡也有一句同方向的話（`wf/user/advice` 的 `README.md`，11-25 讀到）：「對於子節點來說，他的"人類"就是父節點。」

**proc 死了那一行怎麼辦**（連結懸空）：

| 做法 | 那一行印什麼 | 代價 |
|---|---|---|
| 甲　照 `$ref` 不動 | `kid	bad $ref (file not found: …)`（實測 9） | 不用做事，而且是真話（讀不到＝不在）。字面像出錯，訊息還帶一句叫人建檔的提示，對死掉的 proc 是誤導 |
| 乙　daemon 收屍時把那一項改成一句話 | `kid	stopped: <原因>` 之類 | daemon 多寫一次檔。它本來就得記停掉的原因與 persist 在哪（別人要問信箱），順手寫進這一項，列表就同時答了「誰死了、為什麼」 |
| 丙　daemon 收屍時拿掉那一項 | 那一行消失 | 停著但 persist 還在的 proc 從列表上看不到 |
| 丁　daemon 一開始就抄一句（不用 `$ref`） | 跟活著時一模一樣（實測 10） | 最省事，但列表完全看不出死活 |

推薦：活著用 `$ref`（或 add 時給的那一句），死了走乙。index 的一項可以放別的鍵，index_view 不印但 `json_get` 拿得到，所以乙那一項還能順便帶 `persist`、信箱的位置；這等於把「問 daemon 信箱在哪」做成讀一個檔。這是推論，要不要讓 index 兼這個用途在 `02-aos-daemon現況.md`、`20-送訊息兩條路的細節.md` 的範圍。

### 3.6 每隻 agent 自己的根 index，與 `/proc/<PID>/root`（題目 7）

先講清楚這一條的身分：「每個 agent 有自己的根 index」是昨天 `main` 的意見，不是使用者的話。使用者對 namespace 說的是（11-24）：「或是獨特命名空間這個特性，plan 9的，這可以之後想想。」所以這節只攤事實與形狀，不列成要他現在裁的題。

**是兩件事，形狀相同、可以疊**（推論，實測 12 佐證）：

| | 根 index | mount namespace（`/proc/<PID>/root`） |
|---|---|---|
| 管什麼 | 每樣東西**是什麼**、先看哪幾樣 | **碰得到**什麼 |
| 硬不硬 | 軟：沒列的照樣打得開 | 硬：沒掛進來的不存在 |
| 有沒有描述 | 有 | 沒有 |
| 今天有沒有 | 機制有（index_view 的 `index` 參數）；活樹的 stack 裡沒有任何 index 檔 | aos-sandbox 用 bwrap 做得到（今天套在哪裡見 `15-權限過去的規劃對照新模型.md`） |

Plan 9 的 namespace 一次做兩件事：它既是名字表，也是牆（憑記憶）。aos 要同樣的效果就是兩層疊起來：namespace 決定樹長什麼樣，樹根放一份 `_index.json` 說每樣是什麼。實測 12 就是這個組合：外面的人對 `/proc/<PID>/root` 做 index_view，看到的就是「這隻 agent 眼中的世界」，一行一樣、各附一句話。只做軟的那一層也行：一個夾，裡面幾條連結加一份 `_index.json`，index_view 與 json 工具今天就走得通（實測 4、8 都是穿過連結讀的）。

**今天其實已經有一份沒有描述的根表**：環境變數。`AOS_STACK`、`AOS_WS`、`AOS_DAEMON`、`AOS_HOME`、`AOS_LLM_KERNEL`、`AOS_KERNEL`、`AOS_CLOCK`、`AOS_PARENT_STACK`、`AOS_NOTIFY_BOX`（`proto8/knowledge/aos/world.md:22`）就是「每個行程各自一份的具名入口」。新模型的 `settings` 是它的檔案版，根 index 是它加上描述的版本；三樣列的是同一批錨點（推論）。

**放哪**，三個位置各有道理，而且 index_view 現成就能疊（實測 15）：

| 位置 | 是誰的話 | 留不留得住 | 別人看得到嗎 |
|---|---|---|---|
| 身體裡（proc 目錄） | 起它的人給的：「給你看這些」 | 跟行程一起沒，每次起來重給 | 看得到。Plan 9 也把每個行程的 namespace 放在它的 proc 目錄裡給人讀（`ns` 檔，憑記憶） |
| persist 裡 | agent 自己的：「我覺得這些重要」 | 留得住 | 要知道 persist 在哪 |
| daemon 那邊 | daemon 的預設 | 跟 daemon 一起 | 看得到 |

推論：身體裡那份當底（給的），persist 那份疊上去（自己的），正好是使用者 11-12 分的「通用視角」與「主觀」，也符合他說的主觀那份「就自己想想要放哪，我們不規定」。所以**規格裡不必規定根 index 的位置**，頂多留一個約定俗成的名字。

**兩個要先知道的坑**（細節在 `08-Linux機制實測.md`、`15-權限過去的規劃對照新模型.md`）：

- 沙箱裡的行程走不進 `/proc/<外面的 PID>/cwd`（實測 13）。一旦用 bwrap 給 agent 各自的 namespace，`AOS_ROOT=/proc/<PID>/cwd` 這個入口，連同每一條 `procs/<名>` 連結，在沙箱裡全都斷。要嘛把樹綁進沙箱，要嘛那棵樹由 FUSE／9P 或 socket 來答。「連到 `/proc/<PID>/cwd`」這個做法只在大家同一個 namespace 時成立。
- 先解開連結再開檔的程式，隔著 mount namespace 會讀錯檔（實測 14）。`/proc/<PID>/cwd` 讀出來的字串是**對方 namespace 裡**的路徑，拿到自己這邊再開，開到的是自己這邊同名的東西。aos-json 就是先解連結的（`proto8/cpp/aos-json/src/doc/file.cpp:24`）。同一個 namespace 裡沒事。

### 3.7 一個具體的例子（題目 8）

下面每一行右邊標「定了」或「例子」。PID 與路徑是舉例。除了 `interfaces.json`，這些檔在暫存夾裡真的擺過一遍（兩隻玩具行程各站在自己的夾）；最後兩段 index_view 的輸出是實際跑出來的，玩具只有一層 daemon，所以路徑比上面少一段 `repo-aos/procs`。

```
$ echo $AOS_ROOT
/proc/2223/cwd                                    定了：入口是根 daemon 的 PID（實測要多一個 cwd）
$ ls -l $AOS_ROOT/procs/repo-aos/procs/           定了：daemon 多一個 procs 夾，每一項連到那個 proc 自己的目錄
_index.json                                       例子：這個夾的說明（3.5）
eca-aos -> /proc/2243/cwd
eca-aos-kb -> /proc/2244/cwd
$ ls -l $AOS_ROOT/procs/repo-aos/procs/eca-aos/   這隻 agent 的身體
_metainfo.json -> …/templates/agents/eca-claude/_metainfo.json     定了「照現有」；用連結是 3.2 的推薦
_metainfo -> _metainfo.json                       例子：第二個名字（3.3）
ctl                                               定了
status                                            定了
settings                                          使用者提過這個名字；裡面的格式沒定
persist -> /home/guanyu/aos-home/persist/repo-aos/eca-aos          定了推薦位置 procs/<名>/persist；指到哪是例子
sock                                              定了「活著走 unix socket」；檔名是例子
_index.json                                       例子：這個目錄的說明
interfaces.json                                   例子：對外那份宣告（3.4）
```

daemon 自己的目錄多兩項：`procs/` 與 `proc -> procs`（定了：兩個名字指同一處）。

`cat status`（格式定了；有哪些行還沒談，下面是例子）：

```
phase: running
pid: 2243
started_at: 2026-11-25T00:01:15Z
queued: 0
mailbox_waiting: 2
tokens_in: 18234
tokens_out: 911
```

`cat settings`（例子；這裡照 `status` 的樣子寫）：

```
name: eca-aos
def: /home/guanyu/repo/aos/proto8/templates/agents/eca-claude
ws: /home/guanyu/repo/aos
persist: /home/guanyu/aos-home/persist/repo-aos/eca-aos
mailbox: /home/guanyu/aos-home/persist/repo-aos/eca-aos/mailbox
daemon: /proc/2241/cwd
parent:
notify_box:
```

`cat _metainfo.json`（定了：照現有；這就是今天 eca-claude 範本那份，一個字沒改）：

```json
{"summary": "Run Claude Code as an aos agent: one turn per queue batch, answers appended to history.", "cost": {"time_ms": 60000}, "resource": ["llm"]}
```

`ctl`：`echo stop > ctl`，寫回來就是收到（定了）；收哪些字、讀它回什麼還沒談。

`cat interfaces.json`（例子；檔名相對這個目錄，接在 `persist` 這個錨點後面）：

```json
{"aos-proc": {}, "aos-agent": {"history": "persist/history.jsonl", "queue": "persist/queue"}}
```

`cat _index.json`（例子），以及對這個目錄、對上一層 `procs` 做 index_view 實際印出來的：

```
{"ctl": "write one word to command me; a write that returns means received",
 "status": "what I am doing now, one 'name: value' per line",
 "settings": "where my things are (persist, mailbox, ws, def); fixed when I started",
 "_metainfo.json": "what I am: one sentence and declared properties, from my definition",
 "persist": "what I keep across restarts",
 "sock": "talk to me here while I am alive"}

[index] /proc/<根的 PID>/cwd/procs/eca-aos/_index.json, 6 entries
ctl	write one word to command me; a write that returns means received
status	what I am doing now, one 'name: value' per line
settings	where my things are (persist, mailbox, ws, def); fixed when I started
_metainfo.json	what I am: one sentence and declared properties, from my definition
persist	what I keep across restarts
sock	talk to me here while I am alive

[index] /proc/<根的 PID>/cwd/procs/_index.json, 1 entry
eca-aos	Run Claude Code as an aos agent: one turn per queue batch, answers appended to history.
```

改走另一個名字（`…/cwd/proc`）印出來的一樣，只有標頭那行的路徑變成 `…/cwd/proc/_index.json`。最後那一行就是 3.5 第 4 點的問題：這句話說的是「這一種」，四隻 eca 會印出同一句。

## 4. 邊緣狀況

1. **經連結寫 `_metainfo` 會改到定義**。`json_set` 寫的是解開連結後的真檔（實測 4）。任何 agent 對 `procs/<名>/_metainfo.json` 下 `json_set`，改到的是所有同定義 proc 共用的那一份。規格要寫「這個檔不收寫入」；落檔的實作擋不住同帳號的寫，只能靠規矩。
2. **死掉的 proc 連 `settings` 都讀不到**。persist 在哪寫在 `settings`，`settings` 在身體裡，身體跟行程一起沒。所以 daemon 得在 proc 還活著時把 `persist`、信箱位置抄到自己那邊（接 `9p-proc-1125.md`「persist 的位置得在 proc 還活著時就讓 daemon 知道」那條）。停掉的原因、結束碼也一樣，只有 daemon 留得住。
3. **原樣連過來的 `_metainfo.json` 不能順便帶 proc 目錄的 index**。`_metainfo.json` 的 `index` 鍵講的是「這個夾底下有什麼」；同一份檔在定義夾講的是 `fsm.json`、`tools.json`，連到 proc 目錄後 index_view 會把它當成 proc 目錄的說明。proc 目錄要自己一份 `_index.json`，3.7 的例子就是這樣擺。兩份是逐項疊的：同名的鍵 `_index.json` 贏，定義那份多出來的鍵還是會混進來。好在今天 95 份 `_metainfo.json` 沒有一份寫 `index`。
4. **PID 被重用**。`procs/kid -> /proc/1234/cwd`，kid 死後 1234 給了別的行程，連結就指到別人站的夾。對面如果剛好也是 aos proc，讀到的是別人的 `status`。用「連結名＝對面 `settings` 自稱的 `name`」可以便宜地擋掉（推論）；根本的做法在 `08-Linux機制實測.md`。
5. **兩個 `status` 長得像**。Linux 的 `/proc/<PID>/status` 也是一行一個「名稱:〈TAB〉值」（這台 59 行，名稱大寫開頭）。路徑少打 `/cwd` 一樣讀得到一份看起來合理的東西。工具認 aos 的 `status` 要找認得的行（例如小寫的 `phase`），不能只看檔在不在。
6. **`..` 有兩種走法**。index 與 `$ref` 裡的路徑是照字面消掉 `..`（`proto8/py/aos/refpath.py:43`）；`cat`、`read` 是核心照連結的真位置走。穿過 `procs/<名>` 這條連結後，兩邊答案不同（實測 11）。FUSE 版的 `procs/<名>` 是真的目錄，沒有這個差別。C++ 那邊（`aos::ref_spot`）我沒另外驗，照說明是同一張對照表。
7. **純文字檔進不了 `$ref`**。3.5 的列表想多顯示一欄「現在的 phase」做不到：index 裡寫 `{"$ref": "<名>/status#/phase"}`，那一行印的是 `bad $ref (…/status is not JSON)`（實測過）。
8. **先解連結的程式會把 `/proc/<PID>/cwd/…` 換回真實路徑**。除了第 3.6 節的讀錯檔，還有一個推論、沒測：eca-aos 量到走 `/proc/<PID>/cwd/procs/kid/sock` 可以繞過 unix socket 路徑 108 bytes 的上限；這一招對先 realpath 再 connect 的程式無效。
9. **定義改了的那一小段時間**。甲（動態連結）下，別人立刻看到新的 `_metainfo`，但 `loop.json`、`.env` 要重起才生效；這段時間「說的」比「跑的」新。
10. **`procs/` 裡多了一個不是 proc 的名字**。`procs/_index.json` 會跟各 proc 並列；數 proc 的程式要跳過它。今天 `_` 開頭的列名是 daemon 自己的小幫手（`_clock`、`_sweeper`），規則要講清楚「`_` 開頭的不一定是 proc」。
11. **`_metainfo` 是軟的，kernel 卻要拿它當判斷標準**。它「不強迫寫、壞了當沒寫、寫錯自己負責」。kernel 照它分資源時，沒寫的、寫壞的、寫得好看的各該怎麼算，今天沒有答案；這在 `14-kernel過去的規劃對照新模型.md` 的範圍。3.1 的「宣稱在 `_metainfo`、實測在隔壁的 `status`」至少讓 kernel 兩樣都拿得到。
12. **小毛病**：index_view 的 `bad $ref` 那行帶著「create it first, e.g. json_set …」的提示。`index.py:38-47` 的 `read()` 會拿掉這句，`:277-298` 的 `deref()` 沒有。

## 5. 要問使用者的

1. **proc 目錄裡的 `_metainfo` 是誰的話？**
   - a. 定義那份原樣（動態連結），跑的時候誰都不改。
   - b. 起來時抄一份（靜態連結），定義之後怎麼改都不影響已經在跑的。
   - c. 這隻行程自己答，可以加這一隻特有的鍵、可以隨跑隨變。
   - 推薦 a：N-69 已經規定跑的時候不改，你 11-07 也說過設計者寫的與 agent 自報的要分清；這一隻特有的放 `settings`、量到的放 `status`，三個檔才不重疊。
2. **`status`、`settings` 這種純文字檔，要不要讓 json 工具讀得到？**
   - a. 不用，agent 用 `read`、`grep`。
   - b. json 工具（只讀）認「一行一個 名稱: 值」的純文字，`…/status#/phase` 拿得到那一行，像 11-21 讓它認 md 那樣。
   - c. `settings` 用 JSON，`status` 維持純文字。
   - 推薦 b：`status` 會是 proc 目錄裡最常被讀的檔，不補的話單一路徑走到這裡就斷，agent 又多記一套；改動只在讀的那一側，`status` 的格式不用動。
3. **`procs` 列表上每隻 proc 的那一句話從哪來？**
   - a. 各 proc 的 `_metainfo` 的 `summary`。今天做得到，但同一個範本起的會一模一樣，daemon、kernel 目前沒有這個檔。
   - b. 起它的人 add 時給一句，daemon 記在自己 `procs` 的 index；沒給才退回 a。
   - c. proc 自己在 `settings` 寫一句。
   - 推薦 b：分得出誰是誰的那句話是「這一隻被叫來做什麼」，只有起它的人知道；記在 daemon 那邊，proc 死了那句話還在，可以順手改成停掉的原因。
4. **最少要有哪幾個檔才算 aos proc？其餘的怎麼讓別人知道有沒有？**
   - a. `ctl` 加 `status` 就算；其餘有就有，看檔在不在。
   - b. a，再加一份選配的 `interfaces.json`（只是參考），說這隻還會哪些介面、檔叫什麼。
   - c. 一定要有 `interfaces.json` 宣告 `aos-proc` 才算。
   - 推薦 b：你 11-24 說「提供這些可存取的檔案佈局，如ctl/status等，那你就是aos proc」，11-07 說 metainfo 不強迫，11-21 說宣告只是參考；b 三句都不違反，又讓 agent、kernel 這類加掛的介面有地方說。
5. **檔名：`_metainfo` 還是 `_metainfo.json`？**
   - a. 只有 `_metainfo.json`（今天的名字，你 11-04 裁的「留 _、加 .json」）。
   - b. 兩個名字都給、指同一份（像 `proc`／`procs`）。
   - c. 只有 `_metainfo`。
   - 推薦 a，b 也行（一條連結）：c 要改 index_view、`metainfo.read`、aos-tools、`defs` 等至少六處，而且跟定義夾裡的名字對不上。

## 6. 沒查到／沒把握的

- 九軸逐軸的定義不在這個 repo（原文在 repo 外的 `ai_core`），我只有九個名字。
- 「今天的身體每拍重讀定義的大部分檔」是從「身體每拍是新行程」推的，沒有逐檔驗。
- FUSE／9P 版底下 index_view、aos-json 的行為沒測（這台沒有 libfuse 標頭）；在 `09-FUSE與9P實作可行性.md` 的範圍。
- 不同 Linux 帳號沒測。第 13 列的原因是憑記憶的核心規則，只有結果是實測的。
- Plan 9 的 `/proc/<pid>/ns`、「看檔在不在就知道支援什麼」是憑記憶，以 `07-9P與Plan9原樣.md` 為準。
- `settings` 的格式沒定，3.7 寫成純文字只是例子；`status` 有哪些行、`ctl` 收哪些字都還沒談，以 `18-ctl、status、settings的候選寫法.md` 為準。
- kernel 實際要讀 `_metainfo` 的哪幾個鍵、讀了做什麼決定，沒查；我只確認今天沒有任何 kernel 在讀。
- `_entry` 放進 proc 目錄是什麼意思（「重起這一隻」還是「對這一隻說話」）沒有任何前例可引，我沒有往下想。
- 實測只在公司 WSL2（核心 6.6.114.1、bwrap 0.9.0、非 setuid）跑過；家機沒跑。
