# 01 · aos 是什麼，怎麼跑起來

## 一句話

`aos` 是一支很薄的命令列程式，它自己不做事，只把你打的參數送給常駐在背景的
`aos-daemon`，再把 daemon 吐出來的東西原封不動印回你的終端。

為什麼要拆成兩支？因為 daemon 不會結束，所以它可以把昂貴的東西（連線、快取、
模型狀態）留在記憶體裡，下一次 `aos` 呼叫可以直接用。CLI 每次都是新的 process，
留不住任何東西。

## 建置

```bash
export VCPKG_ROOT=/home/lorkhan/vcpkg
cmake --preset dev          # 產生 build/，順便叫 vcpkg 裝 asio / json / curl
cmake --build --preset dev  # 產出 bin/aos 與 bin/aos-daemon
ctest --preset dev          # 跑三個測試
```

`ctest` 的實際輸出：

```text
    Start 1: protocol
1/3 Test #1: protocol .........................   Passed    0.00 sec
    Start 2: streaming
2/3 Test #2: streaming ........................   Passed    0.00 sec
    Start 3: end_to_end
3/3 Test #3: end_to_end .......................   Passed    0.10 sec

100% tests passed out of 3
```

執行檔不在 `build/` 裡，而是被送到原始碼樹的 `bin/`，這是 `CMakeLists.txt` 裡
`RUNTIME_OUTPUT_DIRECTORY` 指定的。

## 開一個 daemon

開發時建議自己指定 socket 路徑，不要跟平常在用的那個撞到：

```bash
export AOS_SOCKET=/tmp/aos-dev.sock
./bin/aos-daemon
```

畫面會出現：

```text
aos-daemon 正在監聽 /tmp/aos-dev.sock
```

`AOS_SOCKET` 兩邊都要設，CLI 才找得到 daemon。找路徑的規則寫在
`src/core/socket_path.cpp:24`，順序是：

1. `AOS_SOCKET`
2. `$XDG_RUNTIME_DIR/aos.sock`
3. `/tmp/aos-<uid>.sock`

## 用 CLI 打它

另開一個終端（同樣要 `export AOS_SOCKET=/tmp/aos-dev.sock`）：

```text
$ ./bin/aos ping
pong

$ ./bin/aos help
用法：aos <command> [arguments...]

可用的命令：
  ping    回覆 pong，用來確認 daemon 還活著
  echo    把 stdin 原封不動送回 stdout（串流）
  help    列出所有命令
  daemon  操作常駐程式本身 …

$ printf 'hi' | ./bin/aos echo
hi
```

名稱後面的 `…` 表示那是分組，後面還有一層：

```text
$ ./bin/aos daemon
用法：aos daemon <command> [arguments...]

可用的命令：
  status  顯示已經活多久、服務過幾次
  stop    請 daemon 做完手上的事之後收工
$ echo $?
2
```

## 證明 daemon 真的是常駐的

連打兩次 `daemon status`，`served` 會累加。因為那個數字存在 `Runtime` 裡，
而 `Runtime` 活在整個 daemon 的生命週期，不是每條連線各一份：

```text
$ ./bin/aos daemon status
uptime = 0s
served  = 4 次請求

$ ./bin/aos daemon status
uptime = 0s
served  = 5 次請求
```

細節見 [08 · Runtime](08-runtime.md)。

## 打一個不存在的命令

不會報錯，而是走 fallback 命令 `describe`，把 daemon 實際收到的東西列出來。
這是用來確認參數邊界（空白、引號、非 ASCII）在傳輸中沒被弄壞的：

```text
$ ./bin/aos new "bot alpha" --verbose
daemon 收到 3 個參數
argv[0] = <new>
argv[1] = <bot alpha>
argv[2] = <--verbose>
工作目錄 = /home/lorkhan/repo/simple_tools/aos
stdin = 0 bytes
```

注意 `bot alpha` 中間的空白還在，沒有被重新切成兩個參數。CLI 送的是一個
字串陣列，不是重新拼起來的 shell 字串。

## 關掉 daemon

```text
$ ./bin/aos daemon stop
aos-daemon 收工中
```

⚠️ 目前這個命令**只會停止接受新連線，process 不會真的結束**。要真的關掉請用
`Ctrl-C` 或 `kill`。這是一個已知的 bug，說明在
[10 · 已知地雷](10-gotchas.md#daemon-stop-不會讓-process-結束)。

---

下一篇：[02 · 大架構](02-architecture.md)
