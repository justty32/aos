## 試用者
gpt-6-luna（新手）
## 分鐘
0.2
## 有沒有跑成功
成功，obs 的 `hello` 事件讀得出來，must 重送顯示 `dup: true`，並看到 `acked_upto: 1`。
## 對外指令數
2：`aos7-events pub`、`aos7-events read`
## 新概念數
5：events 夾、seq、obs／must、ack、event_id
## 卡點
無
## 五條分數（0–10，10 最好）
- 容易上手：9 指令可直接從 README 複製執行，成功結果也有範例。
- 容易理解：8 五個名詞都有解釋，但第一次仍要分清楚兩種帳與 ack。
- 複雜的藏起來：9 第一次跑不用啟 daemon，也不用處理檔案輪替細節。
- 外層簡單但全面：9 用 pub／read 就完成寫、重送、讀、ack。
- 要背的少：8 記住 pub 和 read 兩個子命令即可，其他選項照範例帶入。
- 平均：8.6
## ELI5
events 像一本可以記事情的小本子。用 `pub` 把事情寫進去，再用 `read` 看裡面寫了什麼。特別重要的事情要用 must 本，做完再說一聲 ack。相同的 event_id 重寫時，不會多出一筆。
## ELI5 之後還複雜嗎
是，因為實際使用時還要選 obs 或 must，並在處理完成後用正確的 seq ack。
