## 試用者
Claude Haiku（新手）
## 分鐘
0.2
## 有沒有跑成功
成功，`now --force` 看到「220 則 → 21 則（摘掉 200、open 20 全留），102580 → 4013 bytes，原文在 compact/archive/<job>.jsonl」，與 README 預期一致；未啟動背景程序。
## 對外指令數
3：`aos7-compact now`（含 `--dry-run`、`--force`）、`forget`、`watch`；第一次跑另需照抄 `examples/make_demo.py` 造資料。
## 新概念數
4：node（README 沒先解釋）、open 項、archive／`ref://compact/<job>`、dry-run 與 force。
## 卡點
1. README 沒說 node 是什麼，猜是資料夾，約 1 分鐘。
2. `now --dry-run` 說原因是「大小超過 16384」，正式跑 JSON 的 `trigger` 卻是 `"force"`，README 沒說明差異，約 1 分鐘。
## 五條分數（0–10，10 最好）
- 容易上手：8 照抄四行，預期輸出對得上。
- 容易理解：6 node、open、archive、觸發原因要自己拼湊；dry-run 與 force 的 trigger 不一致。
- 複雜的藏起來：6 第一次跑沒露出 llmcall／budget，但同份 README 很快帶出 compact.json、stage 相似度、bigram、退出碼 0–3。
- 外層簡單但全面：7 三指令加 demo 就涵蓋整理、預覽、忘掉、常駐。
- 要背的少：6 指令只 3 個，但概念與設定鍵多。
- 平均：6.6
## ELI5
這是一個幫電腦「整理舊筆記」的小工具。筆記太多時，它先把舊原文收進備份資料夾，再換成一則短摘要，最近的和還沒做完的都留著。先用 `now` 看計畫，確定後 `now --force` 真的整理。要還原，原文都在備份裡。
## ELI5 之後還複雜嗎
是，第一次跑簡單，但 README 後面接 llmcall、budget、真 AI、pending 與退出碼，概念一層包一層。
