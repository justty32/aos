# metrics 效率量測包

← [modules](../README.md)｜進階（token 拆項、`--json`、算法、契約卡、退出碼）→ [ADVANCED.md](ADVANCED.md)

**一句話**：一把量尺。指一個資料夾給它，它看 AI 工作留下的紀錄，回答四個問題：**用了多少 token、同時跑幾個、花幾秒、重試幾次**。只讀不寫，可以一直重跑。

| 項目 | 內容 |
|---|---|
| 指令 | 只有一個：`aos7-metrics job PATH`（細節看 `--help`） |
| 依賴 | Python 3.11+ 標準庫 |
| 測試 | `python3 proto7-2/tests/run_all.py modules/metrics/tests -v` |

## 第一次跑（從 repo 根照抄，不用任何選項）
```sh
python3 proto7-2/modules/metrics/aos7-metrics job proto7-2/modules/metrics/baseline/r1/loop-gpt-6-sol
```
會印一行：
```text
loop-gpt-6-sol：1 件工作｜每件用 2590 token｜同時最多 1 個在問模型｜花 11.486 秒｜重試 0 次
```
逐格看：

| 這一格 | 意思 |
|---|---|
| `loop-gpt-6-sol` | 你給的資料夾名 |
| `1 件工作` | 找到幾件 AI 工作：同一張需求不管問模型幾次都算一件；沒掛在需求下的單次呼叫自己算一件 |
| `每件用 2590 token` | 平均一件工作花掉的 token（錢主要看這個） |
| `同時最多 1 個在問模型` | 最忙的那一刻，同時有幾件在等模型回答 |
| `花 11.486 秒` | 從收到工作到做完的秒數 |
| `重試 0 次` | 問了不只一次、重送、重跑的次數加總；0 最好 |

看到這一行就算成功。偶爾會多出尾巴：`另有 N 件還沒結束`、`N 次還沒結帳`（工作還在跑或中斷了）、`N 個檔讀不了已跳過`（紀錄檔壞了）。

## 量自己的資料
`baseline/r1/` 是 repo 附的範例：13 個真 AI 跑完留下的資料夾（2026-10-09 實跑的凍結副本）。

量你自己的：把 PATH 換成**你跑 AI 工作的那個資料夾**。認法：裡面（可能往下一兩層，例如 `llm/llmcall/`）看得到 `llmcall/`、`budget/`、`author/` 其中一個子資料夾。不確定是哪一層就指大一點的上層，工具會自己往下找；指錯了會印「沒找到 AI 工作紀錄」，換一層再試就好。

一次給多個資料夾，每個印一行，最後多一行「合計」：
```sh
python3 proto7-2/modules/metrics/aos7-metrics job proto7-2/modules/metrics/baseline/r1/*
```
```text
litellm-smoke：1 件工作｜每件用 1649 token｜同時最多 1 個在問模型｜花 1.67 秒｜重試 0 次
…（中間 11 行略）
loop-gpt-6-sol-r3：1 件工作｜每件用 2583 token｜同時最多 1 個在問模型｜花 9.043 秒｜重試 0 次
合計：13 件工作｜平均每件用 2491 token｜同時最多 6 個在問模型｜平均花 8.867 秒（最長 15.291 秒）｜重試 0 次
```

想知道**每個模型各用多少**（以前的 `aos7-usage`）：在後面加 `--by model`。下面把整個 baseline（`r1/*`）一起量，每行下面多列每個模型一行：
```sh
python3 proto7-2/modules/metrics/aos7-metrics job proto7-2/modules/metrics/baseline/r1/* --by model
```
```text
…（每個資料夾一行細節，略）
合計：13 件、13 次呼叫｜…｜重試 0｜帳差 0（帳 30739－回條 30739；另 1 次呼叫沒帳、用 1649 token）、缺口 0
　　model chatgpt-gpt-6-astra：3 次呼叫、用 7511 token、超支 0
…
　　model chatgpt-gpt-6-sol：4 次呼叫、用 9449 token、超支 0
```
這時每行會多出對帳的幾個詞：

| 詞 | 意思 |
|---|---|
| 回條 | 每次問完模型留下的用量單（真的用了幾個 token） |
| 帳 | 預算帳本記下的用量 |
| `帳差 0` | 帳－回條＝0，兩邊對得上；不是 0 才要查 |
| `另 1 次呼叫沒帳、用 1649 token` | 那次沒走帳本（這裡是 litellm-smoke，直接打代理）。它的 token 照樣算進模型那行，只是不進對帳，所以模型各行加起來 32388＝有帳 30739＋沒帳 1649 |
| 缺口、超支 | 有問沒回條的次數、用超過預留的 token；正常都是 0 |

換 `--by holder`／`day`／`hour` 改按呼叫者／日／時分。

到這裡就會用了。指錯資料夾（例如給了檔案）會印一行 `aos7-metrics: ` 開頭的白話，說錯在哪、該給什麼。

## 想做更多

想看更細（token 拆項、按模型分組與帳差、給程式讀的 JSON、四個數字怎麼算）→ [ADVANCED.md](ADVANCED.md)，或 `--help`。

