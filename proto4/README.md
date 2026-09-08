# proto4 — 資料夾模擬 lisp（Janet）

← [proto3-2](../proto3-2/README.md)（上一版：使用者寫偽碼、我補全）

2026-09-08 開的。一句話：**資料夾就是可以被叫的東西**。`(runf (./xxx a b))` ＝ 切到 `./xxx`、把 `./xxx/.aos/inst` 當 Janet 程式跑、回最後一個值。

## 現在有什麼

- `src/runf.janet`：`runf` 巨集、`run-dir` 函式、`inst-path`。路徑寫 `./xxx`、`../xxx`、`/abs/xxx` 都行（Janet 把它們讀成一個符號），也可以給字串。
  - inst 裡看得到 `args`（參數）、`here`（自己的絕對路徑）、`runf`／`run-dir`（再叫子資料夾，路徑相對於自己）。
  - `.aos/inst` 這段路徑用 dynamic `:inst-path` 設定：`(setdyn :inst-path "my-inst")` 全域改、`(with-dyns [:inst-path "my-inst"] …)` 改一段；子孫沿用。
  - 資料夾不在、inst 不在、inst 自己炸，都 error 往外丟；工作目錄一定切回來。
- `test/runf.janet`：21 條；`test/fx/` 是測試用的資料夾樣本（hello、outer/inner、alt、boom）。
- `notes/`：使用者原話與我的理解。

## 怎麼跑

```sh
cd proto4
jpm test                 # 跑 test/*.janet
janet -e '(use ./src/runf) (pp (runf (./test/fx/hello 1 2)))'
```

## 假設

inst 內容是 **Janet 程式**（proto2 是一段 shell）。要不要也接 shell，等使用者說。
