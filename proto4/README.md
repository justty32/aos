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
- `src/main.janet`：命令列跑時鐘（一次性，跑完就走）。
- `src/daemon.janet`：**daemon＝一個常駐進程裡跑著一個 kernel**，外面的人用「丟檔案」跟它講話。
  - 家（home）是一個資料夾：`kernel.pid`（daemon 的 pid）、`state.jdn`（每格寫一次的快照，`ls` 就是讀它，daemon 沒在跑也讀得到）、`kernel.log`（daemon 的輸出）、`requests/`（請求檔 `.req`）、`requests/done/`（處理完搬過來，內容換成 `{:req 原文 :ok true/false :result …}`）。
  - **請求檔的內容是一個 Janet 表達式**——daemon 在一個綁好 kernel 的環境裡 `eval-string` 它，回傳值就是 result。環境裡有 `(register dir &opt name interval)`、`(unregister name)`、`(pause name)`、`(resume name)`、`(ls)`、`(steps)`、`(stop)`、`(set-interval sec)`，都已經把 kernel 帶進去了。
  - 一格＝處理完 `requests/` 裡所有 `.req`（照檔名排序）→ `kernel/step` → 寫 `state.jdn` → 睡 interval 秒。`(stop)` 或 SIGTERM 就跑完這格收工、刪掉 `kernel.pid`。
  - `serve`／`start`（背景開，`os/spawn … :pd` detach，等第一格跑完才回）／`stop`（先請它自己走，不理就 kill）／`alive?`（看 `/proc/<pid>/stat`，殭屍不算活著）／`request`／`ls`。
  - **dir 一律絕對路徑**：daemon 的 cwd 跟你不一樣，客戶端送之前自己 `os/realpath`（`aos-daemon.janet` 已經幫你做了）。
- `src/aos-daemon.janet`：daemon 的命令列。home 的順序是 `--home DIR` > 環境變數 `AOS_DAEMON_DIR` > 都沒有印一句退 2（**home 只走 `--home`**，不吃位置參數，免得跟 register 的 dir／name／interval 撞在一起）。
- `test/runf.janet`（27 條）、`test/kernel.janet`（40 條）、`test/daemon.janet`（44 條，真的開一個 daemon 進程來測，家開在 `/tmp`，跑完自己收）；`test/fx/` 是測試用的資料夾樣本（hello、outer/inner、alt、boom、k/*）。
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

### daemon：一個常駐 kernel

```sh
export AOS_DAEMON_DIR=~/.aosd4          # 或每次都帶 --home ~/.aosd4

janet src/aos-daemon.janet start --interval 1        # 背景開起來，等第一格跑完才回
janet src/aos-daemon.janet register test/fx/k/counter cnt   # dir 會自動轉絕對路徑
janet src/aos-daemon.janet ls                        # kernel 一行 ＋ 每個 proc 一行
janet src/aos-daemon.janet pause cnt                 # 暫停（登記還在，就是不跑）
janet src/aos-daemon.janet resume cnt
janet src/aos-daemon.janet eval '(steps)'            # 直接丟任意表達式，回傳值就是結果
janet src/aos-daemon.janet stop                      # 跑完這格收工
```

跑起來長這樣：

```
$ janet src/aos-daemon.janet start --home /tmp/aosd --interval 1
起來了（pid 43482，每 1 秒一格）

$ janet src/aos-daemon.janet register test/fx/k/counter cnt --home /tmp/aosd
ok
{:dir "/home/me/proto4/test/fx/k/counter" :interval 1 :name "cnt" :paused false :runs 0}

$ janet src/aos-daemon.janet ls --home /tmp/aosd
kernel  alive  pid=43482  steps=5  interval=1  home=/tmp/aosd
  cnt  /home/me/proto4/test/fx/k/counter  每 1 格  runs=4

$ janet src/aos-daemon.janet pause cnt --home /tmp/aosd
ok
{... :paused true :runs 6}

$ janet src/aos-daemon.janet stop --home /tmp/aosd
收工了（pid 43482）

$ janet src/aos-daemon.janet ls --home /tmp/aosd       # 人走了，state.jdn 還讀得到
kernel  dead  pid=-  steps=9  interval=1  home=/tmp/aosd
  cnt  /home/me/proto4/test/fx/k/counter  每 1 格  [暫停]  runs=6
```

`register`／`unregister`／`pause`／`resume`／`eval` 都是「寫一個請求檔進 `requests/`、等 `done/` 冒出同名檔」；
加 `--no-wait` 就丟了不等，daemon 沒在跑也可以先丟著（它起來就會撿）。

## 假設

inst 內容是 **Janet 程式**（proto2 是一段 shell）。要不要也接 shell，等使用者說。
