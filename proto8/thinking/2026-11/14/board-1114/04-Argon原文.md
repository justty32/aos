board-1114 的 Argon（Gemini 4 Argon High，agy -p --mode plan）審查原文：吃 01 備料＋02 fable 稿＋03 計劃全文、不給工具，(A) 審查 16 條 (B) 提案 5 條 (C) U1～U7 選擇；一字未改。

# board-1114 04 Argon 原文

← [board-1114](../board-1114.md)｜上一份 [03-計劃](03-計劃.md)｜2026-11-14；指令：`agy -p "$(cat prompt.txt)" --model "Gemini 4 Argon (High)" --mode plan --print-timeout 840s`（在 /tmp 跑，提示 86 KB）

---

### (A) 審查：設計與計劃中的具體問題

#### A1. 〔擋路〕03 計劃 C6 拒絕 `comm_send --to user`，直接弄壞使用者第 1 條核心需求與待辦彙總
* **問題**：使用者原話 1 點名「我去睡覺的時候，agent 寄信給我發現很久沒回，他就會去看（布告欄）」，02 稿 §3.4/§3.5/§7.4 也以此設計 `comm_send --wait` 自動帶回 `user` 布告欄、寫入 `waiting_on`（供 ok-view 左欄「在等使用者的」待辦統計）、30 分鐘未回由 `comm_tick` 發出 `no_reply` 並附上 `user` 布告欄。但 03 計劃 **C6** 改為「`comm_send --to user` 直接拒（`UseUserSend`），提示改用 `user_send`／`aos-user send`」。一旦改用舊 `user_send`，寄信時既不會帶回 `~/.aos/user/board.json`、不會自動登記 `waiting_on: [{who: "user"}]`，`comm_tick` 也永遠不會在 30 分鐘後提醒 agent 去看使用者布告欄。
* **修法**：保留 C6「不混用信件 schema」的好處，但補兩步：(1) `aos-user send`／`user_send`（不在禁改名單，02 稿 §十 本就會改 `aos-user tick`）在寄信成功後順手讀 `~/.aos/user/board.json` 附在回傳，並在呼叫端 `<agent_root>/board.json` 的 `waiting_on`（當 `kind` 為需回覆的 `decide/verify/trial` 時）自動加一筆 `{who: "user", ...}`；(2) 若不想改 `aos-user send`，則在 `comm` 套件的 `after_tool` hook 攔 `user_send` 完成同樣動作。

#### A2. 〔擋路〕MCP 工具的 `$AOS_STACK` 是 `<agent>/tools/<工具名>/`，導致頻道認人、自迴圈、狀態檔路徑全錯
* **問題**：01 備料 §五 明載「工具看到的 `AOS_STACK` 是 `<agent stack>/tools/<名>/`，不是 agent 根」。這會造成三個連鎖錯誤：
  1. **頻道身分分裂與無法用舊工具發言**：`aos-post send` 寫入信封的 `sender` 取自 `$AOS_STACK`。若 agent 先用 MCP `channel_join` 加入（或被記為 `<agent_root>`），之後照 02 稿 §〇.7 用不改動的舊 `mailbox_send` 發言，信封 `sender` 會是 `<agent_root>/tools/mailbox_send`；頻道比對 `members.json`（鍵為 `<agent_root>`）會判定非成員拒收（`ChannelNotMember`），或違反 §4.5 第 1 條把信轉寄回給發言人自己。
  2. **頻道查不到成員 `state.json`**：`<agent_root>/tools/<名>/state.json` 不存在，頻道判斷睡著與否會失靈。
  3. **工具小格不共用**：02 稿 §3.5 把等待帳記在 `tools/comm/waiting.jsonl`、§3.6 記在 `urgent.jsonl`、§4.1 記頻道游標；但 MCP 每個工具各有一格（`tools/comm_send/`、`tools/comm_read/`），CLI `aos-comm` 跑在 bash 下又是另一格，彼此讀不到同一個檔案。
* **修法**：(1) `lib/aos/comm` 統一提供 `resolve_agent_root()`（優先檢查 `$AOS_STACK` 若落在 `.../tools/<name>` 則往上取 agent 根，或呼叫 `ctl who`），所有新工具呼叫 `aos-post send` 前把環境變數 `AOS_STACK` 設回 `<agent_root>`；(2) 頻道 proc 收信時先對信封 `sender` 做正規化（若路徑符合 `<root>/tools/<name>` 且 `<root>/mailbox` 存在，折算為 `<root>`），確保舊 `mailbox_send` 不改也能通過成員檢查與防自迴圈；(3) `waiting.jsonl`、`urgent.jsonl`、頻道讀取游標統一存放在 `<agent_root>/comm/` 下，不放 `tools/<名>/`。

#### A3. 〔擋路〕03 計劃 C1 的 `comm_read` 只看 `new/` 不看 `cur/`，且破壞 `aos-post` 的有序信優先規則與並發安全
* **問題**：03 計劃 **C1** 改為「直接列 `<box>/new/*/letter.json` → 挑一封 → `rename new/<名> → cur/<名>` → `aos-post see`＋`done`」，有三個問題：
  1. **漏讀 `cur/`**：舊 `aos-mailbox read`（或中斷的 `take`）會先讀 `cur/`。若 `cur/` 裡已有上次認領未刪的信，`comm_read` 只看 `new/` 會永遠漏掉 `cur/` 裡的信。
  2. **並發讀檔 Race（ENOENT）**：`comm_read` 在 `rename` 認領前先打開 `new/*/letter.json` 讀 `body.comm.level`，此時若有另一個讀者（如 `aos-mailbox read`）正好將該信 `rename` 走並 `done` 刪除，讀檔會直接拋 `FileNotFoundError`。
  3. **排序與 `aos-post` 不一致**：01 備料 §三 明載 `aos-post` 排序是「先所有有序信（`--ordered`，12 位序號前綴）、再無序信（20 位奈秒前綴），各組字典序」。C1 只寫「照級別、再信名」，若直接字串排或混排，會違反 02 稿 §6.2「沒有 `comm` 時 `comm_read` 順序跟 `mailbox_read` 一樣」的承諾。
* **修法**：(1) 掃描時若 `<box>/cur/` 非空，將 `cur/*` 一併納入候選（挑中 `cur/` 的信時跳過 `rename` 直接 `see`＋`done`）；(2) 讀取 `new/*/letter.json` 時捕獲 `ENOENT`／JSON 解析失敗並跳過；(3) 同級別內的次排序鍵嚴格照 `(is_unordered, letter_name)` 排（先有序信再無序信，各組字典序）。

#### A4. 〔擋路〕頻道分批續寄（§4.6）與每輪 `done`（§4.1）及歷史檔欄位（§4.2）互相矛盾，50 人以上必丟資料或重複編號
* **問題**：02 稿 §4.1 說頻道每輪「`take-all` 自己的信箱、處理、`done`」，§4.6 又說「每輪最多寄 `batch`（50）份，剩的下一輪；每個成員記 `sent_seq`，頻道中途被殺，重起後接著寄」。
  - 若第一輪寄完前 50 人就對原信執行 `aos-post done`（刪除原信），第二輪只能從 `log/YYYY-MM-DD.jsonl` 讀信續寄給後 70 人；但 §4.2 定義的歷史檔每行只有 `{seq, at, from, sender, status, level, title, what}`，**漏掉了 `outputs`、`not_done`、`decide`、`comm.via`、`comm.origin`**，第二輪寄出的信會缺欄位，且 `pull` 模式的成員也永遠讀不到 `outputs/not_done/decide`。
  - 反之，若第一輪不 `done` 原信、留在 `cur/` 等下一輪，頻道一旦重啟或進入下一輪，又會把 `cur/` 裡的信當新發言再編一次 `seq`、再寫一行歷史。
* **修法**：頻道收到發言信時，先把完整轉發內容（含 `outputs`、`not_done`、`decide`、`via`、`origin`）寫入 `log/YYYY-MM-DD.jsonl` 並更新 `seq`，**當場 `aos-post done` 刪掉原信**；之後的分批投遞（每輪最多 `batch` 封）完全由「比對 `members[*].sent_seq < channel.seq`，從 `log/` 讀取對應 `seq` 投遞」驅動。

#### A5. 〔擋路〕頻道「睡著成員不灌信、醒來補一封摘要」（§4.1）在 `members.json` 缺少狀態欄位，無法實作
* **問題**：02 稿 §4.2 與 §八 的 `channel-members/1` schema 每個成員只有一個 `sent_seq`。當成員 M 睡著時來了第 10～12 號信：
  - 若不推進 `sent_seq`（留在 9），下一輪（300ms 後）分批續寄邏輯會以為 M 是還沒寄到的批次，醒來時直接灌 10～12 號全量複本，而非一封摘要；
  - 若推進 `sent_seq` 到 12，則「從第幾號開始欠（a=10）」遺失，且 M 醒來時若頻道剛好沒新信進來，頻道根本不知道要補寄摘要。
* **修法**：`members.json` 的成員物件補一個欄位 `"missed_from_seq": {"type": ["integer", "null"]}`。成員睡著期間跳過投遞時，若 `missed_from_seq` 為 `null` 則設為當前 `seq`，並將 `sent_seq` 推進至當前 `seq`；頻道 loop 每 30 秒檢查一次 `missed_from_seq != null` 的成員之 `state.json`，一旦非 `sleeping/stopped`，寄出一封 `[#ch] N messages while you were sleeping (#a..#b)`（`comm.auto: true`）並清回 `null`。

#### A6. 〔重要〕「收到回信（`in_reply_to` 對上）自動拿掉 `waiting_on`」（§2.6/§3.5）在現有工具鏈下幾乎不會觸發
* **問題**：
  1. 01 備料 §三 指出：舊 `aos-mailbox send` 沒有填任意欄位介面，且 kernel 轉寄會丟掉信封的 `in_reply_to`；02 稿 §5.2 的 `aos-comm send` CLI 甚至沒列 `--in-reply-to` 旗標。絕大多數回信（特別是舊 agent 或使用者）不會帶匹配的 `in_reply_to`。
  2. 若收件人用舊 `aos-mailbox read` 讀信，信會在兩次 `on_clock`（每分鐘一次）之間被認領並 `done` 刪除，`comm_tick` 只看信箱會完全錯過回信。
  3. 結果是 `waiting_on` 消不掉、30 分鐘後 `comm_tick` 誤報 `no_reply`。
* **修法**：(1) 放寬消帳條件：只要收到來自 `waiting_on.who`（比對 `body.from` 或正規化後的 `sender`）、`sent_at >= since_at`、且非機器信（`!comm.auto`、標題非 `[auto] ` 開頭、無 `comm.channel`）的信，不論有無 `in_reply_to` 都自動消掉該 `who` 的等待（若有指定 `in_reply_to` 則精確消該筆 `ref`）；(2) 除了 `comm_tick` 掃描 `new/` 與 `comm_read` 讀信時消帳外，在 `after_tool` hook 攔 `mailbox_read` 的輸出做同樣消帳。

#### A7. 〔重要〕`mode: "here"` 的布告欄永不過期（§2.4/§7.3），導致 `waiting_on` 與 `doing` 卡死在 ok-view 待辦
* **問題**：02 稿 §2.4 第 2 步與 §7.3 規定：「沒有 `expires_at`、**`mode` 不是 `here`**、且超過 `updated_at` 加 24 小時 → 標 `stale`」。當 agent 處於正常 `mode: "here"` 並透過 `comm_send --wait` 或 `board_wait` 寫入 `waiting_on`（未設 `expires_at`），若對方一直沒回或該 agent 後來 stopped，因為 `mode` 是 `here`，這張布告欄**永遠不會變成 `stale`**；§7.4 ok-view「幾隻在等人」與「左欄待辦：在等使用者的」只過濾「沒過期」，會導致陳舊等待項目永久卡在全景頁。
* **修法**：移除「`mode` 不是 `here`」這個條件——凡是沒寫 `expires_at` 的布告欄，一律在 `updated_at` 後 24 小時標為 `stale`（反正 `stale` 的效果本就是「文字標灰、`mode` 當 `here`」，對原本就是 `here` 的通知行為零影響，卻能正確讓過期的 `doing` 與 `waiting_on` 失效）。

#### A8. 〔重要〕頻道對急件降級（§4.1）沒處理標題的 `[URGENT] ` 前綴，舊程式與 xiaosi 仍會當急件
* **問題**：02 稿 §3.1 規定寄信工具對急件自動在標題前加 `[URGENT] ` 給舊程式與 xiaosi 看；§4.1 又規定「頻道轉出的信最高 `normal`，原信寫 `urgent` 也降」；§4.4 規定頻道轉出標題為 `[#頻道名] 原標題`。若發言人寄急件進頻道，寄件端已加上 `[URGENT] `，頻道只降 `body.comm.level = "normal"` 卻保留標題變成 `[#ch] [URGENT] 標題`，只看標題的 xiaosi 與舊程式仍會把它當急件立刻轉發。此外，若發言人自己標題已寫 `[URGENT] `，`comm_send` 不檢查就會變成 `[URGENT] [URGENT] `。
* **修法**：(1) `comm_send` 加前綴前先檢查 `not title.startswith("[URGENT] ")`；(2) 頻道轉出信若將 `level` 封頂至 `normal`/`low`，必須同時剝除 `body.title` 開頭的 `[URGENT] `。

#### A9. 〔重要〕廣播頻道 `members_from: "daemon"`（§4.1）與新加入成員的初始 `sent_seq` 會造成歷史信洪水與頻道互轉
* **問題**：
  1. `members_from: "daemon"` 取同張 daemon 表上所有 proc，但表上包含**廣播頻道自己、同表的其他頻道 proc、以及沒有 `mailbox/` 的系統站（如 `procs-kernel` 用 `requests/`）**。若直接全轉，廣播信會灌進其他頻道觸發連鎖廣播，或投遞失敗。
  2. 新成員 `join` 一般頻道、或新 proc 出現在廣播頻道的 daemon 表時，若 `members.json` 裡的 `sent_seq` 初始設為 `0`，分批投遞邏輯會把過去 30 天所有歷史發言全部塞進新成員信箱。
* **修法**：(1) `members_from: "daemon"` 枚舉時必須排除自己、排除 stack 內含 `channel.json` 的其他頻道、並只收 `<stack>/mailbox/new` 存在的 proc（且 daemon 表結果快取 10 秒，不在 300ms loop 裡每輪呼叫 `ctl ls`）；(2) 新加入成員或新發現的 daemon 成員，其初始 `sent_seq` 一律設為頻道當前的 `seq`（只收加入後的信，歷史用 `channel_read` 讀）。

#### A10. 〔重要〕頻道分批重啟的重複信（§4.6）在 `comm_read` 與 `mail_notify` 無法跨次去重
* **問題**：02 稿 §4.6 說「中斷續寄最多重複一封；複本帶同一組 `channel`＋`seq`，新工具據此去重」。但如果第一封複本已經被 `comm_read` 讀走並 `aos-post done` 刪檔，之後頻道重啟又寄來第二封同 `(channel, seq)` 的複本，`comm_read` 在信箱裡根本看不到已刪的第一封，無從得知它是重複信。
* **修法**：在 `<agent_root>/comm/channel_seen.json` 記錄每個 `channel` 已讀過的最大 `seq`（或最近 64 筆 `seq`）。`mail_notify` 與 `comm_read` 在 `new/` 看到 `comm.channel`＋`comm.seq` 已在已讀集合內時，直接 `rename new -> cur` 並 `aos-post done` 靜默銷毀，不通知也不再讀出。

#### A11. 〔重要〕`dnd_over` 通知在 `mail_notify`（§3.4）與 `comm_tick`（§2.6）雙重負責，且與現有未通知追蹤打架
* **問題**：02 稿 §2.6 把「`dnd` 結束補一則壓住的信有幾封」交給 `comm_tick`，§3.4 又交給 `mail_notify`。且 `mail_notify` 本來就會在每分鐘掃描 `new/` 中尚未通知的信——若 `dnd` 期間只是暫不通知（不標記為已通知），`dnd` 一結束的下一分鐘 `mail_notify` 自然會發 `[aos] new_mail: N new letter(s)...`，若 `comm_tick` 又發一則 `[aos] dnd_over: N letter(s)...`，agent 會收到兩次重複通知。
* **修法**：只留 `mail_notify`（`lib/aos/comm/notify.py`）一處負責，`comm_tick` 不管信件通知。`dnd/away` 期間被壓住的信記在 `notify` 的 `deferred` 集合；`dnd/away` 結束後的下一次 `mail_notify` 若發現原本在 `deferred` 且仍在 `new/` 的信，將通知行前綴改印 `[aos] dnd_over: ...` 並轉入 `notified`，既不重發也不會把 `dnd` 期間已手動讀掉的信算進去。

#### A12. 〔重要〕頻道管理信（`join`/`leave`）回信進信箱（§4.3），會污染成員信箱並觸發多餘的 `new_mail` 通知
* **問題**：02 稿 §4.3 規定 `join`/`leave` 處理完後「頻道回一封結果（status `DONE` 或 `FAILED`）」，同時又說「CLI 的 `join` 寄完後等幾秒看 `members.json` 有沒有自己」。這表示 `channel_join` 工具明明已經看著 `members.json` 返回結果給呼叫者了，頻道卻還往成員的 `mailbox/new/` 塞一封 `DONE` 信，導致一分鐘後 `mail_notify` 吵成員讀一封廢話信。
* **修法**：頻道對成功的 `join`/`leave` **不寄回信**（直接更新 `members.json` 即可，同機可讀）；若失敗則寫入 `<channel_stack>/rejected.jsonl`（帶申請信的信名或 `sender`＋原因），`channel_join`/`channel_leave` 工具輪詢 `members.json` 與 `rejected.jsonl` 即可拿到精確錯誤碼，信箱零垃圾信。

#### A13. 〔小〕`board.json` 並發寫入的暫存檔同名競爭與 `waiting_on` 覆蓋 Race（§2.1/§5.3）
* **問題**：§5.3 範例固定寫死 `$AOS_STACK/board.json.tmp`；而 `board_set`、`comm_send --wait`、`comm_tick`（清 `clear_on_start` 與 `waiting_on`）都會讀改寫 `board.json`。兩支行程同時寫 `board.json.tmp` 會寫壞暫存檔，且不加鎖的讀改寫會互相覆蓋 `waiting_on` 與 `seq`。
* **修法**：暫存檔名必須帶 PID（如 `board.json.tmp.$$`），且 `lib/aos/comm/board.py` 的讀改寫加 `flock(<stack>/board.lock)`。

#### A14. 〔小〕時鐘跳動步驟順序顛倒（§2.4 vs §7.3）
* **問題**：§2.4 與 §7.3 把「第 2 步：算過期（用 `updated_at` 加 24 小時）」放在「第 3 步：`updated_at` 比現在晚超過 5 分鐘時當成現在來算過期」之前。照順序實作時，第 2 步還沒套用第 3 步的時鐘校正。
* **修法**：將第 2 步與第 3 步對調：先校正 `updated_at`（未來時間夾回 `now` 並標 `clock_odd`），再算 `stale`。

#### A15. 〔小〕`comm_send --to #頻道` 的 `#` 前綴與 `ctl where` 名字不對齊（§4.1/§5.1）
* **問題**：§4.1 說頻道就是普通 proc（名字如 `dev`，不靠前綴，所以 `aos-mailbox send --to dev` 能寄），但 §5.1/§5.2 卻叫人傳 `--to #CH`。若 `comm_send` 拿 `#dev` 去查 `ctl where #dev` 會找不到；若不用 `#`（`comm_send --to dev`），`comm_send` 又不知道目標是頻道還是普通 agent。
* **修法**：`comm_send` 對 `to` 先去掉可選的開頭 `#` 再用 `ctl where` 找 stack，並檢查 `<target_stack>/channel.json` 是否存在來判斷目標是否為頻道（是頻道就不要求 `wait`、不回傳個人 `board.json`）。

#### A16. 〔小〕四份 JSON Schema 的三處缺漏（§7.5/§8）
* **問題**：(1) `comm/1/letter-comm` 的 `why` 沒設 `"minLength": 1`，傳空字串 `""` 也能過急件檢查；(2) `comm/1/channel` 與 `comm/1/channel-members` 漏了頂層 `"$schema": "https://json-schema.org/draft/2020-12/schema"`，且 `max_level` enum 少了 `"low"`；(3) `comm/1/board` 的 `waiting_on.items` 只把 `who` 列為 `required`，漏了 `what` 與 `since_at`（§7.4 顯示必備）；(4) `channel_read` 未定義首次無游標時的行為（應取最新 `limit` 則並將游標設為最新 `seq`，而非從 30 天前第 1 則讀起）。
* **修法**：在批 0 落檔 `proto8/schema/comm/1/` 時一併補齊上述約束與 `channel_read` 預設游標規格。

---

### (B) 提案：讓設計更簡單、更穩健的改進

1. **P1：廢除 `tools/comm/waiting.jsonl`，直接以 `<stack>/board.json` 的 `waiting_on` 作為唯一等待帳本**
   * **理由**：02 稿同時維護 `board.json` 的 `waiting_on[]` 與私有的 `waiting.jsonl`，兩邊記一樣的事（等誰、什麼事、何時寄、`ref`）卻容易不同步。只要在 `waiting_on` 項目允許選填 `"notified_at"`（或 `"urgent": true`），`board.json` 一份檔案就能同時供 ok-view 顯示、供別隻 agent 查看「他在等誰」、並供 `comm_tick` 發 `no_reply` 提醒，少維護一個持久檔與一套同步邏輯。
2. **P2：頻道控制面改為「寄信申請、讀檔確認」，徹底取消頻道的管理回信**
   * **理由**：同機架構下 `<channel_stack>/members.json` 與 `rejected.jsonl` 對所有 proc 都是直接可讀的。取消 `join`/`leave`/`info` 的回信（且 `channel_info` 直接讀檔不必寄信），頻道 proc 就不必組裝管理回信，成員信箱也不會混入控制面雜訊，實作瞬間少掉三分之一（連 `comm.result` 欄位都可以從 schema 拿掉）。
3. **P3：`comm_tick` 與 `mail_notify` 二合一（或共用同一個 `on_clock` 入口）**
   * **理由**：兩支 hook 都綁在每分鐘一次的 `on_clock`，也都要讀自己的 `<stack>/board.json` 與 `<stack>/mailbox/new/`。把 `after_start` 撕布告欄與 `on_clock` 的 `no_reply` 檢查直接收進 `lib/aos/comm/notify.py` 由同一個 hook 呼叫，範本不必多掛一支新 hook，也不會有兩支 hook 每分鐘重複掃描同一箱信與競爭鎖。
4. **P4：信件標題不改寫（不硬塞 `[URGENT] `），改在 `aos-mailbox peek` 以外靠 `mail_notify` 與 `comm_read` 呈現**
   * **理由**：寄件時污染 `body.title` 會造成頻道降級後標題仍殘留 `[URGENT] `、急件過期（`expires_at` 已過降為 `low`）後標題仍叫 `[URGENT] `、以及回信標題疊加等後遺症。唯一看標題分輕重的舊讀者只有 `xiaosi`，而 02 稿 §十 本就會在 `xiaosi/system.txt` 加一句看 `comm.level`（`mailbox_read` 原生就會印出 `comm` 欄位！），根本不需要改寫 `body.title`（頻道轉發的 `[#頻道名] ` 保留即可，因為頻道來源不會過期或降級）。
5. **P5：急件額度（Rate Limit）在 `comm_read` 與 `mail_notify` 共用同一個有效級別計算函式 `effective_level(letter, state)`**
   * **理由**：把「缺 `why` 降級、`expires_at` 過期降 `low`、同一 `sender` 一小時超過 3 封降 `normal`」封裝成純函式並共用 `<stack>/comm/urgent.jsonl` 帳本，能保證通知跟讀信插隊看到的級別永遠一致，不會出現「通知被降為平信，但 `comm_read` 仍讓它無限插隊」的漏洞。

---

### (C) U1～U7 選擇與理由（各一行）

* **U1（進 NORMS）**：選 **甲**——先放 `08-待定` 與 `docs/COMM.md`，跑通一輪確認欄位無增減後再收為 N-70～N-72，避免實作微調時反覆改動正式規範。
* **U2（信分幾級）**：選 **甲（三級：`urgent`/`normal`/`low`）**——剛好一對一對應「穿過 DND／每分鐘常規通知／頻道與自動信只計數不點名」三種收件端行為，不多不少。
* **U3（急件叫醒）**：選 **甲（預設不叫醒，收件人布告欄設 `wake_on_urgent: true` 才允許）**——把花錢與被打斷的控制權留在收件人自己手上，防範急件被當成強迫喚醒按鈕。
* **U4（使用者布告欄搬家）**：選 **甲（搬到 `~/.aos/user/board.json`）**——讓 `user` 與所有 agent 的布告欄路徑規則、到期邏輯、讀取工具完全統一，消除特例。
* **U5（頻道收信方式）**：選 **甲（預設 `copy` 每人一份，可選 `pull`，逾 50 人預設 `pull`）**——小頻道零學習成本（舊 `mailbox_read` 直接能收），大頻道自動保護信箱不被灌爆。
* **U6（全員廣播頻道）**：選 **甲（支援 `members_from: "daemon"` 但不自動建）**——用同一套頻道 proc 就能涵蓋廣播，按需建立可避免沒人用時每張表多一隻常駐 loop proc。
* **U7（誰能叫醒睡著的 agent）**：選 **甲（第一版不自動發 `ctl wake`，僅在回傳與 `no_reply` 告知寄件人與上層 kernel 名字）**——避免跨隊 `ctl wake` 撞牆或繞過 kernel gate，等 kernel 線定好跨隊喚醒規則再接。
