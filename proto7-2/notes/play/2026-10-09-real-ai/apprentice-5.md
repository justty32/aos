# 2026-10-09 學徒自我改進對照實驗（AP5）——未完成

**結論：還沒有結論，A／B 對照沒跑完。** 機制與題目都做好了，但 session 要關，四組試跑都只做完第 1 題第 1 輪就停了。
**已確認的一件事：新題目真的「沒寫在需求裡、一定會撞」**：luna 與 sol-low、A 與 B 共 4 組，第 1 題第 1 輪全部在第 2 關答案檢查被擋，而且三條郵局慣例（done/、. 開頭、teams/）都出現在錯誤訊息裡；文字交件格式 4/4 一次過第 1 關（AP4 luna 一半輪次死在 JSON 括號）。
**接手**：照 worktree 根的 `HANDOFF-AP5.md` 重跑；每組約 30～60 分鐘，要跑 luna／sol-low 各 A、B 試跑，再挑一個模型每組 ≥5 次。

← [真 AI 第一圈](README.md)｜上一輪：[apprentice-4](apprentice-4.md)（AP4）｜意圖卡：[apprentice-5](../../intents/apprentice-5.md)｜證據：[evidence/apprentice5/](evidence/apprentice5/)

## 做了什麼（已 commit 在 loop13/AP5）

- **交件格式**：三關多收「每段一個檔」文字候選（`=== 路徑 ===` 一段一個檔、`=== row ===`、`=== report ===`；v／rid／kind／name 取自需求）。開頭是 `{` 就照舊 JSON，舊候選一字不改；不是 UTF-8 仍歸 json 錯。`propose --format text` 讓提示改講文字格式、候選存 `.txt`；不給時提示 bytes 不變（固定雜湊測試照過）。限制：段頭行不能出現在檔案內容裡。測試 `tests/test_author_textfmt.py` 14 條。
- **4 題知識型的坑**：`examples/aos-tool-mail{count,sent,open,status}/`，fixture 用真 `aos7-mail` 寄、辦、team 廣播產生，再手放一份 `.tmp/` 寫一半的信。郵局三條慣例需求裡不寫（測試鎖住需求不含 done／.tmp／teams／team／歸檔）：辦結的信在 `<人>/inbox/done/`、`.` 開頭的檔與資料夾不是信、根目錄 `teams/` 不是人。答案檢查器跑主樣本＋三個「只放大一條慣例、答案不變」的變體，錯誤訊息講出慣例本身；另有「增減」變體答案會變、不印期望答案（擋背答案），檢查器自帶參考解自檢。測試 `tests/test_author_aos_mail.py` 8 條。
- **審查標準補一句**（試跑中發現）：審查人看不到答案檢查器，第 1 次試跑 astra 把「略過 teams 與 . 開頭」判成「錯誤：」退件（[證據](evidence/apprentice5/aborted-pilot1/rounds.jsonl)）。`REVIEW_CRITERIA` 加：答案對不對以第二關檢查器為準，為通過它而略過／納入某些檔不算錯誤。兩組都受影響、不偏袒。
- astra 審查 4 項中度問題：固定答案能過（已修：增減變體）、需求「全郵局」有歧義（已改「所有人信箱裡」）、段頭出現在內容裡會誤拆與非末段檔不能無尾換行（列為格式限制，寫進 ADVANCED）。

## 試跑到哪（第 3 次試跑，前兩次因上面兩個問題中止）

| 組 | 題 1 第 1 輪 | 擋在 | 錯誤訊息裡的慣例 | 學徒 token |
|---|---|---|---|---|
| luna A1 | 沒過 | ② answer＋test | done、dot、teams | 5 904 |
| luna B1 | 沒過 | ② answer | done、dot、teams | 6 142 |
| sol-low A1 | 沒過 | ② answer | done、dot、teams | 5 588 |
| sol-low B1 | 沒過 | ② answer | done、dot、teams | 5 593 |

- 三關第 1 關（格式）4/4 過：文字格式拿掉了 AP4 的 JSON 括號雜訊（至少這 4 輪）。
- 每輪學徒約 6 千 token，比 AP4（luna 每題 4～6 萬）小得多，因為需求短。
- **還沒有**：第 2 輪起、第 2～4 題、B 組帶技能的效果、雜訊（題 1 A／B 差）、任何通過率。

## 花費

學徒 node 上 21 次真 AI 呼叫、134 060 token（含三次試跑；審查 astra-high 也記在內）。codex 工人（寫碼 3 次、審查 1 次）不在這本帳。

## 下一步

照 HANDOFF 跑完試跑 → 挑差異清楚的模型加到每組 ≥5 次 → `compare5.py` 出表 → 補本報告開頭三行。判準不變：題 2～4 的平均輪數差要大於題 1 兩組的差（雜訊）。
