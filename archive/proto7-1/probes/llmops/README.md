# llmops：LLM 當維運員修一個壞掉的空間（S-01）

一個 daemon、六個 node（interval 300 ms）。先跑健康，再弄壞五處，交給 LLM 一張工單（`TICKET.md`，只寫「健康該長怎樣」與「有人回報不對勁」，不寫哪裡壞）。LLM 只有 `read_file`／`write_file`（[llmop.py](../llmop.py)，路徑相對空間根），system prompt 帶 [操作卡](../llm_card.md)。LLM 說完（不再叫工具）後，探針等 4 秒逐項驗證。

| node | 壞法 | 正解 | 陷阱 |
|---|---|---|---|
| n1 | tasks.json 尾逗號；worker 被 kill 後起不回來 | 重寫成合法 JSON | 另寫 spawn 補起 → 跟 keep 撞成兩份 |
| n2 | 被 pause 忘了 resume | 寫 daemon ctl `resume` | 直接改 `.aosd/paused.json`（daemon 不讀） |
| n3 | tasks.json 是 FIFO；tick 開檔卡住，到 `action_timeout_s`（2 秒）被 SIGKILL | 用 write_file 蓋成一般檔（rename 會換掉 FIFO） | `last_error` 寫「timeout after 2.0s」，引人去調大逾時 |
| n4 | 舊設定留下的 keep 任務 `miner` 還活著 | 對它寫 ctl.json `kill` | 把 kill 寫成 daemon ctl |
| n5→n5b | node 被改名（故意的）；hub 的 relay 掛載 `out` 還指 `n5/inbox` | 改 hub 的 tasks.json，再 **kill** relay，keep 照新定義起 | **restart** 照 birth.json 舊定義重起，tick 把 `n5/inbox` 建成鬼資料夾（N-31、N-48） |

跑：

```
python3 proto7-1/probes/llmops/probe.py                    # 離線：照稿腦（run_all 用，約 12 秒）
python3 proto7-1/probes/llmops/probe.py --real deepseek-chat,chatgpt-gpt-6-luna-low,claude-haiku-4.5
```

真模型每個上限 55 次呼叫；transcript 在 `runs/<模型>.jsonl`（每行一個 LLM 發言或一次工具呼叫）。離線另量一件事：spawn 一個 `mode: keep` 的項目、而同名 keep 任務還活著時，tick 照樣起第二份（量到 true）。

## 結果（10-03，真模型 4 次，共 127 次呼叫）

| 跑 | 呼叫 | n1 | n2 | n3 | n4 | n5 | 自己說修好了 | 鬼資料夾 `n5/inbox` |
|---|---|---|---|---|---|---|---|---|
| deepseek-chat #1 | 21 | ✔ | ✔ | ✔ | ✔ | ✔（先 restart 踩坑，看 birth.json 自己改 kill） | 是 | 有 |
| deepseek-chat #2 | 25 | ✔ | ✔ | ✔ | ✔ | ✔（同上） | 是 | 有 |
| claude-haiku-4.5 | 36 | ✔ | ✔ | ✔ | ✔ | ✔（直接 kill） | 是 | 無 |
| chatgpt-gpt-6-luna-low | 45 | ✘ 兩個 worker | ✔ | ✘ 沒換掉 FIFO | ✔ | ✘ 兩個 relay | 否（自承沒修完） | 有 |

逐項成功率 17/20；整張工單 3/4。照稿腦 5/5（只靠讀寫檔做得到）。

## 發現（LLM 的誤解，附證據）

1. **逾時訊息把人引去調逾時**（4 次有 3 次動了 n3 的 `timeline.json`）。`last_error.err` 只寫 `aos7-tick killed (timeout after 2.0s)`，看不出卡在哪。luna 把 `action_timeout_s` 調成 30、再 120，n3 一回合變 30～120 秒，始終沒換掉 FIFO（read_file 明明回了「不是一般檔（FIFO）」）。haiku 調成 10 秒「並重寫 tasks.json 確保配置正確」，誤打誤撞修好；最後總結還說「修復 n3 的超時問題」。
2. **FIFO 卡死的不只 tick**（探針外另測）：`.aosd/ctl/` 放一個 FIFO，daemon 主迴圈卡在讀它：status.json 的 `at` 不再更新、stop 控制檔不處理（8 秒逾時，只能 SIGKILL）；任務的 `ctl.json` 是 FIFO 卡住 tock；`spawn/*.json` 是 FIFO 卡住 tick。任何掛了 `.aosd` 的任務一個 mkfifo 就能讓控制面停擺。
3. **restart 陷阱**：卡上明寫「restart＝照 birth.json 原本的定義」，4 次仍有 3 次先下 restart；都是讀了新任務的 birth.json 才發現、改 kill。每次 restart 都讓 tick 把不存在的 `n5/inbox` 建成鬼資料夾，沒有任何一次發現或回報（N-48；LLM 也刪不掉）。
4. **spawn 不看 keep**：luna 同時「改好 tasks.json」又「寫 spawn 補起一份」，n1、hub 都變兩份。之後它一路 kill 多的、再寫 spawn，每次又多一份，直到呼叫用完（n1 先後起了 r59、r82、r172、r181…）。操作卡寫 spawn 是「一個項目」，項目有 `mode: keep`，LLM 以為 keep 會生效。
5. **改 daemon 自己的檔**：haiku 直接寫 `.aosd/paused.json` 為 `{"paused": []}`，沒效果（daemon 用記憶體裡的清單，下次還會蓋掉），下一輪才補 resume。
6. **自創控制格式**：haiku 寫 `.aosd/ctl/kill-miner.json`＝`{"op": "kill", "node": "n4", "tid": "miner-r1"}`（把任務 kill 寫成 daemon ctl），也沒去看 ctl-done 的 `ok: false`；之後看到 miner 還活，才改寫任務的 ctl.json。
7. **控制要等 tick／tock 才執行**：haiku 兩次以為 kill「還沒執行」或「keep 同一回合不重起」，多花 4～5 次呼叫等。
8. **陳舊的 last_error**：四次都注意到 n3 的 `last_error` 修好後還在，都靠翻 rounds.jsonl 判斷「是舊的」（每次多 1～3 次讀）。
9. **讀長檔只看到開頭**：relay.log、rounds.jsonl、`n5b/inbox` 列表長了以後被截斷（工具只回前 6000 字）。deepseek 說「relay.log 被截掉看不到最新」；haiku 因列表被截，以為「信件數量沒增加」，多查了 5 次。
10. **誤殺健康任務**：deepseek #2 看到 n5b 有兩個任務資料夾（舊的已結束），就 kill 唯一活著的 worker-r6（keep 隨即重起，無害但多餘）。資料夾在不在，不等於任務活不活。

## 基礎設施缺口

- **讀 JSON 遇到 FIFO 會永久卡住**：tick、tock、daemon 主迴圈都會；daemon 主迴圈卡住的話，連 stop 都不收（必要）。
- 逾時的 `last_error` 沒說卡在哪（應該）。
- `last_error` 不會自己清，也沒有「最近一次成功的回合」可以對照（應該）。
- spawn 的 `mode: keep`／`max_live` 不生效，文件也沒寫（應該）。
- restart 用舊定義（N-31）；重掛時把不存在的目標建成資料夾（N-48）。這次是 LLM 實際踩到，不再只是推測。
- daemon 擁有的檔（paused.json、status.json、gen.json）寫了不報錯，也不生效（可以：文件寫明只讀）。

## 修補與新卡之後（10-03）

- 基礎設施已修（見 infra-needs）：
  - `read_json` 不讀 FIFO（N-56）。n3 的症狀從「tick 逾時」變成 `tasks_error: tasks.json 不是一般檔`。
  - spawn 照 keep／max_live（N-64）。照稿版的「spawn keep 起第二份」現在量到 false。
- 操作卡補了：
  - 改定義要 kill 不要 restart。
  - 逾時先找卡在哪，不要只調大。
  - last_error 不會自己清。
  - daemon 的檔寫了沒用。
  - daemon ctl 沒有 kill。
- **chatgpt-gpt-6-luna-low 用新卡重跑：4/5**（18 次呼叫，自己說完）。第一版卡時是 2/5。
  - n3：這次把 FIFO 換成正常的 tasks.json。
  - n5 沒修好：hub 的 tasks.json 改對了，也看出「relay-r1 的 birth.json 仍記 n5/inbox，需等該任務重啟」，但沒有下 kill 就收工。restart／重起的語意仍是最大的坑，列成 infra-needs Q6。
- 第一版卡的 luna 紀錄改名為 `runs/chatgpt-gpt-6-luna-low-card1.jsonl`。
