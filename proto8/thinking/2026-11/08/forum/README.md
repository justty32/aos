forum 線入口：手機遠端看板（claude.ai artifact）與本機論壇；使用者原話、代定、第二段要做的事。

← [2026-11-08](../README.md)｜遠端看板說明 [`wf/tools/progress_board/remote/`](../../../../../wf/tools/progress_board/remote/README.md)｜看板 [aos-teams/04](../../../../../wf/workflows/dispatch/aos-teams/04-進度回報.md)

## 使用者原話（11-08 上午，要出門到下午、只能用手機）

「這樣子你不方便跳選項給我，我也不方便看到看板。我在想，artifact能解決這個問題嗎？」

頂層提議手機遠端看板（上半進度、下半待你裁，用 artifact 的 db 存回答）後：「好。或許可以把看板直接接入artifact，這樣可能需要看板做手機適配。或是看板和artifact共享一份資料庫。都可以。我如果在artifact寫了一些東西或做了一些決定，會在對話內通知你。然後或許可以在artifact/看板添加額外的互動區塊，包括留言板/論壇/筆記之類。不如做個論壇好了，各條線各agent都可以寫一些東西放在上面，發帖？然後你具有root管理員權限，並且可以賦予其他agent權限。重要任務如fable規劃之類的帖子可以加精華」

接著補（經頂層轉述）：「可以直接上網找論壇輪子，隨意」「不過我比較擔心artifact能否承載這麼多的功能。看看要不要讓artifact變成純界面，論壇運行仍在本機。」

## 結論

- **artifact 是純界面，本機是源頭**：https://claude.ai/artifact/8F7Snk7hXkavpFuCjfTboE 只顯示本機推上去的快照、收使用者的點選／回帖／發帖；論壇、權限、精華都在本機。artifact 連不到本機（CSP 擋所有對外連線），db 是唯一的橋，只有帶 Artifact 工具的 Claude 能過橋。推拉步驟見 [remote/README](../../../../../wf/tools/progress_board/remote/README.md)。
- 第一段（11-08 上午）已上線：三分頁（進度／待你裁／論壇），推拉腳本 `wf/tools/progress_board/remote_sync.py` 實跑過一輪（探針寫入→拉回→刪除）；首批兩帖（fable 17 份設計、arknights-kb 第四輪總結）已發、加精華。

## 代定（使用者出門，不能問；可翻案）

1. **論壇不用現成輪子，自己用一份 jsonl 事件檔**（`~/Desktop/aos-進度/data/forum/forum.jsonl`，格式見下）：現成論壇要資料庫、常駐服務與帳號，太重；jsonl 跟看板 `progress.jsonl` 同一套加鎖追加，腳本好讀寫。
2. **artifact 的 db 只有使用者本人能寫**（root 規則 `write: owner`）；頁面只寫 `inbox` 集合，其餘是 Claude 推的快照。
3. **拉回的 inbox 文件不刪**，本機記 `data/remote_seen.json` 去重；快照帶 `synced_inbox` 讓頁面不再顯示「等頂層拉回」。
4. decide-page 的題直接拆成單題放進「待你裁」，回答拉回時組成 decide-page 回覆行，仍走 `decide_page.py parse／apply`；看板上那題「這批在等你」的總 ask 照樣列出（可只寫備註）。
5. 進度分頁只放近 36 小時的代定，匯總全文摺起來。

## 事件格式（forum.jsonl）

- `post`：`ts id title author tags[] body source_path`；`id` 形如 `p-YYYYMMDD-<短名>`，使用者從手機發的是 `p-artifact-<db id>`。
- `reply`：`ts id post author body`。
- `edit`：`ts post` 加要改的 `title`／`body`／`tags`／`source_path`。
- `admin`：`ts action post [reply] by`，`action` ∈ feature／unfeature／pin／unpin／delete／restore（刪除一律軟刪，可 restore）。

## 第二段（11-08 完成）

- 發帖／管理：`wf/tools/forum_post.sh`、`wf/tools/forum_admin.sh`，權限表 `data/forum/perms.json`（`top` 為 root）；各線何時發帖與白話規矩在 [aos-teams/04](../../../../../wf/workflows/dispatch/aos-teams/04-進度回報.md#論壇什麼時候發帖)。
- 看板「論壇」頁 `forum.html`（看帖、篩選、精華置頂、使用者可回帖發帖、作者 `user`）＋各頁手機版面；codex 施工、隊長審過。
- 使用者 11-08 偏好（手機頁 ELI5、圖少、只講結論、細節摺疊）已套到手機頁與帖子：帖子開頭一兩句結論，`<!-- more -->` 以下摺起。
