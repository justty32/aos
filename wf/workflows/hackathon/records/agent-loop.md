# 在 `aos exec` 上做一條會動的 agent loop

> **以下是風格模擬，不是本人的意見。** 底下寫「Carmack persona 這一路」「Pike persona 這一路」，指的是那個場地跑出來的東西，不是本人的看法。

| 項目 | 內容 |
|---|---|
| 題目 | 在現有的 `aos exec` 之上，真的做出一條會動的 agent loop——包含 LLM 呼叫與 tool 呼叫（不改 C++、不 build）。對到 roadmap 的 **T5** |
| 開場日期 | 2026-08-26 |
| 環境 | 原生 Linux（Manjaro，不是 WSL）；參賽者是 **Claude Opus 5 sub agent**（不是 codex）；**有網路**；四位平行；場地是 repo 的完整複製品，**不准 build、不准改 C++**（場地裡沒有 `CMakeCache.txt`，這是刻意的） |
| 機器上的模型 CLI | `codex 0.149.1`（`/usr/bin/codex`）、`claude 2.1.246`（`~/.local/bin/claude`）、`pi 0.84.2`；LM Studio（`localhost:1234`）沒在跑 |
| 狀態 | 第 1 輪已完成，共兩輪 |

| 參賽者 | persona | 場地 |
|---|---|---|
| p1 | John Carmack | `~/aos-hack/agent-loop/p1` |
| p2 | Rob Pike | `~/aos-hack/agent-loop/p2` |
| p3 | Joe Armstrong | `~/aos-hack/agent-loop/p3` |
| p4 | Julia Evans | `~/aos-hack/agent-loop/p4` |

---

## 分檔目錄

> 2026-09-25 整理：原檔 163 KB 超過門檻，按標題逐字拆進 [`agent-loop/`](agent-loop/01-第-1-輪紀錄.md)；本檔只留前言與目錄（原路徑保留當入口）。

| # | 檔 | 段落 | 大小 |
|---|---|---|---|
| 1 | [01-第-1-輪紀錄.md](agent-loop/01-第-1-輪紀錄.md) | 第 1 輪紀錄 | 3.3 KB |
| 2 | [02-2-坑的總表.md](agent-loop/02-2-坑的總表.md) | 第 1 輪紀錄 ＞ 2. 坑的總表 | 19.0 KB |
| 3 | [03-3-好處.md](agent-loop/03-3-好處.md) | 第 1 輪紀錄 ＞ 3. 好處 | 5.4 KB |
| 4 | [04-4-壞處.md](agent-loop/04-4-壞處.md) | 第 1 輪紀錄 ＞ 4. 壞處 | 3.9 KB |
| 5 | [05-5-題目那四個問題.md](agent-loop/05-5-題目那四個問題.md) | 第 1 輪紀錄 ＞ 5. 題目那四個問題 | 2.7 KB |
| 6 | [06-2-真模型跑不跑得起來哪一支以及.md](agent-loop/06-2-真模型跑不跑得起來哪一支以及.md) | 第 1 輪紀錄 ＞ 5. 題目那四個問題 ＞ ② 真模型跑不跑得起來、哪一支，以及那四件事 | 7.7 KB |
| 7 | [07-3-aos-exec-這一層讓你.md](agent-loop/07-3-aos-exec-這一層讓你.md) | 第 1 輪紀錄 ＞ 5. 題目那四個問題 ＞ ③ `aos exec` 這一層讓你手寫了幾次同樣的東西 | 6.8 KB |
| 8 | [08-6-仍然不知道的.md](agent-loop/08-6-仍然不知道的.md) | 第 1 輪紀錄 ＞ 6. 仍然不知道的 | 3.4 KB |
| 9 | [09-規格級的發現.md](agent-loop/09-規格級的發現.md) | 規格級的發現 | 6.2 KB |
| 10 | [10-六exit-欄位是回合後的資訊而.md](agent-loop/10-六exit-欄位是回合後的資訊而.md) | 規格級的發現 ＞ 六、`exit` 欄位是「回合後」的資訊，而復原需要的是「回合中」的資訊 | 6.1 KB |
| 11 | [11-第-1-輪評分與意見.md](agent-loop/11-第-1-輪評分與意見.md) | 第 1 輪評分與意見 | 5.2 KB |
| 12 | [12-p3joe-armstrong.md](agent-loop/12-p3joe-armstrong.md) | 第 1 輪評分與意見 ＞ p3（Joe Armstrong persona） | 5.1 KB |
| 13 | [13-二aos-agent-該收掉什麼.md](agent-loop/13-二aos-agent-該收掉什麼.md) | 第 1 輪評分與意見 ＞ 二、`aos agent` 該收掉什麼——有優先序的清單 | 6.6 KB |
| 14 | [14-三哪條路最值得繼續走.md](agent-loop/14-三哪條路最值得繼續走.md) | 第 1 輪評分與意見 ＞ 三、哪條路最值得繼續走 | 3.7 KB |
| 15 | [15-五規格級的發現11-條逐條表態.md](agent-loop/15-五規格級的發現11-條逐條表態.md) | 第 1 輪評分與意見 ＞ 五、〈規格級的發現〉11 條，逐條表態 | 8.8 KB |
| 16 | [16-六哪個坑是致命的哪個只是麻煩.md](agent-loop/16-六哪個坑是致命的哪個只是麻煩.md) | 第 1 輪評分與意見 ＞ 六、哪個坑是致命的、哪個只是麻煩 | 7.4 KB |
| 17 | [17-下一輪的資料包.md](agent-loop/17-下一輪的資料包.md) | 下一輪的資料包 | 3.3 KB |
| 18 | [18-2-repo-裡已經有答案的.md](agent-loop/18-2-repo-裡已經有答案的.md) | 下一輪的資料包 ＞ 2. repo 裡已經有答案的 | 18.9 KB |
| 19 | [19-3-兄弟專案裡可以抄的.md](agent-loop/19-3-兄弟專案裡可以抄的.md) | 下一輪的資料包 ＞ 3. 兄弟專案裡可以抄的 | 10.3 KB |
| 20 | [20-4-還是查不到的.md](agent-loop/20-4-還是查不到的.md) | 下一輪的資料包 ＞ 4. 還是查不到的 | 3.8 KB |
| 21 | [21-第-1-輪白話導讀.md](agent-loop/21-第-1-輪白話導讀.md) | 第 1 輪白話導讀 | 6.9 KB |
| 22 | [22-三看到的錯誤訊息各是什麼意思.md](agent-loop/22-三看到的錯誤訊息各是什麼意思.md) | 第 1 輪白話導讀 ＞ 三、看到的錯誤訊息各是什麼意思 | 4.6 KB |
| 23 | [23-四所以呢.md](agent-loop/23-四所以呢.md) | 第 1 輪白話導讀 ＞ 四、所以呢 | 5.7 KB |
| 24 | [24-3aos-agent-該收掉什麼.md](agent-loop/24-3aos-agent-該收掉什麼.md) | 第 1 輪白話導讀 ＞ 四、所以呢 ＞ （3）`aos agent` 該收掉什麼的優先序 | 6.4 KB |
