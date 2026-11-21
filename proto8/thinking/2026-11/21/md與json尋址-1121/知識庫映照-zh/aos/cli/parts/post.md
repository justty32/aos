# `knowledge/aos/cli/parts/post.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/parts/post.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

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
