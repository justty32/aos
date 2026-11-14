這份是 wake-1114 送 Argon（Gemini 4 Argon High）審 02、03 與原型補丁的回覆原文，一字不改。

# wake-1114 04 Argon 原文（第一輪審 02、03 與原型補丁）

← [wake-1114](../wake-1114.md)｜2026-11-14 13:31，`agy -p … --model "Gemini 4 Argon (High)" --mode plan`，提示在 `/tmp/ok-wake-argon-1/prompt2.txt`（第一行加「不要呼叫任何工具」；第一次沒加，輸出是空的）。以下一字不改。

### 總結論

1. **方向可行，但不能照原型直接上，且不屬於「不必使用者細看的小改」**：`claude -p` 透過中途塞信確實能省掉「等背景任務」與「跨輪重開 CLI」的時間；但原型存在**超時或崩潰時永久掉信且連同前序回答一併丟失**、**開關名稱寫錯導致存檔即全活樹預設開啟**、**`select` 在串流輸出時無節流狂刷磁碟**、以及 **`midturn.More` 本身無法支援批次投信且有卡死漏洞**等問題。
2. **實測數據混淆了兩個不同指標**：「四個工具」那組在表格裡填的是「回執時間 8.0 秒」，但模型實際要等四步工具全部跑完（約 27 秒）才真正處理該信，並非「工具做完＋1 秒就得到回應」；真正降到 1.3 秒的只有「前景已結束、單純在等背景任務」的情境。
3. **有比未公開 socket 更穩的官方替代路**：不需改成常駐行程，只要在現有「一輪一行程」內改用官方 `--input-format stream-json` 延後關 `stdin`，或改用官方 `Stop` hook，就能避開未公開 `cc-socks` 與行程退出競態。

---

## (A) 審查發現（共 12 項）

### 一、事實錯誤與測量缺口

#### 1. 【高】「四個工具」實測把「收件回執時間」當成「模型回應延遲」，誇大了中途插隊效果
- **問題**：`02` 定義「延遲＝t1（模型跑 `date` 的時間）− t0（送出時間）」。各列都填 `t1 − t0`，唯獨「一輪在跑（四個工具）」填了「**回執 8.0 秒**」，並在說明承認「第一個工具空檔就收進去；模型選擇做完四步才回」。這代表實際回應延遲 `t1 − t0` 仍在 **25～27 秒左右**，跟現況（27.3 秒）幾乎沒差。`02` 與 `03` 結論卻據此宣稱「一輪正在跑時，延遲從等整輪降到等手上那個工具做完＋約 1 秒」，把「信進 context 的時間」跟「模型動手處理的時間」混為一談。
- **具體修法**：在 `02` 表格把「回執延遲（進 context）」與「回應延遲（t1 − t0）」拆成兩欄，補上「四個工具」真正的 `t1 − t0` 秒數；並在結論改寫為：「信可在下一個工具空檔（約 1 秒）進 context；若行程正在等背景任務，模型約 1.3 秒即回應；若模型正在跑多步前景計畫，何時回應取決於模型是否決定中斷原步驟。」

#### 2. 【中】「暖好快取比下一輪重起 CLI 省額度」說法不實；中途塞信在多工具輪反而更耗 token
- **問題**：`03` 比較表說主案 A「是在已經暖好快取的同一段對話裡處理，比下一輪重起 CLI 省」。事實上 Anthropic 的 Prompt Cache 存在雲端伺服器（TTL 5 分鐘），下一輪用 `claude -p --resume <sid>` 重起 Node 行程**照樣命中同一份雲端快取**，重起只多花本機 Node 啟動的 1～2 秒 CPU，不會多花快取 token。反過來，在「四個工具」這種中途把新信塞進第 1 個工具空檔的情況，第 2、3、4 步工具呼叫的每次 LLM 請求都會多帶這封新信的 token，**反而增加 token 消耗**。
- **具體修法**：修正 `03` 額度成本欄說明：省下的是本機啟動 CLI 的 1～2 秒延遲，不是雲端快取額度；若在長工具鏈早期塞入普通信，後續每步工具呼叫會重複計費該信的長度。

#### 3. 【中】僅測 Haiku，且未測模型在「多步修改／寫檔中途」被打斷時的行為風險
- **問題**：`02` 只用數質數（純讀取／計算）配 Haiku 測試。實務上 eca 用 Opus／Sonnet 做多步改檔與 commit 時，中途從 `UserPromptSubmit` 插入一封新信：
  1. 模型可能直接轉去做新信的事，把原本改到一半的工作忘在半路（工作被打斷、半成品殘留）。
  2. 模型也可能像四步數質數那樣把新信晾到最後才回，甚至忘記回。
- **具體修法**：補跑一組 Opus／Sonnet 在「三步改檔工作」中途收到（a）普通問候信、（b）急件信的實測，確認原工作完成率與新信回覆率，並在信封格式上標註優先級（見提案 B-2）。

---

### 二、漏掉的風險（掉信、重複、重入、中斷、成本）

#### 4. 【高】掉信與連坐丟失：回執即刪信（`more.sent`）＋固定 `deadline` 砍行程＝新舊信回答全滅
- **問題**：
  1. `UserPromptSubmit` 觸發只代表「信進了 CLI 輸入端」，**不代表模型已經回答完**（如四個工具案，第 8 秒就有回執，但第 27 秒才回答）。原型卻在一拿到回執就呼叫 `more.sent()` → `hand.extra()`，把信從 queue 標記完成消掉。
  2. `run_claude_stream_mid` 的 `deadline`（預設 600 秒）在行程啟動時算死，**中途塞信不會延長 `deadline`**，且所有 `results` 都存在 Python 記憶體裡等行程結束才一次回傳。
  3. 一旦因為中途多塞了幾封信導致總時間超過 600 秒，`p.kill()` 砍掉行程並呼叫 `cli_base.die("CliFailed")`：不僅最後那封已拿回執的信**永久掉信**，連同同一行程前面已經跑完的 `result` #1、#2 的回答也**全部在記憶體裡被丟棄、沒寫進 history**，還會觸發 `cooldown.json` 冷卻！
  4. 更嚴重的是：`run_claude_stream_mid` 在 `p.kill()` 跳出迴圈後，竟然還跑 `mid.finish()`；若 `p.kill()` 前一刻回執剛寫入，`mid.finish()` 會在行程被砍死後照樣呼叫 `self.more.sent()` 把信消掉！
- **具體修法**：
  1. `run_claude_stream_mid` 若因 `timed_out` 或 `p.returncode != 0` 結束，**絕不可呼叫 `more.sent()`**。
  2. 區分「已進 socket（acked）」與「已拿到對應 `result`（completed）」：直到看見該輪 `result` 事件落地前，信在 queue 應維持可復原狀態（或每收到一個 `result` 就即時 flush 並結清對應信件）。
  3. 每次成功中途投信時，適度順延 `deadline`（但設單輪總上限與最多中途投信封數，見第 5 點）。

#### 5. 【中】重入與「黏輪」（Unbounded Turn）：信源源不絕時單一 `-p` 行程永遠不結束
- **問題**：如果某隻 eca 在忙時每 10～20 秒就收到一封新信，中途投信會讓同一個 `claude -p` 行程一輪接一輪跑下去，永遠走不到 `aos-eca-turn` 的收尾階段：
  1. `aos-eca-turn` 的輪末整理、history 寫入、冷卻重置都被卡住。
  2. 若後面排了一封 `/slash` 指令信，`More.take()` 雖會設 `self.stopped = True`，但前面已塞進去的信若拖太久，slash 指令也會跟著被卡。
  3. 多封信的回答最後只用 `"\n\n".join(texts)` 糊成同一個字串回傳，history 與呼叫端分不清哪一段回答對應哪一封信，且 `out` 只留最後一個 `ev`，若前一輪 `is_error` 或最後一輪 `is_error` 狀態不同會被蓋掉。
- **具體修法**：為 `MidPrint` 加上單輪上限（例如 `max_mid_letters = 3` 或單輪已跑超過 300 秒就不再中途塞信，留給下一輪）。

#### 6. 【中】退回的信（`unsent`）在下一輪會重複執行 `before_queue` hook
- **問題**：`More.take()` 先把信從 `new/` 移到 `cur/`，接著跑 `before_queue(self.stack, self.box, sig, body, self.template)`。若隨後 socket 投遞失敗或行程結束前沒拿到回執而呼叫 `more.unsent()`，信留在 `cur/`；下一輪再處理 `cur/` 這封信時，**`before_queue` 會對同一封 `sig` 再跑第二次**。若 `before_queue` 有副作用（記帳、轉發、改寫內容），就會重複觸發。
- **具體修法**：在 `More.take()` 裡，或者先確認 socket 可連再 `take`，或者對已進 `cur/` 跑過 `before_queue` 的信做記號避免重複執行。

#### 7. 【中】未帶 `CLAUDE_CODE_MESSAGING_TOKEN` 且開 `crossSessionInbound: accept` 的安全與改版風險
- **問題**：`02` 提到環境裡有 `CLAUDE_CODE_MESSAGING_TOKEN`，但目前不帶 token 也能投。原型開了 `crossSessionInbound: accept` 卻不驗 token：
  1. 同 UID 下任何子行程（含模型跑的第三方腳本）都能掃 `/run/user/1000/cc-socks/*.sock` 偽造使用者指令塞進任何 eca（不像 `PostToolUse` 會被模型視為外部工具輸出，socket 進去的信擁有 User Prompt 最高權限）。
  2. Claude Code 既然已放進 `CLAUDE_CODE_MESSAGING_TOKEN`，未來小改版隨時可能強制驗 token。
- **具體修法**：`SessionStart` 的 `note_socket(cell)` 順手記下環境變數 `CLAUDE_CODE_MESSAGING_TOKEN`，`cli_a2a.deliver` 投信時一併帶上 token。

---

### 三、原型程式碼與現有 `midturn.More` 的具體臭蟲

#### 8. 【高】開關名稱與預設值寫反：存檔當下活樹就會全開（違反 06 第 5 條）
- **問題**：`03` 寫明「`cli.json` 加 `"a2a_print": false` 開關，先預設關……原型可以直接抄 `patch_proto.py`」。但 `patch_proto.py` 實際寫的是：
  `if more is not None and cli_a2a.ENABLED and cfg.get("a2a", True) is not False:`
  它讀的是畫面用的 `"a2a"`，而且**預設值是 `True`**！照抄進 `proto8` 存檔的瞬間，活樹所有沒開畫面的 eca 都會立刻啟用。
- **具體修法**：改為 `cfg.get("a2a_print", False) is True`，先預設關閉。

#### 9. 【高】`run_claude_stream_mid` 的 `select(0.5)` 在有輸出時完全沒節流，變成每毫秒狂刷磁碟
- **問題**：`02` 寫「讀 stdout 改成 select 每 0.5 秒醒一次」。但 `sel.select(0.5)` 的 `0.5` 是**最長等待時間（timeout）**；當 `claude -p` 正在串流輸出 JSON 行時，stdout 隨時可讀，`sel.select(0.5)` 會**立即返回（每毫秒等級）**，每讀一個 chunk 就呼叫一次 `mid.tick()`！而 `mid.tick()` 每次都讀 `socket_path` 檔案、列出 `new/` 與 `cur/` 目錄（或讀 `acks` 檔），等於在模型吐字期間每秒執行數百次檔案系統 I/O。
  - 順帶兩個小洞：`sel = selectors.DefaultSelector()` 沒 `close()`（洩漏 epoll fd）；stdout 結尾若有沒有 `\n` 的殘留 `buf` 會在 EOF 時被直接丟掉。
- **具體修法**：
  1. 用 `with selectors.DefaultSelector() as sel:`。
  2. 記錄 `last_tick = 0.0`，只有當 `now - last_tick >= 0.5` 時才呼叫 `mid.tick()`。
  3. 迴圈結束後若 `buf` 非空，補處理最後一行。

#### 10. 【高】`midturn.More` 的兩處邏輯缺陷：無法支援「一次投完」且在 `hand.good` 殘留時會永遠卡死
- **問題**：
  1. `03` 說施工時要補「一次投完所有正在等的信，不要一封等一封」，但修改清單**只列了 `lib/agent/` 的 4 個檔，漏了 `cmd/aos-eca/aos_eca/midturn.py`**。現有 `More.take()` 寫死 `if self.pending: return []`，且只設單一 `self.pending = (sig, body)`、每次只從 `new/` 搬一封信，不改 `midturn.py` 根本不可能一次投多封。
  2. 現有 `More.take()` 第 9～13 行有既有 bug：
     ```python
     if not names(self.box, "cur"):
         must_post(["take", self.box], ok=(0, NOT_FOUND))
     for sig in names(self.box, "cur"):
         if sig in self.hand.good:
             continue
     ```
     當 `cur/` 裡剛好有一封屬於 `self.hand.good`（上一批收信 `done` 沒消掉）的信時，`names(self.box, "cur")` 非空，導致 `must_post(["take", self.box])` **永遠不會執行**，`new/` 的新信永遠搬不進 `cur/`，`take()` 永遠回傳 `[]`！
- **具體修法**：把 `cmd/aos-eca/aos_eca/midturn.py` 納入修改清單：
  1. 將條件改為先扣掉 `self.hand.good`：`cur_active = [s for s in names(self.box, "cur") if s not in self.hand.good]`，若 `not cur_active` 才 `must_post(["take", self.box])`。
  2. 若要支援一次投多封，`More.take()` 應循環將 `new/` 搬進 `cur/`（遇到 slash 信則停在該封之前），將 `self.pending` 改為 list。

#### 11. 【中】`print_claude` 覆蓋既有 hooks 且與畫面共用 `cell` 的 socket／ack 檔
- **問題**：
  1. `mine.setdefault("hooks", {}).update({e: ... for e in ("SessionStart", "UserPromptSubmit")})` 用 `.update()` 直接**覆蓋**了 `guard_hooks(cfg)` 可能已經註冊在 `SessionStart` 或 `UserPromptSubmit` 的規則。
  2. `print_claude` 與畫面模式共用同一個 `cell` 底下的 socket 與 ack 記錄檔：啟動時 `cli_a2a.forget(cell)` 會清掉同 `cell` 的狀態，結束時卻**沒清掉已死 `-p` 行程的 socket 路徑**，留下過期路徑。
- **具體修法**：
  1. 改用 `mine.setdefault("hooks", {}).setdefault(e, []).append({"hooks": [{"type": "command", "command": cmd}]})`。
  2. 在 `print_claude` 的 `try...finally` 結束時清掉 `-p` 寫入的 socket 檔（或讓 `a2a-print` 使用獨立檔名如 `print_socket.txt`／`print_acks.txt`）。

---

### 四、「小改」判斷是否成立？

#### 12. 【高】不屬於「不必使用者細看的小改」，應定性為「中改（跨層行為變更）」
- **問題**：雖然程式碼行數約 100 多行，但它改變了 `aos-eca-turn` 最核心的不變量（從「一輪一行程、固定一批信、單一 result、原子超時」變成「單一行程中途動態領信消 queue、多 result 拼接、變長執行時間」），且涉及 `cmd/aos-eca/aos_eca/midturn.py` 與失敗復原語意。
- **具體修法**：維持「先加 `a2a_print: false` 開關、預設關、挑一兩隻試跑」，但修完上述第 4、8、9、10、11 項問題並通過超時／崩潰掉信測試後，再請使用者審視放行。

---

## (B) 提案：未考慮的其他做法與改良（共 5 項）

### 1. 不必常駐也能用官方介面：在「一輪一行程」內用 `--input-format stream-json` 延後關 `stdin`（改良方案 D）
- **為什麼沒想到**：`03` 把方案 D（`--input-format stream-json`）當成必須改成「常駐一個 node 行程」的大改而淘汰。其實**完全不必常駐**！
- **怎麼做與好處**：
  - 維持現有 `aos-eca-turn`「有信才起 `claude -p`、跑完就退」的短行程模型。
  - 啟動 `claude -p --input-format stream-json --output-format stream-json` 時，把第一封信寫入 `p.stdin` 後**先不要 `p.stdin.close()`**。
  - 在 `run_claude_stream_mid` 等待期間，若 `more.take()` 拿到新信，直接由父行程往 `p.stdin` 寫入一行官方格式的 user JSON 訊息；等看到 `result` 事件且 queue 已空（或達到單輪上限），再呼叫 `p.stdin.close()` 讓 `claude -p` 乾淨結束。
  - **優勢**：
    1. **100% 官方公開介面**，不靠未公開的 `cc-socks`、不怕 Claude Code 改 socket 格式。
    2. **零退出競態（no exit race）**：只要 `p.stdin` 沒關，`claude -p` 就不會自己退出，徹底消掉「行程快退出時把信投進死 socket」的風險。
    3. **零跨行程安全漏洞**：只有父行程握有 `p.stdin` pipe，不需開 `crossSessionInbound: accept`。

### 2. 利用 Claude Code 官方 `Stop` Hook 在輪末攔截新信（改良備案 B）
- **為什麼比 `PostToolUse` 好**：`02`／`03` 測試了 `PostToolUse`，發現兩個致命傷：（a）模型不用工具時收不到；（b）Haiku 把工具輸出附帶的 `additionalContext` 當成提示注入（prompt injection）而拒絕執行。但研究漏掉了官方的 **`Stop` hook**。
- **怎麼做與好處**：
  - `Stop` hook 會在模型「準備結束當前回答（含不用工具的純文字回答，以及剛把長工作丟背景準備停下的那一刻）」時觸發。
  - 此時 hook 檢查 queue，若有新信就回傳官方格式 `{"decision": "block", "reason": "<aos 信封>"}` 阻止結束並請模型接著處理；若無新信則放行結束。
  - **優勢**：
    1. **不用工具也能觸發**（解決備案 B 最大盲點）。
    2. **不會在四步工具鏈半路插隊打亂計畫**，一定等模型手頭這段做完要停下時才交信。
    3. `Stop` 的 `reason` 是官方設計用來指示模型「繼續未完事項」的管道，不會像 `PostToolUse` 被當成工具輸出的惡意注入。

### 3. 依「行程狀態」與「信件急迫度」分流投遞時機（改良主案 A）
- **為什麼需要**：從 `02` 實測可看出，前景跑四個工具時提早在第 8 秒把普通信塞進去，模型還是第 27 秒才回，白白承擔打亂上下文與多花 token 的風險；真正需要立刻塞進去的是**「行程正在等背景任務」**或**「ok-board 急件」**。
- **怎麼做與好處**：
  - **普通信**：只在 `run_claude_stream_mid` 已經看過至少一個 `result` 事件（代表前景工作已告一段落、行程只是活著等背景任務或 Monitor）時才中途投遞；前景還在跑緊密工具鏈時先不塞，等它吐出第一個 `result` 或進 `Stop` 時再塞。
  - **急件（urgent）**：一到工具空檔立刻投遞，並在信封開頭加上明確系統指示（如 `[aos 急件：請先暫停手頭步驟，優先處理此信]`），讓模型知道這封信應該插隊處理。

### 4. 用 `PreToolUse` Hook 強制「長工作背景化」，不靠模型自己守規矩（強化配套 C）
- **為什麼需要**：`03` 配套 C 指出「30 分鐘的前景 Bash 任何做法都只能乾等」，但解法只寫「在 system 或任務書寫明超過一兩分鐘用 `run_in_background`，靠模型守規矩」。實務上模型常忘記設 `run_in_background`。
- **怎麼做與好處**：
  - 在 `--settings` 的 `PreToolUse`（針對 `Bash` 工具）加一道輕量檢查：若指令未設 `run_in_background: true`，且未設短 `timeout`（或命中耗時指令特徵如 `pytest`、`cargo`、`make`、長腳本），由 hook 自動將 `updatedInput` 的 `timeout` 限制在例如 `60000`（60 秒），或提示模型改用 `run_in_background`。
  - 把「靠模型守規矩」變成「機構硬約束」，確保前景單一工具不會卡死收信超過 1 分鐘。

### 5. 兩階段確認（Two-Phase Commit）與逐輪 `result` 即時落盤
- **為什麼需要**：解決審查第 4 點「拿到 `UserPromptSubmit` 回執就把信消掉，結果後面超時或崩潰導致信與前序回答一起消失」的結構性風險。
- **怎麼做與好處**：
  - **階段一（In-flight）**：`UserPromptSubmit` 回執到達時，只代表信進了 CLI，此時在 `MidPrint` 記為 `in_flight`，**還不呼叫 `more.sent()` 消掉 `cur/` 裡的信**。
  - **階段二（Completed）**：當 `stdout` 讀到對應的那個 `result` 事件（且 `is_error` 為 false）時，才呼叫 `more.sent()` 正式結清該封信，並同時把該段 `result` 文字寫入落盤，就算後面再塞進來的信超時被砍，前面已完成的工作與回答也不會陪葬。
