## 試用者
Claude Haiku（新手）
## 分鐘
0.2
## 有沒有跑成功
成功，`check` 印「OK：連結、活狀態與佔位檢查通過」（退出碼 0），`state` 寫入續行點 `wf/handoffs/2026-10-09/STATE.md`，`cat AGENTS.md` 看得到入口。
## 對外指令數
3：`init`、`state`、`check`
## 新概念數
7：node、工作流樹（`wf/`）、open 項（SESSION-LOG／WAIT_USER）、續行點（STATE／NEXT-SESSION）、flavor（heartbeat／multi-agent／dev）、workflows 模板與 `AOS7_WF_HOME`、〔導入判斷〕與佔位（`{{`、`（未定：…）`）
## 卡點
1. [init 輸出] 印「未定 97 處」，緊接 `check` 卻「{{：剩 0 處」並 OK；以為 OK 代表都填好了，後來才懂「未定」是另一種、check 不管。約 2 分鐘。
2. [init 輸出「已處理導入判斷」五行] 看不懂「導入判斷」是什麼、是我要處理還是工具已處理；「一字不差的那幾段」無法判斷。約 2 分鐘，略過。
3. [`cat AGENTS.md`] 入口又連到 STRUCTURE.md、WORKFLOWS.md、INDEX.md 一堆檔，不知道人該先讀哪個。約 2 分鐘。
4. [「看成果」] 要跑 `examples/minimal/run.sh`，怕它寫進 repo，沒跑。
5. [「要懂的四個詞」] open 項「只列還沒做完的」，沒說怎麼知道哪些沒做完。約 1 分鐘。
6. [`check` 的 OK] 不查「未定」，README 有寫但第一次跑步驟裡不容易注意到。
## 五條分數（0–10，10 最好）
- 容易上手：8 三條指令照抄就通。
- 容易理解：5 導入判斷、未定、open 項要讀完整份 README 和入口檔才拼得出意思。
- 複雜的藏起來：6 init 輸出與 AGENTS.md 漏出不少名詞。
- 外層簡單但全面：7 一條 init 裝出完整一棵樹，state 接續行點。
- 要背的少：8 只要記三個。
- 平均：6.8
## ELI5
這是幫 AI 助手準備「工作筆記資料夾」的小工具。第一次 init 一次，目錄和入口都放好。每次收工用一句話告訴它「停在哪、下一步做什麼」，它記下來；下次 AI 開工先看這句就知道從哪接。最後 check 看到 OK 就表示資料夾沒壞。
## ELI5 之後還複雜嗎
是，要懂「未定」「導入判斷」「open 項」才放心用。
