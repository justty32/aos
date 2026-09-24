← [工具大開發時代](2026-09-24-tool-era/README.md)｜[notes 索引](README.md)

# 第一波第 2 隊：郵差、書記、驗收員、心跳（2026-09-24）

一句話：**模型只會往自己的 outbox 放一個檔（`team_say`）；搬信、改任務單、交驗收、記帳、看誰卡住、定時派工，全是不叫模型的機械程式。**

| 東西 | 一句話 | 規範 |
|---|---|---|
| `tools/team/`：`team_say` | 模型寄信：只寫 `team/outbox/<自己>/<id>.json`；收件人不在 `mail_to`、STATUS 不在六個＝`BadArguments`。`_common.py` 是 base 的逐位元組副本 | [mail.md](../spec/team/mail.md) |
| `lib/aos_team_post.py`：郵差兼書記（`aos-team post`、`mail`） | 投信、退件、照任務單的後續動作做事、交驗收工作並收結果、看停滯與期限、改專案的 SESSION-LOG／WAIT_USER | [post.md](../spec/team/post.md) |
| `lib/aos_team_verify.py`：驗收員（`aos-team verify`） | 照 `done_when` 跑固定檢查器（`file_exists`、`table_filled`、`contains`、`not_contains`、`wf_residue`、`wf_lint_strict`），每條 過／不過／檢查失敗 | [verify.md](../spec/team/verify.md) |
| `lib/aos_team_beat.py`：心跳（`aos-team beat`、`routine ls/add/rm`） | 照 `team/routines.json` 到期就以開單派出；在途不重派、done 才算、漏跑只補一次、模型提的要人批 | [beat.md](../spec/team/beat.md) |
| `lib/aos_team_requests.py` | 只加一行：申請種類 `routine` → `aos_team_beat:on_routine` | |
| `lib/test/test_team_{post,post_crash,post_live,beat,say,verify}.py`、`_team_util.py` | 124 條（見下） | |

狀態機一行都沒寫：郵差只叫 `aos_team_task` 的 `on_letter`、`letter_delivered`／`letter_picked_up`（只對帶 `dispatch` 的派工信）、`step`、`open_review`、`due_deadlines` 與 `aos_team_requests.handle`；去重用 `aos_team_format.already_delivered`；投檔用 `aos_agent_say.drop_new`。
`aos-team start`／`stop`（隊 1）會叫 `aos_team_post.start/stop` 與 `aos_team_beat.start/stop`：郵差每 1 秒、心跳每 60 秒一輪，都是 kernel 的反覆工作。

## 驗收 8 條

| # | 驗收 | 怎麼驗（測試） | 結果 |
|---|---|---|---|
| ① | `team_say` 名冊外收件人、非白名單 STATUS 回 `BadArguments`；信在別人的 outbox＝身分不符退信 | `test_team_say` RecipientTests／StatusTests；`test_team_post` `test_letter_in_someone_elses_outbox_is_bounced`（檔名寄件人段不符＝`BadId`）、`test_from_field_lies_is_not_sender`（`NotSender`），原檔進 `rejected/`、寄件格主人收到 FAILED | 過 |
| ② | 信進 `input/mail-<id>.json`、`post/sent/<id>.json` 有紀錄、原檔進 `outbox/done/` | `test_letter_goes_to_input_sent_record_and_done` | 過 |
| ③ | 崩潰窗口：投了、紀錄前 KILL＋收件人先收走（done/ 或 intake）不重投；紀錄後、搬檔後同樣 | `test_team_post_crash`：真 SIGKILL（`AOS_TEAM_POST_CRASH`），`delivered`（done／intake 兩種、派工信）、`recorded`、`moved`、`effect`、`job-submitted`，外加四個窗口連崩 | 過 |
| ④ | DONE → 提交一次性驗收（不同步跑）→ 不過＝「REQUEST 修正（第 2/3 次）＋逐條結果」；用完＝FAILED 給領隊與人 | `test_done_submits_verify_job_not_run_inline`、`test_verify_fail_sends_fix_then_failed`、`test_real_verify_command_result_is_collected` | 過 |
| ⑤ | 有 judge＝開審查子任務，逐條全 PASS 才 done | `test_judge_opens_review_all_pass_done`、`test_judge_one_fail_goes_back_to_worker`、`test_review_result_partial_rejected`、`test_no_reviewer_blocks` | 過 |
| ⑥ | 看停滯：卡在 think（健康不是 ok）與收單後沒進展都只報一次；在等別人的不報 | `WatchTests`：`test_unhealthy_reported_once`、`test_idle_after_pickup_reported_once`（有進展後再停＝新的一次）、`test_waiting_on_others_not_reported`、`test_watch_throttled` | 過 |
| ⑦ | 心跳：到期派出、在途不重派、DONE 才更新；漏三次只補一次並報告；模型提的列未經 answer 不跑 | `test_team_beat`：`test_due_dispatch_inflight_not_redispatched_done_updates`、`test_missed_three_dispatches_once_and_reports`、`ProposalTests`（沒答、答「不要」都不跑；答「批准」才跑） | 過 |
| ⑧ | 真 daemon＋kernel：郵差當反覆工作、信從 outbox 到對方記憶 | `test_team_post_live`（**假模型**、池式 kernel）：一封信到記憶；handoff → 工人在 bwrap 牢裡叫 `team_say` → 驗收是 kernel 一次性工作（ack 了）→ done；`aos-team init`／`start` 生的真家整圈。另有**真模型**跑 10 次（下一節） | 過 |

## 真跑（LiteLLM `deepseek-chat`，池式 kernel，`aos-team init`＋`start` 生的家）

腳本：daemon＋kernel（default 3 顆、llm 1 顆）→ `aos-team init`（lead、worker-1、reviewer，T1 的模板）→ `aos-team start`（成員＋郵差＋心跳）→ 人往 `team/outbox/human/` 放一份 handoff：「在專案建立 notes/hello.md：第一行寫「# 你好」，第二行寫一句自我介紹」，done_when＝`file_exists` ＋ `contains "# 你好"`。每次全部重置。

```text
started team-post-team-0bf290d5
started team-beat-team-0bf290d5
RUN 1 status=done seconds=31.4
--- aos-team mail
09-24 19:04  post → worker-1  REQUEST  t-0001 rev1  ✓收  任務 t-0001（rev1，第 1/3 次）：在專案建立 notes/hello.md：第一行寫「# 你好」，第二行寫…
09-24 19:04  worker-1 → 人  DONE  t-0001 rev1  已建立 notes/hello.md：第一行「# 你好」，第二行自我介紹。
09-24 19:05  post → 人  DONE  t-0001 rev1  t-0001 完成：在專案建立 notes/hello.md：第一行寫「# 你好」，第二行寫一句自我介紹。
--- 單子歷程
opened:queued → delivered:sent → picked_up:working → report:verifying → verified:done
--- 專案
# 你好
我是 worker-1，負責依來信處理專案裡的小任務。
```

**10 次：10/10 done**，每次 25～35 秒（中位 33.4），工人每次問模型 3 次（有一次 2 次）、領隊與審查 0 次。
（改 astra 必修之前在舊版 kernel 上也跑過 10 次：10/10，27～34 秒。）時間大多在模型；郵差每輪 1 秒、驗收工作排隊一格。

## 量測（`python3 rtime.py`＝子行程的 user＋sys；這台沒有 `/usr/bin/time`）

| 什麼 | cpu 秒 | 牆上 | 記憶體 |
|---|---|---|---|
| `aos-team post` 閒著一輪 | 0.034～0.035 | 37 ms | 25 MB |
| `aos-team post` 一封信／十封信 | 0.039／0.040 | 38～40 ms | 25 MB |
| `aos-team beat` 閒著一輪 | 0.029～0.030 | 30 ms | 20 MB |
| `aos-team verify`（file_exists＋wf_residue） | 0.033 | 31 ms | 21 MB |
| `wf_lint_strict`（空專案） | 0.061 | 59 ms | 19 MB |
| `team_say` | 0.018 | 18 ms | 17 MB |

郵差 1 秒一輪＝閒著每小時約 **125 cpu 秒**（約一顆核心的 3.5%）；多半是 Python 起行程與 import。心跳 60 秒一輪＝每小時約 1.8 cpu 秒。
工具描述：`team_say` 描述 138 字元，整段 function JSON 680 字元（約 170 token）。

## 六軸自評（axes.md §5；每軸 1～5、不加總）

**`team_say`**（工具）

| 軸 | 分 | 依據 |
|---|---|---|
| 1 LLM 參與 | 5 | 不叫模型 |
| 2 穩定 | 4 | 單元測試連跑 10/10；手動 10/10；錯誤一律最後一行 JSON。寫檔是 link 一步（原子），沒有專門的 KILL 測試；模型重送＝多一封新信（新 id，照 M14 不算不冪等） |
| 3 資源 | 5 | 0.018 cpu 秒；描述約 170 token |
| 4 快 | 5 | 18 ms |
| 5 人易懂 | 4 | 輸出一行 `queued <id> DONE → lead`；還沒新手試玩 |
| 6 邊界 | 4 | 只寫設定裡固定的 outbox，模型選不了路徑；關牢時就是 `/work/outbox` |

最弱兩軸：穩定（補一條 KILL 測試）、人易懂（試玩）。

**郵差兼書記**

| 軸 | 分 | 依據 |
|---|---|---|
| 1 LLM 參與 | 5 | 不叫模型 |
| 2 穩定 | 4 | 郵差測試連跑 10/10；投信路徑 6 個窗口真 SIGKILL；驗收工作的「起一半」「回音晚到」「結果壞」是改狀態檔模擬、不是真 KILL；astra 一輪抓到 11 條必修（全修）→ 先給 4 |
| 3 資源 | 2 | 閒著每小時約 125 cpu 秒（1 秒一輪）；改 5 秒一輪約 25 秒＝3 分 |
| 4 快 | 5 | 一輪 37 ms；信從 outbox 到 input 最多等一輪（1 秒）＋kernel 一格 |
| 5 人易懂 | 4 | `aos-team mail` 一封一行（誰寄誰、狀態、單號、收了沒）、`post` 一件事一行；紀錄要看 post.md 才懂 |
| 6 邊界 | 3 | 會寫別人的 `input/`（原子投檔、固定檔名）、任務單（經 aos_team_task）、專案的 SESSION-LOG／WAIT_USER（只改自己的區塊）；不進牢；outbox 搬檔不跟連結 |

最弱兩軸：資源（1 秒一輪起一個 Python：要嘛放慢、要嘛改成常駐）、邊界（牢外機械員，靠寫法守）。

**驗收員**

| 軸 | 分 | 依據 |
|---|---|---|
| 1 LLM 參與 | 5 | 不叫模型（judge 交給審查員） |
| 2 穩定 | 5 | 只讀、結果三態、結果檔暫存＋rename；測試連跑 10/10；郵差那端每次執行各寫各檔、驗身分 |
| 3 資源 | 5 | 0.03～0.06 cpu 秒 |
| 4 快 | 5 | 31～59 ms（wf_lint 對大專案會到秒級） |
| 5 人易懂 | 4 | 一條一行「過／不過／檢查失敗＋原因」、judge 列「略過」；沒試玩 |
| 6 邊界 | 4 | 只讀專案（相對路徑、關在專案裡；是防手滑不是沙盒）、只跑工具包自帶的快照；在牢外跑 |

最弱兩軸：人易懂、邊界（二波 `cmd_ok` 要進牢）。

**心跳**

| 軸 | 分 | 依據 |
|---|---|---|
| 1 LLM 參與 | 5 | 不叫模型 |
| 2 穩定 | 4 | 測試連跑 10/10；「派出」窗口真 SIGKILL；報告待寄是模擬崩潰；夏令、時區錯字有測 |
| 3 資源 | 4 | 閒著每小時約 1.8 cpu 秒（60 秒一輪） |
| 4 快 | 5 | 30 ms；到期到派出最多等一輪（60 秒） |
| 5 人易懂 | 4 | `routine ls` 一行一條（時間表、授權、上次、在途、下次）；沒試玩 |
| 6 邊界 | 3 | 以 human 名義往 `outbox/human/` 放派工申請（授權來源是人登記／人批准）、往 `team/post/outbox/` 放報告、寫自己的 `beat.json` |

最弱兩軸：邊界（代人寄申請：要不要給心跳一個自己的寄件身分，見要拍的）、穩定。

## astra 審查（[任務書](2026-09-24-tool-era/review-post-task.md)／[回報](2026-09-24-tool-era/review-post-astra.md)）

11 條必修全修；5 條建議修了 S1、S4，其他記在「沒做的」。

| # | 問題 | 改法 | 測試 |
|---|---|---|---|
| M1 | outbox 的 `done/`、`rejected/` 被換成連結，郵差搬檔會蓋到別人家 | `archive()` 用資料夾 fd、`O_NOFOLLOW` 搬；壞掉的先改名 `.bad-<ns>`；信檔是連結＝`NotARegularFile` 不讀 | `test_symlinked_done_folder_is_not_followed`、`test_symlinked_letter_not_read` |
| M2 | 共用 kernel 時別隊的 `v-t-0001-r1-a1` 撞名；`/a/team`、`/b/team` 的郵差撞名 | kernel 單名、行程名都帶團隊識別（真路徑雜湊）；`AlreadyExists` 要核對是自己的 inst | `test_kernel_submit_crash_recovery` |
| M3 | 另開行程「起了、還沒記 pid」崩了會重起；逾時重交兩支共寫一個結果 | 每次執行各有編號與結果檔 `result-<n>.json`；先記「要起」再起；逾時的行程整組砍掉 | 同上＋`test_retry_each_run_acked_separately` |
| M4 | ack 狀態跨重試沿用、晚到回音沒人收 | `acked` 記在每一次執行上；kernel 還記得的那次沒 ack 就不收尾 | `test_retry_each_run_acked_separately` |
| M5 | 結果檔不驗身分，`pass` 用 `bool()` | 驗 task／rev／attempt、`pass` 布林、逐條格式、`pass`＝逐條全過；不對＝`.bad`、換下一次 | `test_bad_result_not_trusted` |
| M6 | 同名例行刪了重加，派工 id 撞舊單 | id 帶「名字｜登記申請 id」 | `test_readded_routine_gets_new_tickets` |
| M7 | 心跳放棄一次之後、寄報告之前崩＝永遠不寄 | 報告先記進 `beat.json` 的 `reports`（跟放棄同一次寫），寄完才拿掉 | `test_failure_report_survives_crash` |
| M8 | `[{}]`、錯的 contract、重名欄會「填滿」 | 驗 contract、欄名非空不重複、至少一欄、列寬 | `test_team_verify` 原有 34 條＋邊界 |
| M9 | 書記吃掉人寫的空行、長得像的行 | 只改標記夾住的區塊，區塊外逐字不動；略過程式碼區塊；內容攤成一行 | `ClerkTests` 6 條 |
| M10 | 工作記了 complete、還沒搬就崩＝永遠不搬 | 看到 `complete` 就只補搬 | `test_complete_job_moved_after_crash` |
| M11 | 時區錯字默默變本機；夏令重複小時算錯 | `tz` 要載得起來；到期一律 UTC 比 | `test_daily_dst_repeated_hour`、`test_bad_timezone_rejected` |

另外照隊 1 的話改了：投信前先 `aos_team_format.already_delivered()`；`letter_delivered`／`letter_picked_up` 改成只對帶 `dispatch` 的派工信叫（隊 1 改了介面）；期限改用 `due_deadlines`。

## 跟共用格式不合、或我加的

1. **一次性例行叫 `once`，不叫 `at`**：申請的共同欄位已經有 `at`（寄出時間），撞名。catalog T-beat 寫的是 `at`。
2. **心跳的狀態檔 `team/beat.json`**（layout.md 列的是 `routines.json  schedule.json`）：`schedule.json` 沒用到；`routines.json` 只有郵差寫（`routine` 申請），`beat.json` 只有心跳寫。
3. **郵差自己的地方**（layout.md 只列了 `post/sent/`）：`team/post/{open,jobs,jobs-done,outbox}/`、`watch.json`、`clerk.json`、`.lock`、`post.inst.json`／`beat.inst.json`、`post.err`／`beat.err`；`team/.beat.lock`。`team/post/outbox/` 是**機械員寄信的入口**（`from: post`，可寄任何成員或人），心跳用它寄報告。
4. **心跳用 human 名義寄 handoff**：派工只能經 handoff 申請，而 `post` 不是能寄申請的身分；例行本來就是人登記或人批准的。單子的開單人因此是 human，完成信寄給人（每 2 分鐘一條的例行＝人的收件匣每 2 分鐘一封）。
5. **隊 1 的 `test_team_init.py` 改了兩處**：`team` 包現在在了，工具清單多 `team_say`；整合測試 `aos-team start` 之後把真郵差、心跳撤掉（那條用自己的假郵差一步一步走，兩個郵差會搶信）。
6. layout.md 寫事件紀錄可能在 `team/events/<名>.jsonl`；隊 4 放在成員家 `log/events.jsonl`。看停滯兩處都看。

## 沒做的

- `routine import`（把 workflows 的 `routines.md`／`schedule.md` 表抄過來）。
- `post/sent/` 30 天清理；`mail --follow` 每秒重讀全部紀錄（很多信時會慢）；每輪沒有處理上限（astra S2）。
- 模型版的 `verify` 自查工具、模型提 `routine` 的工具（現在只有申請格式；模板的 `may` 也還沒有 `routine`）。
- 書記的區塊單子很多時會超過 wf-lint 的 1 KB 條列門檻（astra S3）。
- 停滯的「進展」看的是成員整體（記憶、事件檔），不是這張單自己的（astra S1 後半）；第一波一人一張單夠用。
- 驗收員的路徑檢查是防手滑，不擋「檢查後、開檔前換連結」（在牢外跑，照 plan.md 第一波的信任前提）。

## 給收尾隊的列

- `proto5/README.md` 指令表：`aos-team post`（郵差走一輪）、`aos-team mail [--follow]`（一封信一行）、`aos-team verify t-0001`（固定檢查器驗收）、`aos-team routine ls/add/rm`（心跳的例行）、`aos-team beat`（心跳走一輪）。
- `lib/README.md`：`aos_team_post.py`（郵差兼書記）、`aos_team_verify.py`（驗收員）、`aos_team_beat.py`（心跳、routine 申請）；測試 `test_team_post.py`、`test_team_post_crash.py`、`test_team_post_live.py`、`test_team_beat.py`、`test_team_say.py`、`test_team_verify.py`、`_team_util.py`。code map 同。
- `tools/README.md`：工具包 `team/`：`team_say`（寄信，只寫自己的 outbox；`config.json` 由 `aos-team init` 寫）。
- `notes/README.md`：本報告、`2026-09-24-tool-era/review-post-task.md`／`review-post-astra.md`。
- `spec/team/README.md` 的〈各節〉表：`post.md`、`verify.md`、`beat.md` 三列（這三份是新檔，README 我沒動）。

## 要使用者拍的

1. **郵差多久一輪**：現在 1 秒（catalog 的例），閒著每小時約 125 cpu 秒（資源軸 2 分）。改 5 秒＝約 25 秒（3 分），代價是信晚到最多 5 秒。先照 1 秒做。
2. **心跳要不要有自己的寄件身分**：現在用 human 名義寄派工申請，單子的開單人是人、完成信寄給人。另一種是讓 `post` 也能寄 handoff（要改隊 1 的權限規則）。先照 human 做。
3. **一次性例行的欄位名**：`once`（避開申請的 `at`）。要不要把 catalog 改成 `once`？
4. **驗收的「檢查失敗」要不要用掉工人的次數**：現在算沒過（例如 wf 工具包快照壞了，工人三次後 failed）。另一種是檢查失敗直接 BLOCKED 給人、不扣次數。先照「算沒過」做。
5. **例行的完成信**：心跳派的單完成時人會收到一封 DONE。要不要讓心跳派的單完成時不通知人（只記在 `routine ls`）？先照現狀。
