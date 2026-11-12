# Argon（Gemini 4 Argon High，agy）對第一版圖紙的審查意見原文（11-12；是 Argon 的意見，不是使用者的；fable 怎麼採納見 README「Argon 審查與改圖」）

← [kernel-framework](README.md)｜審的是第一版 `db14cd838`；叫法：Windows PowerShell 的 `agy --model "Gemini 4 Argon (High)" --mode plan --add-dir <暫存夾>`，材料是圖紙七份、11-11 kernel 四份、C-52／新版 C-47／N-42、user/02「審」的範圍。以下照錄（只把指向暫存夾的本機連結換成檔名，行號是第一版的）。

## (A) 審查

- **A1**
  - **類別**：必修
  - **位置**：`01-框架零件.md`「一輪的順序」與 L145、L163、`02-判官收編.md`、`06-邊緣狀況.md` #14（對應 **K-F11**）
  - **問題**：
    1. **一輪的步驟順序導致 `forwarded.json` 防重失效**：「一輪的順序」（L91～95）把步驟 1（收 `replies/` → 代回 → **從 `forwarded.json` 刪列**）排在步驟 2（`requests/cur/` 防重檢查「已轉寄過的 → 收掉」）之前。若站在「已寫 `forwarded.json` 並轉寄、但還沒收掉 `requests/cur/` 原信」時當機重起，而下游在它重起前已處理完該信並把回信寄進 `replies/`，下一輪步驟 1 會先代回並把 `forwarded.json` 那一列刪掉；接著步驟 2 檢查 `requests/cur/` 時，`forwarded.json` 與下一站 `new/`、`cur/` 都已找不到該信，就會把同一封信**再轉寄第二次**，直接推翻 `02` L26 與 `06` #14「有 `forwarded.json` 當防重依據」的保證。
    2. **`forwarded.json` 鍵值方向與無 `reply_to` 有序信的防重缺口**：L163 定義 `forwarded.json` 為 `{轉寄後信名: {"letter": 原信名, "reply_to": 原回信箱}}`（為了給回信依 `in_reply_to` 查表），但步驟 2 防重手上是 `requests/cur/` 的「原信名」——在 `keep_ordered: true` 時轉寄後信名與原信名不同，只查 key 會找不到。且 L163 規定「原信沒 `reply_to`＝不改、不記表」，若有序信沒帶 `reply_to`，轉寄後信名變了又不記 `forwarded.json`，重起時防重完全對不上。
  - **建議改法**：
    1. 一輪的順序先把 `requests/cur/` 裡「已轉寄過的原信」對照 `forwarded.json` 與下一站信箱收掉，之後才跑 `replies/` 代回與刪列。
    2. `already_forwarded` 同時比對 `forwarded.json` 的 key 與 value 裡的 `"letter"`。
    3. `keep_ordered: true` 時就算原信沒 `reply_to` 也記進 `forwarded.json`（`"reply_to": null`），原信收掉後即可清掉 `reply_to: null` 的列。

- **A2**
  - **類別**：必修
  - **位置**：`01-框架零件.md` 步驟 2～3、L134、L174（對應 **K-F8**、**K-F10**、**K-F16**）
  - **問題**：
    1. **`queue_wait_ms: 0`（或當下有格但超過期限）在步驟 2 被誤殺**：步驟 2（L95）在進步驟 3 看規則與格數之前，對所有信無條件執行「帶 `queue_wait_ms` 且已到期 → 拒 `SlotMissing`」，且 L174 寫「`0`＝不排、沒格立刻拒；不管開沒開 `queue` 都先驗期限」。因為寄出（`sent_at`）到站下一輪取信必有時間差（`now > sent_at + 0`），放在步驟 2 先驗會導致凡是帶 `queue_wait_ms: 0` 的信——**就算當下格數全空、或該信根本不佔新格、或站根本沒設 `max_running`**——在步驟 2 就全數被當成過期拒回 `SlotMissing`。
    2. **到期拒信跳過了 `before_verdict` 與 `after_verdict`**：因為到期拒信放在步驟 2，新信若到期不會跑 `before_verdict`（違反 `06-邊緣狀況.md` #23「每封新信都跑」）；排隊中的信到期出隊也不會跑步驟 3 的 `after_verdict`（直接違反 **K-F16** 與 L134「排隊的信後來出隊（forward 或到期 refuse）再一次」）。
    3. **排隊中的信在等待期間每輪重跑 `after_verdict`**：步驟 3 偽碼（L97～100）只標「新信：`before_verdict`」，但對已在隊的信每輪仍跑「內建規則 → `queue` → `after_verdict`」，若隊首等 50 輪就會跑 50 次 `after_verdict`，違反 **K-F16**（「進隊一次、出隊再一次」）。
  - **建議改法**：
    把 `queue_wait_ms` 到期檢查從步驟 2 移入步驟 3 的規則判決：
    - 有格（或該信不佔新格、或站沒設 `max_running`）→ 判 `forward`（不管 `queue_wait_ms` 是否為 0 或已到期）。
    - 沒格時才看排隊與期限：若 `queue: false`、`queue_wait_ms == 0`、或 `now >= sent_at + queue_wait_ms` → 判 `refuse`（`SlotMissing`）；否則判 `queue`。
    - 已在 `queue.json` 的信：每輪先看是否到期（轉 `refuse: SlotMissing`）或有格（轉 `forward`）；**只有判決脫離 `queue`（變成 `forward` 或 `refuse`）時才跑第二次 `after_verdict`**，繼續留隊的不跑。

- **A3**
  - **類別**：必修
  - **位置**：`README.md` **K-F3**、`01-框架零件.md`
  - **問題**：`01` L47 寫「讀進來先過 `aos-directive`（所以可以寫 `{"$env": …, "$path": …}`）；相對路徑從 `kernel.json` 所在的資料夾算」，接著 L71～73 的範例寫 `"handler": "hooks/need_owner"`（普通相對路徑字串，沒包 `{"$path": ...}`）。但 `aos-directive` 只展開 `{"$path": ...}` 物件、不會動普通字串；而 `aos-exec <lib/aos/kernel> <kernel.json>` 執行時的 `cwd` 在共用件那邊、不在 `kernel.json` 所在資料夾（見 `C-52-principles.md` 10-28 例外）。若框架沒有把 `next`、`count_daemon`、`hooks.*.handler` 的普通相對路徑字串也對 `dirname(kernel.json)` 轉成絕對路徑，L71～73 的範例一跑就會找不到 handler。
  - **建議改法**：在 **K-F3** 與 `01` 明定：除 `aos-directive` 的 `$path` 以 `dirname(kernel.json)` 為基準外，`next`、`count_daemon`、`hooks.*.handler` 三欄若為相對路徑字串，載入設定時同樣以 `dirname(kernel.json)` 為基準轉為絕對路徑。

- **A4**
  - **類別**：必修
  - **位置**：`03-狀態查詢信.md` 與 L66～68（對應 **K-F28**）
  - **問題**：`03` L66 規定 `aos-agent ctl who -j` 的 `"daemon"` 改成「問來那份表所在的資料夾（相對路徑的基準）」，L68 讓 `fork`、`subagent` 跟著拿 `who -j` 的 `"daemon"` 用。但當中間站用 `before_reply` hook 產出刪減表時，L34 規定刪減表「放在自己的 stack 裡」（且表內各列 `stack` 寫絕對路徑，**K-F28**）。這時 `who -j` 的 `"daemon"` 會變成**中間站的 stack 資料夾**，而非底層真正掛 proc 的 daemon 資料夾；`fork`／`subagent` 若拿這個 `"daemon"` 去算子項或分身的位置就會指錯地方，也違反「背後是黑盒子」（`11/kernel/README.md` 結論 2）。
  - **建議改法**：`py/daemon_ctl/table.py` 讀表時直接把各列的相對路徑（`stack` 等）依 `dirname(表檔路徑)` 解成絕對路徑；`fork`／`subagent` 直接以 `who -j` 裡自己那一列的 `stack`（已是絕對路徑）為基準，不依賴 `"daemon"` 欄位。

- **A5**
  - **類別**：必修
  - **位置**：`README.md` **K-F14**、`01-框架零件.md` 與 L163、`05-施工步驟.md` 步 8 段 3
  - **問題**：
    1. `05` 步 8 段 3 要驗 `station_a` 的 `before_reply` hook 產出刪減表（「只有 agent 自己那幾列」）。但 `forwarded.json`（`01` L163）只記 `{"letter": 原信名, "reply_to": 原回信箱}`，而 `before_reply` 事件 JSON（L135）的 `sender` 是「回信的寄件人」（下游 daemon），不是原請求的 `sender`。當寄件人用共用回信箱（如 `$AOS_KERNEL/reply/`）或 `before_reply` 要依原寄件人過濾時，hook 根本不知道是誰問的。
    2. 步 8 的樹（`05` L37～43）裡 `foreman` 底下本來就只有 `假腦 agent` 與它的 subagent，沒有別的 proc，就算沒刪減也只有它自己那幾列，驗不出過濾效果。
  - **建議改法**：
    1. `forwarded.json` 多記一個輕量欄位 `"orig_sender"`（原信封的 `sender`，仍不留原 `body`），並放進 `before_reply` 事件 JSON。
    2. 步 8 的 `foreman` 底下多掛一個無關的陪測 proc（例如 `other`），段 3 明驗刪減表裡看得到 `agent`、看不到 `other`。

- **A6**
  - **類別**：設計問題
  - **位置**：`01-框架零件.md`、`06-邊緣狀況.md` #4（對應 **K-F13**）
  - **問題**：`01` L164 寫「代回前先看原回信箱還在不在：不在＝warning、收掉、刪列；**在但寄不出去＝留著下一輪再試**」。若原回信箱資料夾存在，但因 Linux 權限不足或非合法信箱而寄不進去，留在 `replies/cur/` 下一輪再試會導致**之後每一輪步驟 1 都對同一封回信重跑一次 `before_reply` hook**，且永遠卡在 `replies/cur/`。對照轉寄請求（L149）寄不進去都不重試了，代回失敗卻無限重試，違反 C-53「錯誤路徑收斂」與 C-56（KISS）。
  - **建議改法**：代回時原回信箱不在**或 `aos-post send` 失敗**，一律印一行 warning、刪 `forwarded.json` 該列、收掉回信（寄件人本來就靠自己的逾時處理）。

- **A7**
  - **類別**：設計問題
  - **位置**：`README.md` **K-F18**、`01-框架零件.md`
  - **問題**：
    1. 11-11 選項框裁定（`01-原話與經過.md`）明寫三個時機「沿用 agent 那套 hook 契約（退 0 加輸出＝修改、退 10＝攔下、逾時、on_error）」。**K-F18** 與 `01` L135 卻特判 `before_reply`「退 10：不能攔（當 0）」。寫 hook 的人照契約退 10 想攔截，框架卻偷偷當成退 0 把未修改的原回信放行出去，這是違反 `C-56`「寫什麼就做什麼、不埋暗規則」的地雷。
    2. `01` L129 寫沿用 `intercept`（預設 `true`）與 `async`（預設 `false`），但 L131～135 表格沒交代當 `intercept: false` 或 `async: true` 時，stdout 輸出與退 10 要忽略（不改、不攔）。
    3. `01` L98～100 沒寫當 `before_verdict` 退 10 攔下時，是否跳過內建規則與 `after_verdict`。
  - **建議改法**：
    1. `before_reply` 退 10 時照契約攔下原回信，改代回 `{"applied": false, "error": {"code": "HookRejected", "msg": ...}}`（或收掉不代回＋warning，不可當成退 0 放行原內容）。
    2. 明定 `intercept: false` 或 `async: true` 時不取 stdout 修改、退 10 不攔。
    3. 明定 `before_verdict` 退 10 時直接進 `refuse`（`HookRejected`），不跑內建規則與 `after_verdict`。

- **A8**
  - **類別**：設計問題
  - **位置**：`README.md` **K-F6**、**K-F7**、L101～107「衝突 2」、`01-框架零件.md`
  - **問題**：
    1. **衝突 2 的分析理由不準，但代定 K-F6 的結論是對的**：圖紙把「去看 `next` 上一層有沒有 `procs_state.json`」定性為違反 C-52「認對方身分」，但 `procs_state.json` 是公開窗（`C-52-principles.md` 11-06 P7 註明文准看公開窗）。真正不能猜的實質原因是：(a) `next` 是信箱路徑而非 stack，daemon 的 ctl 信箱未必在 stack 直屬下一層；(b) daemon 剛起還沒寫出 `procs_state.json` 時（`01` L154）會把真 daemon 誤判成非 daemon；(c) **若下一站是「當別台 daemon 身體（繼承式）的中間站」，它上一層真的有那台中間 daemon 的 `procs_state.json`，去猜就會數錯台**！因此 **K-F6**（寫了 `next` 又寫了 `max_running` 必寫 `count_daemon`）完全符合 C-56「不猜」，這其實是把 11-11 裁定落實精確，不必當成跟 C-52 打架。
    2. **K-F7 自指檢查漏了「沒寫 `next`」的情況**：在繼承式擺法中（`$AOS_STACK == $AOS_DAEMON`），若沒寫 `next`、而 `daemon.json` 的 `procs_requests` 被誤設成 `"requests"`，預設算出來的目標信箱也是自己的 `$AOS_STACK/requests/`，一樣會自指成環。
  - **建議改法**：
    1. 衝突 2 改用上述三個實質理由說明（尤其是繼承式中間站會數錯台），維持 **K-F6**。
    2. **K-F7** 改為：不論 `next` 是明寫或由 `$AOS_DAEMON/<procs_requests>` 算出，只要目標信箱的 `realpath` 等於 `$AOS_STACK/requests` 的 `realpath`，一律報 `CfgBad` 退 1。

- **A9**
  - **類別**：設計問題
  - **位置**：`01-框架零件.md` 與 L173（對應 **K-F2**、**K-F8**、**K-F17**）
  - **問題**：
    1. L134 在通用框架的 `after_verdict` 事件 JSON 頂層塞了 `procs_*` 專用的 `names`（「要新格的名字」），既與 `body` 重複，又在通用 hook 介面裡混入 `procs_*` 假設。
    2. **K-F17** 准 `after_verdict` 把 `verdict` 從 `"forward"` 改成 `"refuse"`，但沒規定當 hook 只回 `{"verdict": "refuse"}` 沒帶 `"error"` 時，拒信的 `error.code` 與 `error.msg` 填什麼。
    3. L173 規定 `before_verdict` 改過 `body` 且信進隊時，把整份 `body` 寫進公開窗 `$AOS_STACK/queue.json`。`queue.json` 是給外部查排隊位置用的公開窗，把可能很大或含敏感設定的完整請求 `body` 塞進公開窗既肥大又洩漏內容。
  - **建議改法**：
    1. `after_verdict` 事件 JSON 拿掉頂層 `names`（hook 要看自己讀 `body`）。
    2. 明定 `after_verdict` 改判 `"refuse"` 而未給完整 `error` 時，預設填 `{"code": "HookRejected", "msg": "refused by hook <名>"}`。
    3. `before_verdict` 改過的 `body` 不要放進公開的 `queue.json`（可改存私有檔或直接更新 `requests/cur/` 內該信）。

- **A10**
  - **類別**：設計問題
  - **位置**：`03-狀態查詢信.md`（對應 **K-F28**、**K-F30**、**K-F31**）、`06-邊緣狀況.md`
  - **問題**：
    1. **L48 與 L65 自相矛盾**：L48（**K-F30**）規定「有設 `AOS_KERNEL` 卻問不到（沒回信）＝報 `KernelFailed`」，L65 講 `ctl_wait`／`phase_body` 卻寫「要對表的地方讀問來的那份，**問不到表就只看回信**」。若 `state_path()` 問不到就直接報 `KernelFailed`，`ctl_wait` 便走不到「問不到表就只看回信」；反之若手寫的 kernel 不答查詢信（L35），`ctl_wait` 就會壞掉（見提案 B3）。
    2. **刪減表放在中間站 stack 的權限與 `event.json` 洩漏**：`03` L34 讓 `before_reply` hook 把刪減表「放在自己的 stack 裡」，但 `01` L42／L129 規定框架會在 `$AOS_STACK/hooks/<名>/event.json` 留最後一次事件（含**未刪減前**的底層 `procs_state_path`）。若對下游開放中間站 stack 的 Linux 讀取權限，下游可順手讀走 `hooks/<名>/event.json`；且若底層 daemon 的 `procs_state.json` 本身沒靠 Linux 權限擋住下游，換路徑也擋不住直讀。
    3. **3 秒逾時（K-F31）在多站鏈＋慢 hook 下的邊緣狀況**：`01` L129 的 hook 預設 `timeout_ms` 是 60 秒；若中間站在跑慢的同步 hook 或鏈較長，查詢信穿過多站再代回很容易超過 3 秒而報 `KernelFailed`。`06-邊緣狀況.md` #31 應補註此情況（並說明可帶 `--timeout` 調大或讓中間站 hook 走 `async`）。
  - **建議改法**：
    1. 採提案 B3，`ctl_wait`／`phase_body` 有設 `AOS_KERNEL` 時只看請求本身的回信，不另外寄 `procs_state_path` 查詢信。
    2. `03` L34 與 `06` #30 補註：要做讀取隔離時，底層表與中間站 `hooks/` 須靠 Linux 權限對下游關閉讀取，刪減表寫在對下游開放的位置。

- **A11**
  - **類別**：要使用者裁定
  - **位置**：`README.md`、`04-問腦併不併.md`、`11/kernel/03-過時清單與日後清單.md`（對應 **K-F29**、**K-F37**）
  - **問題**：
    1. **方向題 1 的推薦 A 站得住，但漏說了「框架站可直接串在 C++ 問腦總機前面」**：`04-問腦併不併.md` 寫選 A 的後果是「問腦沒有 hook」。其實因為 **K-F8**（不寫 `allowed`／`max_running` 的站不驗 `body`、原樣轉），在選項 A 下，**只要在 C++ `aos-llm-kernel` 前面擺一站 `lib/aos/kernel`（`next` 指到 `aos-llm-kernel/requests`），問腦鏈就自動擁有 `before_verdict`／`after_verdict`／`before_reply` 三個 hook 與 `reply_via_me`**，0 小時就能在問腦前做審計、改 prompt、攔截或過濾回信，完全契合 11-11「在請求格式之內不多做限制……在這個框架下擴充更多功能如 llm」，根本不必把 2343 行負責排程與掛 proc 的 C++ `aos-llm-kernel` 拆掉重寫（選項 B 違反 KISS）。
    2. **漏列給使用者拍板的題（猜 `./.stack` 留不留）**：11-11 使用者明說「`AOS_KERNEL` 沒設的話就走 `AOS_DAEMON`，兩個都沒設，那就報錯」（`11/kernel/README.md` 結論 2）；11-12 使用者問「只是猜 `.stack` 感覺可以留著?」（帶問號）。`README.md` L127 標註「11-12 未定案」卻直接寫進 **K-F29** 且未列給使用者確認，步 9（`05` L19）又寫「N-63 02 加註成已實作」（而 `11/kernel/03` L22 原列 N-63 02 要改成「不再猜」）。
  - **建議改法**：
    1. 方向題 1 維持推薦 A，並補入「問腦需要 hook 時直接在前頭串一站 `lib/aos/kernel` 即可，不用動 C++ 總機」。
    2. 補一題給使用者確認：「`AOS_KERNEL` 與 `AOS_DAEMON` 都沒設時，確定保留 fallback 猜 cwd 的 `./.stack` 嗎？（留＝N-63 02 的 11-05 例外不動）」。

- **A12**
  - **類別**：建議
  - **位置**：`05-施工步驟.md`、`02-判官收編.md`
  - **問題**：
    1. **步 2 的 `rg` 驗收條件在步 9 完成前必敗**：步 2（L12）驗法要求 `rg 'aos/judge|judge\.json|judge_replies|judge_ordered'` 在 `proto8/`（不含 thinking、`templates/judge-llm`）0 命中，但 `docs/NORMS/附錄4-持久檔.json`（11 處）、`kernel/README.md`、`kernel/docs/02`、`knowledge/` 的舊名被排在**步 9** 才改，步 2 做完跑 `rg` 必會命中。
    2. **步 2 與步 3 切開造成重工**：原判官已有 `keep_ordered` 的代回（`judge_replies/`＋`judge_ordered.json`）。步 2 先搬進 `letters.py` 改名成 `replies/`＋`forwarded.json`，步 3 馬上又改同一段 `letters.py` 把它泛化成 `reply_via_me` 並加上 **K-F12**（弄壞步 2 剛改好的舊 `keep_ordered` 測試）。
    3. **步 5 並行前提不一致**：L15 寫步 5 先做完誰：「另一條線進 main」，L27 卻寫「一開始三條同時開：步 1、步 2、步 5」。
  - **建議改法**：
    1. 步 2 與步 3 合併成一步（改名拆模組時順手把代回泛化為 `reply_via_me`，工時約 9 小時，省 2 小時重工）。
    2. 步 2 的 `rg` 驗收範圍明寫排除步 9 負責的 `docs/`、`kernel/docs/`、`knowledge/`（或把 `附錄4-持久檔.json` 隨步 2 一起改）。
    3. L27 明寫「待 `/tmp/line-kernel` 與 `/tmp/line-kernel-norms` 進 main 後，步 1、步 2、步 5 三條同時開」。

---

## (B) 提案

- **B1：拿掉 **K-F33**（`aos-agent ctl state-path`），`on_clock` 直接快取「鐘檔路徑」而非「狀態表路徑」**
  - **做法**：不新增 `aos-agent ctl state-path` 子命令。`lib/agent/hooks.py` 的 `_clock_file` 當 `clock` 寫 proc 名時，第一次（或快取的 `clock.json` 讀不到時）直接呼叫既有的 `aos-agent ctl ls --json` 找到該 proc 的 `stack` 絕對路徑，把算好的 `<proc_stack>/clock.json` 記進 `on_clock.json`；之後每拍直接讀那份 `clock.json`。
  - **理由**：`on_clock` 真正要讀的是目標 proc 的 `clock.json`，不是整張 `procs_state.json`。照原 **K-F32**／**K-F33**，`on_clock` 快取表路徑後，每拍還要自己讀整張 `procs_state.json`（並在 `hooks.py` 重寫一次 `aos-directive` 解超過 100 列切檔與相對路徑換算）。直接快取最終的 `clock.json` 路徑，每拍少讀一張表、`hooks.py` 不必複製 `table.py` 的讀表邏輯，連專為它新開的 CLI 子命令 `aos-agent ctl state-path` 都能整支省掉。
  - **代價**：若鐘 proc 被移除又在別處同名重建、且舊的 `clock.json` 檔案還殘留在磁碟上，快取不會察覺（但這與原設計舊 `procs_state.json` 殘留是同一等級的邊緣狀況）。

- **B2：`ctl_wait`／`phase_body` 有設 `AOS_KERNEL` 時只看請求回信，不額外寄 `procs_state_path` 查詢信**
  - **做法**：在 `03-狀態查詢信.md`，`aos-agent` 寄控制請求（掛 proc、start、stop、rm 等）且設有 `AOS_KERNEL` 時，只等該封請求的回信（`{"applied": true}` 或 `false`），不再呼叫 `state_path()` 去拉狀態表核對；只有明確查表的子命令（`ctl ls`、`ctl who`）才寄 `{"procs_state_path": true}`。
  - **理由**：徹底落實 11-11「一律寄 `AOS_KERNEL`、背後是黑盒子」，消除 `03` L48 與 L65 的矛盾，省掉每次掛 proc 多走一趟跨站查詢信的雙倍延遲，而且當對象是「只處理掛 proc、不回答狀態查詢」的手寫 kernel（`03` L35）時也能正常運作。
  - **代價**：無。

- **B3：`keep_ordered: true` 自動開啟代回（或允許不代回），拿掉 **K-F12** 的組合 `CfgBad`**
  - **做法**：當 `kernel.json` 寫 `"keep_ordered": true` 而未顯式寫 `"reply_via_me": false` 時，自動視同開啟代回（相容原判官 `judge.json` 的寫法）；若顯式寫 `"keep_ordered": true, "reply_via_me": false`，就照字面「有序轉寄、不代回」（對不設 `reply_to` 或不靠原信名對 `in_reply_to` 的寄件人完全合法）。
  - **理由**：消除「開 A 旗標時必須手動跟著寫 B 旗標」的耦合規則，符合 C-56「寫什麼就做什麼」，也減少 `keep_ordered` 與 `reply_via_me` 的概念重疊。
  - **代價**：無（少一條 `CfgBad` 檢查）。

- **B4：步 1 抽 `lib/hook_run.py` 時，連同 hook 格設定驗證、排序、`condition` 比對與 `event.json` 落檔一併收進去**
  - **做法**：`lib/hook_run.py` 不只封裝「跑單一 handler 子行程」，也提供驗證 hook 格欄位（`event`、`handler`、`condition`、`intercept`、`async`、`on_error`、`timeout_ms`）、依名字排序、比對 `condition`、寫 `hooks/<名>/event.json` 與處理 `on_error` 的共用函數。
  - **理由**：避免同一套 hook 契約的設定檢查與派發迴圈在 `lib/agent/hooks.py` 與 `lib/aos/kernel/` 各寫一份（消除 `PROMPT.md` 點名的「hook 契約兩份實作」冗餘），步 4 工時可從 5 小時縮減為 3 小時。
  - **代價**：步 1 多抽約 40 行共用邏輯。

---

整體評價：圖紙把判官收編為通用框架站與「狀態在哪」查詢信的大方向乾淨且忠於 11-11 裁定與 KISS 原則（方向題 1 推薦 A 先不併完全正確），唯獨「一輪的順序」存在防重刪列先後顛倒與 `queue_wait_ms` 先驗誤殺兩個實作必踩的邏輯漏洞，加上刪減表下 `who -j` 路徑基準與 `before_reply` 缺少 `orig_sender` 等五處必修問題，修正後即可穩健動工。
