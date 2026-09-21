# aos-exec：把一個目標跑一次（命令列說明）

← [proto5 README](../README.md)｜實作：[lib/aos_exec.py](../lib/aos_exec.py)（執行）＋
[lib/aos_inst.py](../lib/aos_inst.py)（讀／驗 inst.json）＋ [bin/aos-exec](../bin/aos-exec)（入口）；
inst.json 的格式與執行語意在 [inst-posix.md](inst-posix.md)，指示詞在 [directives.md](directives.md)

> **命令列走法照 proto4-3 現況整理，使用者還沒逐條拍板。** 旗標、三種目標的分法、退出碼都
> 是從 [proto4-3/docs/exec.md](../../proto4-3/docs/exec.md) 搬過來的，沒有新發明；哪天拍板了
> 再回來改這份。

一句話：**aos-exec 把一個目標執行一次，然後把「這次是誰的碼」分清楚交回來。**
「照一份 inst.json 跑一次」到底做什麼（驗完才跑、mkdir／append／inherit／merge、環境清空或
疊加、逾時怎麼砍、exit 檔怎麼寫），全部照 [inst-posix.md 第 6 節](inst-posix.md#6-執行語意執行者要做到的)，
這裡不重講。

## 用法

```
aos-exec xxx [--dir-target REL] [--timeout-ms N] [--stderr PATH|-] [-- ARG...]
```

## 三種目標：`xxx` 是什麼決定怎麼跑

| `xxx` 是 | 做什麼 | base（`cwd` 沒寫時的預設、相對路徑的起點） | 串流 |
|---|---|---|---|
| 普通檔案（副檔名不是 `.json`） | 直接執行它：`argv[0]` 是它的絕對路徑，`--` 後面的東西原樣接成 `argv[1:]` | 它所在的資料夾 | **繼承** aos-exec 的 |
| `.json` 檔（**不存在也走這條**） | 讀進來當 inst.json 解析、執行 | 那個 `.json` 所在的資料夾 | 照 inst.json |
| 資料夾 | 執行 `xxx/.aos/inst.json`（`--dir-target` 可改） | `xxx` 自己 | 照 inst.json |

- **先看是不是資料夾、再看副檔名**：一個名字剛好以 `.json` 結尾的**資料夾**還是照資料夾走。
- **普通檔案模式**不解析 `--` 後的內容：空字串、空白、看起來像旗標的字串都原樣當一個 argv
  元素。環境就是繼承的、沒有 exit 檔、沒有重導向。它沒有執行位＝126。
- **`.json` 或資料夾目標給了 `--`**（就算後面沒有元素）是用法錯（退出碼 2）：inst 目標的參數
  寫在 inst.json 的 `argv` 裡。
- **一個以 `.json` 結尾但不存在的路徑不是用法錯**，是 aos-exec 自己失敗（125、`ReadFailed`）：
  這樣之後的 daemon 才能先收下一份還沒出現的 inst.json，檔案一出現就自然跑起來。不存在的
  **非** `.json` 路徑照舊是用法錯（2）。

## 旗標

| 旗標 | 意思 |
|---|---|
| `--dir-target REL` | `xxx` 是資料夾時要跑的相對路徑，預設 `.aos/inst.json`。指的檔不存在＝用法錯（2）。base 還是 `xxx` 自己，不是那個檔所在的資料夾 |
| `--timeout-ms N` | 這一次執行的上限（毫秒）。三種目標都吃；`0` 或不給＝不限；負數＝用法錯（2）。到了就砍整個 process group：SIGTERM、等 2 秒、還在就 SIGKILL（碼是 143／137，見下） |
| `--stderr PATH` / `--stderr -` | 蓋掉子程式的 stderr：`-`＝印到 aos-exec 自己的 stderr；給路徑＝寫進那個檔，路徑**以呼叫 aos-exec 時的 cwd 為中心**（不是 inst 的 cwd）。蓋的是 inst.json 的**整個** `stderr` 設定，包括 `merge`／`inherit`／`append`／`mkdir`（被蓋掉的 `mkdir` 也不會建）；stdin／stdout／exit 不受影響。普通檔案模式也吃 |
| `--` | 之後的東西原樣交給普通檔案當參數；inst 目標不准給 |

**看不到錯誤？** inst.json 沒寫 `stderr` 時，子程式的錯誤預設進 `/dev/null`。加 `--stderr -` 就看得到。

## 退出碼：自己的失敗跟子程式的碼分開

`run_target()` 回的是 **`(code, kind)`**，`kind` 說這個碼是誰的；命令列照 `kind` 換算成退出碼：

| `kind` | 意思 | 命令列的退出碼 |
|---|---|---|
| `child` | **子程式真的跑完了一次**：它的 exit code、被訊號 N 砍＝128+N、沒執行權＝126、找不到程式＝127、逾時＝143／137 | **原樣** |
| `aos` | **aos-exec 自己失敗，那次根本沒跑**（`code` 是 1） | **125** |
| `usage` | 用法錯（`code` 是 2） | 2 |

`kind == "child"` ⇔「跑完了一次」⇔ inst 有寫 `exit` 就有被寫進去；125 與 2 **不寫 exit 檔**。

| 退出碼 | 什麼時候 |
|---|---|
| 2 | 用法錯：旗標不認得、沒給 `xxx`、`--timeout-ms` 是負數、inst 目標卻給了 `--`、`xxx` 是不存在的**非** `.json` 路徑、`--dir-target` 指的檔不存在 |
| **125** | **aos-exec 自己失敗**：inst.json 讀不到（**指名的 `.json` 不存在也算**）、不是 JSON、格式壞（[inst-posix.md 第 5 節](inst-posix.md#5-錯誤代號讀驗階段)的代號）、指示詞解不開（[directives.md 第 6 節](directives.md#6-錯誤代號)的代號）、`mkdir` 建不起來、`exit` 檔的父目錄不存在、`cwd` 不是資料夾、重導向的檔開不起來、`--stderr PATH` 開不起來 |
| 126 | 沒執行權（普通檔案沒 +x、或 inst 的 `argv[0]` 沒 +x） |
| 127 | 找不到程式（`argv[0]` 在疊加後的 PATH 裡找不到） |
| 143 / 137 | `--timeout-ms` 到了：SIGTERM 就死＝143，要 SIGKILL 才死＝137 |
| 其他 | **原樣**是子程式的結束狀態：正常結束＝它的 exit code，被訊號 N 砍＝128+N |

**為什麼是 125**：子程式回 1 很常見，aos-exec 自己失敗也回 1 的話，看的人分不出「指令跑了但
失敗」跟「指令根本沒跑」。125 撞不到 shell 那套（126／127／128+N），跟 `timeout(1)`、`env(1)`
挑的號碼是同一個理由。

## 125 與 2 時 stderr 印什麼

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

## 給程式用：`run_target()`

```python
import aos_exec
code, kind = aos_exec.run_target(xxx, dir_target=".aos/inst.json", timeout_ms=0,
                                 on_spawn=None, stderr=None, args=None)
```

- `on_spawn`：子行程一開起來就用那個 `Popen` 叫它一次、收完屍再用 `None` 叫一次（給之後的
  aos-run 砍正在跑的那個用；命令列用不到）。
- `stderr`：同 `--stderr`（`None`＝照 inst.json、`"-"`＝繼承、字串＝路徑）。
- `args`：同 `--`（`None`＝沒給、陣列＝有給，含空陣列）。只對普通檔案有效。
- 反覆執行不是這支程式的事：aos-run 就是 import 它、反覆叫 `run_target()`。

## 例子

```sh
aos-exec ./job                          # 跑 ./job/.aos/inst.json，base＝./job
aos-exec ./job --dir-target other.json  # 改跑 ./job/other.json，base 還是 ./job
aos-exec ./one.json --timeout-ms 5000   # 單一 .json，base＝它所在的資料夾，5 秒上限
aos-exec ./job --stderr -               # 子程式的錯誤印出來看
aos-exec ./hello.sh -- a "b c" --x      # 普通檔案：直接跑，參數原樣接
echo $?                                 # 0＝子程式回 0；125＝aos-exec 自己失敗；2＝用法錯
```
