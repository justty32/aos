# proto8/lib — 函式庫

← [proto8](../README.md)

只用 Python 標準庫。

## 指示詞 lib（`aos_directives.py`）

讓 JSON 裡某一格的值「從別處來」。一個檔、一個入口：

```python
from aos_directives import resolve, DirectiveError
out = resolve(doc, base_dir)   # doc＝parse 好的 JSON；base_dir＝相對檔名的基準路徑
                               # 選填 ident＝doc 從哪來（檔案的 realpath），錯誤訊息用它指出是哪份檔
```

整份 JSON 一層層全部解掉，回一份新的（原本那份不動）。`base_dir` 整趟都用它，進了別的檔也不換。

兩種指示詞（兩個都寫了只看 `$ref`，其餘 key 忽略）：

```jsonc
{"$ref": "other.json#/a/0"}          // 讀一份 JSON 的某一格；"" 是目前這份；位置也可寫成 "$at": "/a/0"
{"$ref": "#../x"}                    // ./ ../ 從這個指示詞所在的位置算
{"$env": "HOME"}                     // 讀環境變數
```

取回來的東西裡如果還有指示詞，照它所在的那份檔、那個位置接著解。繞回自己（指到正在解的位置或它的上層）＝`ReferenceCycle`。
錯了一律丟 `DirectiveError`，代號七種，寫在檔頭。

命令列 TARGET 的 `檔#/位置` 也在這裡（三支程式共用）：`split_target(target)` → (檔, 位置)、`target_id(realpath, 位置)` → id、`locate(root, 位置, ident)` → 那一格的原值；`resolve(..., at=位置)` 只解那一格。

三支程式一個手感：`aos_inst.py x.json`、`aos_loop.py x.json`、`aos_daemon.py x.json`，命令列都只有一個引數，Python 的 `run(path)` 也一樣；相對路徑一律從呼叫者的 cwd 算。

**`檔#/位置`**（10-13 D1）：TARGET（含 `run(path)`、daemon 指令的 `id`）後面可以接 `#/位置`，只用那份檔裡那一格；`#` 後面是 JSON pointer，寫法同 `$ref`。
- 遇到第一個 `#` 就切，檔名含 `#` 的不支援。位置只認 `/` 開頭（不是＝`ReferencePointerInvalid`）；空的或只有 `/`＝整份。
- id＝realpath ＋ `#` ＋ 位置（正規化過：`.`／`..` 消掉、`~0`／`~1` 重新轉義）；沒位置或 `#/`＝純 realpath。同一份檔兩個位置＝兩個 id。
- 指到的值不是物件＝`FieldType`；走不到＝`ReferencePointerInvalid`。錯誤訊息帶路徑。
- 那一格是整份檔的視窗、不是切下來：裡面 `$ref` 的位置照整份檔算（`#/` 是檔的根、`../` 可以摸到旁邊）。
- inst 的 TARGET 是資料夾：先照現有規矩找 inst.json 再套位置。退出碼／`run()` 只說自己有沒有出錯（只有 0／非 0 是確定的，其他數字只供參考）；子程式的碼只寫進 inst.json 的 `exit` 檔。

## inst（`aos_inst.py`）

讀一份 JSON → 用指示詞 lib 解好 → 挑認得的 key（其他忽略）→ 跑一次。

```
python3 proto8/lib/aos_inst.py TARGET
```

- TARGET：`.json` 檔，或資料夾（找 `.aos/inst.json`，沒有再找 `inst.json`），後面可接 `#/位置`（見上）。`find()` 回 id（realpath，有位置就接 `#/位置`）。
- 基準一律是呼叫者的 cwd：指示詞的檔名、`cwd` 這個 key 從這裡算。`cwd` 沒寫＝呼叫者的 cwd；`stdin`／`stdout`／`stderr`／`exit` 的相對路徑從解出來的 `cwd` 算。
- key：`argv`（必填）、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit`、`timeout_ms`（沒寫＝不限）、`grace_ms`（沒寫＝2000），加上布林的 `cwd_mkdir`、`envs_clear`、`*_inherit`、`*_append`、`*_mkdir`、`stderr_merge`。完整說明在檔頭。
- `run(target)`：跟命令列一模一樣。正常做完回 None（命令列 0），子程式回幾號、被限時收掉都算正常做完；aos_inst 自己出錯丟 `InstError`（命令列印「代號: 白話」，參考 127＝找不到程式、126＝不能執行、125＝其他，`exit_code(err)`）。
- 子程式的碼只寫進 `exit` 檔：自己結束＝它的碼，被訊號停掉＝128＋N；沒起來不寫；寫不進去不管。`read_exit(path)` 讀最後一行（給 loop、tasks 用）。
- 子程式留在 aos_inst 的行程群組。在主執行緒（命令列就是）收到 SIGINT／SIGTERM／SIGHUP 不死、轉給子程式，過 `grace_ms` 還沒結束就 SIGKILL，照樣寫 exit。要從外面停它、連孫程式一起清，是啟動它的人的事（aos_loop 把它起在新 session、整群收）。
- API：`find(target)`、`load(target)`、`parse(doc, base_dir, ident, at=())`、`run(target)`、`read_exit(path)`、`exit_code(err)`。

## loop（`aos_loop.py`）

包一個 inst：跑幾次、隔多久，一邊讀一個 ctl.json。

```
python3 proto8/lib/aos_loop.py LOOP.json
```

```jsonc
{
  "inst": {"$ref": "job/inst.json"},   // 一份 inst 格式（內嵌或 $ref）
  "times": null,                       // 總數；null＝不限；沒寫＝1
  "interval_ms": 5000,                 // 沒寫＝0
  "interval_mode": "after",            // after＝跑完再隔；fixed＝固定週期，跑超過就跳拍（state 的 skipped）
  "grace_ms": 5000,                    // 收掉這次時整群 SIGTERM 之後等多久整群 SIGKILL
  "ctl": "job-ctl.json", "ctl_poll_ms": 1000,
  "state": "job-state.json",
  "error_wait_ms": 1000                // aos_inst 自己出錯之後至少隔多久
}
```

- `LOOP.json` 可接 `#/位置`（見上）：loop 本體是那一格，id（state 的 `id`）＝realpath#/位置。
- loop.json（含 `inst` 那格與裡面的指示詞）**只在起來時讀一次、解一次**；`inst` 不對＝起不來（沿用 aos_inst 的碼，參考 125）。跑的途中要改只能走 ctl.json。
- 每一次：起子程序 `aos_inst.py`（自成一個 session）→ 等它結束 → 整群補 SIGKILL 清孫程式 → 收屍。解好的 inst 在起來時寫成暫存資料夾裡的一份 inst.json，每次都把它的路徑交給 aos_inst，結束刪掉。
- 結果：aos_inst 回 0 → `last_code`＝exit 檔最後一行（沒寫 exit＝null）；非 0 → `last_error`＝它 stderr 的最後一行。
- **ctl.json**（宣告式，NORMS N-06～）：`paused`、`stop`（`true` 或 `{"val": true, "now": true}`；now＝當場收掉正在跑的）、`times`、`interval_ms`、`interval_mode`。沒寫的欄位＝loop.json 的初始值（只在 `want()` 一處）。stop 是終點。壞檔、型別錯、不見了＝維持上一次、印一次。(inode, mtime, 大小) 變了才重讀。
- 次數跑完（runs ≥ times）就結束、退出，有 ctl 也一樣；想再跑就重新起。
- **state.json**（選填）：共同骨架（見[下面](#ctl-與-state-的慣例)）加上 `skipped`、`last_code`；`last_error`＝aos_inst 自己出錯時它 stderr 的最後一行。暫存再改名。
- 退出碼只說 loop 自己：0＝正常結束（子程式回非 0 不算）；最後一次是 aos_inst 自己出錯＝沿用它的碼；被訊號停掉＝128＋N；loop.json 不對＝125。`run(path)` 正常回 None，否則丟 `LoopError`（`exit` 屬性＝退出碼）。
- 給 daemon 共用的：`load_config()`、ctl 那組（`parse_ctl()`、`want()`、`CtlFile`）、state 那組（`STATES`、`state_doc()`、`read_state()`、`StateFile`：欄位、狀態值、讀、寫只在這裡）、`write_json()`、`kill()`／`reap()`。

## daemon（`aos_daemon.py`）

管很多個 loop 的表；自己也是一個 loop（每一圈＝掃一次控制資料夾）。

```
python3 proto8/lib/aos_daemon.py DAEMON.json
```

- daemon.json 只在起來時讀一次：`control_dir`（必填）、`load`、`save`、`work_dir`（沒寫＝control_dir 旁的 `loops/`）、`grace_ms`（10000）；比照 loop：`times`（null）、`interval_ms`（200）、`interval_mode`（after；fixed＝固定週期、掃超過一拍就跳拍）、`ctl`（不能在 control_dir 裡）、`ctl_poll_ms`、`state`。
- 自己的 state.json：共同骨架加上 `skipped`、`loops`（表上幾個，只寫個數；要細節用控制指令 `list`／`get`／`state` 查）；`last_error`＝最近一圈印到 stderr 的最後一行錯（ScanFailed、ReplyFailed），那圈沒錯＝null。
- 自己的 ctl.json：paused＝不掃（指令堆著、loop 照跑）；stop＝收工（先 save；now＝底下 loop 當場收掉，沒 now＝替它們寫 stop、等它們跑完）；times 跑完同 stop（不帶 now）。
- 表上每個 loop 是一支子程序 `aos_loop.py`（自成 session）。daemon 只靠兩個檔控制它：寫它的 ctl.json、讀它的 state.json。loop.json 沒寫 ctl／state 的，在 `work_dir/<編號>/` 生包裝檔（每個 key `$ref` 回原檔、補上 ctl／state），移除或收工時刪掉。
- 控制資料夾（NORMS N-10）：放 `名字.json`，處理完變 `名字.json.done`，內容 `{"request", "ok", "result"|"error": {"code", "msg"}}`；`.` 開頭不讀；`.done` 由丟的人清。指令 `{"op", "id", ...}`，id＝loop.json 的絕對路徑，可接 `#/位置`（見上；save 存的、load 帶的 id 也一樣）（`add` 也收 inst.json：頂層沒有 `inst`、有 `argv` 的，包成只跑一次的 loop `{"inst": {"$ref": 它}, "times": 1}`，id 是那份 inst.json 的 realpath）：`add`、`set`（`how`：times／interval_ms／interval_mode）、`pause`／`remove`（`wait` 預設 true）、`resume`、`add_times`（`delta`）、`state`、`get`、`list`、`save`／`load`（`path`）。
- 次數跑完的 loop 自己退出，留在表上（state `done`），要再跑就 remove 再 add。set／pause／resume／add_times 等 loop 讀到了才回（state.json 的 ctl_mtime 趕上），pause 還要等真的停了，remove 等行程結束；等的期間指令檔留在原地。
- save 存 `[{"loop": realpath, "ctl": 當下 ctl.json}]`；runs 不存。load 全有全無（不在＝NotFound、重複或 state.json 的 pid 還活著＝Exists、格式不對＝FieldType），會把 ctl 內容寫回各 loop 的 ctl.json 再起。
- 收工：SIGTERM＝先 save、對每個 loop 的 session 送 SIGTERM、等 grace_ms、整群 SIGKILL；SIGINT 一樣但不存。巢狀 grace：inst（2000）＜ loop（5000）＜ daemon（10000）。
- 出意外不結束、stderr 印一次：ScanFailed、ReplyFailed、Internal。退出碼 0＝正常、1＝起不來或 save 失敗。

## ctl 與 state 的慣例

NORMS N-11 的骨架是「設定檔讀一次 → ctl 蓋過 → state 回報」；下面是 lib 照著做的慣例，不是規範。

| 層 | 設定檔 | ctl | state |
|---|---|---|---|
| inst | inst.json | 沒有（跑一次，沒東西可改；要停用訊號） | **就是 exit 檔**：一個數（十進位＋換行），不是 json、不另開 state.json |
| loop | loop.json | ctl.json | state.json |
| daemon | daemon.json | ctl.json | state.json |

key 分四組，每組落在哪幾個檔是固定的：

| 組 | key | 設定檔 | ctl | state |
|---|---|---|---|---|
| 節奏 | `times`、`interval_ms`、`interval_mode` | 初始值 | 期望值（可蓋） | 生效中的值 |
| 旗子 | `paused`、`stop` | — | `{val, now}` | 併進 `state` 那格 |
| 位置／身體／收尾 | `ctl`、`ctl_poll_ms`、`state`、`inst`、`grace_ms`、`error_wait_ms`、`control_dir`、`load`、`save`、`work_dir` | 有 | 不能蓋 | 不回報 |
| 回報 | 見下面 state 骨架 | — | — | 有 |

**ctl.json**（loop、daemon 同一份）：`paused`、`stop`、`times`、`interval_ms`、`interval_mode`，規矩照 N-06～N-08。

**state.json 共同骨架**（loop、daemon 都有）：

```jsonc
{
  "id": "/abs/x.json",         // 設定檔的 realpath
  "state": "running",          // 七個狀態值之一，見下表
  "pid": 12345,                // 自己的 pid
  "runs": 2,                   // 身體跑了幾次（loop：inst；daemon：掃幾圈）
  "times": 5, "interval_ms": 1000, "interval_mode": "after",   // 節奏組＝生效中的值
  "ctl_mtime": 1760280000.123, // 上次套用的 ctl.json 的 mtime；沒有＝null
  "last_error": null           // 最後一次自己出錯的那行；沒有＝null
}
```

各層擴充：loop 加 `skipped`（fixed 跳拍數）、`last_code`（exit 檔最後一行）；daemon 加 `skipped`、`loops`（表上幾個，只寫個數；要細節用控制指令查）。

**狀態值**：一套七個（`aos_loop.STATES`），意思固定，各層用得到哪幾個不限。

| 值 | 意思 | 誰會寫 |
|---|---|---|
| `starting` | 行程起了、第一份 state 還沒寫出來 | daemon 替底下的 loop 答 |
| `waiting` | 等下一次（間隔中） | loop、daemon |
| `running` | 身體正在跑 | loop（daemon 掃一下就完，看不到） |
| `paused` | 期望 paused、身體沒在跑 | loop、daemon |
| `done` | 次數跑完（runs ≥ times），最後一份 | loop（daemon 次數到＝收工，寫 stopped） |
| `stopping` | 讀到 stop 或收到訊號，收尾中 | loop、daemon |
| `stopped` | 結束，最後一份 | loop、daemon；daemon 看到底下 loop 行程沒了也這樣答 |

## 測試（`tests/`）

```
python3 -m unittest discover -s proto8/lib/tests
```

只用標準庫，46 個、約 12 秒。一個檔 `test_lib.py` 分四組（指示詞、inst、loop、daemon），loop 與 daemon 都起真的行程、走檔案；每個測試用 mktemp 的暫存資料夾，跑完刪掉。改 lib 就跑一次，新行為補一個測試。

## 行程與執行緒的規矩

inst、loop、daemon 都是單執行緒（loop 多一條轉 stderr 的小執行緒），子程式一律用 `subprocess.Popen` 起，不用 `os.fork()`、不用 `preexec_fn`；cwd、環境變數經 `Popen(cwd=, env=)` 只給子程式，不 `chdir`、不改 `os.environ`。誰起子程序誰負責收：loop 把 aos_inst 起在新 session、daemon 把 loop 起在新 session，收的時候整群送訊號、收屍前整群補 SIGKILL（群組號碼不會先被拿走）。
