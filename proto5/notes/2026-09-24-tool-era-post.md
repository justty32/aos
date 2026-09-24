← [工具大開發時代](2026-09-24-tool-era/README.md)｜[notes 索引](README.md)

# 第一波第 2 隊：郵差、書記、驗收員、心跳（2026-09-24）

一句話：**模型只會往自己的 outbox 放一個檔（`team_say`），其餘搬信、改任務單、交驗收、記帳、看誰卡住、定時派工，全是不叫模型的機械程式。**

| 東西 | 一句話 | 規範 |
|---|---|---|
| `tools/team/`：`team_say` | 模型寄信：只寫 `team/outbox/<自己>/<id>.json`；收件人不在 `mail_to`、STATUS 不在六個＝`BadArguments` | [mail.md](../spec/team/mail.md) |
| `lib/aos_team_post.py`：郵差兼書記（`aos-team post`、`mail`） | 投信、退件、照任務單的後續動作做事、交驗收工作並收結果、看停滯與期限、改專案的 SESSION-LOG／WAIT_USER | [post.md](../spec/team/post.md) |
| `lib/aos_team_verify.py`：驗收員（`aos-team verify`） | 照 `done_when` 跑固定檢查器，每條 過／不過／檢查失敗 | [verify.md](../spec/team/verify.md) |
| `lib/aos_team_beat.py`：心跳（`aos-team beat`、`routine ls/add/rm`） | 照 `team/routines.json` 到期就以開單派出；在途不重派、done 才算、漏跑只補一次、模型提的要人批 | [beat.md](../spec/team/beat.md) |
| `lib/aos_team_requests.py` | 只加一行：申請種類 `routine` → `aos_team_beat:on_routine` | |

狀態機一行都沒寫：郵差只叫 `aos_team_task` 的 `on_letter`、`letter_delivered`、`letter_picked_up`、`step`、`open_review` 與 `aos_team_requests.handle`，投檔用 `aos_agent_say.drop_new`（照隊 1 給的話）。

（待補：驗收、真跑、量測、六軸、astra）
