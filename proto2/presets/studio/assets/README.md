# 工作室資產（team/assets）

這裡是**專接 Python 小程式的工作室**的家當。開隊時整包複製到 `team/assets/`，全隊共用、隨時可讀。
不確定有什麼就叫 `asset_list`，要看內容就叫 `asset_get`（都在 `pyshop` 包）。

## snippets/ — 常用骨架，複製後改名

給寫程式的人（chief、dev-a、dev-b）。**不要直接改這裡的檔**，它們是母本；
`scaffold` 會用它們在 `team/projects/<單號>/` 生一份出來，你改生出來的那份。

| 檔 | 是什麼 | 給誰 |
|---|---|---|
| `cli_argparse.py` | 一支 CLI 小程式的骨架：`add`／`list`／`delete` 三個子命令，`main(argv)` 可以被測試 import。 | dev |
| `json_store.py` | 讀寫一個 JSON 檔的 `load(path, default)`／`save(path, data)`，路徑自己傳、不寫死。 | dev |
| `test_template.py` | unittest 樣板：`setUp` 用 `tempfile` 開自己的暫存資料檔，測完自動清掉。 | dev、qa |
| `readme_template.md` | 小程式 README 樣板：用法、測試怎麼跑。`{{NAME}}`／`{{ORDER}}` 由 `scaffold` 填。 | dev |

`cli_argparse.py` 裡 `# SNIPPET-MERGE: json_store` 那行，`scaffold` 會換成 `json_store.py`
`# SNIPPET-BODY` 以下的內容，合成單獨一支可以跑的程式。
`test_template.py` 裡的 `MODULE = "cli_argparse"` 會被換成你的程式名。

## checks/ — 驗收腳本

給 qa 與 pm（dev 交件前也該自己先跑一次）。都在專案目錄 `team/projects/<單號>/` 底下跑。

| 檔 | 做什麼 | 退出碼 |
|---|---|---|
| `run_tests.sh [專案目錄]` | `python3 -m py_compile *.py` 加 `python3 -m unittest discover -v`，最後印一行總結。 | 0 全過／1 有錯／3 沒有測試 |
| `smoke_cli.sh <主程式.py>` | 對 CLI 小程式跑 `--help`，再走 add → list → delete 三步冒煙。 | 0 過／1 某一步失敗／2 參數或檔案不對 |
| `README.md` | 驗收標準：什麼樣才算能交。 | — |

`pyshop` 包的 `run_checks(order_id, main=?)` 就是幫你在專案目錄叫這兩支，不必自己拼指令。
