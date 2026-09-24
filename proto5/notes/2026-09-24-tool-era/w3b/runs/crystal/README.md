# T-crystal 真跑（第三波 W3-2，2026-09-24）

規範：[spec/team/crystal.md](../../../../../spec/team/crystal.md)。模型：LiteLLM `localhost:4000` 的 `deepseek-chat`。

## 怎麼重跑

1. 開團隊（lead＋worker-1，worker 開完就停，只收領隊開的單）：`~/tmp/w3b-crystal/setup.sh` 那套（教程 08 的名冊去掉 reviewer）。
2. 訓練組：`python3 train.py`（[sentences.json](sentences.json) 的 `train` 20 句一句一句 `aos-team ask`，等領隊處理完才送下一句；紀錄在 `train-log.jsonl`）。
3. 對照：`bash run.sh`（機械版一次、`--suggest-with-llm` 三次，再用 `eval.py` 拿測試組判）。
4. 刁鑽句：`python3 probe.py out/mech.json out/llm-*.json`。舊資料：`python3 old.py`。
5. astra 審查改完之後重判（不叫模型）：`python3 replay.py`，再 `python3 eval.py - out/mech.json out/llm-1.json out/llm-{1,2,3}-rescreen.json`。
6. 領隊用量原始紀錄：`python3 usage.py` → [train-usage.jsonl](train-usage.jsonl)。

## 結果

訓練組：20 句全部落穿（沒命中 19、否定 1），領隊開了 18 張單（4 種句型各 4 句全開單，而且每型都是同一種單；雜的 4 句開了 2 張）。
領隊處理這 20 句：想了 59 次、524k token（prompt 517,586＋completion 6,759）、模型時間 62.7 秒，約每句 3 次、26k token；逐次原始紀錄 [train-usage.jsonl](train-usage.jsonl)（59 行，工人停著、0 行）。

| 版本 | 候選 | 正例（12） | 負例誤觸（8） | 刁鑽句誤吃（8） | token | 秒 |
|---|---|---|---|---|---|---|
| 沒候選（範例規則） | 0 | 0/12 | 0/8 | — | 0 | — |
| 機械 | 4 | 12/12 | 0/8 | **0/8**（第一版 2/8：`../` 開頭的路徑 2 句；隊長把候選群組收窄成「專案裡的相對路徑」後重跑） | 0 | 0.04 |
| 模型 第 1 次 | 4 | 11/12 | 0/8 | 7/8 | 4238＋1372 | 4.1 |
| 模型 第 2 次 | 4 | 11/12 | 0/8 | 7/8 | 4238＋1153 | 3.9 |
| 模型 第 3 次 | 4 | 11/12 | 0/8 | 7/8 | 4238＋1153 | 3.7 |
| 機械（審查改完重判） | 4 | 12/12 | 0/8 | 0/8 | 0 | 0.04 |
| 模型 1～3 次（審查改完重篩，沒重叫） | **0**（4 條全丟） | 0/12 | 0/8 | — | 同上 | 同上 |

- 機械版刁鑽句：候選群組每一段要以英數或底線開頭（擋 `/`、`~`、`-`、`..`），8 句只吃「把x.md改名成y.md」這句正常的（`out/mech.json` 是收窄後重產的；舊的吃了兩句 `../`）。
- 模型版漏的那句都是 `把x.md改名成y.md`（沒空白）：模型的 pattern 把空白寫死。
- 模型版刁鑽句誤吃：`把 old.md 改名成 new.md，然後刪掉x.md`（`\S+` 把後半句吞進群組）、`-rf.md`、寫進 `/etc/passwd`、沒副檔名的 `out`、中文檔名。回測抓不到，因為 route.log 裡沒有這種句子。
- **審查改完（M2～M5、S3）之後**：機械版 4 條照樣全收、數字不變（訓練句都是一句一句送的，可信度全 `high`，內建反例一句都吃不到）。模型三次的 4 條全被內建反例丟掉（`\S+` 吃 `../x.md`、`~/x.md`、`-rf.md`…，每條 20～48 句），提案檔不寫（[out/llm-N-rescreen-report.json](out/)）。
- 機械版批准後真的 `aos-team ask "把 d.md 改名成 dd.md"` → `handoff`、`crystal-2`，領隊沒被叫；加「不要」照樣落穿（[out/approve.txt](out/approve.txt)）。

前兩波的舊 log（5 個團隊，共 10 行，只讀）：各團隊單獨跑都沒候選（落穿最多 2 句）。
五隊合起來：落穿 5（沒命中 3、否定 2），5 句都靠原文＋時間對回了信（可信度全 `medium`，沒有歧義）；教程那句「在專案建一個 hello.md，第一行寫「# 你好」…」
兩隊各說一次、領隊兩次開同一種單 → 提 1 條**整句照抄**的候選（同一句重複，推不出哪裡會變）。樣本太少，這條只證明「對得回來」，不代表值得固化。
