# 05 Python：第三方模組、最低版本、requirements、pip 裝不裝

← [入口](../外部依賴.md)｜上一份 [04-cgroup-s6-系統工具](04-cgroup-s6-系統工具.md)｜下一份 [06-要裁的題](06-要裁的題.md)

**結論**：`proto8/lib`、`proto8/cmd`、`proto8/templates`、`wf/tools`、`impls/*/tests` 掃下來，**第三方模組只有一個 `jsonschema`，而且是選用**——沒有它就改用內建的檢查。所以 aos 現在「只靠標準庫就能全跑」。Python 最低版本：執行 3.10、跑全部測試 3.11。推薦放一份只列 `jsonschema` 的選用清單，安裝腳本只檢查、不自己 pip。

## 第三方模組

| 模組（pip 名） | 誰用 | 怎麼 import | 分類 | 沒有會怎樣 |
|---|---|---|---|---|
| `jsonschema` | `lib/aos/comm/check.py:46`（`engine()` 裡）；`cmd/aos-comm/tests/test_comm.py:34` | 函式裡 `try: import … except ImportError` | **某功能才要（而且有替代）** | 改用內建的檢查（`builtin`）；要 Draft 2020-12，所以要 4.x |

掃法：用 `ast` 解析每個 `.py` 與有 python shebang、沒副檔名的腳本（WSL 的 Python 3.12，0 個解析失敗），repo 裡找得到同名檔或夾的算 aos 自己的模組。另外直接 grep 了 yaml、requests、toml、tomli、psutil、pytest、click、rich、httpx、numpy、jinja2、pexpect、watchdog、dotenv、pydantic，**全部 0 筆**。

| 其他事實 | 實況 |
|---|---|
| 測試框架 | 標準庫 `unittest`（`python3 -m unittest discover -s …`），沒有 pytest |
| 現有的打包檔 | proto8 與 wf 都沒有 `requirements*.txt`、`pyproject.toml`、`setup.py`、`setup.cfg`、`conftest.py` |
| aos 自己的模組怎麼被找到 | 靠各腳本改 `sys.path` 或 `env.sh`；這部分由 `cpp-py-改名` 處理 |

## Python 最低版本

| 最新用到的特性 | 在哪 | 需要 |
|---|---|---|
| `import tomllib` | 只有測試：`lib/agent/tests/test_cli_codex_mcp.py:8`、`test_cli_external_mcp.py:11` | 3.11 |
| 執行時求值的 `dict \| None` 註記（沒有 `from __future__ import annotations`） | `lib/metainfo.py:40` 等 | 3.10 |
| `removeprefix`、`Path.is_relative_to`、內建泛型 `dict[…]` | `lib/aos_json.py:177`、`lib/aos/promote/swap.py:26` 等 | 3.9 |

沒找到：`match`、`except*`、`datetime.UTC`、`itertools.batched`、`Path.walk`、`TaskGroup`、`zip(strict=)`。**建議宣告「Python ≥ 3.11」一個數字**（執行與測試一致；Ubuntu 24.04 是 3.12、Debian 12 是 3.11），安裝腳本低於就報錯。若要支援更舊的，宣告 3.10、測試那兩支再處理。

## requirements 草稿

```
# requirements-optional.txt — optional Python packages for aos (aos runs on the stdlib alone).
# jsonschema: full JSON Schema (Draft 2020-12) checks in aos-comm; without it a builtin checker is used.
jsonschema>=4.18
```

| 決定點 | 推薦 | 理由 |
|---|---|---|
| 檔名 | `requirements-optional.txt`（不叫 `requirements.txt`） | 叫 `requirements.txt` 會讓人以為不裝就不能跑 |
| 放哪 | `py/` 夾頂（`cpp-py-改名` 的 Python 原始碼夾） | 跟 Python 原始碼一起；repo 根依「非侵入式」佈局只放入口 |
| 釘版本 | 只寫下限 `>=4.18`，不釘死 | 只有一個選用套件；釘死反而跟系統套件（`python3-jsonschema`）衝突 |

`>=4.18` 是我挑的保守下限（`referencing` 那代），**沒查**我們用到的 API 最低要哪版；4.0 起就支援 Draft 2020-12。

## 安裝腳本要不要自己 pip

很多發行版的系統 Python 有 `EXTERNALLY-MANAGED` 標記（PEP 668），直接 `pip install` 會被拒；**公司 WSL 實查：有這個標記、而且根本沒裝 pip、也沒有 venv 模組**（`ensurepip` 不在）。

| 選項 | 後果 |
|---|---|
| **A 只檢查並提示（推薦）** | 沒有 `jsonschema` 就印一行「optional, install `python3-jsonschema` or `pip install -r py/requirements-optional.txt` in your own venv」；不碰使用者的 Python 環境；永遠裝得完 |
| B 安裝腳本建一個 venv（例 `$AOS_HOME/venv`）再 `pip install -r` | 要 `python3-venv` 套件（公司 WSL 沒有→這條直接失敗）；第一次要網路；所有入口都得改成用 venv 的 Python，入口產生器要多一層 |
| C `pip install --user`（必要時加 `--break-system-packages`） | 繞過發行版保護，可能弄壞系統套件；使用者不一定有 pip；**不推薦** |
| D 不放清單、不檢查 | 最省事；使用者不會知道有個選用功能 |

**沒測**：venv 與 pip 實際裝 `jsonschema`（公司 WSL 沒 pip、沒 venv，任務書不准裝系統套件）。
