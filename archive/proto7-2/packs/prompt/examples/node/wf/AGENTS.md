# demo node — AI 的入口

這個 node 的 AI 每回合先讀這裡，再往下一層走：

- 手上還沒做完的事 → `wf/SESSION-LOG.md`（只列 open，做完就刪）
- 別人寄來的信 → `wf/inbox/`（檔名以時間開頭，讀完搬進 `done/`）
- 等人做的事 → `wf/WAIT_USER.md`
