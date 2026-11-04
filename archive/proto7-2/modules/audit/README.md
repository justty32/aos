# 稽核包（audit）

← [proto7-2](../../README.md)｜[核心 spec](../../spec.md)

**可選的寫入紀錄**：任務是 Python 程式時，盡力記下它的「寫」動作（涵蓋範圍見保證），事後挑出寫到「自己的 node 與掛載點」之外的（S-10「只碰給的資料夾」沒有強制，這裡只記不擋）。

| 項目 | 內容 |
|---|---|
| 接法 | B 包裝程式：tasks.json 項目的 argv 寫成 `aos7-audit -- <argv...>`（設 `AOS7_AUDIT=1`、把 `audit_site/` 放到 `PYTHONPATH` 最前面，再 exec argv）。核心不知道稽核 |
| 預設 | 關 |
| 依賴 | 核心協定：無；程式依賴：`aos7_audit.py` 匯入工具包的 `aos7_taskside`（`read_jsonl`） |
| 程式 | `aos7-audit`（包裝程式）、`audit_site/sitecustomize.py`（任務裡的 audit hook，寫 `$AOS7_TASK/writes.jsonl`）、`aos7_audit.py`（`scan(root)` 掃全空間的紀錄） |
| 測試 | `tests/`（`python3 proto7-2/tests/run_all.py modules/audit/tests`） |

## 契約卡

- **職責**：Python 任務的寫入紀錄（`writes.jsonl`）＋全空間掃描挑出越界的；**只記不擋**（下面規則節）。
- **前置條件**：argv 經 `aos7-audit` 包起；任務是 Python 程序；`nodes.json` 只有 daemon 寫。
- **保證**：
  - 已涵蓋的 Python audit 寫入事件，在空間根底下的都有紀錄與 `ok` 判定：落在自己的 node（扣掉巢狀的別的 node／daemon 根）或某個掛載目標底下（核心 spec §5.5）。以整數 fd 指定的目標、沒涵蓋的事件、紀錄本身寫失敗（吞掉、只記不擋）時可能沒有紀錄——`writes.jsonl` 是觀察資料，不是完整寫入清單，沒有紀錄不能證明沒寫。
  - 登記邊界照**判定當下**的 `nodes.json`：執行中才登記的巢狀 node，之後寫進去就是 `ok: false`（A4-05）。
  - 通用 `AOS7_AUDIT_ALLOW` 由包裝程式設定（例如 subd 包設子根），以 `os.pathsep` 分隔絕對路徑；每次判定重讀並取 realpath，只承認自己 node 內的項目，其底下寫入豁免巢狀邊界，node 外的項目忽略（N-66、D9）。
  - 遞迴旗標各 thread 獨立；其他 thread 正在追加紀錄時，也會記下本 thread 的寫入（R8-25）。
  - 不改任務的行為、不擋寫入；紀錄只留這次 run（核心 §5.1 換 run 清掉）。
- **明確不管**：非 Python 的寫入；繞過包裝；強制隔離（S-10 仍是合作式）。

## 規則

- 例：`{"name": "w", "argv": ["python3", "<proto7-2>/modules/audit/aos7-audit", "--", "python3", "job.py"]}`。
- 紀錄每筆 `{"op", "path"（實際位置）, "ok", "pid", "via"}`；只記空間根底下的寫入。`ok`＝落在自己的 node（扣掉巢狀的別的 node／daemon 根）或某個掛載目標底下。`aos7_audit.scan(root)` 把全空間的紀錄拼起來，挑出 ok 是 false 的。
- `AOS7_AUDIT_ALLOW` 是通用巢狀邊界豁免：包裝程式可設 `os.pathsep` 分隔的絕對路徑（例如 subd 包設子根），每次寫入判定都重讀並取 realpath；只在自己 node 內的項目底下直接判 `ok: true`，相對路徑與 node 外項目忽略，不能藉此把 node 外變合法。
- `writes.jsonl` 也只留這次 run（換 run 時 tick 清掉）。

## 界線

- 只看得到 Python 程序；sh、C 程式的寫入看不到。只記不擋：S-10「只碰給的資料夾」仍是合作式的。
- 繞過包裝（argv 沒加 `aos7-audit`）就沒有紀錄；以前核心照任務環境的 `AOS7_AUDIT` 自動加，現在核心不知道稽核（方案第 6 節）。

`aos7-audit --help` 看包裝用法；參數不合時一行說明並附例子。正常仍 exec 子命令並透傳它的退出碼，程式起不來仍沿用既有處理；入口遇到未預期例外時只報一行「不確定」，保留證據供檢查。
