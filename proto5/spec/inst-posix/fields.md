← [inst-posix](README.md)｜[spec 總導航](../README.md)

# 2. 整體形狀

- 一份 inst.json 是**嚴格一個 JSON 物件**（頂層不能是陣列、字串、null）。
- 七個欄位，**只有 `argv` 必填**，其餘沒寫就用預設。
- 四個路徑欄（`stdin`／`stdout`／`stderr`／`exit`）寫**空字串 `""` 等於沒寫**，走預設；只有帶 `append`／`mkdir`
  選項時空字串才是錯（3.3）。
- **不認得的頂層鍵一律忽略**，不會拒絕、也不會參與執行。`_metainfo` 走自己的規則（見上，
  裡面 `_type`／`_version` 以外的 key 也是忽略）。
- 任何一個「值」的位置都可以改寫成**指示詞**（第 4 節），解出來的東西就當成本來寫在那裡。

```json
{
  "_metainfo": {"_type": "posix", "_version": 1},
  "argv":   ["sh", "-c", "cat; echo $GREET"],
  "stdin":  "in.txt",
  "stdout": "out.txt",
  "stderr": {"$opt": "merge"},
  "exit":   "code.txt",
  "cwd":    "sub",
  "envs":   {"GREET": "hi", "PATH": {"$fmt": {"$val": "${p}:/opt/bin", "p": {"$env": "PATH"}}}}
}
```

# 3. 七個欄位

| 欄位 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `argv` | 非空字串陣列 | **必填** | 跑什麼。`argv[0]` 是程式，其餘是參數。`argv[0]` 用**疊加後的 `envs` 裡的 PATH** 找；`argv[0]` 不能是空字串 |
| `stdin` | 路徑或 `$opt` 選項物件 | `/dev/null` | 拿這個**檔案**當標準輸入（是檔案，不是字串內容）；也可以用 `inherit` 選項繼承執行者的標準輸入（見 3.3） |
| `stdout` | 路徑或 `$opt` 選項物件 | `/dev/null` | 標準輸出寫到這個檔（預設建立並清空，即 `>` 不是 `>>`）；可以用 `append`／`mkdir`／`inherit` 選項（見 3.3） |
| `stderr` | 路徑或 `$opt` 選項物件 | `/dev/null` | 寫到檔；可以用 `merge`（跟 stdout 同一條，shell 的 `2>&1`）／`append`／`mkdir`／`inherit` 選項（見 3.3） |
| `exit` | 路徑或 `$opt` 選項物件 | 不寫 | 跑完把結束碼（十進位＋換行）寫進去；寫完 fsync 檔案與父目錄。預設**父目錄要先存在**，不會幫忙建，除非用 `mkdir` 選項；也可以用 `append` 選項一行一行接在檔尾（見 3.3） |
| `cwd` | 路徑或 `$opt` 選項物件 | base（見 3.1） | 工作目錄；跑之前必須已經是資料夾，除非用 `mkdir` 選項先建（見 3.3） |
| `envs` | 物件 | `{}` | 環境變數，兩種寫法見 3.2 |

## 3.1 路徑怎麼算：中心是解出來的 `cwd`

- **base** ＝ 這份 inst 的「家」：給資料夾就是那個資料夾，給 `.json` 檔就是它所在的資料夾。
- `cwd` **最先解**，它的相對路徑以 base 為中心；沒寫就是 base。如果 `cwd` 用了 `mkdir`
  選項，是先解出路徑、再建目錄，之後其他相對路徑一樣以它為中心（不管資料夾原本存不存在）。
- 之後 `stdin`／`stdout`／`stderr`／`exit`、以及 `$ref` 指的檔，相對路徑**一律以解出來的 `cwd`
  為中心**。
- 絕對路徑照字面用。

所以解的順序固定是：頂層整份 → `cwd` → `argv` → `envs` → 四個路徑欄。

## 3.2 `envs` 的兩種寫法

```json
"envs": {"GREET": "hi"}                                疊在執行者的環境上，只加不減
"envs": {"$opt": "clear", "$val": {"LANG": "C"}}       從空環境開始，只放 $val 裡的
"envs": {"$opt": "clear"}                              $val 可省＝完全空的環境
```

- key 是純字串、**不解指示詞**；不能是空字串、不能含 `=`（這兩種才是 `EnvKeyInvalid`），
  也不能 `$` 開頭——但 `$` 開頭時程式實際走的是另一條路，看 4.1。
- 值可以是字串或指示詞，解完必須是字串。
- 清空之後 PATH 也沒了，`argv[0]` 退回系統預設路徑（Python 的 `os.defpath`，一般是
  `/bin:/usr/bin`），所以 `sh` 之類的還是找得到；想讓它找不到就自己塞一個 `PATH`。
- 整包 `envs` 或 `$val` 都可以是 `$ref` 從別的檔拿來的。
- 執行者（aos-exec）**不注入任何 `AOS_*` 變數**。

## 3.4 沒有 shell

參數不會被切分、展開，也不會被當成重導向。要 shell 行為就自己寫 `["sh", "-c", "…"]`。
