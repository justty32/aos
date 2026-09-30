← [基底](README.md)

# proto6 inst 第 1 版

〔使用者方向 2026-09-29〕以 [proto5 inst-posix 第 1 版](../../../proto5/spec/inst-posix/README.md) 加頂層 `user` 為 proto6 第 1 版，不管 proto5 相容。inst 只描述一次 POSIX 執行；排程、資源框、tick 任務與 git 提交不在其中，100＝做完等產品退出碼約定也另定。〔使用者方向 2026-09-30，第十九批〕aos-exec 是跑一份 inst 的程式；`aos-tick` 的核心本質上是加了一些功能的 aos-exec，任務表的每項是 inst 的超集（[B-626](../settled/tick.md)、[B-620](../settled/tick.md)）。

## 形狀與版本

```json
{
  "_metainfo": {"_type": "posix", "_version": 1},
  "user": "aos-a0042",
  "argv": ["aos-tick"],
  "cwd": "."
}
```

〔使用者方向 2026-09-29〕解完須為 JSON 物件，只有 `argv` 必填。未知頂層鍵忽略，`_` 開頭的鍵保留給格式資訊；**執行者不認得 `user` 語意，就不能執行 proto6 inst。**

`_metainfo` 預設 `{"_type":"posix","_version":1}`；有寫須為含這兩鍵的物件，只認字串 `"posix"` 及整數 `1`（布林不算），其他鍵忽略。種類／版本不合就拒絕；本欄不吃指示詞、不傳給子程式。

| 欄位 | 解完的值 | 省略時與用途 |
|---|---|---|
| `user` | Linux 帳號名稱字串或非負整數 UID；布林不算 | 省略／空字串＝繼承上層（有效上層，[B-628](../settled/tick.md)），頂層繼承通用 user；任務表的項目省略時用該 node 的執行帳號；禁指示詞 |
| `argv` | 非空字串陣列，首項不可空字串 | 必填；首項是程式，其餘是原樣參數 |
| `stdin` | 路徑字串，或下表選項 | `/dev/null`；指定的是檔案，不是輸入內容 |
| `stdout` | 路徑字串，或下表選項 | `/dev/null`；一般檔案預設建立並清空 |
| `stderr` | 路徑字串，或下表選項 | `/dev/null`；一般檔案預設建立並清空 |
| `exit` | 路徑字串，或下表選項 | 不寫；跑完寫十進位結束碼加換行 |
| `cwd` | 路徑字串，或下表選項 | inst 的 base；執行前須為資料夾 |
| `envs` | 鍵值都是字串的物件，或 `clear` 選項 | `{}`；疊到 runner 的環境上，只加不減 |

## inst 目標：檔案或資料夾

〔使用者方向 2026-09-29；第十八批從 [P-010](../protocol/README.md) 搬上〕沿 proto5 `aos-exec xxx` 的慣例，凡是「給一個目標去跑 inst」（daemon 登記、runner、人手直接跑）都照這張表找 inst：

| 目標 `xxx` 是 | 用哪份 inst | base（相對路徑起點、`cwd` 沒寫時的預設） |
|---|---|---|
| 檔案 | 就是它，當 inst JSON 讀 | 檔案所在的資料夾 |
| 資料夾 | 先找 `xxx/.aos/inst.json`，沒有再找 `xxx/inst.json` | `xxx` 自己（不是 `.aos/`） |

〔使用者方向 2026-09-29〕首版**不提供**改尋找路徑的選項（環境變數或旗標都沒有），只照上表。先看是不是資料夾，再當檔案；資料夾裡兩個位置都沒有＝用法錯（2）。node 是資料夾；`once` 工作通常是單檔。登記的 id 就是這個目標路徑。〔使用者方向 2026-09-30，第十九批第 7 條〕辨識一個 tick 時，給的是 node 資料夾裡的 `.aos/inst.json` 或 `inst.json` 路徑，一律正規化成那個資料夾（`.aos/inst.json` 的是 `.aos` 的上一層）；once 的單檔目標不做這個正規化。投件時「目標是不是 node」也照這張表的資料夾那列判斷（[B-624](../settled/tick.md)）。

## 先決定身分，切完才解析

〔使用者方向 2026-09-29〕daemon 只取原始 `user` 做額度檢查，不展開其他欄位。〔第十九批改寫〕省略時繼承有效上層的身分：預設上層看資料夾包含、登記可以覆蓋（[B-628](../settled/tick.md)）；身分本身不由資料夾位置決定。名稱與 UID 比對同一 Linux 身分，補充群組照系統帳號設定（等同 `initgroups`），inst 不另帶群組。

額度由上層註冊時授予，詳見 [B-301／B-303](identity-resources.md)。授權不過就根本不跑，回 125、不寫 `exit`，並留下待處理事項。先安置已配置資源、切身分，再由 runner 解指示詞、驗欄位、建 `cwd`／父目錄與開串流、`exit` 檔；daemon／helper 不代開任意路徑。無 helper 時 runner 直接以通用 user 做相同工作。

**`$env` 讀的是切身分後 runner 自己的環境，不是 inst 的 `envs`；`$ref` 讀檔也只能用該身分的權限。** runner 的描述須符合本次已授權身分，不可在兩階段間換身分；固定輸入的方法留實作。資源框由 kernel 樹的註冊及已裝 module 決定。

## 路徑、環境與指示詞

〔使用者方向 2026-09-29〕**完整沿用 [proto5 directives](../../../proto5/spec/directives/README.md)** 的取值、優先順序、巢狀、`$ref`／`$at`、實體位置與錯誤；這裡只列 inst 宿主規則。

- 七個執行欄位、`argv` 元素、`envs` 值與選項的 `$val` 可放取值指示詞，展開後驗型別；key、`user`、`_metainfo` 不展開。整份頂層也可用指示詞，但身分接法見篇末。
- base＝輸入資料夾，或輸入 `.json` 的所在資料夾。切身分後依序解整份頂層 → `cwd` → `argv` → `envs` → 四個路徑欄；`_metainfo` 取自頂層展開結果。整份及 `cwd` 以 base 解相對路徑／`$ref`，其餘以解出的 `cwd` 為中心，絕對路徑照字面用。`cwd` 的 `mkdir` 先建目錄再解其他欄位；四個路徑欄空字串等於省略，但 append／mkdir 不接受空路徑。
- 各執行欄位從獨立循環鏈開始，進入引用得來的 `argv`／`envs` 容器時把鏈帶下去；跨欄位引用同一檔不算循環。
- `envs` 的 key 不可空或含 `=`，值解完須為字串；`$` 開頭的 key 會讓整包變成指示詞，不能當環境變數。無 `clear` 就複製 runner 環境再疊上，有則從空環境開始；runner 不注入 `AOS_*`，唯一例外〔使用者方向 2026-09-30，第十九批第 9 條〕是 daemon 開 tick 時給的通道變數（[B-612](../settled/daemon/channel.md)），任務照一般繼承拿到，`clear` 會把它們一起清掉（helper 以指定帳號開的例外：runner 最後才補、不受 `clear` 影響，[B-609](../settled/daemon/helper-actions.md)）；另外 helper 以指定帳號開任務時，runner 把繼承來的鎖 fd 號碼放進 `AOS_TICK_LOCK_FD`（[B-609](../settled/daemon/helper-actions.md)、[B-602](../settled/tick.md)），它不受 `clear` 影響。`argv[0]` 用最後的 PATH 找，未設 PATH 時用系統預設路徑（proto5 的 `os.defpath`，通常 `/bin:/usr/bin`）。
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

同位置只有 append＋mkdir 可合用；inherit／merge 與其他選項互斥。衝突、缺必帶值、空路徑或多帶值報 `OptionConflict`。`$opt` 型別錯報 `DirectiveValueTypeMismatch`；重複／未知名字或放在頂層、argv／其元素、envs 值、$val 等不吃選項的位置，報 `UnknownOption`。`user` 的選項物件算身分欄位錯誤，不展開。

## 執行與錯誤

〔使用者方向 2026-09-29〕驗完才跑。授權、解析驗證與執行前讀寫／建目錄失敗，自己的 stderr 印「代號: 白話」，回 125，**不寫 `exit`**。無 mkdir 時 `exit` 父目錄須已存在。前置檢查可能已建目錄或清空輸出檔；撤回範圍：有 git 時只有 aos 範圍照存檔點的組還原（[B-630](../settled/tick.md)），其餘不還原；沒有 git 時沒有還原。

開始執行後，找不到程式回 127，無執行權回 126；這兩種算跑完一次，有 `exit` 就照寫。正常退出用子程式結束碼，被訊號 N 結束則用 128+N。`exit` 寫十進位加換行，預設覆蓋、`append` 則追加，寫完 fsync 檔案與父目錄。runner 的用法錯誤回 2。子程式也可能退出 125，是否啟動須看結果證據。

子程式另開 session／process group（`setsid`）；逾時先對整組 TERM，2 秒後仍在就 KILL，對應碼為 143／137。這 2 秒只指 inst 自己的逾時；daemon 收尾整個框用 `shutdown_grace_ms`（[B-604](../settled/daemon/lifecycle.md)），兩者不混用。後代脫離 process group 也須清空、結果只發布一次，見 [工作執行](execution.md)。runner 明示的 stderr 覆寫蓋過 inst（含 merge／inherit／append）；CLI 另定。

| 錯誤代號 | 意思 |
|---|---|
| `ReadFailed`／`JsonSyntax` | inst 讀不到／不是合法 JSON |
| `NotAnObject` | 頂層解完不是物件 |
| `MetainfoInvalid` | `_metainfo` 不是物件或缺必要鍵 |
| `UnsupportedInstType`／`UnsupportedInstVersion` | 種類／版本不認得 |
| `EmptyArgv` | 缺 argv、空陣列或 argv 首項為空字串 |
| `FieldTypeMismatch`／`EnvKeyInvalid` | 執行欄位型別錯／環境變數名為空或含 `=` |

指示詞錯誤代號沿用 [directives/errors](../../../proto5/spec/directives/errors.md)。〔建議預設，未拍板〕身分錯誤用 `UserInvalid`（型別錯、含指示詞、帳號無法解析）、`UserNotGranted`（不在額度）與 `UserMismatch`（授權後描述改了身分）；〔使用者方向 2026-09-29，第十七批〕另有 `SourceChanged`：授權後原來源的內容與快照不同（不管改的是不是 user），跟 UserMismatch 分開；代號可再定；125、不啟動、不寫 `exit` 已定。

## 頂層整份指示詞

〔使用者方向 2026-09-29〕整份 `$ref` 可能藏 `user`，仍然允許，不另加禁止。讀引用檔前先取原始頂層字面 `user`（省略則繼承）、授權及切身分，再展開整份。結果如帶 `user`，須為合法字面值並解析到同一已授權 UID，否則 125、不寫 `exit`，不能忽略或再次切身分；沒寫則沿用本次身分。普通頂層物件也遵守同一身分邊界。
