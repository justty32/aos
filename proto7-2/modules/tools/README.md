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

## aos7-ctl

- `aos7-ctl daemon <root> <op> [node] [--kill] [--rounds N] [--owner X] [--all]`：寫 `<root>/.aosd/ctl/<by>.<op>.<node>.json`；帶 `--owner` 時是 `<by>.<op>.<node>@<owner>.json`。固定名，回條只留最近一份。`<root>` 也可以是掛進來的 `.aosd`。
- **檔名編碼**：by／node／owner 每段無損編碼——`/`→`+`；其他不是英數、`_`、`-` 的字元（含 `.`、`@`、`+`、`%`、非 ASCII）把 UTF-8 位元組寫成 `%XX`；一段編碼後超過 64 字就取前 40 字＋`~`＋原字串 sha1 前 16 碼。不同的 by／node／owner 不會撞成同一個檔名。
- `aos7-ctl task <槽> kill [why] [--run N]`：寫 ctl.json `{"op": "kill", "run"}`；沒給 `--run` 就讀槽的 birth.json 帶現在的 run（讀不到＝報錯、不寫）。
- `aos7-ctl task <槽> restart [why] [--reload] [--id ID]`：呼叫控制包的 `restart`（先加 once 再寫 kill），stdout 印它的結果（加上 `wrote`）；沒給 `--id` 就自動產生新的請求 id，重送同一件才沿用原 id。`ok: false` 時退出碼 1。
- `aos7-ctl add <node> '<項目 JSON>'...`：拿 `tasks.json.lock` 把一或多項加進 tasks.json（一次 rename）。
- 都可加 `--by WHO`（預設：在任務裡是 `<node-id>:<tid>`，否則 `cli`）；stdout 印 `{"wrote": 路徑}`。印出路徑只表示寫好了，接受與執行看 daemon／tick／tock 的回條。

## aos7-wait-tock

`aos7-wait-tock [--after N] [--timeout 秒] [--task 任務資料夾]`：給非 Python 任務用，等 `$AOS7_TASK/tock.json` 的回合數大於 N，印出回合數；逾時退出碼 1、什麼都不印。漏掉的回合只看得到最新一個（S-11）。

## 任務端函式（`aos7_taskside.py`）

把 `proto7-2/modules/tools` 與 `proto7-2/lib` 加進 `sys.path` 後 import：

- `task_env()`：從 `AOS7_*` 環境讀自己是誰（root、node、node_id、task、tid、run）。
- `wait_tock(task_dir, last_round, timeout=None)`：同 aos7-wait-tock；`run` 對不上的舊 tock.json 不算。
- `resolver(taskdir)`：空間路徑 → 經過 `mnt/` 掛載點的實際路徑（取最長前綴，沒掛到回 None）。
- `request(taskdir, path, why)`：執行中加掛——寫 `mount-req/<名>.json`，下一個 tick 審核（核心 spec 4.5），回 `mounted`／`pending`／`refused: 原因`。
- `read_jsonl(path)`：讀流水帳（歷史、事件），壞行跳過。
- `decl_of(birth)`：birth.json 的 mounts → 原本的宣告（控制包、once 保證包照 birth 重起時用）。

## 界線

- `aos7-ctl task … kill` 沒給 `--run` 就照 birth.json 帶現在的 run：寫完到 tick／tock 執行之間槽換了 run，這份 kill 就不會打到新的那個（回條說已換人），要收新的再送一次。
- 工具的 bug 歸工具，不因工具的問題改 daemon／tick（組件契約藍圖 2.9；A2-13、A3-06 兩次都照這條修在工具）。
