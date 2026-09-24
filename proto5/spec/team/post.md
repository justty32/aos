← [team](README.md)｜信與申請：[mail.md](mail.md)｜任務單：[tasks.md](tasks.md)

# 郵差兼書記：`aos-team post`

一支機械程式，kernel 反覆叫（`aos-team start` 登記），**不叫模型**。
**多久一輪**：`team.json` 的 `"post": {"interval_s": 5}`（1～3600，沒寫＝5 秒，2026-09-24 使用者裁）；改了要 `aos-team stop` 再 `start` 才生效。
成本（實測）：閒著一輪約 0.035 cpu 秒 → 5 秒一輪＝閒著每小時約 **25 cpu 秒**（1 秒約 125 秒）；代價是信平常多等一個巡查週期。
程式：[`lib/aos_team_post.py`](../../lib/aos_team_post.py)。第 2 隊，2026-09-24 第 1 版。

## 一輪做什麼（照順序）

1. **接著做上一輪沒做完的**：`team/post/open/<紀錄 id>`（空檔）＝那份紀錄還有動作沒勾、或投給成員的信還沒被收走。
2. **收驗收結果**：`team/post/jobs/<工作 id>/result.json` 出現了＝叫 `aos_team_task.step(…, verified)`，照回的動作做。
3. **收 outbox**：`team/outbox/<名>/*.json`（每個成員、`human`、心跳 `beat`）＋`team/post/outbox/*.json`（機械員以 `post` 名義寄的信，現在沒人用）。照 id 裡的時間排。
4. **看停滯與期限**（每 30 秒一次，見下）。
5. **書記**：任務單或問題資料夾有變，就重寫專案的 `SESSION-LOG.md`／`WAIT_USER.md` 那一節。

同一時間只有一個郵差：`team/post/.lock`（拿不到＝略過、退 0）。

## 一封信怎麼投（每步都可重跑）

1. `post/sent/<id>.json` 已在＝處理過了，跳到 4。
2. 讀驗（`aos_team_format.read_outbox_file`；符號連結或不是一般檔＝`NotARegularFile`，不跟過去讀）；不合＝**退件**：寫紀錄（`kind: rejected`、`code`、`message`）、原檔搬進 `outbox/<名>/rejected/`、寄一封 `FAILED` 給那一格的主人（不明的格子＝寄給人），內文是代號＋白話。
3. 叫 `on_letter`（回報、恢復）→ **投**：收件人是成員＝`members/<名>/input/mail-<id>.json`（`aos_agent_say.drop_new`，不覆蓋）；是 human＝`team/human/<id>.json`（信＋`header` 那一行）；是 `beat`＝**不投**，只寫投遞紀錄（`where: null`）。
   投之前先查「是不是已經投過了」：還在 input、已收進 `input/done/`、或停在收件人 `state.json` 的 intake——有一個就不投。
   → 先放 `open/` 標記、再寫紀錄（含全部後續動作，每件 `done: false`）。
4. 原檔搬進 `outbox/<名>/done/`（退件＝`rejected/`）。outbox 是模型寫得到的：用資料夾的 fd 搬、不跟符號連結；`done`／`rejected` 被換成連結或檔＝先改名成 `<名>.bad-<ns>`、再建真的資料夾。
5. 逐件做後續動作，**做一件勾一件**（勾之前崩了＝重做同一件；每一件都冪等）。
6. 投給成員的信：之後每輪看 `input/mail-<id>.json` 還在不在，不在了＝收件人收走了，記 `picked_up_at`。
   動作都勾了、也收走了＝紀錄 `complete: true`、拿掉標記。

讀驗之後再驗一次路徑、操作與假信頭（`BadPath`、`NotAllowed`、`ForgedHeader`，[wall.md §3](wall.md)）。
申請一樣：讀驗 → `aos_team_requests.handle`（權限＋處理函式）→ 紀錄（`kind: request`）→ 搬 → 做動作。處理函式丟 `TeamError`＝退件（同上）。

**郵差自己生的信**（後續動作、退信、停滯通知）：id＝`<紀錄 id>.e<第幾個動作>`，重跑算出來一樣；投法同上、也有自己的紀錄，所以不會重投。
動作帶 `dispatch`（派工信，[tasks.md](tasks.md)）的：投到之後叫 `letter_delivered(lay, 信, dispatch)`、被收走之後叫 `letter_picked_up(lay, 信, dispatch)`（`dispatch` 記在紀錄裡）；別的信不叫。

## 後續動作

照 [tasks.md〈後續動作〉](tasks.md)：`letter`、`verify`、`open_review`、`step`。動作做不到（例如收件人的家不在、單子壞了）：那一件記 `error`、勾掉，另寄一封 `FAILED`「郵差做不到 …」給人。

**`verify`**＝建一份一次性驗收工作並提交，**不在郵差裡跑**；下一輪起收結果檔。做法見 [verify.md〈郵差怎麼交驗收〉](verify.md#郵差怎麼交驗收)。

## 投遞紀錄 `team/post/sent/<id>.json`（只有郵差寫）

```json
{"_metainfo": {"_type": "aos_team_post_record", "_version": 1},
 "id": "1790000000123456789-4242-worker-1", "kind": "letter", "recorded_at": "2026-09-25T10:00:01+08:00",
 "where": "…/members/lead/input/mail-1790000000123456789-4242-worker-1.json",
 "watch_pickup": true, "picked_up_at": "…",
 "from": "worker-1", "to": "lead", "status": "DONE", "reply_to": "t-0001", "rev": 1, "text": "…", "at": "…",
 "effects": [{"do": "verify", "task": "t-0001", "rev": 1, "attempt": 1,
              "id": "1790000000123456789-4242-worker-1.e0", "done": true, "result": "v-t-0001-r1-a1"}],
 "complete": true}
```

`kind`：`letter`（信，含郵差生的；派工信多 `dispatch`）、`request`（申請；多 `request_kind`）、`rejected`（多 `code`、`message`）、`notice`（停滯 `stall.…`、期限 `expire.…`）。
`aos-team mail` 讀的就是這些。

## 看停滯（每 30 秒一次）

只看 `sent`／`working`、`waiting_on` 是 null 的單（blocked、waiting_user、驗收或審查中、結束的都不報）：

- **健康不是 ok**（`aos_agent_status.collect` 的 health：retrying、paused、bad、kernel 壞、沒登記…）**連續** 60 秒以上（代碼換來換去也算同一段，回到 ok 才重算）；
- 否則**超過 `limits.stale_minutes` 沒進展**：最後進展＝單子最後一次變動、成員記憶檔最後一次寫、事件紀錄（成員家 `log/events.jsonl`）最後一次寫，取最晚。

→ 寄一封 `PROGRESS`「觀察到停滯：…」給每個領隊（負責人自己是領隊就不寄給自己）與人。**同一次只報一次**：通知的紀錄 id 由「單號、rev、attempt、哪一種、從什麼時候起」算出來，紀錄在＝報過了；有了新進展又停住＝新的一次。
只報看到的事，不替負責人說 BLOCKED。

期限：`aos_team_task.due_deadlines` 回的每一件＝先開一份 `notice` 紀錄（動作是 `step` 那個 `expire` 事件），再照做；崩了照樣做完、不會丟通知。

## 書記

專案裡有 `SESSION-LOG.md`（或 `wf/SESSION-LOG.md`）才寫，沒有不建。書記**只改自己的區塊**，區塊外逐字不動：

```text
## 最新進度

<!-- aos-team 書記：這一段自動產生，別手改 -->
- [t-0001 IMPORT.md] 做事中（worker-1，第 1/3 次）→ 等 worker-1 回報：把 workflows 的 heartbeat 包導入…
<!-- /aos-team 書記 -->
```

- 每張還沒結束的單一行；`WAIT_USER.md` 的 `## 待使用者項` 每個 open 的問題一行 `- [q-0001] worker-1 問：…（選項：…） → aos-team answer q-0001 "…"`。一行都沒有＝區塊裡寫 `（目前無）`。
- 還沒有區塊：放在那個標題底下（那一節只有一行 `（目前無）` 就換掉它）；標題也沒有就加在檔尾。找標題、找區塊都略過 ``` 程式碼區塊。
- 內容攤成一行（換行、連續空白變一格），插不進新標題或新清單；內容一樣不重寫（看任務單與問題資料夾的 mtime，有變才重算）。

## 指令

| 指令 | 做什麼 |
|---|---|
| `aos-team post [--quiet]` | 走一輪，一件事一行（`投遞`、`申請`、`退件`、`驗收`、`停滯`、`書記`）；`--quiet` 給 kernel |
| `aos-team mail [--last N] [--to 名] [--from 名] [--task 單號] [--full] [--json] [--follow]` | 一封信一行（誰寄誰、狀態、單號、收了沒、內文開頭）；退件也一行 |
| `aos-team start`／`stop`（第 1 隊） | 會叫 `aos_team_post.start(團隊資料夾)`：登記 kernel 反覆工作 `team-post-<資料夾名>-<團隊識別>`（同名已在且是這個團隊的＝already started）；stderr 在 `team/post/post.err` |

退出碼：0＝走完一輪（個別檔的問題寫 stderr、留著下一輪再試）；1＝名冊讀不到這種整輪做不了的。
測試用：環境變數 `AOS_TEAM_POST_CRASH=<點>` 在那個點 SIGKILL 自己（`delivered`、`recorded`、`moved`、`effect`、`job-submitted`、`beat-dispatch`）。
