# `knowledge/aos/cli/parts/post.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/parts/post.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/parts/post.md#/…` 對的就是它。改請改正本，再照 [README](../../../README.md) 的做法跟上這份。

---

**`#/aos-post: mailboxes and letters`**

# aos-post：信箱與信

信箱是一個有 tmp/、new/ 和 cur/ 的資料夾；每封信是一個有 letter.json 的資料夾。aos-mailbox、aos-agent say 和 llm kernel 底下都用它。

```sh
aos-post init box
echo '{"q": 1}' | aos-post send --reply-to rbox box    # prints the letter name
aos-post take box                                     # claims the next letter (new/ -> cur/), prints its name
aos-post see box NAME            # {"sender": "...", "sent_at": "...", "reply_to": "../rbox", "body": {"q": 1}}
echo '{"a": 1}' | aos-post done --reply box NAME      # finish it; the answer goes to its reply_to
```

`take-all` 領走所有在等的信。沒給 NAME 時，see 和 done 用 cur/ 裡的第一封信。`done --keep` 會把它留在 archive/。對沒有 reply_to 的信用 `done --reply`，會把它結束但什麼都不寄。`regret box NAME` 收回一封還沒被領走的信。`send --ordered` 在名字前面加一個序號。`send --in-reply-to NAME` 記下這封信是在回覆哪一封。結束碼 10 = 沒有信。`MailboxMissing`：先跑 init。`InputBad`：stdin 不是 JSON。

更多旗標：跑 `aos-post --help`。
