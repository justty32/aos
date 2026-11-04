<!-- 這是 snippet，複製後改名成專案的 README.md；{{NAME}} 與 {{ORDER}} 由 scaffold 填掉。 -->
# {{NAME}}

一句話說它做什麼（單號 {{ORDER}}）。

## 用法

```sh
python3 {{NAME}}.py --file items.json add "買牛奶"
python3 {{NAME}}.py --file items.json list
python3 {{NAME}}.py --file items.json delete 1
```

`--file` 是資料檔路徑，不給就用目前目錄的 `items.json`。

## 測試怎麼跑

```sh
python3 -m unittest discover -v      # 全部測試
python3 -m py_compile *.py           # 只檢查語法
bash ../../assets/checks/run_tests.sh    # 工作室的標準檢查（語法＋測試）
bash ../../assets/checks/smoke_cli.sh {{NAME}}.py   # CLI 冒煙
```

## 還沒做的

- 這裡列已知的限制，交件時要講清楚。
