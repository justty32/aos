← [aos-exec](README.md)｜[spec 總導航](../README.md)

# 退出碼：自己的失敗跟子程式的碼分開

`run_target()` 回的是 **`(code, kind)`**，`kind` 說這個碼是誰的；有沒有撞到逾時不從碼猜，要的話用
`run_target_full()`（見下面「給程式用」）。命令列照 `kind` 換算成退出碼：

| `kind` | 意思 | 命令列的退出碼 |
|---|---|---|
| `child` | **子程式真的跑完了一次**：它的 exit code、被訊號 N 砍＝128+N、沒執行權＝126、找不到程式＝127、逾時＝143／137 | **原樣** |
| `aos` | **aos-exec 自己失敗，那次根本沒跑**（`code` 是 1） | **125** |
| `usage` | 用法錯（`code` 是 2） | 2 |

`kind == "child"` ⇔「跑完了一次」⇔ inst 有寫 `exit` 就有被寫進去；125 與 2 **不寫 exit 檔**。

| 退出碼 | 什麼時候 |
|---|---|
| 2 | 用法錯：旗標不認得、`--timeout-ms` 是負數、inst 目標卻給了 `--`、`xxx` 是不存在的**非** `.json` 路徑、`--dir-target` 指的檔不存在 |
| **125** | **aos-exec 自己失敗**：inst.json 讀不到（**指名的 `.json` 不存在也算**）、不是 JSON、格式壞（[inst-posix.md 第 5 節](../inst-posix/errors.md#5-錯誤代號讀驗階段)的代號）、指示詞解不開（[directives.md 第 6 節](../directives/errors.md#6-錯誤代號)的代號）、`mkdir` 建不起來、`exit` 檔的父目錄不存在、`cwd` 不是資料夾、重導向的檔開不起來、`--stderr PATH` 開不起來 |
| 126 | 沒執行權（普通檔案沒 +x、或 inst 的 `argv[0]` 沒 +x） |
| 127 | 找不到程式（`argv[0]` 在疊加後的 PATH 裡找不到） |
| 143 / 137 | `--timeout-ms` 到了：SIGTERM 就死＝143，要 SIGKILL 才死＝137 |
| 其他 | **原樣**是子程式的結束狀態：正常結束＝它的 exit code，被訊號 N 砍＝128+N |

**為什麼是 125**：子程式回 1 很常見，aos-exec 自己失敗也回 1 的話，看的人分不出「指令跑了但
失敗」跟「指令根本沒跑」。125 撞不到 shell 那套（126／127／128+N），跟 `timeout(1)`、`env(1)`
挑的號碼是同一個理由。

# 125 與 2 時 stderr 印什麼

一律**一行**、印到 **aos-exec 自己的 stderr**，開頭是 `aos-exec: `：

- **格式／指示詞壞掉（125）**：`aos-exec: <代號>: <白話>`，代號就是規範裡的那個字，例如
  `aos-exec: OptionConflict: /stdout 的 inherit 不能帶 $val`、`aos-exec: ReferenceCycle: …`、
  `aos-exec: ReadFailed: 讀不到 …`。程式抓的話認開頭的代號就好。
- **前置檢查沒過（125）**：白話一句，沒有代號，例如 `aos-exec: cwd 不是資料夾：/x/y`、
  `aos-exec: exit 檔的父目錄不存在（沒開 mkdir 不會幫你建）：/x`、
  `aos-exec: stdout 的 mkdir 建不起來 /x：…`、`aos-exec: 重導向的檔案開不起來：…`。
- **用法錯（2）**：`aos-exec: 找不到 xxx`、`aos-exec: 資料夾 /x 裡沒有 .aos/inst.json`、
  `aos-exec: inst 目標的參數寫在 inst.json 的 argv 裡`；旗標本身錯的是 argparse 的
  `usage: …` ＋ `aos-exec: error: …`。
- 126／127 也印一行（`aos-exec: 找不到程式：…（exit 127）`），但那是 `child` 的碼、exit 檔照寫。
