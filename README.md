# aos

`aos` 是薄型命令列入口；`aos-daemon` 是真正處理命令的常駐程式。
兩者以 Unix Domain Socket 通訊。

```text
Shell → aos（CLI）→ Unix Domain Socket → aos-daemon → 命令處理器
```

CLI 不解析業務命令。以下呼叫會把三個參數逐項送給 daemon：

```bash
aos new "bot alpha" --verbose
```

傳送內容是 `new`、`bot alpha`、`--verbose`，不是重新拼接的 shell 字串，
所以空白、引號與空字串的參數邊界都能保留。

pipe 或檔案重新導向提供的 stdin 也會傳給 daemon；daemon 回傳的 stdout、
stderr 會分別寫回 CLI 的 stdout、stderr：

```bash
printf 'hello\n' | aos new bot-a >output.txt 2>error.txt
```

傳輸協定已把三條串流拆成 64 KiB chunk。目前命令處理器仍會在 daemon 端收完
stdin 後才執行，總 stdin 上限為 8 MiB；互動式 TTY 留待真正需要時再加入。

## 相依套件

專案使用 vcpkg manifest 管理：

- standalone Asio：Unix Socket 與非同步連線。
- nlohmann/json：request metadata 與 exit code。

版本由 `vcpkg.json` 的 `builtin-baseline` 固定。第三方原始碼與安裝結果位於
`build/`，不會加入 Git；Asio/JSON 也不需要成為 Git submodule。

## 建置與執行

```bash
export VCPKG_ROOT=/home/lorkhan/vcpkg
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
```

先在一個終端啟動 daemon：

```bash
./bin/aos-daemon
```

再從另一個終端呼叫 CLI：

```bash
./bin/aos ping
./bin/aos new "bot alpha"
```

第一版的 `ping` 會回傳 `pong`。其他命令目前會列出 daemon 實際收到的參數，
方便驗證傳輸；尚未實作 `new` 的業務行為。

## Socket 路徑

兩個程式使用相同規則決定 socket 路徑：

1. 環境變數 `AOS_SOCKET`
2. `$XDG_RUNTIME_DIR/aos.sock`
3. `/tmp/aos-<uid>.sock`

需要自行指定時，兩邊使用相同環境變數即可：

```bash
AOS_SOCKET=/tmp/my-aos.sock ./bin/aos-daemon
AOS_SOCKET=/tmp/my-aos.sock ./bin/aos ping
```

## 程式分工

- `src/cli/main.cpp`：收集 argv 與工作目錄，啟動 client。
- `src/daemon/main.cpp`：選擇 socket 路徑，啟動 daemon。
- `src/core/client.cpp`：轉送 stdin、stdout、stderr 與 exit code。
- `src/core/daemon.cpp`：接受連線並管理每個 Asio session。
- `src/core/channel.cpp`：Asio 訊框讀寫。
- `src/core/protocol.cpp`：JSON 控制訊息編解碼。
- `src/core/command.cpp`：所有業務命令的唯一入口。

新增 `src/core/` 下的 `.cpp` 後，CMake 會自動遞迴編入核心 library。
兩個入口分別放在 `src/cli/` 與 `src/daemon/`；`include/` 下的標頭不需登記。

## Git 關係

`aos` 目前是 `simple_tools` 底下的獨立 Git repo，但尚未登記為 submodule。
若要讓 `simple_tools` 固定某個 `aos` 版本，應先替 `aos` 建立 commit 與 remote，
再由外層 repo 加入 submodule；不要直接在外層執行 `git add aos`。

## VS Code

建議直接以 VS Code 開啟本目錄：

```bash
export VCPKG_ROOT=/home/lorkhan/vcpkg
code /home/lorkhan/repo/simple_tools/aos
```

設定 CMake 後，`build/compile_commands.json` 會保存實際的 C++23 編譯參數與
include 路徑；專案內的 `.vscode/settings.json` 已設定 IntelliSense 使用它。
