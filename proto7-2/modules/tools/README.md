# 工具包（tools）

← [proto7-2](../../README.md)｜[核心 spec](../../spec.md)

**人、LLM、kernel 用的小工具，加上任務端的小函式庫。** 不在核心的任何迴圈裡，只是替你寫檔／輪詢；LLM 直接讀寫同樣的檔一樣做得到（S-01）。

| 項目 | 內容 |
|---|---|
| 接法 | C 工具（命令列）＋任務端函式庫 |
| 預設 | 開（入口 `aos7-ctl`、`aos7-wait-tock` 留在 `proto7-2/bin/`，任務的 `PATH` 有它） |
| 依賴 | [控制包](../control/README.md)（`aos7-ctl task … restart` 呼叫它）；其餘只用核心公開的檔案格式，import 核心 `lib/` 的讀寫小函式 |
| 程式 | `aos7_ctl.py`（`bin/aos7-ctl` 的本體）、`aos7_taskside.py`（任務端函式） |
| 測試 | `tests/`（`python3 proto7-2/tests/run_all.py modules/tools/tests`） |

## 契約卡

- **職責**：替人、LLM、kernel 寫檔與輪詢——`aos7-ctl` 寫控制檔、加任務，`aos7-wait-tock` 等 tock，任務端函式（下面各節）；不在核心的任何迴圈裡。
- **前置條件**：呼叫者給對 root、槽、node；任務端函式在任務環境裡用（`AOS7_*` 齊）。
- **保證**：
  - daemon 控制檔名照 by／node／owner 逐段編碼：短的可逆編碼、不同的不會撞名；編碼後太長的改用前綴＋雜湊，屬實務上的低碰撞命名、不是數學上的零碰撞（下面「檔名編碼」；檔名是寫者的事，核心 spec §2.3、W3）。
  - `task … kill` 一律帶 `run`；沒給 `--run` 就讀槽 birth，讀不到＝報錯、不寫（核心 §6）。`restart` 交給[控制包](../control/README.md)。
  - `add` 拿表鎖、一次 rename 加多項（核心 §4.3）。
  - 印出路徑只表示寫好了；接受與執行看回條。
- **明確不管**：寫完到執行之間槽換了 run（kill 不打新的，見界線）；工具的 bug 不改 daemon／tick（[組件契約](../../notes/component-contracts.md) 2.9）。

## aos7-ctl

- `aos7-ctl daemon <root> <op> [node] [--kill] [--rounds N] [--owner X] [--all]`：寫 `<root>/.aosd/ctl/<by>.<op>.<node>.json`；帶 `--owner` 時是 `<by>.<op>.<node>@<owner>.json`。固定名，回條只留最近一份。`<root>` 也可以是掛進來的 `.aosd`。
- **檔名編碼**：by／node／owner 每段編碼——`/`→`+`；其他不是英數、`_`、`-` 的字元（含 `.`、`@`、`+`、`%`、非 ASCII）把 UTF-8 位元組寫成 `%XX`；一段編碼後超過 64 字就取前 40 字＋`~`＋原字串 sha1 前 16 碼。沒截短的段是可逆、不撞名的；截短的段靠 64-bit 雜湊尾碼區分，只是實務上不撞，不是無損。
- `aos7-ctl task <槽> kill [why] [--run N]`：寫 ctl.json `{"op": "kill", "run"}`；沒給 `--run` 就讀槽的 birth.json 帶現在的 run（讀不到＝報錯、不寫）。
- `aos7-ctl task <槽> restart [why] [--reload] [--id ID]`：呼叫控制包的 `restart`（先加 once 再寫 kill），stdout 印它的結果（加上 `wrote`）；沒給 `--id` 就自動產生新的請求 id，重送同一件才沿用原 id。`ok: false` 時依新增的 `outcome` 區分不確定與確定拒絕；鎖忙、birth／tasks 讀取故障會報不確定，保留檔案並提示用同一個請求 id 接續。
- `aos7-ctl add <node> '<項目 JSON>'...`：拿 `tasks.json.lock` 把一或多項加進 tasks.json（一次 rename）。
- 用法給錯時會附一行例子且不寫檔；讀寫失敗或無法判定時保留已有請求與檔案、提示先查控制檔與回條，不印 traceback。
- 都可加 `--by WHO`（預設：在任務裡是 `<node-id>:<tid>`，否則 `cli`）；stdout 印 `{"wrote": 路徑}`。印出路徑只表示寫好了，接受與執行看 daemon／tick／tock 的回條。

## aos7-wait-tock

`aos7-wait-tock [--after N] [--timeout 秒] [--task 任務資料夾]`：給非 Python 任務用，等 `$AOS7_TASK/tock.json` 的回合數大於 N，印出回合數；逾時退出碼 1、什麼都不印。漏掉的回合只看得到最新一個（S-11）。

## 任務端函式（`aos7_taskside.py`）

把 `proto7-2/modules/tools` 與 `proto7-2/lib` 加進 `sys.path` 後 import：

- `task_env()`：從 `AOS7_*` 環境讀自己是誰（root、node、node_id、task、tid、run）。
- `wait_tock(task_dir, last_round, poll=0.02, timeout=None, run=None)`：同 aos7-wait-tock，回新的回合數、逾時回 `None`；`run`（預設取 `AOS7_RUN`）對不上的舊 tock.json 不算。**第三個位置參數是輪詢間隔秒數**，要設等待上限寫 `wait_tock(task, last, timeout=5)`。
- `resolver(taskdir)`：回一個解析函式——`resolve = resolver(taskdir)`，再 `resolve(空間路徑)` 取得經過 `mnt/` 掛載點的實際路徑（取最長前綴，沒掛到回 None）。
- `request(taskdir, path, why)`：執行中加掛——寫 `mount-req/<名>.json`，下一個 tick 審核（核心 spec 4.5），回 `mounted`／`pending`／`refused: 原因`。
- `read_jsonl(path)`：讀流水帳（歷史、事件），壞行跳過。
- `decl_of(birth)`：birth.json 的 mounts → 原本的宣告（控制包、once 保證包照 birth 重起時用）。

## 界線

- `aos7-ctl task … kill` 沒給 `--run` 就照 birth.json 帶現在的 run：寫完到 tick／tock 執行之間槽換了 run，這份 kill 就不會打到新的那個（回條說已換人），要收新的再送一次。
- 工具的 bug 歸工具，不因工具的問題改 daemon／tick（組件契約藍圖 2.9；A2-13、A3-06 兩次都照這條修在工具）。
