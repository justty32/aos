# 04 Argon 審查原文（view-1114）

← [view-1114](../view-1114.md)｜Argon（Gemini 4 Argon High，plan 模式），對 01～03 的 (A) 審查 8 條、(B) 提案 4 條，原文照錄

指令：在 /tmp 跑 `agy -p <01+02+03 全文與要求> --model "Gemini 4 Argon (High)" --mode plan --print-timeout 840s`。第一次沒有輸出（`jetski: no output produced — a tool required the "read_file" permission that headless mode cannot prompt for`）；提示開頭加「不要使用任何工具、不要讀檔，全文已貼在下面」後重跑成功。沒有加任何繞過權限的旗標。

---

以下根據 01 備料、02 fable 設計稿、03 opus 實作計劃三份材料進行審稿。

---

## (A) 審查：錯誤、漏洞、邊緣狀況、與現況不符、安全與成本問題

### 1. [高] 組樹邏輯與現況不符：已停隊長不查 `subagents` 且依賴前綴，會使「隊長 143 倒下、隊員照跑」的核心驗收直接失效
* **問題**：
  1. **03 §4.0.2** 寫道：「對每個 **`state=running`** 的 agent 跑 `ctl state -t NAME subagents` 拿歸屬；(b) 名字前綴 `<隊>-`；(c) 都歸不到的收『未歸隊』。」
  2. 但對照 **01 結論 5 的 11-14 實況**：隊長 `ok-skyrim` 停在 code 143（此時它的 `state` **不是 `running`**），而它底下的成員叫 **`sky-sol-a/b/c`、`sky-astra-d`**（前綴是 `sky-`，**不是** `ok-skyrim-`）。
  3. 照 03 的寫法，因為 `ok-skyrim` 已停，固定程序不會查它的 `subagents`；又因為 `sky-sol-a` 前綴對不上 `ok-skyrim-`，這 4 隻成員會全部掉進「未歸隊」，而 `ok-skyrim` 會被誤判為「底下無成員在跑」而亮灰燈，**第 0 期最重要的紅燈驗收條件當場失效**。
* **建議**：
  1. `ctl state -t NAME subagents` **必須包含非 `running`（已停止／崩潰）的 agent**。因為已停 agent 的 `subagents` 清單不會再變，固定程序查過一次即可快取在 `state/`，不會增加每分鐘 tick 的負擔。
  2. 親子歸屬優先序應為：`aide.json`／信件 `team` 宣告 ＞ `subagents` 紀錄（含已停隊長）＞ 名字前綴（僅作最後兜底，不可當主力）。

### 2. [高] 退場死結：隊伍收隊（`DONE`）後，小助手會變成「殭屍程序」或觸發「假紅燈」
* **問題**：
  1. **01 F 與 02 §4** 指出：小助手是 daemon 的子程序，隊長停了它不會跟著停。
  2. 當一支隊伍正常完工收隊（隊長與隊員皆結束）後：
     * 若**不停小助手**：場上所有歷史隊伍的小助手會永遠活著，每 60 秒跑 hook、每 15 分鐘寄 `beat` 信到中轉信箱，隨時間累積成大量殭屍程序。
     * 若**停掉小助手**：照 **02 §5 燈號表**，「小助手不在 daemon 表上，或 35 分鐘沒收到信」是**紅燈**，排在灰燈（`DONE`）前面；一旦停掉小助手，所有已收隊的歷史隊伍都會在網頁上永遠亮紅燈喊「小助手沒聲音」。
* **建議**：
  1. **調整燈號判定優先序**：若隊長與所有成員皆已停止，且最後一封 `report` 為 `DONE`（或無未決事項），直接判定為**灰燈（收隊）**，不再檢查小助手心跳。
  2. **明定小助手自動退場機制**：當 hook 發現隊長已記入 `view_note done`、隊長與所有成員皆已 `stopped`、且 `outbox/` 已清空時，小助手寄出最後一封 `status: DONE` 的 `report` 後即自我停止（或由固定程序標記收隊）。

### 3. [高] 小助手 `history rm` 與模型執行中的競態條件（Race Condition）及狀態斷鏈
* **問題**：
  1. **03 §0.2 與 §3** 設計：hook 在叫模型前先跑 `aos-agent history -t <自己> rm --no-keep -y 1-`，再寫進 queue。
  2. 但 `terra-aide` 只有 **`slots: 1`**（六隊共用），模型完成一次回報需要跑 2 個 turn。如果小助手正在跑第 1 個 turn 或正在等 slot（`busy=true` 或 `queued>0`），此時使用者按了「現在回報（`poke`）」或跨入下一個定時週期，hook 若不檢查狀態就直接 `history rm 1-` 並塞 queue，會清空正在進行中的上下文或造成重複排隊。
  3. **Hook 與 `view_report` 缺少交接媒介**：hook 是 `on_clock` 外部觸發，模型是在 brain turn 內呼叫 `view_report(now, next, blocked, what)`。03 沒有定義：`view_report` 被呼叫時從哪裡拿到 hook 蒐集好的 `facts`、`snapshot_sha256` 與 `seq` 來合成完整信件？若模型因 `spent=refuse` 或連錯兩次沒呼叫成功，下一次 hook 怎麼知道上次模型失敗了並改寄 `summary_by: "none"`？
* **建議**：
  1. Hook 欲喚醒模型前，先看 daemon 表：若小助手 `busy == true` 或 `queued > 0`，本次不執行 `history rm` 也不重複塞 queue。
  2. 明確定義交接狀態檔（例如 `<小助手 stack>/pending_report.json`）：hook 算好 `facts`、`snapshot_sha256` 後寫入該檔並記錄 `requested_at`；模型呼叫 `view_report` 時讀取該檔合成信件寄出並刪檔；下次 hook（60 秒後）若發現 `pending_report.json` 仍在且小助手已非 `busy`，即判定模型回報失敗（格式連錯或被 kernel refuse），由 hook 直接將該檔作為 `summary_by: "none"` 寄出。
  3. 隊伍的信件序號 `seq` 由 `pass`、`beat`、`report` 共用，讀寫遞增時必須透過同一個加 `flock` 的小函式操作，避免 `pass`（hook 寄）與 `report`（模型工具寄）撞號。

### 4. [高] 遮蔽 Key 的正則表達式會誤殺所有 SHA-256 與 Git Commit Hash，甚至弄壞決策單驗證
* **問題**：
  1. **03 §4.1.3** 規定：「遮 key：掃 `sk-[A-Za-z0-9]{20,}`、`[A-Z_]*KEY=\S+`、**長度 ≥40 的 base64 樣字串**，換成 `[masked]`」。
  2. **SHA-256 hex（64 字元）與 Git commit SHA（40 字元）完全符合「長度 ≥40 的 base64 樣字串（`[A-Za-z0-9+/=]{40,}`）」**！此外，長檔案路徑（含 `/` 且超過 40 字元）也會中招。照這條規則跑下去，信裡的 `snapshot_sha256`、`payload_sha256`、`origin` 裡的 hash、以及進度裡提到的 commit hash 全部會被洗成 `[masked]`。
  3. 若對 `pass` 決策單的 `payload_text` 做字串替換，會直接導致送進專區的內容與隊長留底的 hash 不符。
* **建議**：
  1. 移除「長度 ≥40 的 base64 樣字串」這種過寬規則，改為針對明確的憑證前綴（`sk-`、`ghp_`、`AIza`、`xox[baprs]-`、`Bearer ` 等）及 `KEY/TOKEN/SECRET/PASSWORD` 賦值語句進行遮蔽，並明確排除純 40/64 位 `[0-9a-f]` hex 字串與結構化欄位（`*_sha256`、`origin`）。
  2. 對 `pass` 決策單：在隊長端執行 `view_decide` 時就先掃描一次，若含疑似 secret 直接拒絕建單（Fail Fast），中轉與固定程序絕不改動 `payload_text` 的任何字元。

### 5. [中] `view_match` 的信任鏈破口與「原檔逐位元組相同」的實作矛盾
* **問題**：
  1. **02 §12** 驗收要求「專區收到的內容與隊長原檔逐位元組相同」，但 **03 §4.1.3** 寫固定程序送專區時「body 加 `origin: "<隊>/<id> sha256:<hex> via <小助手>"`」。只要往 body 多塞了 `origin` 欄位，專區存下的 JSON 就不會與隊長原檔逐位元組相同。
  2. **03 §4.1.4** 設計 `view_match`：「讀回信的 `in_reply_to` → **查 `~/.aos/view/state/passed/` 收據** → 比 `view/sent.jsonl` 的 hash」。這把信任建立在 `~/.aos/view/state/passed/` 的收據上（而 `state/` 是隨時可重建的衍生資料），萬一收據對應錯信，隊長只驗「回信來自專區」＋「view 收據裡的 hash」，並未驗證**專區實際展示給使用者的那封信（或回信所帶的 `origin`）**是否真為該 hash。
  3. 此外，**03 §4.1.3** 把送專區的指令寫死為 `aos-user send --kind decide`，漏掉了專區原有的 `verify`、`trial`、`chore`、`fyi` 四種信（01 A）。
* **建議**：
  1. 隊長在跑 `view_decide` 產生 `<id>.json` 時，先把除 `via` 以外的欄位（含 `kind`）定好；或者明確定義 `payload_sha256` 是算在**正規化（Canonical JSON，排除 `origin` 欄位）的題目內容**上。
  2. `view_match` 不應只查 `~/.aos/view/state/passed/` 收據，而應直接核對**專區 `~/.aos/user/done/<月>/<原信>` 裡的 `origin` 欄位內含的 `sha256:<hex>`（或重算專區原信扣掉 `origin` 的 canonical hash）**是否與隊長 `view/sent.jsonl` 一致，這樣驗證鏈才真正閉環在專區上，而且不把收據綁在可抹除的 `state/` 裡。
  3. `aos-view tick` 轉送專區時，應從 `payload_text` 讀取原本的 `kind`（`decide|verify|trial|chore|fyi`），不要寫死 `--kind decide`。

### 6. [中] 固定程序每小時 8 封排隊限制，與決策單 `deadline`／`default_if_silent` 及 Crash 保存衝突
* **問題**：
  1. **01 A** 說明決策單有 `deadline` 與 `default_if_silent`（到期未答，隊長就照預設值行動）。
  2. **02 §5 與 03 §4.1.3** 設計固定程序每小時最多送 8 封進專區，其餘排到下一小時。若一張帶有 30 分鐘 `deadline` 的單子被排隊卡在中轉站 40 分鐘，**使用者連題目都還沒在專區看到，隊長就因為超時而自動執行 `default_if_silent` 了**。
  3. **03 §4.1.3** 寫：`aos-post take-all` → 分流 → 排隊 → `aos-post done --keep`。如果信已經 `done` 進了 `done/<月>/`，那些「排到下一小時才要送專區」的 `pass` 信存在哪裡？若 tick 結束或重跑，記憶體裡的排隊就消失了；同理，若 `take-all` 把信從 `new/` 搬到 `cur/` 後程式異常中斷，下次 tick 若只看 `new/` 就會把信遺忘在 `cur/`。
* **建議**：
  1. 排隊優先序應為：`urgent` ＞ 有 `deadline`（依到期時間由近到遠）＞ 一般 `decide/verify` ＞ `chore/fyi`。且在等待進入專區期間，若離 `deadline` 不足 30 分鐘應優先放行（利用預留的 10 - 8 = 2 封裕度）。
  2. **不要先 `done` 再排隊**：尚未送進專區的 `pass` 信應留在中轉信箱 `cur/`（或 `state/pass_queue/` 持久化），等真正成功 `aos-user send` 拿到專區信名、寫好收據後，才對該封中轉信執行 `aos-post done --keep`。同時每次 `tick` 必須先處理 `cur/` 裡未完成的信，再 `take` `new/` 的信。

### 7. [中] 隊伍工作區 `<隊長 ws>/view/` 會弄髒 Git Working Tree
* **問題**：
  * **03 §3** 將 `view/notes.jsonl`、`view/outbox/`、`view/sent.jsonl`、`view/aide.json` 直接放在 `<隊長 ws>/view/` 底下。但隊長的 `ws` 往往是程式碼 repo 的工作樹，這批執行期檔案會讓 `git status` 出現 untracked files，在跑測試或走 `commit-request` 時造成干擾甚至誤提交。
* **建議**：
  * `view_note`／`view_decide` 初始化 `<隊長 ws>/view/` 時，若偵測到 `<隊長 ws>` 為 git repo，自動在 `.git/info/exclude`（不動 repo 內受版本控制的 `.gitignore`）加入 `/view/`；或者將小助手的內部狀態檔放在 `<小助手 stack>/` 或 `~/.aos/view/workspaces/<team>/`。

### 8. [低] 施工前需先驗證的現況假設與小瑕疵
* **問題**：
  1. **`aos-post send` 的 body schema 限制**：01 D 提到信件 body 有固定欄位與 6 個 status 字；03 §1 查了 `aos-post send --help` 確認不能帶附件，但尚未實測 `aos-post send` 是否允許 `body.json` 包含 `zone`、`kind`、`facts`、`payload_text` 等擴充欄位（抑或有 `additionalProperties: false`）。
  2. **燈號同時滿足多個條件時的優先序**：02 §5 未說明當一隊同時處於「有決策單等你（藍燈）」且「因等決策而 60 分鐘沒進度或標 BLOCKED（黃燈）」時亮哪顆燈。若亮黃燈並計入頁頂「可能卡住」，會誤導使用者。
  3. **`state/*.json` 讀寫競爭**：`aos-view tick` 寫檔與 `aos-view serve` 每 5 秒讀取之間未提原子寫入，可能讀到寫一半的 JSON。
  4. **小助手的同時喚醒（Thundering Herd）**：多隊小助手的 15 分鐘門檻若同時到期，會同時搶唯一的 `terra-aide` slot。
* **建議**：
  1. 第 1 期動工第一件事先用 `aos-post send` 實測擴充欄位；若 `aos-post` 鎖死欄位，就把擴充 JSON 包在標準欄位（如 `outputs` 或 `what`）內。
  2. 明定燈號優先序為：**紅（隊長崩潰／小助手失聯）＞ 藍（等你決策）＞ 黃（卡住／久無進度）＞ 綠（正常）＞ 灰（收隊）**；且有待決策單時，暫停「60 分鐘無進度」的黃燈計時。
  3. 所有 `state/*.json` 一律先寫 `.tmp` 再 `os.replace()` 原子替換；小助手的 15 分鐘門檻加上依隊名算出的固定相位偏移（0～180 秒 jitter）錯開請求。

---

## (B) 提案：在既有骨架上的補強與改良做法

完全保留使用者定的骨架（**每隊聘便宜小助手 → 定期蒐集 → 決策單隊伍先寫、小助手只傳 → 中轉信箱 → 固定程序 → 網頁**），提出以下四點改良：

### 1. 用「雙軌事實對照」取代「小助手白話覆蓋隊長原話」
* **做法**：
  * 隊長透過 `view_note` 寫下的最新一句話（例如 `B2 圖紙改完，等 build`），本來就是高階模型（opus/sol）親手寫的精確白話。
  * 在網頁的每隊卡片上，**固定並排顯示兩行**：
    1. **【隊長留話】**（程式直接抄 `notes.jsonl` 最新一筆，零失真、零延遲）。
    2. **【助手觀察】**（便宜模型根據成員 `history` 與 daemon 狀態寫出的一句話，例如：`sol-1 正在跑單元測試，sol-2 閒置 20 分鐘`）。
* **好處**：
  * 小助手的模型不需要去「重寫／摘要隊長已經寫好的話」，而是專門負責**「看隊員的 `history` 與 `state` 正在忙什麼」**！這讓便宜模型（terra/haiku）的任務變得更聚焦、更有附加價值；同時就算便宜模型一時胡說或額度用完退回 `none`，【隊長留話】那一行永遠精準可用。

### 2. 決策單的「零信任端到端簽章（Content-Addressed Origin）」
* **做法**：
  * 不靠 `~/.aos/view/state/passed/` 的收據來對帳（因為 `state/` 是隨時會被 `rebuild` 清掉重建的快取）。
  * 隊長跑 `view_decide` 時，工具將問題欄位（`kind, title, questions, risk, deadline, default_if_silent, dedupe_key`）做 Canonical JSON 序列化（鍵排序、無多餘空白），算出 `sha256` 記在隊長的 `view/sent.jsonl`，並把這個 hash 直接寫進決策單的 `id` 或 `origin` 前綴（例如 `d-003@sha256:9f86d08...`）。
  * 固定程序送進專區時，專區原信與專區寄回給隊長的回信（`in_reply_to` 關聯）都會保留這個 `origin`。
  * 隊長收到回信跑 `view_match` 時，除了跑 `user_verify`，直接抓專區 `done/` 原信的題目內容重算一次 Canonical JSON 的 `sha256`，與自己 `sent.jsonl` 裡的 hash 比對。
* **好處**：
  * **完全不依賴中轉站 `aos-view` 的收據狀態**：就算在等待使用者回答的期間跑過 `aos-view rebuild`，或者兩隊用了同一個 `dedupe_key`，隊長都能直接在專區原信上完成密碼學等級的一致性核對，確保「使用者在網頁上看到的每一個字與選項，跟隊長當初寫的一字不差」。

### 3. 給小助手一個「零模型的微體檢」指標（順手抓無效空轉）
* **做法**：
  * 既然小助手的 hook 每 5 分鐘會讀成員的 `aos-agent history -t NAME ls`（唯讀，不花 turn），hook 可以用 10 行純 Python 順手算一個數字放進 `facts`：**「成員最近 5 則 history 裡，是否連續出現相同的錯誤訊息或重複指令（looping）」**以及**「成員最後一則訊息距今幾分鐘」**。
* **好處**：
  * 現有燈號只看「60 分鐘快照沒變」才會亮黃燈，但 agent 常見的另一種卡住是**「一直在忙、history 一直變，但其實是在同一個報錯裡鬼打牆（loop）」**。
  * Hook 把最後幾則訊息的變化與重複率抽成結構化事實交給便宜模型，便宜模型就能在【助手觀察】一眼寫出 `sol-2 連續 4 次卡在同一個權限錯誤`，讓使用者不用等滿 60 分鐘就能在網頁上抓到空轉的隊員。

### 4. 第 0 期的決策回答直接「同頁內嵌或代理」，不要求使用者同時開 8766 與 8767 兩個伺服器
* **問題背景**：
  * **01 A** 指出專區的 `aos-user serve`（8766）目前**沒在跑**，也不是常駐 daemon。
  * **03 §2.3** 把第 0 期改成「全景頁（8767）只顯示待辦，按鈕連去 `127.0.0.1:8766/l/<信>`（要使用者自己另外開著 `aos-user serve`）」。這會讓第 0 期的體驗變成「為了看一頁，反而要顧兩個 port」。
* **做法**：
  * 全景頁（8767）在第 0 期處理答題 POST 時，不需要重寫或複雜地 import `zone.py` 內部狀態，直接由 8767 後端用 `subprocess.run(["aos-user", "answer", ...])` 呼叫專區現成的 CLI 即可！
* **好處**：
  * `aos-user answer` CLI 本來就是專區經過測試的正式入口（`via=cli` 或補一個 `--via web` 旗標），全景頁只需約 20 行 Python 轉發就能在第 0 期立刻實現「只開 8767 一個常駐網頁就能看全景＋答決策」，完全不碰專區內部程式碼，驗證鏈也 100% 原生相容。
