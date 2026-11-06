# 2026-11-06 用 git 暫存 image 會不會膨脹失控、會不會慢、.gitignore 怎麼寫（git-image，I 隊：opus 隊長＋codex 隊員；沒改程式、沒改條文、沒新增任何 .gitignore）

← [2026-11-06](../README.md)｜[thinking](../../../README.md)｜背景：[portable-flow 02 image 模型](../../05/portable-flow/02-image-模型.md)、[04 跨電腦與 git](../../05/portable-flow/04-跨電腦與git.md)、[daemon-board](../daemon-board/README.md)、[os-concepts 10](../os-concepts/10-可遷移性原則草稿與root例外.md)、[os-impl](../os-impl/README.md)、[C-83](../../../../docs/CONCEPTS/01-設計理念/09-C-83.md)、[N-67](../../../../docs/NORMS/10-基礎設施-定義與工作區/09-N-67.md)、[apply-ideas 01 § C](../apply-ideas/01-逐項落點.md)

## 使用者原文（11-06）

> 派一隊幫我去看看，綜覽我們產出的檔案，討論在極限狀況下，我們使用git去暫存，是否會導致膨脹無法遏止，或者是git處理起來很慢，並提出gitignore建議。

## 一句話結論（白話）

如果什麼都不改，也就是留全部歷史、只用現有範本，git 會越跑越大，而且是平方成長：50 隻 agent 跑一週，`.git` 約 70 GiB，gc 一次要半天。

只要做兩件事就不會失控：

1. 用推薦的 `.gitignore`（[04](04-gitignore建議.md)）。
2. image 放在專門的 repo，每次凍住只留最新一份（[05](05-其他手段與衝突.md) 手段 2）。

做了之後，git 的大小就等於一份 image，一週約 0.8 GiB，不會跟著跑多久一直長。

image 本身還是會線性長。長的是 agent 的記憶 `history.jsonl`，這部分本來就該長。

## 三個要點

1. **長最快的是兩個檔：`history.jsonl` 和 `think/request.json`。**兩個都是只增不減的大檔，每次 commit，git 都要再存一份整份的新版本。
   - 信件沒有累積：處理完就刪，`archive/` 目前沒有程式在用。
   - log 跟 eca 的 `live.jsonl` 擋掉就沒事。
2. **`git gc` 救不回來。**50 隻 agent 的檔案同名，git 打包時配不到「自己上一版」來壓縮差異。
   - 把配對視窗調大可以壓回來，但單執行緒要慢 8 倍以上，不划算。
3. **`git status` 跟 `commit` 不是瓶頸。**
   - 慢的是 `add`（要整份重讀大檔）和 `gc`（最慢）。
   - 自動 gc 很快就會被觸發：A 模式第 9 次 commit 就觸發，archive 變體第 2 次就觸發。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-盤點表](01-盤點表.md) | daemon stack、agent-fsm 小格：每類檔會不會長、名字唯一嗎、該不該搬；三個跟預設不同的事實 |
| [01-續-盤點表](01-續-盤點表.md) | eca、LLM kernel、ws、定義資料夾、任務書列了但程式裡沒有的、試驗場現況 |
| [02-極限分析](02-極限分析.md) | 50 隻 × 一週 × 每小時 commit：為什麼平方膨脹（公式）、gc 為什麼救不回、哪一步會慢 |
| [03-實測數據](03-實測數據.md) | 六種做法 A～F 的實測主表、delta 視窗實驗、一週外推與方法、沒量到的 |
| [04-gitignore建議](04-gitignore建議.md) | 建議的 `.gitignore` 逐條理由、絕對不能擋的、跟現有 `stack.gitignore` 的差別 |
| [05-其他手段與衝突](05-其他手段與衝突.md) | 專門 repo、只留最新、depth 1、關自動 gc、分段、log 上限、archive 輪替、LFS 不值得——各附門檻；跟 N-16／C-17／C-79／N-67 的衝突 |

**實測腳本放在 repo 裡**：[scripts/](scripts/)（`gitimage_bench.py`、`summarize.py`、`run_all.sh`；照 `/tmp/i-team/sim/` 的路徑寫的，要重跑先複製過去）。原始量測結果 `results*.jsonl`（約 1 MB）留在 `/tmp/i-team/sim/`，重開機就沒了；結論都在 03。

## 方向題（推薦放第一）

1. **image 的 git 要不要留歷史？**
   - **推薦：只留最新一份。**image 用專門的 repo，每次凍住做一個沒有上一版的新 commit，再 `push --force`；想留的版本打 tag。
     - 好處：git 大小等於一份 image，不用改程式，也幾乎不用 gc。
     - 代價：不能 `git log` 看 image 怎麼一路變過來，舊版只剩打了 tag 的那幾份。
   - 另一個選擇：留完整歷史。
     - 要一起改：history 分段、request.json 改成可以重建，打包時還要調大視窗。
     - 代價：要改程式，gc 會慢好幾倍；一週約 1 GiB，跑越久越大。
2. **`think/request.json` 要不要改成可以重建？**改法是 wait 格找不到這個檔，就退回 think 重組；這樣 `.gitignore` 才能把它擋掉。
   - **推薦：先不改。**題 1 選「只留最新」的話，它只多佔一份 image 的大小（一週約 0.4 GiB），不值得為此動程式。
   - 改的話：image 小一半，也順便解掉跟 C-79「實例不存 source 的副本」的小衝突（[05](05-其他手段與衝突.md)）。
3. **ws 的 `.trash/` 要不要跟著 image 搬？**
   - **推薦：擋掉不搬**，由人定期清。
   - 代價：搬過去之後就不能還原上一台丟進垃圾桶的檔。

**後續（等使用者點頭才做，這次沒做）**：
- 照 04 更新範本 `cmd/aos-agent/stack.gitignore`。
- `cmd/aos-agent/docs/04-搬家.md` 補一段「image 用專門 repo、只留最新」。
- 推薦跟 no-pid P8 的搬家食譜同一個 commit。
