# 第三段：daemon 核心（最核心版）

← [plan 入口](README.md)｜依據：[最核心 aos-daemon（已裁定 10-01）](../notes/2026-10-01-daemon-core-sketch.md)｜結束碼：[verdicts 11 篇末「aos 結束碼慣例」](../notes/verdicts/11-tick-as-unit.md#aos-結束碼慣例待統一更新-spec)｜正本（大部分先不做）：[B-601](../spec/settled/daemon/runtime.md#b-601記憶體登記與按需執行)、[B-606](../spec/settled/daemon/registration.md#b-606登記解除換父與身分額度)、[B-607](../spec/settled/daemon/registration.md#b-607叫醒暫停故障停格與格次序號)、[P-101](../spec/settled/protocol/daemon/startup-and-ipc.md#p-101啟動設定與-socket建議預設未拍板)

**做完的樣子**：沒有 root、systemd、cgroup、helper 的機器上，一般帳號跑 `aos-daemon --config F`：讀設定檔裡的 inst 路徑清單，每一項照自己的週期叫一次 `bin/aos-exec <inst 路徑>`，每次結束在 stdout 印一行 `id=… exit=… ms=…`；非 0 時停不停照該項設定；Ctrl-C 直接退出、回 0。node 資料夾放一份 `argv` 寫 `aos-tick` 的 `inst.json`，把它加進清單，就是「daemon 定期跑一個 node」。

> **這次範圍砍到哪（使用者 2026-10-01）**：[plan 入口第三段](README.md#第三段daemon-核心)原本寫的是 spec 完整的開格核心——登記／解除／換父、叫醒／暫停、`aos-runner` 開格與格後收屍、重啟與停機收尾、通道憑證、socket 與 IPC、`state.json`、掛行程與砍掉。這次全部不做，只做[最核心草稿](../notes/2026-10-01-daemon-core-sketch.md)裁定後的版本：**一個叫 `aos-exec` 的 cron**。daemon 不認得 node，node 的事（`tasks.json`、鎖、擋板、紀錄）全在 `aos-tick` 那側（草稿「管 node 變成可掛載的模組」）。
>
> **挪到之後**（還沒排進哪一段，等這版做完、使用者看過再排）：叫醒（第一個要加，要 socket）、暫停／恢復、登記與上下層、runner 與收屍、逾時、收尾寬限與排空停機、重啟清理與 `state.json`、通道與憑證、事項、熱重載、B-615 五個開關、`aos daemon` 子命令。第四、五段（訊息、cgroup、helper）原本建在完整第三段上，開工前要重看前提。

> **POC 總原則**：默認一切正常——設定檔讀得懂、路徑都對、`aos-exec` 叫得起來、沒有兩個 daemon 跑同一份清單。不寫異常處理，出事讓 Python 自然丟錯（traceback、回 1）。

> **結束碼**（使用者 2026-10-01）：0＝預料之中；0 以外＝要額外處理；1＝通用錯誤，沒特別設的錯一律 1。`aos-tick` 的忙、擋板、停格都回 0；`aos-exec` 用法錯回 1（這兩處程式改動另有人做，本段當它已改好）。

- 由 AI 隊實作、照各步驟驗收試跑，做完交使用者看；每步的「要使用者裁定的點」集中在文末待問。
- Python 3.9、只用標準庫。放 [src/py](../src/py/README.md)：入口 `bin/aos-daemon`（薄殼，`.gitignore` 擋 `bin/`，要 `git add -f`）、`lib/aos_daemon*.py`；測試 `tests/test_daemon.py`，用 `unittest`。檔案怎麼切 AI 隊自己定。
- 叫的是**同一個 `bin/` 資料夾裡的 `aos-exec`**（不靠 PATH），參數只給 inst 路徑，不帶 `--stderr`、`--timeout-ms`。
- 做完要補 src/py README 的檔案表與 [code map](../../wf/workflows/common/code-map.md)（鐵律 3）。

## 步驟 1：讀設定檔

- **要做到**：`aos-daemon --config F` 讀設定檔，得到一份清單，每項有 id（＝`inst` 字面值）、`inst` 字面值、週期、非 0 停不停；另外算好一個「起點資料夾」給步驟 2 開子程序用。
- **依據**：草稿裁定 1、7 與[設定檔追加裁定](../notes/2026-10-01-daemon-core-sketch.md#設定檔追加裁定使用者-2026-10-01)；[B-606](../spec/settled/daemon/registration.md#b-606登記解除換父與身分額度)「頂層從設定載入」只留這條路；[P-101](../spec/settled/protocol/daemon/startup-and-ipc.md#p-101啟動設定與-socket建議預設未拍板) 的設定欄位這版不沿用（裁定 7 隨意）。
- **設定檔**（使用者 2026-10-01 認可）：

  ```json
  {
    "cwd": "/home/u/nodes",
    "interval_ms": 60000,
    "stop_on_nonzero": false,
    "insts": [
      {"inst": "a"},
      {"inst": "jobs/report.json", "interval_ms": 5000, "stop_on_nonzero": true}
    ]
  }
  ```

  上例：`a` 是資料夾（aos-exec 自己去找 `a/.aos/inst.json` 或 `a/inst.json`），用頂層的 60 秒、非 0 不停；`jobs/report.json` 是檔，自己蓋成 5 秒、非 0 就停。兩項都相對 `/home/u/nodes`。
  - `insts`：陣列。每項 `inst` 必填，可另寫 `interval_ms`、`stop_on_nonzero` 蓋過頂層。
  - `inst`：**原樣交給 aos-exec**，資料夾或檔都行，只要合 aos-exec 的目標規則（見 [src/py README 改動 2](../src/py/README.md#改動-2資料夾目標怎麼找-inst)）；daemon 不檢查、不解析、不轉絕對路徑。
  - 頂層 `cwd`（可省略）：相對路徑的起點。沒寫＝daemon 啟動時的工作目錄；本身是相對路徑時也以 daemon 啟動時的工作目錄為起點。daemon 開起來時算成一個絕對路徑（`os.path.abspath`，不解符號連結）。
  - 頂層 `interval_ms`、`stop_on_nonzero`（可省略）：所有項的預設；每項自己寫的蓋過頂層。`interval_ms` 正整數，兩邊都沒有＝設定錯、回 1（沒有叫醒，沒週期就永遠不會跑）；`stop_on_nonzero` 布林，兩邊都沒有＝`false`。
  - 其他鍵（頂層或每一項）一律忽略，所以寫 `_metainfo` 也沒關係。
  - 不驗格式（默認是對的），缺鍵或型別錯就自然丟錯、回 1。
- **id**：就是 `inst` 的字面值，不另外算。上例兩項的 id 是 `a` 和 `jobs/report.json`。同字面值重複默認不會發生，不檢查。
- **做法**：argv 只認 `--config F`（必填；`F` 相對路徑照常以 daemon 啟動時的工作目錄為準）；用法錯 stderr 一行、回 1（argparse 預設 2，要改）。
- **要使用者裁定的點**：無（原待問 1、2 已因追加裁定結案）。
- **驗收**：
  - id 照字面：`a`、`./a`、`/abs/a/inst.json` 印出來就是這三個字串。
  - 起點：沒寫 `cwd` 時用 daemon 啟動時的工作目錄；`"cwd": "sub"` 是啟動時工作目錄底下的 `sub`；`"cwd": "/abs"` 就是 `/abs`。
  - 頂層預設與覆蓋：頂層 `interval_ms` 套到沒寫的項，有寫的項用自己的；`stop_on_nonzero` 同理，兩邊都沒有＝不停。
  - 兩邊都沒有 `interval_ms`：回 1。
  - 沒給 `--config`、多給不認得的參數：回 1。
  - 設定檔不存在或不是 JSON：回 1（traceback 就好）。

## 步驟 2：叫一次 aos-exec、印一行

- **要做到**：對清單的一項開一個子程序 `<bin>/aos-exec <inst 字面值>`，工作目錄設成步驟 1 的起點資料夾，等它結束，stdout 印一行。
- **依據**：草稿「怎麼叫」「怎麼看結束碼」；裁定 1、8。
- **做法**：
  - 子程序自成 session（`start_new_session=True`），stdin 接 `/dev/null`，stdout、stderr 繼承 daemon 的（inst 自己決定要不要 `inherit`，預設都是 `/dev/null`）。**子程序的工作目錄設成起點資料夾**（`Popen(cwd=…)`），`inst` 字面值原樣當參數：相對的 `inst` 由 aos-exec 照它自己的規則、從起點解析，跟人站在起點手打 `aos-exec <inst>` 一模一樣，daemon 不碰路徑。環境變數照 daemon 的。inst 自己的 `cwd` 預設是 inst 所在資料夾（資料夾目標是那個資料夾），由 aos-exec 處理，不受起點影響。
  - 一行的格式：`id=<id> exit=<碼> ms=<毫秒>`，寫完立刻 flush。碼照實印；aos-exec 被訊號殺（`returncode` 是負的）印成 `128+N`，跟 shell 一致。
  - 多項同時結束時，一行不能被另一行插進來（印的時候上鎖，或只有一條執行緒在印）。
- **要使用者裁定的點**：無（行格式見待問 4）。
- **驗收**：
  - 假 inst `{"argv": ["sh", "-c", "exit 3"]}`：印 `exit=3`；`{"argv": ["true"]}`：`exit=0`。
  - 從別的資料夾啟動 daemon、設定檔寫 `"cwd"` 加相對 `inst`：照樣找得到、跑得起來；不寫 `cwd` 時相對 daemon 啟動時的工作目錄。
  - 假 inst 把 `$$`、`$PPID` 寫進檔：子程序的 session id 不等於 daemon 的。
  - inst 寫 `"stderr": {"$opt": "inherit"}` 時 stderr 印到 daemon 的終端；沒寫時 daemon 的終端看不到。

## 步驟 3：照週期叫、各跑各的

- **要做到**：每一項 daemon 一開就立刻跑一次；之後每次結束後隔 `interval_ms` 再叫；同一項不疊著開；不同項同時跑、互不等。
- **依據**：裁定 4；[B-607](../spec/settled/daemon/registration.md#b-607叫醒暫停故障停格與格次序號) 定期那段、[B-601](../spec/settled/daemon/runtime.md#b-601記憶體登記與按需執行) 同一項只一個子程序。
- **做法**（建議）：每一項一條執行緒，跑一個迴圈「叫 → 等 → 印 → 睡 `interval_ms`」。不補跑漏掉的次數，週期是「間隔」不是「時刻表」。
- **要使用者裁定的點**：無（已裁定）。
- **驗收**（都用短週期，例如 100 ms）：
  - 假 inst 每次在檔裡加一行時間：daemon 一開 100 ms 內就有第一行；跑 1 秒後大約 9～10 行。
  - 假 inst `sleep 0.3`、週期 50 ms：任兩次的開始時間至少差 350 ms（不疊）；檔裡永遠沒有兩個同時在跑的記號。
  - 兩項，一項 `sleep 30`、一項 `true` 週期 100 ms：`true` 那項照常一直印，不被卡住那項拖住。

## 步驟 4：非 0 停不停

- **要做到**：一次跑完碼不是 0 時，`stop_on_nonzero` 是 `true` 就不再叫這一項（直到重開 daemon），`false` 就照常排下一次。
- **依據**：裁定 2、3、8；結束碼慣例「0 以外要額外處理」。
- **做法**：停的時候在那一行之後多印一行 `id=<id> stopped`。其他項不受影響。所有項都停了，daemon 照樣開著、什麼都不做（見待問 3）。
- **要使用者裁定的點**：待問 3。
- **驗收**：
  - `{"argv": ["false"]}` 帶 `stop_on_nonzero: true`：只印一行 `exit=1` 跟一行 `stopped`，之後一秒內不再出現這個 id；同時另一項照跑。
  - 同樣的 inst 帶 `false`（或不寫）：一直印 `exit=1`。
  - 碼是 0 時 `true` 也不停。
  - inst 路徑不存在：aos-exec 回非 0（改好後是 1），照上面停或不停。

## 步驟 5：Ctrl-C 與 SIGTERM

- **要做到**：收到 SIGINT 或 SIGTERM，daemon 直接退出、回 0，不殺也不等正在跑的子程序。
- **依據**：裁定 5；[B-604](../spec/settled/daemon/lifecycle.md#b-604收尾停機停用與退役) 的收尾這版不做。
- **做法**：兩個訊號都當「使用者要停」。子程序在自己的 session，終端的 Ctrl-C 打不到它們，會自己跑完。
- **要使用者裁定的點**：無（已裁定）。
- **驗收**：
  - 開 daemon，等第一行後送 SIGINT：1 秒內退出、回 0。SIGTERM 一樣。
  - 退出時有一項正在 `sleep 1; touch done`：daemon 退出後那個檔照樣出現（子程序沒被殺）。

## 步驟 6：掛上 aos-tick（node 當模組）

- **要做到**：證明「daemon 定期跑一個 node」不需要 daemon 認得 node，只要一份 inst。
- **依據**：裁定 1「管 node 變成可掛載的模組」；[第一段](m1-tick-core.md)的 `aos-tick`。
- **做法**：不寫新程式，只寫測試與 README 例子。node 資料夾長這樣：

  ```text
  /n/a/inst.json         {"argv": ["aos-tick"], "stderr": {"$opt": "inherit"}}
  /n/a/.aos/tasks.json   照第一段的任務表
  ```

  inst 的 `cwd` 預設就是 `/n/a`，tick 不帶 `--node` 用 `./`。測試裡 `argv[0]` 寫 `bin/aos-tick` 的絕對路徑，不靠 PATH。
- **要使用者裁定的點**：無。
- **驗收**：
  - 清單放 `/n/a/inst.json`、週期 100 ms，跑 1 秒：每次印 `id=/n/a/inst.json exit=0`，`.aos/tick/current.json` 的 `seq` 一直往上加。
  - 清單改寫資料夾 `/n/a`：一樣跑得起來（aos-exec 自己找到 `inst.json`），印 `id=/n/a`。
  - 放上擋板檔：照樣每次 `exit=0`，`seq` 不動；拿掉後又開始加。
  - 任務表寫壞：tick 回 1，daemon 印 `exit=1`；`stop_on_nonzero: true` 時印 `stopped`。
  - 同一個 node 放進兩個 daemon 同時跑：都只看到 `exit=0`，紀錄沒壞（靠 tick 的鎖）。

## 步驟 7：整段驗收

- 步驟 1～6 的驗收合成 `tests/test_daemon.py`，一條指令跑完；不需要 root、systemd、網路，全部用暫存資料夾、短週期、假 inst，每條幾秒內結束。
- 測試結束自己殺掉 daemon 和留下的子程序（daemon 不殺，見步驟 5），用 process group 殺乾淨。
- 原有的測試（tick、exec、inst）照樣全過。

## 這段不做的，先怎麼擋著

| 不做 | 這版的樣子 | 什麼時候 |
|---|---|---|
| 叫醒、socket、IPC、授權 | 只有週期；要馬上跑就重開 daemon | 之後第一個加 |
| 暫停／恢復 | 放擋板檔（tick 回 0、什麼都不做） | 之後 |
| 登記、上下層、身分額度 | 清單只從設定檔來，平的 | 之後 |
| runner、收屍、逾時 | 叫現成的 `aos-exec`；卡住就一直卡、留下的程序沒人收 | 之後 |
| 收尾寬限、排空、重啟清理、`state.json` | Ctrl-C 直接退出；重開就從頭來 | 之後 |
| 熱重載 | 改設定就重開 | 之後 |
| 訊息、cgroup、helper、B-615 開關 | 沒有 | 第四、五段（前提要重看） |
| `aos daemon` 子命令 | 獨立指令 `aos-daemon` | 之後 |

## 待問

1. ~~**`/n/a/.aos/inst.json` 的 id 怎麼算？**~~ **結案**（使用者 2026-10-01）：id 不另算、就是 `inst` 字面值，沒有「拿掉 `/inst.json`」這回事了。node 的 inst 放在 `.aos/` 裡時，清單直接寫 node 資料夾（例如 `/n/a`），aos-exec 先找 `.aos/inst.json`、base 是 `/n/a`，不用寫 `"cwd": ".."`。
2. ~~**清單能不能直接寫資料夾？**~~ **結案**（使用者 2026-10-01）：能。`inst` 原樣交給 aos-exec，資料夾或檔都行，只要合 aos-exec 的規則。
3. **所有項都停了，daemon 要不要自己退出？** 建議：不退，照樣開著（不加特例）；要不然得定退出碼，而「全停」本身是要額外處理的狀況，回 0 或 1 都說得通。
4. **一行的格式夠不夠？** 目前只有 `id`、`exit`、`ms`，沒有時間戳、沒有開始那一行。建議：先這樣，要時間戳由外面加（例如 `| ts`）。
5. **inst 的 stderr 要不要 daemon 幫忙接？** 草稿原本建議帶 `aos-exec --stderr -`；這版改成不帶、交給 inst 自己寫 `inherit`，理由是「怎麼跑由 inst 決定」。代價是忘了寫的 inst，錯誤訊息看不到，只看得到碼。
