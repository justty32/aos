# proto8/extras/langs/janet：用 Janet 寫 aos 程式

← [proto8/extras/langs](../README.md)｜[proto8](../../../README.md)

`aos-janet - 把一份 Janet 寫的 aos 程式編成資料夾（_entry、loop.json、fsm.json…）`（NAME，C-54 R1）

**一句話：與其一個個 mkdir、vim 堆出一整套資料夾，不如用 Janet 寫一段、`aos-janet` 把它生成出來**（C-43，使用者 10-19「不如直接用lua/lisp生成這麼一套資料夾佈局」；10-24「我想試試看janet編譯成這套」）。
編出來的就是普通的資料夾＋JSON＋短腳本，跟手寫的一樣，可以直接看、直接手改、直接 `aos-exec`。設計與代定在 [thinking 2026-10-24-janet-compile](../../../thinking/2026-10-24-janet-compile.md)。嘗試性質。

```sh
proto8/extras/langs/janet/bin/aos-janet proto8/extras/langs/janet/examples/agent_dan.janet /tmp/dan   # 編
aos-exec --ws 工作區 /tmp/dan                                                            # 跑（PATH 照 demo/README 放好 aos-*）
```

要裝 Janet（這台在 `~/.local/bin/janet`，1.41.2）；不用 spork、不用 jpm。

## 用法

```
aos-janet [--force] 原始檔.janet 輸出資料夾
```

- 原始檔是普通的 Janet：下面那些名字直接能用（不用 import），最後要 `(def program (dir …))`——program 就是那支程式（一個資料夾）。
- 輸出資料夾已經有東西＝`OutExists`；`--force`＝只蓋這次要寫的檔，其他檔不刪。
- 錯：stderr 一行 `aos-janet: 代號 原因`、退 1。代號：`ArgumentsBad`、`SourceMissing`、`SourceBad`（原始檔跑不起來，上面先印 Janet 的錯）、`ProgramMissing`、`ProgramBad`、
  `OutExists`、`OutBad`、`NameBad`、`NameTaken`、`KeyTwice`、`ValueBad`、`HoistBad`、`StepBad`。

## 寫法 ↔ 編出來的東西

| Janet | 編出來 |
|---|---|
| `(dir "a" x "b" y)` | 資料夾，裡面 `a`、`b` |
| struct／table／tuple／字串／數字（放在 dir 裡） | 那個檔寫成 JSON（中文不跳脫、短的擠一行） |
| `(obj "k" v …)` | JSON 物件、key 照寫的順序；值 `nil`＝不寫那個 key，要 JSON 的 null 寫 `null` |
| `(inst ["python3" "brain.py"] :timeout_ms 120000)` | `{"argv": ["python3", "brain.py"], "timeout_ms": 120000}` |
| `(env "AOS_WS" "/out.txt")`、`(ref "a.json#/b")` | `{"$env": "AOS_WS", "$path": "/out.txt"}`、`{"$ref": "a.json#/b"}` |
| `(aos-loop "fsm.json" :max 40)` | `{"exec": "fsm.json", "max": 40}` |
| `(aos-fsm :entry (self-entry "aos-fsm") (idle x -> think) …)` | `{"_entry": ["aos-fsm", {"$env": "AOS_CF"}], "start": "idle", "states": {"idle": {"exec": …, "next": "think"}, …}}`（start 沒給＝第一格） |
| 某格的 exec 寫 `(dir …)` | 長成同一層的子資料夾 `idle/`，exec 換成 `"idle"`（名字取那格的名字） |
| `(text s)`、`(script s)`、`(sh 行 …)` | 文字檔（644）、可執行檔（755）、`#!/bin/sh` 加上每一行 |
| `(copy "路徑")` | 照抄那個檔（相對路徑從原始檔所在的資料夾算），權限照原檔 |
| `(dotenv "# 註解" ["名" "值"])` | `.env` |
| `(tool :description … :parameters … :entry …)` | 工具資料夾：`_tooldef.json`＋`_entry`（agent-dan 範例另外生 `tools.json` 登記它們） |
| `(janet-main [_ & args] 程式…)` | `#!/usr/bin/env janet` 的可執行檔，內容 `(defn main [_ & args] 程式…)` |
| `(aos-seq a b c)`、`(aos-par a b)`、`(aos-if c t e)` | 一個資料夾：`_entry` 是短 shell 腳本，每一步 `aos-exec` 一次、各給一個小格 `$AOS_STACK/<步名>`；單子放 `steps.json`、資料夾長成 `s1/`、`p1/`、`cond/`… |

key 照寫的字面用（`:timeout_ms` 就是 `timeout_ms`，不換 `-`）。一般 struct 的 key 照固定順序（`_entry`、`argv`…、`exec`、`max`、`start`、`states`、`next`…）再照字母。

## 例子（[examples/](examples)）

- `agent_dan.janet`：agent-dan 的 Janet 版。`agent` 是一個普通的 Janet 函數（範本），給 system、工具、腦，回一個資料夾。編出來跟 [demo/agent-dan](../../../demo/README.md) 的檔一樣多、JSON 內容相同，假腦跑出來一樣；差別只在 `_entry` 寫成 argv 陣列（手寫版是 sh）、幾行註解。Python 的葉子照抄手寫版。
- `count.janet`：loop＋fsm，葉子用 Janet 寫（`janet-main`）。
- `steps.janet`：seq／par／if。

## 檔案

| 檔 | 做什麼 |
|---|---|
| `bin/aos-janet` | 命令列：在子環境裡跑原始檔、拿 `program`、交給 emit |
| `aos.janet` | 寫法：JSON 的值（obj、inst、env、ref、aos-loop、aos-fsm…）與檔案節點（dir、text、script、sh、copy、dotenv、tool、janet-main） |
| `combine.janet` | aos-seq、aos-par、aos-if（編成 shell 入口的資料夾） |
| `emit.janet` | 寫到磁碟；JSON 裡碰到檔案節點就長成子資料夾 |
| `json_write.janet` | Janet 的值 → 好讀的 JSON |
| `code_write.janet` | Janet 程式碼 → 原始碼字串（janet-main 用；中文照原樣） |

測試：`python3 -m unittest discover -s proto8/tests -p test_janet.py`（沒裝 janet 就 skip）。
