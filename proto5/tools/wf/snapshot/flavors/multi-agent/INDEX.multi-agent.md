| `inbox/` | agent 之間的信件收件匣：頂層＝未處理、`done/`＝已處理；使用方式 [workflows/inbox/](workflows/inbox/README.md) |
| `tools/` | inbox 腳本：`inbox_send.sh`（原子投遞一封信）、`inbox_read.sh`（唯讀列出未處理的信）；升級五通道後另加 `inbox_mail.sh`、`inbox_poll.sh`、`inbox_team.sh`、`notify_watch.sh`、`test_inbox.sh` |
