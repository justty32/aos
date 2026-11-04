## 試用者
Claude Haiku（新手）
## 分鐘
0.2
## 有沒有跑成功
成功，第一次跑整段 exit 0：send 印 JSON 與信檔路徑，read 列序號 1，done 印「已辦結…已回 DONE 給 alice」，audit 印 0。
## 對外指令數
6：`send`、`read`、`done`、`audit`、`roster`、`team`
## 新概念數
10：信（唯一 id）、STATUS（REQUEST／PROGRESS／DONE／BLOCKED／NEEDS-USER／FAILED）、信箱與 done（讀過≠辦完）、序號快照（done 要先 read）、終局回覆與 reply-to／re、必達提醒（events must）、團隊與 `--up` 上游、ROSTER、復原日誌、AOS_MAIL_ROOT／`--root`
## 卡點
1. [`aos7-mail --help`、`send --help`] 沒有 help，直接印「請設定 --root 或 AOS_MAIL_ROOT」退出 2。約 1 分鐘。
2. [契約卡、已知限制] D1、D2、F4、F5、W0、「審查 1–7」等代號沒定義。約 2 分鐘。
3. [done] 序號必須來自最近一次 read 的快照，否則「請先 read」退出 2；README 沒說為什麼。約 1 分鐘。
4. [`--up`] ROSTER 從哪來、指向哪、團隊信箱只收廣播的規則不清楚（沒實際試 team／roster）。
## 五條分數（0–10，10 最好）
- 容易上手：7 整段貼上就過，三個日常指令名字直觀；但要先懂 REQUEST 與 done 的關係。
- 容易理解：5 五個概念段清楚，但代號與團隊、上游說明不足。
- 複雜的藏起來：5 進階、契約卡、已知限制和日常用法同一頁，D2、F5 等內部細節一眼就看到。
- 外層簡單但全面：6 日常三指令簡單，涵蓋團隊、orders、復原；但沒有 --help。
- 要背的少：5 6 個指令、6 種 STATUS、退出碼 0／1／2、done 三種參數形式、先 read 規則。
- 平均：5.6
## ELI5
這是讓程式之間用檔案寄信的小郵局。寫一句話、指定寄給誰和狀態，信就放進對方資料夾。對方用 read 看信，做完用 done 歸檔並回一封 DONE 給寄件人。最後 audit 查還有沒有沒結案的請求。
## 日常 3 指令＋進階 3 個算不算仍複雜
是，日常三個要先懂 REQUEST 與序號快照，roster／team 還要懂 ROSTER、團隊與上游，概念明顯比三個動詞多。
## ELI5 之後還複雜嗎
是，ELI5 只講寄、看、結案，STATUS、序號快照、團隊上游仍要靠 README 才用得對。
