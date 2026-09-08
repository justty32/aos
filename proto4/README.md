# proto4 — 資料夾模擬 lisp（Janet）

← [proto3-2](../proto3-2/README.md)（上一版：使用者寫偽碼、我補全）

2026-09-08 開的。一句話：**資料夾就是可以被叫的東西**。`(runf (./xxx a b))` ＝ 切到 `./xxx`、把 `./xxx/.aos/inst` 當 Janet 程式跑、回最後一個值。

## 現在有什麼

- `src/runf.janet`：`runf` 巨集、`run-dir` 函式、`inst-path`。路徑寫 `./xxx`、`../xxx`、`/abs/xxx`、`~/xxx` 都行（Janet 把它們讀成一個符號，`~` 由 `expand` 換成家目錄），也可以給字串。`runf` 是巨集，所以不用加引號；加了 `'(./xxx)` 也當同一回事。
  - inst 裡看得到 `args`（參數）、`here`（自己的絕對路徑）、`runf`／`run-dir`（再叫子資料夾，路徑相對於自己）。
  - `.aos/inst` 這段路徑用 dynamic `:inst-path` 設定：`(setdyn :inst-path "my-inst")` 全域改、`(with-dyns [:inst-path "my-inst"] …)` 改一段；子孫沿用。
  - 資料夾不在、inst 不在、inst 自己炸，都 error 往外丟；工作目錄一定切回來。
- `src/kernel.janet`：**時鐘**。登記一群資料夾，每走一格，該輪到的資料夾就 `run-dir` 一次。
  - `(new)` 開一個 kernel；`(register k dir &opt name interval)` 登記（name 預設＝路徑最後一段，interval＝每幾格跑一次，預設 1，同名重登記＝覆蓋）；`(unregister k name)`、`(pause k name)`、`(resume k name)`、`(ls k)`（照 name 排序）。
  - `(step k)` 走一格：輪到的資料夾各跑一次 `(run-dir dir 現在第幾格)`——inst 裡 `(first args)` 就是格數；回傳這格跑了誰。inst 炸了只記在那個 proc 的 `:error`、印一行到 stderr，kernel 不停、別人照跑；下一格成功就把 `:error` 清掉。
  - `(run k &opt steps interval)` 連走 N 格（nil＝一直走），每格之間睡 interval 秒；`(stop k)` 讓無限迴圈下一格停。先做同步版，沒有 fiber。
  - **狀態歸資料夾自己管**：inst 想留東西就自己 `spit`（例如每格讀寫 `count.txt`），kernel 不管。
- `src/main.janet`：命令列跑時鐘。
- `test/runf.janet`（27 條）、`test/kernel.janet`（40 條）；`test/fx/` 是測試用的資料夾樣本（hello、outer/inner、alt、boom、k/*）。
- `notes/`：使用者原話與我的理解。

## 怎麼跑

```sh
cd proto4
jpm test                 # 跑 test/*.janet
janet -e '(use ./src/runf) (pp (runf (./test/fx/hello 1 2)))'

# 時鐘：DIR 寫成 [名字=]資料夾[:間隔]，可以只寫資料夾
janet src/main.janet test/fx/k/a x=test/fx/k/b:2 --steps 4
janet src/main.janet ./w1 ./w2 --steps 10 --interval 1   # 每格睡 1 秒
```

## 假設

inst 內容是 **Janet 程式**（proto2 是一段 shell）。要不要也接 shell，等使用者說。
