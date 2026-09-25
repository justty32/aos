找到 **11 項必修**。全程未修改檔案；以靜態追蹤及純記憶體檢查確認，未跑會建立暫存檔的測試。

**必修**

1. **附件複製有換連結的時間差，可洩漏牢外檔案。**  
   [aos_team_commons.py:396](../../lib/aos_team_commons.py)：`realpath`、檔案種類、大小檢查完，才以路徑重新 `copyfile`。成員在中間換掉檔案或父目錄連結，郵差就可能把主機上的其他檔案抄到公開 inbox；檔案持續增長也能突破複製階段的大小限制。**修法：**以 outbox 的目錄描述符逐層開啟、禁止跟隨連結，以同一個已開啟的檔案檢查及限量讀取。

2. **commons 唯讀掛載仍可被另一個可寫掛載繞過。**  
   [aos_team.py:93](../../lib/aos_team.py)、[aos_agent_init.py:102](../../lib/aos_agent_init.py)：只擋 commons 在 project 裡，沒擋 project 在 commons 裡。例如 project 指向 `commons/lessons`，工人可從 `/work/ws` 改館藏；額外可寫 mounts 也未保護 commons。**修法：**檢查所有可寫掛載與 commons 的雙向 realpath 重疊，重跑 init 也要驗。

3. **其他圖書館員可以搶判。**  
   [aos_team_commons.py:550](../../lib/aos_team_commons.py)：只確認 `judge.json` 存在，沒核對 `team`、`to`。B 隊圖書館員可接受或退回指定給 A 隊的投稿，同隊未被指定者也可以。**修法：**在處理判決及重播結果前，核對指定隊伍、指定成員；冪等識別也包含隊伍身分。

4. **結果信可能永久漏寄。**  
   [aos_team_commons.py:450](../../lib/aos_team_commons.py)：先寫 `status`，到 `post_round` 才建立 notice。中間崩潰，下一輪直接略過；處理後面另一筆時出錯，也會丟掉前面尚未寄出的通知。**修法：**先持久化 notice，再標完成；或每輪重送同一 notice id，交給郵差去重。

5. **入庫與結果沒有共同的恢復紀錄。**  
   [aos_team_commons.py:480](../../lib/aos_team_commons.py)、[同檔:562](../../lib/aos_team_commons.py)：index 已更新、`result.json` 尚未寫時崩潰，機械重試會把已成功的投稿退成 Duplicate；模型判決重試則再產生一條。檔案 rename 後、index 前崩潰，也會留下未登錄館藏。**修法：**以投稿號記錄固定條目 id 與入庫階段，重試接續同一筆，完成後補結果及索引。

6. **模型接受時沒有重驗「完全重複」。**  
   [aos_team_commons.py:559](../../lib/aos_team_commons.py)：兩份相同內容都先進等待判決，第一份接受後，第二份仍可接受入庫。這不需要崩潰就能觸發。**修法：**在鎖內、入庫前重新比內容雜湊；先區分上一項的「同投稿恢復」，再拒絕其他投稿的重複內容。

7. **`README.md/x` 可讓圖書館持續卡住。**  
   [aos_team_commons.py:201](../../lib/aos_team_commons.py)、[同檔:310](../../lib/aos_team_commons.py)：只禁止附件恰好叫 `README.md`，其子路徑會通過。入庫先建立 README 檔，再建立附件父目錄就失敗；沒有結果紀錄，往後每輪重撞，排序在後的投稿也被擋住。**修法：**禁止第一段為 `README.md` 的附件路徑；單筆確定無效的投稿應退回，不能中止整輪。

8. **投稿 rename 後崩潰，恢復仍依賴原附件。**  
   [aos_team_commons.py:385](../../lib/aos_team_commons.py)：final 已發布、團隊紀錄尚未寫時崩潰，重試仍重新抄 outbox。若附件已刪除或更動，可能退件，已發布投稿卻繼續入庫，且沒有紀錄可追結果。**修法：**發現 final 已存在時，驗證投稿身分，直接從已發布快照恢復紀錄，不再讀原附件。

9. **隊伍識別會碰撞，可混用投稿與判決。**  
   [aos_team_commons.py:367](../../lib/aos_team_commons.py)：`Team-A`／`team-a`、`same.name`／`same-name` 都得到相同 tag；不同父目錄的同名隊也一樣。配上相同申請 id，會共用 final、暫存路徑和結果；判決 team 也分不開。**修法：**使用持久化且唯一的團隊識別，遇到既有投稿必須驗證來源，不能直接當作自己送過。

10. **import 撞 slug 會刪掉非來源條目。**  
    [aos_team_commons.py:630](../../lib/aos_team_commons.py)：人工或成員先建立 `playbook-lesson-1`，匯入時只要內容不同就直接 `remove`，沒有核對來源。先刪再新增也會在失敗時失去舊版。**修法：**記錄來源資料夾及來源項目識別，只更新同來源條目；其他撞名報錯或另取名。新版備妥後才替換舊版。

11. **首次初始化的空索引可能覆蓋已入庫資料。**  
    [aos_team_commons.py:102](../../lib/aos_team_commons.py)：多隊同時 `ensure()`，A 判定 index 不存在後暫停，B 建好並入庫，A 恢復仍會寫空索引。這些呼叫不全在 `.lock` 內。**修法：**初始化也共用鎖並在鎖內重新檢查，或採用不覆蓋既有檔案的原子建立方式。

**建議**

- [aos_team_commons.py:631](../../lib/aos_team_commons.py)：import 只比內容雜湊；只改經驗標題或部門會被當成沒變，標題、標籤、適用對象不更新。匯入更新應另外比較完整來源資料。
- [aos_team_commons.py:250](../../lib/aos_team_commons.py)：現在「像」還比較標籤、適用對象，規格仍主要描述標題。補同步規格；小集合只碰到一個泛用詞就可能叫模型，也值得增加最低交集門檻。
- [aos_agent_init.py:215](../../lib/aos_agent_init.py)：工具開關只處理模板中有 `only` 清單的 task 包，沒有 task 包或成員額外裝包不在這條路上。若支援自訂模板，應統一套用，或明列限制。

**不用修**

- 正常郵差入口會先查 `commons_write` 權限，普通成員不能靠手寫申請冒充圖書館員。
- 沒有 `judge.json` 會回 `NotAsked`；結果已完整落盤後，同申請可重播、另一申請會回 `AlreadyDone`。
- `judge.json → notice` 的恢復方向正確：下一輪會再提供相同通知 id，郵差負責去重。
- 正常開關三層覆蓋正確；關閉後重跑 init 會撤掛、更新工具設定，handler 也拒絕投稿。工具檔仍留著是規格明列的限制。
- 正常郵差入口會驗申請 id；slug、附件的絕對路徑與 `..` 有擋，未見單靠檔名字串穿越的路。
- 已安全複製的附件只准 `#!` 檔案帶執行位；複製使用新檔案，不會把來源硬連結關係帶進館藏。
- 一般機械審查以種類、正文及附件雜湊判完全重複，只換標題不會逃過。
- 目前 playbook 實際解析為 **14 條 lesson、1 條 workflow**，15 個 slug 不重複；README 導航檔有排除。