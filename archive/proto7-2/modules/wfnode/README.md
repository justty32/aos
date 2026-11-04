# node 工作流包（wfnode）

← [modules](../README.md)｜進階（選項、init 填了什麼、出錯怎麼看、契約卡）→ [ADVANCED.md](ADVANCED.md)

**一句話**：替 AI 準備一個「工作筆記資料夾」，並讓你每次收工記一句「停在哪、下一步做什麼」；AI 下次開工先看這句就知道從哪接。

## 第一次跑（約 3 分鐘）

要有 Python 3、bash，和工作流模板 `~/repo/workflows`（沒有就先 `git clone git@github.com:justty32/workflows.git ~/repo/workflows`）。先 `cd` 到 aos repo 根（看得到 `proto7-2/` 的那層），再照抄這三行；全部只寫到 `/tmp/mynode`，不動 repo：

```bash
proto7-2/modules/wfnode/aos7-wfnode init  /tmp/mynode                              # 1. 裝好資料夾
proto7-2/modules/wfnode/aos7-wfnode state /tmp/mynode '寫完第一版，下一步跑測試'   # 2. 記一句「停在哪」
proto7-2/modules/wfnode/aos7-wfnode check /tmp/mynode                              # 3. 體檢
```

你會看到（數字可能不同）：

```text
裝好了：/tmp/mynode（AI 開場讀 AGENTS.md；人不必讀）
空格：97 處寫著「（未定：…）」＝工具查不到、之後由你或 AI 慢慢補；不影響使用，check 也不檢查它
下一步：aos7-wfnode check /tmp/mynode
已記到 wf/handoffs/2026-10-09/STATE.md（AI 下次開場從這裡接）
待辦清單：AI 手上 0 件（wf/SESSION-LOG.md）、等人做 0 件（wf/WAIT_USER.md）
OK：資料夾沒壞（連結都通、清單沒有做完沒刪的、模板記號都處理了）。「（未定：…）」空格 97 處不在檢查範圍
```

**看到最後一行 `OK` 就成功了。** OK 的意思是「資料夾沒壞」，不是「每個空格都填好了」——那 97 處空格本來就留給之後慢慢補，第一次可以完全不管。

看成果：`proto7-2/modules/wfnode/aos7-wfnode state /tmp/mynode`（不給句子＝印出剛才記的那句）。試完 `rm -rf /tmp/mynode` 即可。

## 只有三個指令

| 指令 | 做什麼 | 什麼時候用 |
|---|---|---|
| `init <資料夾>` | 裝好資料夾；**重跑安全**，只補缺的，你寫過的不動 | 新 node 一次 |
| `state <資料夾> '一句'` | 記一句「停在哪、下一步」；不給句子＝印出最新那份 | 每次收工、被打斷前 |
| `check <資料夾>` | 體檢：印 `OK`＝沒壞；不 OK 會指出哪個檔第幾行、該怎麼改 | 隨時 |

## 要懂的三個詞

1. **node**：AI 住的資料夾（就是你給 init 的那個路徑）。
2. **續行點**：你用 `state` 記的那句「停在哪」；一天一份，AI 開場先看最新那份。
3. **空格**：init 查不到的資訊寫成 `（未定：…）`，之後誰知道誰補；不填也能用。

裡面其他檔（`AGENTS.md`、`wf/` 底下一疊 md）是**給 AI 讀的**，人不必讀；想瞄一眼，只看 `AGENTS.md` 最上面「開場與入口」那段就夠。

## 想做更多

日常用不到；需要時看 [ADVANCED.md](ADVANCED.md)：`--flavor` 等選項、一鍵示範、待辦清單規則、init 填了什麼、出錯怎麼看（給腳本用）、契約卡。測試：`python3 proto7-2/tests/run_all.py modules/wfnode/tests`。
