← [cpu](README.md)｜[spec 總導航](../README.md)

# 4. exec cpu 認的 method

## 4.1 `aos-exec`：params 就是 aos-exec 的命令列

request 的意思是「像命令列 `aos-exec TARGET --dir-target R --timeout-ms N --stderr S -- ARGS`
那樣跑一次」，params 的欄位一對一照 [aos-exec](../aos-exec/README.md) 的 `run_target_full()`：

```json
{"jsonrpc":"2.0","id":"agent-1790000000000000000-77","method":"aos-exec",
 "params":{"target":"/abs/agent-bob/think.json","timeout_ms":60000}}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `target` | 字串 | 必填 | aos-exec 的 `xxx`：普通檔、`.json`、資料夾三種都行，怎麼分、base 是誰、串流怎麼接**全照 aos-exec**。相對路徑以 **C** 為起點（cpu 的 cwd 就是它的家） |
| `dir_target` | 字串 | `.aos/inst.json` | 同 `--dir-target` |
| `timeout_ms` | 非負整數 | info 的預設 | 同 `--timeout-ms`；0＝不限；bool 不算 |
| `stderr` | `null`／`"-"`／字串 | `null` | 同 `--stderr`；`"-"`＝接 cpu 自己的 stderr（`cpu.log`）；路徑相對 C |
| `args` | 字串陣列 | **沒這個鍵**＝沒給 | 同 `--`；只有普通檔目標能給。`[]` 是「有給 `--` 但沒元素」，inst 目標一樣拒；`null` 不合法 |

**cpu 的環境就是工作的環境。** cpu 是被拉起來的一支行程，它帶著什麼——環境變數、PATH、跑它的身分與權限、
cwd（＝它的家）——工作 inst 沒寫 `clear` 就整包繼承（aos-exec 的規則）；普通檔目標更是全部繼承。
所以「llm cpu」不是另一種 cpu：是一顆普通 exec cpu，拉它的那份 inst（[kernel 替它寫的 `K/cpus/<c>/inst.json`](../kernel/README.md)）
把 `llm-http` 所在目錄放進 PATH、把 API key 放進 `envs`；工作 inst 的 argv 直接寫 `llm-http` 就找得到。
cpu 自己讀的是它自己的環境，不會替工作補任何東西。

cpu **不讀、不解 inst**：指示詞、base、`$ref` 都是 aos-exec 讀那份檔時照它自己的規則做。
指到還不存在的 `.json` 也收，跑起來是 kind=aos（`ReadFailed`），跟 aos-exec 一樣——**收下不等於會等它出現**，
每次跑都是一次 aos 失敗，怎麼算是收件者的事（[kernel §4](../kernel/echo.md)）。
aos-exec 會回「用法錯」（退出碼 2）的情況——`.json`／資料夾目標卻給 `args`、不存在的非 `.json` 路徑、
`dir_target` 指的檔不在——在這裡是 `-32602`／`data.code:"Usage"`，不算跑過。

一顆 cpu **一次只做一件**；`requests/` 按檔名排序取第一份（所以交件者想排序就靠檔名）。

result：

```json
{"code":0,"kind":"child","timed_out":false,"stopped":false,"ms":42}
```

| 鍵 | 意思 |
|---|---|
| `code`、`kind` | 就是 `run_target_full()` 回的 `code`、`kind`：`child`＝子程式真的跑了一次（`code` 是它的退出碼，找不到程式 127、沒執行權 126、逾時 143／137 都算 child）；`aos`＝aos-exec 自己失敗、那次根本沒跑（`code` 是 1，跟 API 一樣、不換算成 125） |
| `timed_out` | 真的撞到 `timeout_ms`（真實旗標，不從 143／137 猜）。aos-exec 的 `run_target_full()` 三種目標都回這格 |
| `stopped` | 是被強制停砍掉的（§5.2）；子程式在強制停到達**之前**就自己結束的，`stopped` 是 false、結果算數 |
| `ms` | 耗時 |

（09-24 補）`run_target_full()` 對三種目標回傳 `code`、`kind`、`timed_out`、`stopped`、`ms`，cpu 用的就是這個入口；
舊的 `run_target()` 保留回 `(code, kind)` 的相容契約，給還沒遷移的呼叫者。

**`kind=aos` 是 result 不是 error**：params 合法、只是那份 inst 讀不到／壞掉／前置檢查沒過。
stdout 不在 result 裡——要輸出就在 inst 裡寫 `stdout`。

## 4.2 `stop`

notification，**檔名必須以 `stop-` 開頭**（主人只掃前綴）。細節整節在 §5。

## 4.3 壞單也回音

§3 那張三類表：讀不出來的回 -32700／-32600（`id` 能抓就抓）、有 id 但 method／params 壞的回
-32601／-32602，都寫 `responses/<n>.json`、再刪原單；notification 壞了只刪不回。cpu 不停、不隔離、不重試。

幾個邊角：request 檔名必須是 `.json` 結尾的單一檔名（不含 `/`、NUL）；`ack-`／`stop-` 開頭但 `method` 不是
`ack`／`stop` 的，照三類表處理（有 id 回 -32600、沒 id 只刪）；`state.runs` 只數真的跑過 aos-exec 的，壞單不算。
（09-24 補）`ack-`／`stop-` 檔必須是相應 method 的 notification；帶 id 時回 `-32600`，不執行控制動作。
合法 notification 的 method／params 錯誤只刪原單、不回音。
