以下為針對這份設計圖紙的審查意見（A）與修改提案（B）。

---

## (A) Review：審查發現（依嚴重度排序）

### 1. [嚴重／資安漏洞] 信任呼叫端環境變數，Agent 可任意擴權甚至在沙箱外執行任意碼（題 a）
- **問題**：在 `aos` 中，Agent 本身只是普通 Linux 行程。當 Agent 呼叫工具（透過 `aos-exec` 或直接跑 `aos-sandbox`）時，若 `aos-sandbox`「環境原樣傳」且直接相信環境變數：
  1. **`AOS_HOME` 劫持（沙箱外 RCE）**：Agent 只要在呼叫時改掉 `AOS_HOME=/tmp/evil`，`aos-sandbox` 在進 `bwrap` 前就會在**沙箱外**直接執行 `/tmp/evil/lib/agent/guard/_entry`。
  2. **範圍變數污染（任意擴權）**：Agent 呼叫工具時可自行竄改 `AOS_WRITE_ALLOW=/`、`AOS_WS=/`、`AOS_GUARD_CFG=/dev/null` 或清空 `AOS_WRITE_DENY`，讓 `--scope` 吐出全系統可寫，形同虛設。

### 2. [嚴重／邏輯矛盾] `AOS_STACK` 在 `--scope` 與 `sandbox.rw` 指涉衝突，導致 Agent stack 保護失效或工具格唯讀
- **問題**：圖紙第 1.4 節寫道：`rw` 裡的 `{"$env": "AOS_STACK"}` 是 `<agent stack>/tools/<名>`，比 agent 的 stack 深所以可寫。但 `aos-sandbox` 又把同一個環境原樣傳給 `_entry --scope`：
  - 若當時 `AOS_STACK` 是 `<agent stack>/tools/<名>`，`_entry --scope` 放進 `deny` 的就會是 `<agent stack>/tools/<名>`（與 `rw` **同深**撞車），反而是上層 `<agent stack>` 根本沒進 `deny`！
  - 若當時 `AOS_STACK` 是 `<agent stack>`，那 `sandbox.rw` 的 `{"$env": "AOS_STACK"}` 就會把**整個 `<agent stack>`** 掛成 `rw`，Agent 可以改寫自己的 stack。

### 3. [嚴重／機制漏接] 「`deny` 落在 `allow` 底下且存在才進 `ro`」漏掉四種破口（題 b）
1. **`deny` 在 `allow` 上層或同層**：`write_guard` 的語意是「deny 永遠壓過 allow」；但 `bwrap` 是「深的說了算」。若 `AOS_WRITE_ALLOW` 有 `/ws/sub`，而 `AOS_WRITE_DENY` 設了 `/ws`（或 `/ws/sub`），圖紙規則會因 `/ws` 不在 `/ws/sub` 底下而忽略它（就算掛了 `ro` 也會被更深的 `/ws/sub` `rw` 蓋過去），導致被禁寫的子樹依然可寫。
2. **尚不存在的 `deny` 路徑**：圖紙要求「而且存在」才加進 `ro`。若某條 `deny`（例如 `$AOS_WS/defs` 或某個禁寫檔）在啟動沙箱時還不存在，`aos-sandbox` 會跳過它；進沙箱後 shell 就能在可寫的 `$AOS_WS` 裡直接 `mkdir` / `touch` 把它建出來寫入。
3. **Symlink 與父目錄改名繞過（VFS rename 破口）**：
   - 若 `deny` 在 `$AOS_WS` 內是條 symlink，`--scope` 對它做 `realpath` 後只把目標掛成 `ro`，沙箱內卻能直接 `unlink` 該 symlink 換成真檔。
   - 若 `deny` 是 `$AOS_WS/a/b/denied`（掛成 `ro`），但中繼目錄 `$AOS_WS/a` 可寫，Linux VFS 允許在同一個 mount namespace 內 `mv $AOS_WS/a $AOS_WS/a.bak`（掛載點跟著搬走），接著 `mkdir -p $AOS_WS/a/b/denied` 就能在原路徑建出一個完全沒被 `ro` 保護的新目錄。
4. **TOCTOU 競爭條件**：`_entry --scope` 算 `realpath`、到 `aos-sandbox` 檢查存在、再到 `bwrap` 掛載之間有時間差；同工作區的並行行程可在這段空窗切換 symlink 或搬移目錄。

### 4. [高／事實錯誤與缺漏] `--scope` 並未包含 `deny_parts`（預設 `.git`），且輸出格式尚未定稿
- **錯誤事實**：圖紙稱「`--scope` 的 JSON 形狀它說已定稿」且「檔案工具的守門和 shell 沙箱一起跟著走」。
- **實際情況**：
  1. Guard 作者已確認 `--scope` **不會列出 `deny_parts`（預設 `.git`）**，且 guard 本身還有破口在修、`--scope` 輸出形狀可能還會變。
  2. 這代表開啟 `"scope": true` 後，shell 沙箱對 `$AOS_WS/.git`（以及子目錄的 `.git`）**完全可寫**，Agent 可在 shell 內改 `.git/hooks` 或 `.git/config` 植入後門。

### 5. [中／防護落差過大] `proc-stack` 只擋「工作區第一層既有的 `.stack`」不足以防跨 proc 竄改（題 c）
- **問題**：
  1. 只看 `$AOS_WS/.stack` 漏掉了 `AOS_WRITE_ALLOW` 其他可寫樹底下的 `.stack`。
  2. 「資料夾即程式」架構下，子專案或深層目錄（深層 ≥ 2）也會有 `.stack`。
  3. 沙箱啟動時尚不存在、跑一半才由其他 proc 建出來的 `.stack` 夾完全不會被擋。
- **結論**：Bwrap 只能在啟動時綁定既有路徑，無法像 `write_guard` 攔截每次寫入，這個落差在靜態 mount 架構下無法 100% 消除，但目前只檢查 `$AOS_WS` 第一層太窄，且 README 若沒寫清楚會造成致命誤判。

### 6. [高／Fail-open 交互破口] `scope` 採 Fail-closed（`ScopeFailed`）是對的，但舊設定的 Fail-open 會把它繞過去（題 d）
- **判斷**：`"scope": true` 問不到範圍時「不跑、退 1（`ScopeFailed`）」**完全正確**——因為開了 `scope` 後原本寫死的規則被拿掉，若退回不套沙箱等於大門全開。
- **破口**：圖紙保留了現有規矩「設定讀不了、型別不對、`$env` 沒設＝當沒寫、不套沙箱直接跑」。如果呼叫端故意 `unset AOS_STACK`（或弄壞其他欄位），`aos-sandbox` 若照舊規矩「整支程式不套沙箱直接跑」，`scope: true` 的 Fail-closed 就被一鍵繞過了。

---

## (B) Proposals：具體修改建議

### 1. 釘死（Pin）執行檔與範圍環境變數來源（對應 A1、A2）
- **`_entry` 路徑不讀 `$AOS_HOME`**：改由 `aos-sandbox` 自身執行檔的 `realpath` 相對推算（例如 `<aos-sandbox真路徑>/../../../lib/agent/guard/_entry`），徹底切斷 `$AOS_HOME` 劫持。
- **拆開 Agent Stack 與 Tool Stack 變數**：由 `aos-exec` 明確區分 `AOS_AGENT_STACK`（Agent 自身 stack，唯讀）與 `AOS_TOOL_STACK`（或讓 `_entry --scope` 認 `AOS_AGENT_STACK`），避免 `--scope` 的 `deny` 與工具自己的 `rw` 小格撞在同一條路徑。
- **環境變數來源釘死**：`AOS_WS`、`AOS_WRITE_ALLOW`、`AOS_WRITE_DENY`、`AOS_GUARD_CFG`、`AOS_CD` 不可任由 Agent 呼叫工具時的 `environ` 覆寫；應由 `aos-exec` 從 `<agent-stack>` 內唯讀的啟動紀錄（daemon 掛載時寫入的 env 快照）載入後再傳給 `aos-sandbox`。

### 2. 修正 `allow` / `deny` 合併演算法與不存在路徑處理（對應 A3、A4）
1. **先做集合裁切（Deny 壓過 Allow）**：在送進 `bwrap` 前，若任何 `allow`（或設定檔 `rw`）路徑等於某條 `deny`、或落在某條 `deny` 底下，**直接從 `rw` 清單剔除**（僅工具自身 `<tool-stack>` 白名單除外），不能只靠 `bwrap` 的深淺規則。
2. **補齊 `.git`（`deny_parts`）**：在 `--scope` 支援輸出 `deny_parts` 前（或輸出後），對每個 `allow` 根目錄檢查常見保護項（如 `<allow>/.git`）並併入 `deny`。
3. **不存在的 `deny` 與中繼目錄保護**：
   - 若 `deny` 落在某個 `allow` 底下但**尚不存在**：不要跳過；要嘛拒絕啟動（若屬於關鍵系統夾），要嘛把該 `deny` 路徑存在的最深父目錄檢查是否可鎖，或在 `bwrap` 中用 `--tmpfs` / 唯讀空檔佔位（視是否允許建空夾而定，或直接在 README 標明 `bwrap` 無法防堵尚未存在的 `deny` 路徑）。
   - 對 `deny` 與 `allow` 之間的中繼父目錄，提醒設計者：只要中繼目錄可寫，`bwrap` 的子目錄 `--ro-bind` 就可能被 `mv` 繞過；因此 `deny` 應盡量設在 `allow` 根的直接子項（第一層），且比對「是否在 `allow` 底下」前，在 `aos-sandbox` 內統一對兩邊做一次無 symlink 成分的檢驗（拒絕路徑中間含可寫 symlink 的 `deny`）。
4. **鎖定 `--scope` 介面版本**：請 `write_guard` 在輸出加上 `"version": 1`（或將 `deny_parts` 一併放入 `"rules"` / `"deny_parts"` 欄位）；`aos-sandbox` 遇到不認識的 `version` 或未支援的 `rules` 時應明確告警或 Fail-closed。

### 3. 擴大 `.stack` 遮罩範圍並精確改寫 README 警語（對應 A5）
- **實作調整**：不要只看 `$AOS_WS/.stack`，改為掃描**所有 `allow` 根目錄**底下第一層（甚至現有子目錄）的 `.stack` 夾與 `.git` 夾，存在者一律加進 `ro`。
- **README 必須白紙黑字寫清楚的邊界**（避免使用者誤以為跟 `write_guard` 一樣嚴密）：
  > **注意：`scope: true` 僅在沙箱啟動瞬間同步「可寫根目錄」與「當時已存在的禁寫路徑」，不等同於 `write_guard` 的逐筆寫入攔截。以下情況沙箱無法擋下，僅能靠檔案工具的 `write_guard` 防護：**
  > 1. **深層或事後新建的 `.stack`**：沙箱只將啟動時各可寫根目錄第一層已存在的 `.stack` 設為唯讀；第 2 層以下（如 `sub/.stack`）或沙箱啟動後才由其他 proc 新建的 `.stack` 夾，shell 仍可寫入。
  > 2. **`deny_parts`（如深層 `.git`）與啟動時尚未存在的 `deny` 路徑**：`bwrap` 只能綁定啟動時已存在的路徑，無法攔截事後 `mkdir` / `touch` 建立的禁寫路徑。

### 4. 將整支 `aos-sandbox`（至少在啟用 `scope` 時）全面改為 Fail-closed（對應 A6）
- 當設定檔含有 `"scope": true`（建議直接推廣為整個 `aos-sandbox` 的新預設，廢除壞設定裸奔），**任何**設定檔讀取失敗、JSON 格式錯誤、`ro`/`rw` 型別不對、或 `{"$env": "..."}` 變數未定義，一律印出錯誤並 `exit 1`，**絕不可退回「不套沙箱直接跑」**。
