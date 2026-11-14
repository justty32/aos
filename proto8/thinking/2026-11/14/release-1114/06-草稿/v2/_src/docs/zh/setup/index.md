# 安裝總覽

安裝分四級，只想試的話 L0 就夠：Linux、git、Python、CMake 加一個 C++ 編譯器，不用任何模型帳號。

<!-- copy:TAG -->
原型 · demo 版

<!-- source: 03-計劃.md 第 3 節；08-批0實測.md #1,#2,#3,#5；proto8/install.sh -->

## 四級一張表

| 級 | 必需 | 得到什麼 | 狀態 |
|---|---|---|---|
| L0 | Linux（含 WSL2）、git、bash、Python 3.11 以上、CMake 3.21 以上、C++20 編譯器、nlohmann-json（vcpkg 或系統套件） | 一棵樹、一隻 agent-fsm、假腦回話 | 已實測（vcpkg 路線，見[需求](requirements.md)） |
| L1 | 再加任一 OpenAI 相容端點，和它的金鑰（放環境變數） | 同一隻 agent 換成真腦、會叫工具 | 端點呼叫已實測；教學頁還沒寫 |
| L2 | 再加已登入的 claude CLI、tmux | 把 Claude Code 當成樹裡的一隻 agent | 未實跑 |
| L3（實驗） | 依功能：bubblewrap、s6、newuidmap、setfacl、systemd 或 s6-supervise；`aos-asuser` 要 Python 3.12 | 隔離、限額、分享、監管 | 實驗，見[安全說明](../manual/security.md) |

## Python：零第三方套件

**沒有 pip、沒有 venv。** Python 這一側只用標準庫；你只要有 `python3`（3.11 以上已實測）。C／C++ 零件另外要 nlohmann-json（建置時才要）。

## 兩條讓殼找得到指令的路

| | 三個環境變數（Get started 用的） | `install.sh`（想長期裝才跑） |
|---|---|---|
| 做什麼 | 只改目前這個殼的 `AOS_HOME`、`PATH`、`PYTHONPATH` | 把指令 symlink 進一個 PATH 上的資料夾，並登記 Python 路徑 |
| 寫到哪 | 哪裡都不寫（關掉殼就沒了） | 兩處：`~/.local/bin`（預設，可改 `DEST`）底下的 symlink；Python user site 的 `aos-proto8.pth`（兩行：repo 的 `py/`、`lib/` 絕對路徑） |
| 適合 | 先試試看 | 每個新殼都想直接用 |

三個變數的寫法在 [Get Started 第 2 步](../get-started.md)。

```bash
# 先看看會做什麼，什麼都不動
~/aos/proto8/install.sh --dry-run
# 真的裝
~/aos/proto8/install.sh
# 拿掉：只移除指進這份 repo 的連結，和內容完全相符的 aos-proto8.pth
~/aos/proto8/install.sh --uninstall
```

- 要先建置：`impls/*/bin` 一支都沒有時，`install.sh` 會報 `ImplsMissing` 並退 1。
- 它不改 PATH、不改任何 shell 設定檔；目的地不在 PATH 上只會印一行提醒，要自己加。
- 用 symlink 不是複製：repo 搬了位置要重跑；舊連結會被報「指向別處」，自己 `rm` 再跑。
- 同名的別的東西不會被蓋掉（印 `skip`、最後 `LinkFailed`、退 1）。
- 請把 repo clone 在 Linux 的檔案系統上（WSL 不要放 `/mnt/c`）。

<details>
<summary>install.sh 會連哪些指令</summary>

掃 `impls/*/bin/*`（C++ 的，例如 `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon`）與 `cmd/*/bin/*`（Python 的，例如 `aos-daemon-ctl`、`aos-agent`、`aos-tools`），只連有執行權限的檔。完整清單與錯誤代號見 `proto8/install.sh` 檔頭說明。`install.sh` 還沒實測，以上依腳本內容整理。

</details>

下一步：[需求清單](requirements.md)、[Get Started](../get-started.md)。
