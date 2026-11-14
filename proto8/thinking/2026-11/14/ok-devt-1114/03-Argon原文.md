# ok-devt-1114 03：Argon 對 02 設計稿的審查原文（11-14）

← [ok-devt-1114](../ok-devt-1114.md)｜審的是 [02-設計](02-設計.md)｜採納表 [04](04-採納表.md)

> 指令：`agy -p … --model "Gemini 4 Argon (High)" --mode plan`，提示＝01＋02 全文。以下原文照貼，沒改字。Argon 沒看過 ok-limits 的 B7 圖紙，所以它對 B7 的幾點是照 02 第四節的摘要推的。

我是 Argon。以下針對 `02-設計.md`（對照 `01-現況.md` 的程式碼事實）進行審查與共同設計，分為 **(A) 02 設計稿具體問題審查（含第五節五題逐題回覆）** 與 **(B) 更簡單或更安全的替代提案** 兩部分。

---

## (A) 02 設計稿審查：具體問題與修正

### 一、具體問題清單

1. **[1.3、3] `notify_box=""`（空字串）與 daemon `CfgBad` 自相矛盾，且漏掉環境變數繼承污染**
   - **嚴重度**：blocking
   - **問題**：
     1. 1.3 一方面寫「`notify_box` 明給的優先（含空字串＝不要）」，另一方面又寫「daemon 收到 spec 裡的 `parent`、`notify_box` 都必須是非空字串，否則 `CfgBad`」。若呼叫端傳 `--notify-box ""` 並被 `add_letter` 寫入 spec，第 2 期 daemon 會直接報 `CfgBad` 拒絕掛載。
     2. 由 `01` 第一節可知，daemon 起子行程時只設 `AOS_STACK`、`AOS_DAEMON`、`AOS_WS`，**其餘環境變數全從 daemon 自身環境繼承**（`child.cpp:81-84`）。若上層啟動下層巢狀 daemon（或啟動 daemon 的環境本身帶有 `AOS_PARENT_STACK`、`AOS_NOTIFY_BOX`），當新行程在表上「沒有 `parent` 或 `notify_box`」時，daemon 若只「有值才 `setenv`」而沒有「無值時 `unsetenv`」，子行程就會**誤繼承 daemon 自己的環境變數**。
   - **修正**：
     1. `add_letter` 收到 `notify_box=""` 時，代表「明確不要回報信箱」，做法應是**不在 spec（及第 1 期 `exec.envs`）寫入該鍵**，而非寫入空字串。
     2. 第 2 期 `child.cpp` 起行程時，若列上無 `parent` 或無 `notify_box`，必須明確呼叫 `unsetenv("AOS_PARENT_STACK")` 與 `unsetenv("AOS_NOTIFY_BOX")`；第 1 期若收到 `notify_box=""` 則設空字串並在 `who.py` 轉為 `null`。

2. **[2.3、4] Linux 行程與訊號事實錯誤：`stop_cause.json` 的「第一個原因不覆寫」、正常退出的競態、以及 `aos-sandbox` 的 PID ticks 錯位**
   - **嚴重度**：blocking
   - **問題**：第 4 節審 `ok-limits` B7 時判定「機制與值都合」，但裡面有三個 Linux 行程層級的漏洞：
     1. **「第一個原因不覆寫」會記錯死因**：當 daemon 執行 `ctl sleep` 時，會寫入 `cause: "sleep"`（綁定該行程的 `started_at_ticks`＋`boot_id`）並送 `SIGTERM`。若該行程卡住沒退，最後觸發 `stuck` 重起或被使用者 `ctl rm`（`remove`）殺掉，因為它**還是同一個行程實例（`ticks`＋`boot_id` 沒變）**，「第一個原因不覆寫」會導致最終 `after_stop` 吐出舊的 `"sleep"` 而非真正殺死它的 `"stuck"` 或 `"remove"`。同理，若 `sleep` 逾時未停、行程繼續跑，兩小時後才因 `shutdown` 被停，也會讀到殘留的 `"sleep"`。
     2. **自然結束與訊號的競態**：當 `aos-loop` 剛跑滿 `max` 或身體退 10（`body_exit`，此時 `code=0, signal=null`）正要跑 `on_stop` 時，若 daemon 剛好發起 `shutdown`／`sleep` 寫下 `stop_cause.json`，`loop` 若無條件先讀原因檔，就會把 `code=0, signal=null` 的自然結束誤報成 `cause: "shutdown"`。
     3. **`aos-sandbox` 與 limits 的行程事實錯誤**：2.3 稱「撞到限額的是身體，loop 只看得到身體被訊號殺」。事實上，daemon 的 `tend.cpp`（如 `cpu_s`、`file_mb`）與 Linux cgroup OOM（`mem`）殺的是整個 cgroup 或頂層行程（包含 `aos-loop` 本身，且 OOM 送 `SIGKILL` 時連 `on_stop` 都跑不到）。此外，若行程外層包了 `aos-sandbox` 且 `aos-sandbox` 有 `fork` 子行程來跑 `aos-loop`，則 `aos-loop` 讀自己的 `/proc/self/stat` 第 22 欄 `starttime`，會跟 daemon 表上記的頂層 PID `started_at_ticks` **不一致**，導致原因檔驗證永遠失敗、全部退化成 `"signal"`。
   - **修正**：
     1. 改為**「最新一次停止指令覆寫 `stop_cause.json`」**，且行程重新 `start`／`wake` 進入 `running` 時必須刪除舊的 `stop_cause.json`。
     2. `aos-loop` **只有在自身因訊號中止（`signal != null`）時**才去讀 `stop_cause.json`；自然結束（`stop`、`max`、`body_exit`）直接由 `loop` 判定。
     3. 確認 `aos-sandbox` 是否 `execve` 原 PID；若有 `fork`，daemon 應透過環境變數（如 `AOS_PROC_TICKS`）把頂層列識別傳給 `aos-loop` 比對，而非讓 `aos-loop` 讀自己的 `/proc/self/stat`。

3. **[1.2、1.4、1.5] 同名重掛（ABA 問題）會重用 stack 路徑，導致認錯 parent、回報信箱誤投、以及 `who --chain` 造出假祖譜與假迴圈**
   - **嚴重度**：blocking
   - **問題**：1.2 寫「`parent` 用路徑、不用名字：名字會被重用」。但在 aos 中，agent 的 stack 路徑通常是 `<daemon>/procs/<name>`（如 1.4 例子 `/…/procs/ok-devt`）。當父 `ok-devt` 被 `rm`，後來又有人掛了一隻同名的新 agent `ok-devt` 時，**連 stack 絕對路徑 `/…/procs/ok-devt` 都會一起被重用**！這會造成三個問題：
     1. **信箱誤投**：舊子行程的 `notify_box`（`/…/procs/ok-devt/mailbox`）還在，舊子的 `brain_notify` 或回報信會直接投進**毫無關係的新 `ok-devt` 信箱**。
     2. **`who` 與 `--chain` 認賊作父**：在 `A -> B -> C` 中，若 `B` 被 `rm` 後重掛了一隻新的 `B`（其 parent 是 `X`），對 `C` 跑 `ctl who --chain` 時，查表找到新 `B` 往上爬，會得出 `C -> B(新) -> X` 的假祖譜；若 `B` 是由 `C` 重掛的，甚至會算出 `C -> B -> C` 的 `loop`（真實的「誰要求掛我」是嚴格依時間先後的樹，若不重用路徑或偽造 `--parent`，根本不可能有 `loop`）。
     3. **跨 daemon 的 `parent.name` 必為 `null`**：1.4 規定只在「同一張表」找 `parent` 的 `name`，因此在 1.2 提到的「上層 kernel 往下層 daemon 掛」跨 daemon 場景下，`parent.name` 永遠是 `null`、`--chain` 第一步就斷在 `unknown`。
   - **修正**：若要保留對表反查 `name` 或 `--chain`，表的列除了記 `parent`（路徑），還必須記下掛載當下父列的 `parent_started_at_ticks`（或唯一執行個體 ID），反查時比對 `stack + ticks` 吻合才算同一隻，不吻合就視為原父已不在（`name: null`、鏈停在 `unknown`）。

4. **[1.4、3、4] 第 1 期與第 2 期的行為落差會弄壞使用者與工具，且第 1 期「小格查自己」有判定漏洞**
   - **嚴重度**：important
   - **問題**：
     1. **「無 parent」與「第 1 期查不到別隻」輸出完全相同**：第 1 期查別隻 agent 時回傳 `"parent": null, "notify_box": null`，這跟第 2 期「該 agent 是人從 shell 掛的、本來就沒有 parent」的 JSON **完全無法區分**。寫在文字版說明裡救不了讀 `--json` 的程式。
     2. **工具小格與 hook 小格查自己會壞**：第 4 節說「只有查自己時照實給 `$AOS_NOTIFY_BOX`」。但當 agent 在 `<stack>/tools/<名>` 或 `<stack>/hooks/<名>` 內呼叫 `ctl who`（或帶 `--stack` 查自己根路徑）時，若 `who.py` 沒有把「目標列 stack」與「當前 `$AOS_STACK`」都先過 `agent_root()` 正規化再比對，就會誤判成「不是查自己」而回傳 `null`。
     3. **第 1 期升第 2 期的斷層（adopt 漏轉）**：第 1 期把值存在 `exec.envs`；升上第 2 期後，`who.py` 改讀表列的 `parent`/`notify_box` 欄位。若 `adopt.cpp` 接回第 1 期已在跑的舊行程時，沒從舊 `exec.envs` 補回這兩欄，升級瞬間所有活著的行程連「自己查自己」都會變成 `null`。
     4. **空字串型別不一致**：第 1 期若 `AOS_NOTIFY_BOX=""`（例如 `subagent add` 明給空字串），直接印 `$AOS_NOTIFY_BOX` 會給出 `""`，而第 2 期是 `null`。
   - **修正**：
     1. `who.py` 判斷是否為自己時，必須比對 `agent_root(target_stack) == agent_root($AOS_STACK)`；且空字串一律正規化為 `null`。
     2. 其實 `01` 第一節第 4 點已指出：`procs_state.json` 列上本來就有 `exec` 與 `as_written`！第 1 期 `who.py` 只要從 `procs_state.json` 該列的 `exec.envs`（或 `as_written`）讀取 `AOS_PARENT_STACK` 與 `AOS_NOTIFY_BOX`，**第 1 期就能查別隻**，完全消除一、二期差異（詳見 B 提案 1）。

5. **[1.1、1.3] `agent_root()` 未處理 `<根>/hooks/<名>` 小格**
   - **嚴重度**：important
   - **問題**：`01` 記載 `ok-board` A2 的 `agent_root()` 是「把 `<root>/tools/<名>` 正規化成 agent 的根」。但 `02` 的 1.1 寫「`<根>/tools/<名>/`、`<根>/hooks/<名>/` 這些小格都算同一隻……直接呼叫 `agent_root()`，不另寫」。若 hook handler 裡呼叫 `ctl add` 或 `ctl who`，`$AOS_STACK` 若指在 `hooks/<名>`，只切 `/tools/` 的 `agent_root()` 就會算錯根路徑。
   - **修正**：跟 `ok-board` 確認並確保 `agent_root()` 同時正規化 `<根>/tools/<名>` 與 `<根>/hooks/<名>`（或以查表最深列為準）。

6. **[1.3、1.4、1.6] 信任與安全錯誤（Trust Mistakes）：未驗證的 `notify_box` 可被當成跨權限寫檔跳板，且 `who --json` 把未驗證登記包裝成權威事實**
   - **嚴重度**：important
   - **問題**：
     1. **`notify_box` 是投遞動作目標，不只是被動登記**：1.6 說 `notify_box` 跟 `sender` 一樣只是登記，1.3 說 daemon 只檢查非空字串就照抄。但 `brain_notify` 是真的會由子行程往 `notify_box` **寫檔投信**的！在 `ok-sec` 多 UID 架構下，若低權限 A 請上層掛出較高權限的 B，並在 spec 裡把 `notify_box` 設成 A 自己無權寫入的敏感信箱（例如 daemon 控制信箱 `/…/.stack/mailbox` 或別人的信箱，甚至夾帶 `..`），B 撞額度時就會替 A 跨權限投信（Confused Deputy），違反 `ok-sec` P1「誰能寄看 Linux 讓誰寫」。
     2. **`who --json` 混裝事實與自填欄位**：`who --json` 裡的 `name`、`stack`、`daemon` 是 daemon 保證的權威事實，但同層的 `parent` 卻允許呼叫端用 `--parent` 任意填，且 `who` 還會幫它去真表查出 `parent.name` 與 `--chain`，讓讀 JSON 的人與 LLM 誤以為這條上下級關係經過 daemon 驗證（警語只印在 `ctl state` 文字版，`who --json` 完全看不出來）。
     3. **1.6 預留的 `added_uid` 在經 kernel 站／gate 時無效**：信若經 kernel 站或 gate 轉寄，daemon 收到的信檔 `st_uid` 永遠是站或 gate 的 UID，不是發起請求的 agent。
   - **修正**：
     1. daemon 與 `add_letter` 必須驗證 `parent` 與 `notify_box` 為正規化後的絕對路徑（以 `/` 開頭、不含 `..` 元件），且拒絕把 `notify_box` 指向 daemon 自己的控制信箱。
     2. `brain_notify` 送信時應遵循 `ok-sec` 權限，失敗即安靜放棄。

7. **[1.2、1.4、2.1、2.2] 命名與結構不一致**
   - **嚴重度**：minor
   - **問題**：
     1. **`parent` 同名異構**：`parent` 在 `add` spec 與 `procs_state.json` 列上是**字串**，到了 `who --json`（1.4）卻變成**物件** `{"stack": ..., "name": ...}`，而同一個 JSON 裡的 `stack`、`daemon`、`ws`、`notify_box` 全是字串。還有環境變數叫 `AOS_PARENT_STACK`（多了 `_STACK`），鍵名卻叫 `parent`。
     2. **2.1 時間欄命名違反 C-54**：`01` 載明 C-54 規則是「時間欄 `_at` 結尾」（如 `sent_at`、`started_at`），但 2.1 卻規定「之後真要加，名字用 `at`」（沒有底線前綴）。
     3. **2.3 `cause: "error"` 與 C-54**：2.2 規定 `cause` 是小寫底線代號，其中一個值叫 `"error"`，需在文件載明它只是停止分類，不是 `brain_failed` 的錯誤結構。
   - **修正**：JSON 的 `parent` 建議維持路徑字串（或另立 `parent_name`，見提案 3）；2.1 預留時間欄改稱 `fired_at` 或刪掉該句。

---

### 二、第五節（請 Argon 特別看的地方）逐題回覆

1. **問 1（有沒有哪條 add 路徑不經 `add_letter`？kernel 站夾限會不會弄丟這兩鍵？）**
   - **有漏掉的路徑**：
     (a) `daemon.json` 靜態設定與重載不經 `add_letter`；
     (b) 任何直接呼叫 `aos-post`／`aos-mailbox` 投遞 `procs_added` 信的腳本或測試不經 `add_letter`；
     (c) **代理人陷阱**：當某個中間管理員或 kernel handler 替別人呼叫 `add_letter` 時，只要忘記傳 `--parent`，`add_letter` 就會自動抓中間人自己的 `$AOS_STACK` 填進去，把 parent 記錯成中間人。
   - **kernel 站與 daemon 白名單風險**：`letters.py` 純轉寄時原樣轉 body 不會丟；但如 `01` 第三節所示，`limits` 等規則在 kernel 與 daemon 有嚴格的鍵名白名單（不認得就報錯或忽略）。若 kernel 的 gate 規則重建 spec 字典，或第 1 期往 spec 塞新鍵時未改 daemon `procs.cpp`，就會被洗掉或報 `CfgBad`。

2. **問 2（預設「沒明給 `notify_box` 就用 parent 的信箱」套到 `fork`、`agents_ctl add`、`ctl add` 有沒有壞處？）**
   - **有明顯壞處，不應這樣預設**：
     (a) **自毀原則**：這直接違背 `0.1`「三者互不推導」以及 skyrim 已定的「派工時明寫回報寄到哪，不讓體系推算上游」。
     (b) **語意錯置**：`subagent add` 是明確的上下屬派工；但 `ctl add`、`agents_ctl add` 常被用來掛平輩常駐服務，`fork` 則是分身。讓所有平輩與分身在腦額度用完時都寄 `brain_notify` 給當初下指令的那隻，語意不對。
     (c) **通知迴圈與死信箱**：在 aos 中，信進 `<parent>/mailbox` 會喚醒父行程跑 loop。若父也處於額度耗盡或自動回覆狀態，子寄給父會觸發父 `brain_failed` 再往上寄的連鎖反應。若父已被 `rm`，送信會失敗或在已刪除的 stack 路徑下重建空資料夾；若父同名重掛，信更會誤投給新 agent。

3. **問 3（1.5 鏈不存、現查：有沒有非存不可的用途？）**
   - **看用途**：如果要看的是「現在還活著的調度關係」，現查才對；但如果要看的是「歷史追查／帳務歸屬（當初是哪條源頭生出我的）」，現查一旦遇到中間那隻被 `rm` 就會斷在 `unknown`，遇到同名重掛（問題 3）更會接錯祖譜。
   - 現階段既無消費者需要跨層祖譜，動態爬鏈又有同名重掛造假鏈的毛病，**既不必存整條鏈，也不該做 `who --chain`**（見提案 3）。

4. **問 4（2.2 把 `reason` 定成句子、另立 `cause`：值得改名嗎？）**
   - **值得，支持改用 `cause`**。因為 `brain_failed` 的 `reason` 與 daemon 表上的 `reason` 都已經是英文句子（`failed to start: …`），若 `after_stop` 拿 `reason` 裝機器代號，寫 hook 的人一定會搞混。趁 `ok-limits` B7 剛做、還沒有外部 handler 依賴時把代號統一叫 `cause`，長期最乾淨。

5. **問 5（第 1 期用環境變數，`ok-sec` 上線後跨 uid 讀不到 `/proc/<pid>/environ`，會不會在第 2 期前害到誰？）**
   - **會害到人，但根本不必讀 `/proc/<pid>/environ`**：
     如問題 4 所述，第 1 期查別隻拿到 `null`，會讓所有監控、測試與上層調度工具把「別隻 agent」誤判為「沒有 parent／沒有 notify_box」。但第 1 期既然透過 `add_letter` 把變數寫進子行程的 `exec` 單子（`exec.envs`），而 `procs_state.json` 列上本來就有 `exec` 與 `as_written`（`01` 第一節第 4 點），`who.py` 只要讀 daemon 表列上的 `exec.envs`，跨 uid 一樣能查到別隻，完全不必碰 `/proc/<pid>/environ`。

---

## (B) 更簡單、更安全的替代提案

1. **提案 1：第 1 期 `who.py` 直接從 `procs_state.json` 的 `exec.envs` 讀取，消除一、二期行為落差（或直接上第 2 期）**
   - **具體做法**：
     - 若要先上純 Python 的第 1 期：`add_letter` 將 `AOS_PARENT_STACK`、`AOS_NOTIFY_BOX` 寫入 `exec.envs`。`ctl who` 與 `ctl state` 查詢任何一隻 agent 時，統一從 `procs_state.json` 該列的 `exec.envs`（或 `as_written`；若查自己再以 `os.environ` 兜底）讀取這兩個值。
     - 這樣第 1 期**查別隻也能拿到正確的 `parent` 與 `notify_box`**，不會出現「查別人回 `null` 與無 parent 混淆」的破壞性差異，也不受 `ok-sec` 跨 UID 讀不到 `/proc/<pid>/environ` 的限制。
     - 升第 2 期時，`adopt.cpp` 若見舊列無 `parent`/`notify_box`，順手從舊列的 `exec.envs` 升格抄入列欄位，做到無縫升級。

2. **提案 2：`add_letter` 只自動填 `parent`，`notify_box` 維持「明給才設」（僅 `subagent add` 預設填父信箱）**
   - **具體做法**：
     - 真正落實 `0.1`「三者互不推導」與 skyrim 原則：`add_letter` 自動填 `parent = agent_root($AOS_STACK)`，但**不再把 `notify_box` 預設綁到 `<parent>/mailbox`**。
     - 只有 `subagent add`（明確的上下屬派工）在呼叫 `add_letter` 時，若使用者沒明給 `--notify-box`，才由 `subagent add` 傳入 `<parent>/mailbox`；`ctl add`、`agents_ctl add`、`fork` 除非呼叫者明傳 `--notify-box`，否則不設 `notify_box`。
     - `add_letter` 收到 `notify_box=""` 時直接**不寫入該鍵**；daemon 與 `add_letter` 強制檢查 `parent` 與 `notify_box` 必須是不含 `..` 的正規化絕對路徑。

3. **提案 3：砍掉 `who --chain`，將 `parent` 統一為純路徑字串（或加記 `parent_ticks` 防同名重掛）**
   - **具體做法**：
     - **砍掉 1.5 的 `ctl who --chain`**：目前沒有任何功能需要爬祖父鏈，省去處理跨 daemon 斷鏈、16 層限制與循環的複雜度。
     - **拉平 JSON 型別**：在 `add` spec、`procs_state.json`、`ctl who --json`、`ctl state` 中，`parent` **一律是根 stack 絕對路徑字串（或 `null`）**，與 `stack`、`daemon`、`ws`、`notify_box` 保持完全一致的型別。
     - 若 `ctl state` 文字版想對人顯示父的名字，只在印文字時順手查表印出即可；若要在 JSON 帶名字，必須在表的列同時記下 `parent_ticks`（掛載時父列的 `started_at_ticks`），反查時 `stack` 與 `ticks` 雙重吻合才填名字，徹底杜絕 `rm` 後同名重掛（ABA）認錯父的問題。

4. **提案 4：修正 `stop_cause.json`（B7）為「覆寫＋重起清除＋僅訊號退出時讀取」**
   - **具體做法**：
     - **Daemon 端**：每次發送停止訊號（`sleep`、`remove`、`shutdown`、`stuck`）前，**直接覆寫** `stop_cause.json`（寫入當下原因與目標行程的 `started_at_ticks`、`boot_id`）；且在行程 `start`／`wake` 轉回 `running` 時**刪除**舊的 `stop_cause.json`。另外若 `tend.cpp` 因 `cpu_s`、`file_mb` 超限主動殺行程，直接寫入 `cause: "limit"`（不必等下一期）。
     - **Loop 端**：`aos-loop` 的 `on_stop` **只在 `signal != null`（確實被訊號中止）時**才去讀 `stop_cause.json`；若是 `stop`（走 ctl 窗）、`max`、`body_exit` 等自然結束，直接用 `loop` 自己判定的 `cause`，避免被最後一刻寫入的原因檔覆蓋。
