← [proto6](../../../README.md)｜正本：[inst 第 1 版](../../../spec/base/inst.md)、[指示詞](../../../../proto5/spec/directives/README.md)

# aos_inst — inst 與指示詞的 Python 實作

把一份 proto6 inst 從「給一個目標」一路做到「解好的執行計畫」，另附一個可以不用的開程序模組。Python 3.9、只用標準庫。

## 怎麼用

```python
import os
from aos_inst import load_plan, grant_only
from aos_inst.spawn import run            # 可選：自己寫開程序就不用 import

plan = load_plan("path/to/node", grant_only([os.getuid()]))   # 丟 InstError 就是被拒
result = run(plan, timeout=30)            # RunResult(exit_code, timed_out, finalize_error)
```

除錯：`cd proto6/src/py && python3 -m aos_inst <目標>` 只印計畫 JSON（不跑、不建目錄）。錯誤在 stderr 印「代號: 白話」回 125，用法錯回 2。

測試：`cd proto6/src/py && python3 -m unittest`。

## 流程（身分先行）

1. `find_inst(目標)`：資料夾先找 `.aos/inst.json` 再 `inst.json`，base＝資料夾；檔案就是它，base＝所在資料夾。
2. `read_snapshot(source)`：讀一次，之後都用這份快照。
3. `raw_user(snapshot)`：只取原始頂層字面 `user`，不展開。
4. **你的** `authorize(user, uid, snapshot)`：授權、切身分，回已授權 UID。
5. `check_unchanged(snapshot)`：授權後來源變了＝`SourceChanged`（`load_plan` 預設會做）。
6. `resolve_plan(snapshot, uid)`：展開整份 → cwd → argv → envs → 四個路徑欄，驗欄位；展開後的 `user` 必須是同一個 UID。

`load_plan` 把 1–6 串起來；`load_plan_obj(dict, base, authorize)` 直接吃記憶體裡的一份（例如 tick 任務表的一項），不找檔、不比對來源。

## 公開 API

| 模組 | 東西 | 用途 |
|---|---|---|
| `errors` | `InstError(code, msg, exit_code)` | 唯一的錯誤型別；`str(e)`＝「代號: 白話」；`exit_code` 125 或 2 |
| `target` | `find_inst(t)` → `Source(path, base, is_dir)` | 找 inst |
| | `node_dir(path)` | 把 node 的 `.aos/inst.json`／`inst.json` 路徑正規化成資料夾，不是 node 回 None |
| `identity` | `read_snapshot`、`snapshot_from_bytes`、`snapshot_from_obj` | 做快照（檔案、已讀好的位元組、記憶體 dict） |
| | `raw_user`、`lookup_uid`、`check_resolved_user`、`check_unchanged` | 身分各步驟 |
| | `Authorizer`、`grant_only(uids)` | 授權接口與現成的「只准這些 UID、不切身分」 |
| `plan` | `resolve_plan`、`load_plan`、`load_plan_obj` | 解成 `Plan` |
| | `Plan`、`Stream`、`OPTIONS`、`KNOWN_KEYS` | 計畫資料結構（`Plan.to_json()` 可直接 dump）、各位置選項表 |
| `directives` | `resolve`、`resolve_located`、`parse_options`… | 指示詞機制本身（搬自 proto5，別的宿主也能用） |
| `spawn` | `run(plan, …)` → `RunResult` | 開程序；另有 `write_exit`、`status_to_code` |

`Plan` 的欄位：`uid`、`user`（字面，None＝繼承）、`argv`、`cwd`、`cwd_mkdir`、`envs`、`envs_clear`、`stdin`／`stdout`／`stderr`／`exit`（`Stream(path, append, mkdir, inherit, merge)`，`path` 空＝沒寫）、`source`、`base`、`metainfo`、`extra`（inst 不認得的頂層鍵，原樣帶出，tick 任務表的 id／kind 等在這裡）。

## 留給呼叫方的接口

- **授權與切身分**：`authorize(user, uid, snapshot) -> uid` 回呼。額度檢查、安置資源、setuid／initgroups／叫 helper 都在這裡做；不准就丟 `InstError("UserNotGranted", …)`。本套件不切身分。
- **繼承的身分**：`inherited_uid`（`user` 省略時用；預設目前 UID）。
- **`$env` 讀的環境**：`env`（預設 `os.environ`，在授權之後才讀）。
- **快照交接**：daemon 讀好的位元組用 `snapshot_from_bytes` 接，再自己決定何時 `check_unchanged`。
- **開程序**（`spawn.run`）：`base_env`（runner 環境，daemon 通道變數放這裡，會被 clear 清掉）、`forced_env`（最後補、不受 clear 影響，例如 `AOS_TICK_LOCK_FD`）、`stderr_override`、`pass_fds`、`on_spawn`、`timeout`、`grace`。
- **不做**：切身分、cgroup、後代脫離 process group 的清理、結果只發布一次、git 還原。

## 自己做的判斷（spec 沒寫死的地方）

- 執行前準備失敗（建目錄、開串流、cwd 不是資料夾、exit 父目錄不存在）spec 沒給代號，用 `PrepareFailed`；子程式跑完但 exit 檔寫不進去用 `FinalizeFailed`（結果照回，錯誤放 `RunResult.finalize_error`）；用法錯用 `Usage`。
- 目標根本不存在也算用法錯（2），跟「資料夾裡找不到 inst」一樣。
- 原始頂層是指示詞物件時（`{"$ref":…,"user":…}`），`raw_user` 一樣讀它旁邊的 `user` 鍵（spec 說「原始頂層字面」）。展開後若也帶 `user` 就要同一 UID；沒帶沿用。
- 整數 UID 原樣接受，不要求系統有這個帳號；名稱查不到才 `UserInvalid`。
- 循環鏈照 proto5：一個欄位解到的容器位置本身也在鏈上，所以 argv 元素指回自己所在的 argv 陣列算 `ReferenceCycle`。
- 同一次解析裡同一個檔只讀一次（快取），而且 inst 自己以檔名被 `$ref` 時讀的是快照，不重讀磁碟。
- 逾時的結束碼照子程式實際狀態（一般是 143／137）；子程式接住 TERM 自己退 0 就回 0，但 `timed_out` 為真。
- exit 檔在跑完才開；前置只檢查父目錄存在（不先開檔），所以沒跑成時完全不碰 exit。
- 找不到程式＝127、其餘 exec 失敗（沒權限、格式錯）＝126。
- `argv`、`envs`、路徑含 NUL 字元＝`FieldTypeMismatch`。
- CLI 只准目前 UID；inst 寫別的帳號會得到 `UserNotGranted`。

## 檔案

| 檔 | 內容 |
|---|---|
| `errors.py` | `InstError` 與代號表 |
| `target.py` | 找 inst、node 資料夾正規化 |
| `identity.py` | 快照、原始 user、UID、授權接口、來源比對 |
| `directives.py` | 指示詞機制（搬自 proto5/lib/aos_directives.py） |
| `plan.py` | 展開、選項、驗欄位 → `Plan` |
| `spawn.py` | 照 `Plan` 開程序（可整個不用） |
| `__main__.py` | 除錯 CLI |
