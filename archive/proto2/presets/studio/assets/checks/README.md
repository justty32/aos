# 驗收標準（checks/）

一張單要能交，四件事全部要過。qa 照這張表看，dev 交件前自己先跑一次。

| # | 標準 | 怎麼確認 |
|---|---|---|
| 1 | 語法沒問題 | `run_tests.sh` 的 `py_compile` 那段過（退出碼不是 1） |
| 2 | 測試全過 | `run_tests.sh` 的 `unittest discover` 全過；**一個測試都沒有算不過**（退 3） |
| 3 | 真的跑得動 | `smoke_cli.sh <主程式.py>`：`--help` 開得起來，add → list → delete 三步走得完 |
| 4 | 有 README | 專案目錄有 `README.md`，寫了用法與測試怎麼跑 |

## 怎麼跑

```sh
cd team/projects/<單號>
bash ../../assets/checks/run_tests.sh
bash ../../assets/checks/smoke_cli.sh todo.py
```

`pyshop` 包的 `run_checks(order_id, main="todo.py")` 會幫你在專案目錄叫這兩支，
回每一步的退出碼與輸出尾巴，不必自己拼路徑。

## 退出碼

- `run_tests.sh`：0 全過、1 有東西沒過、2 目錄或檔案不對、3 沒有測試。
- `smoke_cli.sh`：0 全過、1 某一步失敗（會印是哪一步）、2 參數或主程式不對。

## 幾個約定

- 主程式吃 `--file <資料檔>`，冒煙才不會去動真的資料；沒有 `--file` 時冒煙會改在暫存目錄裡跑。
- 測試檔叫 `test_*.py`，放在專案目錄，`unittest discover` 才找得到。
- 檢查腳本會把跑出來的 `__pycache__` 清掉，專案目錄保持乾淨。
