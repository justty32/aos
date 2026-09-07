# pyshop 工具包

這包是給**專接 Python 小程式的工作室**用的：家當放在 `team/assets/`，
專案放在 `team/projects/<單號>/`，工具就三件事——**看家當、生骨架、跑驗收**。

沒有 `team/`（不在工作室裡）或還沒有 `team/assets/`，每支工具都回
`{"ok": false, "error": "…"}`，不會亂猜路徑。

## 工具

- `asset_list()`：列出 `team/assets` 底下每個檔的相對路徑與第一行說明。第一次接活先叫它。
- `asset_get(path)`：看一個資產檔的內容。`path` 是 assets 底下的相對路徑；超過 4000 字會截斷
  （回值多一個 `truncated: true`）。`../` 與絕對路徑會被擋。
- `scaffold(order_id, name, kind="cli")`：在 `team/projects/<order_id>/` 生出三個檔——
  `<name>.py`（`cli_argparse` 骨架＋`json_store` 合成的單獨一支）、`test_<name>.py`
  （照 `test_template`，import 的模組名換成 `<name>`）、`README.md`（照 `readme_template`，
  填好程式名與單號）。**已經存在的檔不蓋**，回 `created` 與 `skipped` 兩張清單。
  `kind` 目前只有 `cli`。
- `run_checks(order_id, main=None)`：在專案目錄跑 `team/assets/checks/run_tests.sh`；
  給了 `main` 再跑一次 `smoke_cli.sh <main>`。每支最多 60 秒。回
  `{"ok": 全過?, "steps": [{"name", "exit", "tail"}]}`，`tail` 是 stdout＋stderr 最後 1500 字。

## 一張單怎麼走

```
scaffold("ord-7", "todo")     # 生骨架，先跑一次 run_checks 確認起點是綠的
→ 用 fs 的 edit／write 改 todo.py、加 test_todo.py 的測試
→ run_checks("ord-7", main="todo.py")   # 語法、測試、冒煙一次做完
→ 綠了才回報／交件
```

`run_checks` 的 `ok` 就是驗收結果：`false` 時看 `steps[].tail` 的最後幾行，
`Traceback` 或「冒煙失敗：<哪一步>」會直接寫在裡面。

## 家當長什麼樣（team/assets）

開隊時 `presets/studio/assets/` 整包複製過去，全隊共用：

- `snippets/`：`cli_argparse.py`、`json_store.py`、`test_template.py`、`readme_template.md`。
  這些是**母本**，不要直接改；`scaffold` 會用它們生一份到專案目錄，你改生出來的那份。
- `checks/`：`run_tests.sh`（`py_compile` ＋ `unittest discover`）、`smoke_cli.sh`
  （`--help` 與 add → list → delete）、`README.md`（驗收標準四條）。
- `README.md`：每個資產是什麼、給誰用。

## 設定

```json
{"packs": ["pyshop", "fs", "code", "communication"], "tools": []}
```

改檔還是用 `fs` 的 `edit`／`write`，看骨架與存檔用 `code`。這包不改檔、不寄信。

## 約定與坑

- 骨架的主程式吃 `--file <資料檔>`，`main(argv)` 可以被測試 import；冒煙腳本也靠這個約定，
  才不會去動真的資料檔。改程式時盡量留著這兩點。
- 測試檔要叫 `test_*.py` 放在專案目錄，`unittest discover` 才找得到；一個測試都沒有時
  `run_tests.sh` 退 3，`run_checks` 就是不過。
- 單號只能用英數字、底線、點與減號，程式名要是合法的 Python 模組名（英文字母或底線開頭）。
- `run_checks` 的 `main` 只收專案目錄裡的檔名，不能帶 `/`。
- 檢查腳本跑完會清掉專案目錄的 `__pycache__`。
- 第一版只管 `kind="cli"` 的 Python 小程式：不管套件結構、相依安裝、非 Python 的專案。
