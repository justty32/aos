← [基底](README.md)

# proto6 inst 第 1 版

〔使用者方向 2026-09-29〕以 [proto5 inst-posix 第 1 版](../../../proto5/spec/inst-posix/README.md) 為 proto6 第 1 版，不管 proto5 相容。inst 只描述一次 POSIX 執行；排程、資源框、tick 任務與 git 提交不在其中，100＝做完等產品退出碼約定也另定。〔使用者方向 2026-09-30，第十九批〕aos-exec 是跑一份 inst 的程式；`aos-tick` 的核心本質上是加了一些功能的 aos-exec，任務表的每項是 inst 的超集（[B-626](../settled/tick.md)、[B-620](../settled/tick.md)）。〔使用者方向 2026-10-01〕inst 頂層**沒有 `user`**（原本的 `user` 欄位與「先決定身分，切完才解析」一節撤回、直接刪掉，見[暫緩區的撤回清單](../settled/deferred/README.md)）；寫了就是不認得的頂層鍵，照下面的規則忽略，照目前身分跑。結束碼照 [C-08](../settled/conventions.md)，狀態資料夾名照 [C-09](../settled/conventions.md)。

## 形狀與版本

```json
{
  "_metainfo": {"_type": "posix", "_version": 1},
  "argv": ["aos-tick"],
  "cwd": "."
}
```

〔使用者方向 2026-09-29〕解完須為 JSON 物件，只有 `argv` 必填。未知頂層鍵忽略，`_` 開頭的鍵保留給格式資訊。寫了 `user` 也一樣當不認得的鍵忽略（〔使用者方向 2026-10-01〕撤回，見篇首）。

`_metainfo` 預設 `{"_type":"posix","_version":1}`；有寫須為含這兩鍵的物件，只認字串 `"posix"` 及整數 `1`（布林不算），其他鍵忽略。種類／版本不合就拒絕；本欄不吃指示詞、不傳給子程式。

| 欄位 | 解完的值 | 省略時與用途 |
|---|---|---|
| `argv` | 非空字串陣列，首項不可空字串 | 必填；首項是程式，其餘是原樣參數 |
| `stdin` | 路徑字串，或下表選項 | `/dev/null`；指定的是檔案，不是輸入內容 |
| `stdout` | 路徑字串，或下表選項 | `/dev/null`；一般檔案預設建立並清空 |
| `stderr` | 路徑字串，或下表選項 | `/dev/null`；一般檔案預設建立並清空 |
| `exit` | 路徑字串，或下表選項 | 不寫；跑完寫十進位結束碼加換行 |
| `cwd` | 路徑字串，或下表選項 | inst 的 base；執行前須為資料夾 |
| `envs` | 鍵值都是字串的物件，或 `clear` 選項 | `{}`；疊到 runner 的環境上，只加不減 |

## inst 目標：檔案或資料夾

〔使用者方向 2026-09-29；第十八批從 [P-010](../protocol/README.md) 搬上〕沿 proto5 `aos-exec xxx` 的慣例，凡是「給一個目標去跑 inst」（`aos-exec` 命令列、daemon 交給 `aos-exec` 的 inst、人手直接跑）都照這張表找 inst：

| 目標 `xxx` 是 | 用哪份 inst | base（相對路徑起點、`cwd` 沒寫時的預設） |
|---|---|---|
| 檔案 | 就是它，當 inst JSON 讀 | 檔案所在的資料夾 |
| 資料夾 | 先找 `xxx/.aos/inst.json`，沒有再找 `xxx/inst.json`（`.aos` 照 `AOS_DIRNAME`，下面） | `xxx` 自己（不是 `.aos/`） |

先看是不是資料夾，再當檔案；資料夾裡兩個位置都沒有＝用法錯，回 1（[C-08](../settled/conventions.md)）。

- **`AOS_DIRNAME`**〔使用者方向 2026-10-01〕：上表的 `.aos` 是環境變數 `AOS_DIRNAME` 沒設時的名字（[C-09](../settled/conventions.md)）。設成別的名字就找 `xxx/<名字>/inst.json`；設成空字串就只找 `xxx/inst.json`。值不合法（含 `/`、或是 `.`、`..`）時，資料夾目標算用法錯、回 1；直接給檔不受影響。除此之外沒有改尋找路徑的選項或旗標。
- **daemon 核心沒有 id**〔使用者方向 2026-10-01〕：daemon 設定檔 `insts` 的鍵就是 inst 字面值，原樣交給 `aos-exec`，不另算 id、不正規化（[B-640](../settled/daemon/core.md)）。
- **aos-tick 不再拿 inst 認資料夾**〔使用者方向 2026-10-01〕：`aos-tick [<目標>]` 看的是任務表 `tasks.json`，跟 `inst.json` 分開，也不再把 `.aos/inst.json` 路徑正規化成資料夾（[B-620](../settled/tick.md)）。`aos-tick` 的目標只能是資料夾，給檔算用法錯、回 1（這點跟 `aos-exec` 不同；原「給檔就拿它當任務表」撤回）〔使用者 2026-10-01〕。任務表頂層可放 inst 欄位當每一項的預設，合併後的那一項照本篇規則展開（[B-620](../settled/tick.md)、[C-11](../settled/conventions.md)）。
- 投件時「目標是不是 node」照這張表的資料夾那列判斷（[B-624](../settled/tick/mq.md)）。`once` 工作通常是單檔。

## 路徑、環境與指示詞

〔使用者方向 2026-09-29〕**完整沿用 [proto5 directives](../../../proto5/spec/directives/README.md)** 的取值、優先順序、巢狀、`$ref`／`$at`、實體位置與錯誤；這裡只列 inst 宿主規則。

- 七個執行欄位、`argv` 元素、`envs` 值與選項的 `$val` 可放取值指示詞，展開後驗型別；key、`_metainfo` 不展開。整份頂層也可用指示詞（例如整份 `$ref`），照常展開。
- base＝輸入資料夾，或輸入 `.json` 的所在資料夾。依序解整份頂層 → `cwd` → `argv` → `envs` → 四個路徑欄；`_metainfo` 取自頂層展開結果。整份及 `cwd` 以 base 解相對路徑／`$ref`，其餘以解出的 `cwd` 為中心，絕對路徑照字面用。`cwd` 的 `mkdir` 先建目錄再解其他欄位；四個路徑欄空字串等於省略，但 append／mkdir 不接受空路徑。
- 各執行欄位從獨立循環鏈開始，進入引用得來的 `argv`／`envs` 容器時把鏈帶下去；跨欄位引用同一檔不算循環。
- `envs` 的 key 不可空或含 `=`，值解完須為字串；`$` 開頭的 key 會讓整包變成指示詞，不能當環境變數。無 `clear` 就複製 runner 環境再疊上，有則從空環境開始；runner 不注入 `AOS_*`，唯一例外〔使用者方向 2026-09-30，第十九批第 9 條〕是 daemon 開 tick 時給的通道變數（[B-612](../settled/deferred/daemon/channel.md)），任務照一般繼承拿到，`clear` 會把它們一起清掉（helper 以指定帳號開的例外：runner 最後才補、不受 `clear` 影響，[B-609](../settled/deferred/daemon/helper-actions.md)）；另外 helper 以指定帳號開任務時，runner 把繼承來的鎖 fd 號碼放進 `AOS_TICK_LOCK_FD`（[B-609](../settled/deferred/daemon/helper-actions.md)、[B-602](../settled/tick.md)），它不受 `clear` 影響。`argv[0]` 用最後的 PATH 找，未設 PATH 時用系統預設路徑（proto5 的 `os.defpath`，通常 `/bin:/usr/bin`）。
- 不自動呼叫 shell，不拆參數、展開萬用字元或解重導向；需要就明寫 `["sh","-c","…"]`。

## 選項

〔使用者方向 2026-09-29〕形狀是 `{"$opt":"名字","$val":值}`；多選項把名字換成非空字串陣列。選項名只認下表小寫名字、不可重複；`$val` 可以是取值指示詞，但不能再套選項。只讀 `$opt`／`$val`，其他 key 忽略。

| 位置 | 選項 | `$val` 與效果 |
|---|---|---|
| `stdin` | `inherit` | 不可帶值；沿用 runner 的標準輸入 |
| `stdout`／`stderr` | `inherit` | 不可帶值；沿用 runner 的對應串流 |
| `stdout`／`stderr`／`exit` | `append` | 必帶非空路徑；接在檔尾，不存在就建立 |
| `stdout`／`stderr`／`exit` | `mkdir` | 必帶非空路徑；開檔前先建父目錄 |
| `stderr` | `merge` | 不可帶值；與 stdout 走同一條，含其 append／inherit 設定 |
| `cwd` | `mkdir` | 必帶非空路徑；先建工作目錄 |
| `envs` | `clear` | 可帶物件，省略就是 `{}`；從空環境開始 |

同位置只有 append＋mkdir 可合用；inherit／merge 與其他選項互斥。衝突、缺必帶值、空路徑或多帶值報 `OptionConflict`。`$opt` 型別錯報 `DirectiveValueTypeMismatch`；重複／未知名字或放在頂層、argv／其元素、envs 值、$val 等不吃選項的位置，報 `UnknownOption`。

## 執行與錯誤

〔使用者方向 2026-09-29〕驗完才跑。解析驗證與執行前讀寫／建目錄失敗，自己的 stderr 印「代號: 白話」，回 125，**不寫 `exit`**。無 mkdir 時 `exit` 父目錄須已存在。前置檢查可能已建目錄或清空輸出檔；撤回範圍：有 git 時只有 aos 範圍照存檔點的組還原（[B-630](../settled/deferred/git.md)），其餘不還原；沒有 git 時沒有還原。

開始執行後，找不到程式回 127，無執行權回 126；這兩種算跑完一次，有 `exit` 就照寫。正常退出用子程式結束碼，被訊號 N 結束則用 128+N。`exit` 寫十進位加換行，預設覆蓋、`append` 則追加，寫完 fsync 檔案與父目錄。`aos-exec`（與之後的 runner）用法錯回 1（[C-08](../settled/conventions.md)），`-h`／`--help` 回 0。子程式也可能退出 125，是否啟動須看結果證據。

子程式另開 session／process group（`setsid`）；逾時先對整組 TERM，2 秒後仍在就 KILL，對應碼為 143／137。這 2 秒只指 inst 自己的逾時；daemon 收尾整個框用 `shutdown_grace_ms`（[B-604](../settled/deferred/daemon/lifecycle.md)），兩者不混用。後代脫離 process group 也須清空、結果只發布一次，見 [工作執行](execution.md)。runner 明示的 stderr 覆寫蓋過 inst（含 merge／inherit／append）；CLI 另定。

| 錯誤代號 | 意思 |
|---|---|
| `ReadFailed`／`JsonSyntax` | inst 讀不到／不是合法 JSON |
| `NotAnObject` | 頂層解完不是物件 |
| `MetainfoInvalid` | `_metainfo` 不是物件或缺必要鍵 |
| `UnsupportedInstType`／`UnsupportedInstVersion` | 種類／版本不認得 |
| `EmptyArgv` | 缺 argv、空陣列或 argv 首項為空字串 |
| `FieldTypeMismatch`／`EnvKeyInvalid` | 執行欄位型別錯／環境變數名為空或含 `=` |

指示詞錯誤代號沿用 [directives/errors](../../../proto5/spec/directives/errors.md)。
