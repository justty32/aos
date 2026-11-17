← [入口](../cpp-py-改名.md)｜涵蓋：`lib/` 每一類東西的性質、`cmd/` 每支的大小與怎麼找 lib 和 C++、測試怎麼找東西｜上一份 [01-現況-cpp](01-現況-cpp.md)｜下一份 [03-寫死路徑數字](03-寫死路徑數字.md)

# 現況：`lib/` 與 `cmd/`（Python）

## 一張圖：`lib/` 裡其實有五種東西

```
lib/
├─ *.py（27 支）＋ daemon_ctl/      ① 被 import 的共用模組      5,329＋1,261 行
├─ agent/*.py（22 支）              ① 也是被 import 的（混在工具夾裡） 4,091 行
├─ base/ aos/ agent/ 底下的資料夾   ② 「資料夾＝程式」的工具（90 個）  約 18,800 行
├─ packs/                          ③ 純資料：18 份 JSON 工具包清單
├─ schema/                         ③ 純資料：comm/1 的 schema 與樣本（18 檔）
├─ docs/                           ④ README 的分檔（4 份 md）
└─ tests/                          ⑤ 頂層模組的測試（25 支）；工具的測試在各工具夾（99 支）
```

`lib/` 本身不是 Python 套件（沒有 `__init__.py`）；有 `__init__.py` 的只有 `agent/`、`aos/comm/`、`daemon_ctl/` 三處。沒有 `pyproject.toml`、`requirements.txt`。

## ① 被 import 的共用模組

| 類別 | 支數 | 名單 |
|---|---|---|
| 只被 `cmd` 用 | 9 | `aos_flags` `aos_ws` `aos_clock_register` `aos_clock_when` `aos_sweep` `aos_sweep_proc` `env_file` `mcp_freeze` `daemon_ctl/` |
| 只被工具用 | 10 | `aos_index` `aos_json` `declared_files` `file_summary` `file_walk` `hook_run` `observed` `observed_children` `shell_observed` `tool_spec` |
| 兩邊都用 | 7 | `tool_io`（89 個工具＋12 支頂層）`aos_refpath` `directive_value` `mcp_client` `mcp_server_file` `metainfo` `process_group` |
| 只被頂層互用 | 2 | `aos_json_multi` `aos_sweep_files` |
| 沒人用 | 0 | — |

`lib/agent/` 另有 22 支共用模組（`hooks`、`cli_base`、`cli_*`、`cooldown`、`goal_state`、`cmd_call`…），被 aos-agent、aos-eca、aos-mcp、約 23 個工具、範本的格 import。import 法兩種混用：`from agent import hooks` 與直接 `import cli_base`。

全 repo 平鋪 import（`import aos_flags` 這種）：頂層模組 342 行、`lib/agent` 模組 141 行，合計 **483 行**（cmd 129、lib 工具 217、lib 頂層互引 43、lib 測試 53、templates 41）。

## ② 「資料夾＝程式」的工具

| 夾 | 工具數 | 程式行 | 測試行 |
|---|---|---|---|
| `base/` | 32 | 2,705 | 1,603 |
| `aos/` | 21 | 約 5,835 | 6,234 |
| `agent/` | 37（8 個是 hook） | 約 10,265 | 10,168 |

- 一個工具＝一個資料夾：`_entry`（沒副檔名、可執行）＋`_tooldef.json`＋`_metainfo.json`，可選 README、`tests/`、同夾 `.py`。
- 它**不是被 import 的**：定義裡寫指示詞 `{"$env":"AOS_HOME","$path":"/lib/base/read"}`，由 `aos-exec` 當程式跑。
- 90 個入口 89 個是 Python、1 個是 sh（`hook_noop`）。
- **它怎麼找共用模組**：82 個入口「從自己的真實位置往上找，找到**名字叫 `lib`** 且裡面有 `tool_io.py` 的夾」加進 `sys.path`；約 5 個固定數層數。沒有一個讀 `AOS_HOME`。夾一改名，這 82 處全部找不到（另有 77 處錯誤字串寫「not in lib/」）。

## `cmd/` 每支

| 指令 | 程式行 | 測試（支／行） | 形狀 |
|---|---|---|---|
| **aos-agent** | **4,505** | 24／3,907 | 套件 `aos_agent/`（27 支） |
| **aos-view** | **3,107** | 7／1,828 | `bin` 單檔＋`ui/ web/ systemd/ aide-def/` |
| **aos-eca** | **1,941** | 17／3,854 | 套件 `aos_eca/`（12 支），兩個入口 |
| **aos-tools** | **1,163** | 10／1,509 | `bin` 單檔 |
| **aos-daemon-ctl** | **753** | 8／614 | `bin` 單檔（邏輯已在 `lib/daemon_ctl/`） |
| **aos-kit** | **570** | 1／713 | 套件 |
| **aos-comm** | **506** | 1／324 | 套件 |
| 其餘 14 支 | 各 45～481，合計約 4,200 | 21／約 5,000 | 多是 `bin` 單檔 |

粗體 7 支超過 500 行，合計約 12,500 行；21 支總計約 16,700 行程式、108 支測試。已有 6 個套件：`aos_agent aos_comm aos_eca aos_feedback aos_kit aos_mailbox`。

**入口怎麼找 `lib`**（都看自己的位置，沒有一支讀 `AOS_HOME`，合規則一）：

| 寫法 | 支數 |
|---|---|
| 寫死 `os.path.join(HERE,"..","..","..","lib")` | 15 |
| 往上找「有 `lib/aos_flags.py` 的祖先」 | 4（aos-comm 另把 `lib/aos` 也加進去，為了 `from comm import`） |
| 往上找 `lib/aos_flags.py` 與 `lib/agent/__init__.py`，import 完拿掉 | 3 |
| 不 import lib | 1（aos-view） |

**找 C++ 執行檔**：全部靠 `PATH` 上的裸名字。**找工具資料夾**：經定義裡的指示詞；唯一例外是 aos-sandbox 自己拼 `<家>/lib` 做唯讀掛載。

## 測試怎麼找東西

| | 支數 | 怎麼找 |
|---|---|---|
| `lib/` | 124（頂層 25＋工具夾 99），21,516 行 | 107 支用 `Path(__file__).parents[N]`；18 支寫死 `impls/<x>/bin`；59 支靠 `PATH`；32 支拼 `cmd` 路徑 |
| `cmd/` | 108 | 多數拼 `PROTO/"lib"`、`(PROTO/"impls").glob("*/bin")` |
| `templates/tests` | 約 30 | 同上 |
| `impls/` | 35 | 19 支吃自己專案的 `bin/` |

全部是 `unittest`，沒有 pytest、沒有 `conftest.py`、沒有統一的「家在哪」函式：每支自己算。

## 版本與第三方相依

- 最低 Python 3.10（`dict | None`）；測試用 `tomllib` 要 3.11；公司 WSL 是 3.12.3。
- 第三方只有 `jsonschema`，而且是選用的（沒裝就用內建檢查）。
- **公司 WSL 沒有 `pip`，也沒有 `ensurepip`**（實測：`import pip`、`import ensurepip` 都失敗）。要走「`pip install -e`」那條路，得先 `sudo apt install python3-pip python3-venv`。

## 撞名

- 跟標準庫撞名：沒有（比對 Python 3.12 標準庫名單）。
- **`lib/aos/` 是工具夾，不是套件**。如果新套件也叫 `aos`，又有人把 `py/` 加進 `sys.path`，會出現兩個 `aos`（實測結果見 [09](09-實測紀錄.md)）。
- 工具夾裡泛名很多（`hooks` `runner` `ledger` `common` `history` 各有 2～3 支同名），現在靠「每個工具先看自己的夾」不互撞。
