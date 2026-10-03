# 發散探針（probes）

← [proto7-1](../README.md)｜需求清單：[notes/infra-needs.md](../notes/infra-needs.md)

kernel／agent 在這裡**只是探針**：刻意寫得彼此不同，用來逼出 daemon／tick（含 tock、aos7-run、掛載、daemon 控制檔）還缺什麼。探針好不好不重要，重要的是每個 README 的「發現」。不打真 LLM。

跑：`python3 proto7-1/probes/run_all.py [名字 ...]`（全部約 100 秒；fleet 會吃滿多核約 20 秒）。每個探針自己開 `/tmp/aos7probe-*` 暫存根、跑完收乾淨；總結最後兩行檢查沒有殘留程序與暫存。check 只放基礎設施現在做得到的事（全綠＝現況），做不到的記成「量」與「發現」。probelib 建的 node 預設 `keep_ended_rounds` 很大（不把舊任務搬到 tasks-old/，探針好翻）；要量搬的行為就傳 `keep_ended_rounds=`。

> 各 README 的數字與發現是**修補之前**量的（10-03）；哪些後來修了，看 infra-needs.md 每條的「現況」欄。

| 探針 | 想逼出什麼 | 結果一句話 |
|---|---|---|
| [swarm](swarm/README.md) | 一回合幾十個短命任務（map／reduce） | 起 52 個 tick 133 ms；沒有「這批都結束」的訊號；一批 spawn 會被拆兩回合；4000 個舊資料夾讓 daemon CPU 10%→52%（已修：Q3 (a) tock 搬到 tasks-old/，tick／tock 回到 4／3 ms） |
| [event](event/README.md) | 外部丟檔要「盡快」處理 | 靠 tick-tock 延遲≈interval 一半、最慢一整個；沒有「現在開下一回合」的管道（已補 `wake`） |
| [subtimeline](subtimeline/README.md) | 任務執行中生／收子時間線 | 撿到很快（1～2 ms）；收掉時孤兒任務沒人管、資料夾被建回來（都已修：Q4 (a) node 消失就 kill；探針已改驗新行為）、pause 殘留 |
| [selfmod](selfmod/README.md) | 任務改自己的 tasks.json／timeline.json | interval 寫錯整條線永久停（已修）；tasks.json 多人改 lost update；壞欄位讓整個 tick 失敗（已修） |
| [sched](sched/README.md) | 排程型 kernel：round-robin、優先序、類 cron | pause 回條不代表已停（同時跑到 4 條>N=2）；「只跑一回合」要自己補（已補 `resume rounds`）；pause 不搶佔 |
| [multid](multid/README.md) | 一個 kernel 管多個 daemon（路二） | 空間外的 daemon 掛不到；pause 子 daemon 的 node 回 ok 卻沒用（已修）；daemon 死活要靠 pid |
| [nest3](nest3/README.md) | 路一三層巢狀 | 起得來、stop 0.1 秒收乾淨；kill 子 daemon 打斷它的 tick／tock（已修）；P-11 三層塌成兩層（已補 `subroot`）；頑固任務一半留孤兒 |
| [longrun](longrun/README.md) | 長任務與「每回合必須回報」的任務並存 | 慢一點的任務漏看 10～37% 的 tock；基礎設施不知道誰回報了；each 堆到 6～8 個（已補 `max_live`） |
| [lifecycle](lifecycle/README.md) | 重試、自我 restart、「別再起我」、crash loop | 自我 restart 好用；「別再起我」只有改 tasks.json 有效；crash loop 沒退避，每回合一個資料夾 |
| [fleet](fleet/README.md) | 一個 daemon 150 條時間線 | 最先撐不住的是每回合兩個 Python 程序（約 12 核）；啟動 12 秒沒 status、不收 stop（已修） |
| [polyglot](polyglot/README.md) | sh／bash／inst 寫的任務 | 只靠讀寫檔做得到；雙 fork 子程序 kill 不到（已修）；等 tock 要自己輪詢（已補 `aos7-wait-tock`） |
| [rename](rename/README.md) | node 搬家改名時有活任務 | 任務活著但環境變數指舊路徑、收不到 tock（已改：Q4 (a) 舊任務被 kill、新位置 keep 重起；探針已改驗新行為）；結束碼寫回舊路徑（已修）；別人的掛載斷掉 |
| smoke | probelib 本身 | — |

寫新探針：照 [probelib.py](probelib.py) 開頭的範例。
