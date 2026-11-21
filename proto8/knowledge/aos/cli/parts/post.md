# aos-post: mailboxes and letters

A mailbox is a folder with tmp/, new/ and cur/; each letter is a folder with letter.json. aos-mailbox, aos-agent say and the llm kernel use it underneath.

```sh
aos-post init box
echo '{"q": 1}' | aos-post send --reply-to rbox box    # prints the letter name
aos-post take box                                     # claims the next letter (new/ -> cur/), prints its name
aos-post see box NAME            # {"sender": "...", "sent_at": "...", "reply_to": "../rbox", "body": {"q": 1}}
echo '{"a": 1}' | aos-post done --reply box NAME      # finish it; the answer goes to its reply_to
```

`take-all` claims every waiting letter. Without NAME, see and done use the first letter in cur/. `done --keep` keeps it in archive/. `done --reply` on a letter without reply_to finishes it and sends nothing. `regret box NAME` withdraws a letter not yet claimed. `send --ordered` puts a sequence number in front of the name. `send --in-reply-to NAME` records which letter this one answers. Exit 10 = no letter. `MailboxMissing`: run init first. `InputBad`: stdin is not JSON.

More flags: run `aos-post --help`.
