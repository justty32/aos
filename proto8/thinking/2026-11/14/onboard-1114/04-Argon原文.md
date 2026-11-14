# 04 Argon 原文（審 02＋03）

← [onboard-1114](../onboard-1114.md)｜指令：`agy -p <prompt> --model "Gemini 4 Argon (High)" --mode plan --print-timeout 840s`，在 /tmp/ok-onboard-argon 跑，11-14 12:30；prompt＝03＋02 全文＋事實摘要，明寫不准用工具。以下原樣。

### (A) 審查意見（Review）

#### A1 `[must-fix]` 自解限制的「第七個洞」與漏關工具（指 02 §1.3、§1.5；03 §1 #1–2、§2.1–2.2、§3）
1. **第七個洞——利用 Folder-is-a-program 特性直接 `write`/`edit` 改自己的 stack 或定義夾**：
   `aos` 的狀態在 stack 夾、定義在 def 夾，且改定義或 stack 複本在**下一次問腦就生效**（03 §1 #2、#6）。拿掉 6 項自改工具後，「看／做／幫」三包仍保有 `write` 與 `edit`，而檔案工具本身不限路徑：
   - 在 **P0／P1 階段**（03 §2.2 明言守門 P2 才做，P0 先靠「不給工具」），agent 直接用 `write`/`edit` 改寫自己 stack 夾內的 `tools.json`、`hooks.json`、`system.txt` 或線夾下的 `defs/gather/`，下一輪問腦就能掛回 `shell` 或清空守門。
   - 到了 **P2**，若隊長的線夾或共用區被放進 `AOS_WRITE_ALLOW`，而子 agent 的 stack 或定義夾也在同一棵目錄樹下，同樣能跨夾篡改。
2. **漏關第 5 支 JSON 寫入工具 `tools_def` 與 `run_python`**：
   - 03 §2.2 點出寫入類工具有 `json/jsonx` 的 `set`、`add`、`del`、`multi_set` 及 **`tools_def`**（共 5 支），但 03 §1 #1 與 §2.1 只寫「關掉 json 寫入四支」，漏關了 `tools_def`。
   - 02 §1.3 點名不掛 `run_python`，但 03 §2.1 的移除清單完全沒提 `run_python`（若它隸屬保留包如 `gadgets` 就會殘留）。
3. **透過信箱寄控制請求（Confused Deputy）**：
   02 §2.2 提到 kernel 的控制請求是走信箱寄送（`aos/kernel.json#where_to_send`）。在 P0／P1 還沒有 `mail_guard` 時，受限 agent 可用 `mailbox_send` 寄控制信給 kernel 或其他高權限 agent 代為解限。

---

#### A2 `[must-fix]` `write_guard`／`mail_guard` 的全參數誤殺、TOCTOU 與環境變數斷層（指 03 §1 #3、§2.1–2.2；02 §1.5）
1. **「禁寫改准寫」全參數掃描會誤殺正常內文**：
   `user_zone_guard` 原本是**禁寫黑名單**，所以可以無腦「掃參數裡每個字串（含巢狀）接 `$AOS_WS` 再 `realpath`」（03 §1 #3）。但 03 §2.2 直接把它反轉成**准寫白名單**時，`write`／`edit` 的 `content`、`new_str` 等非路徑字串也會被當成路徑檢查——只要報告內文提到 `/etc/...` 或 `/home/...`，`realpath` 算出來在 `$AOS_WS` 外就會被 `exit 10` 誤殺！
2. **Symlink TOCTOU 與尚未存在的目標路徑**：
   - `write` 新建檔案或 `mkdir` 多層目錄時，目標路徑尚不存在，標準 `realpath` 會失敗或未解析尾端；
   - 在「做」包（有 `shell`）或多 agent 並行時，`before_tool` 檢查 `realpath` 到工具實際 open 寫入之間有 TOCTOU 視窗，若 ws 內子目錄被換成指向外部（如活樹或 stack 夾）的符號連結即可穿牆。
   - 03 §2.2 刪掉了 02 §1.5 的「**禁寫清單優先於准寫**」，一旦 `AOS_WRITE_ALLOW` 給太寬或內含 symlink，使用者專區與活樹將失去硬底線保護。
3. **`mail_guard` 的路徑穿越與環境變數傳遞問題**：
   - `mailbox_send` 與 `clock_register` 的收件欄位名稱未必相同；若收件匣支援路徑或 `../other_box` 語法，僅做字串比對而不做 canonical 路徑解析會被繞過。
   - 03 §2.1–2.2 規定「做」包的拋棄式複本靠環境變數 `AOS_WRITE_ALLOW` 傳入，但未交代隊長呼叫 `subagent add` 時如何為單一隊員注入專屬的 OS 環境變數。

---

#### A3 `[must-fix]` 把不該移出 `system` 的高危與收尾規矩推去「站台小卡」（指 02 §2.3、§3.1、§3.4；03 §2.3、§8）
1. **History 裁切導致收尾與禁令失憶**：
   02 §2.3 指出長任務中「history 會被裁掉」，而 `card.md` 只在開場第 2 步讀一次，位於 history 最開頭，**最先被裁掉**。但 02 §3.1 與 §3.4 卻把「**現在凍結的線**」「**往上報的三條**」「**commit 怎麼交**」「**命名**」放進小卡——這些全是防止踩雷的硬禁令，或到第 40～150 輪收工回報、隊長派工時才用到的規矩，屆時早已被裁出 context 或因近因效應失效。
2. **線上更新能力與成本算帳自相矛盾**：
   - `system.txt` 每次問腦都會重讀，改定義下一輪就生效；反觀 `card.md` 只在開場讀一次，長駐的「帶／幫」或執行中的「做」根本拿不到小卡更新後的「凍結清單」（03 §8 也承認這點）。
   - 02 §3.4 自己指出「去讀某檔並不省，進了 history 每次問腦照樣重送，還多一次工具呼叫」，而且 **D 級完全不讀小卡**（02 §3.3）。把核心禁令與回報規矩移出 `system` 是賠了安全性又沒省到 token。

---

#### A4 `[must-fix]` 產品檔洩漏站台規矩與未替換佔位符（指 02 §1.1、§1.4、§2.4、§3.1–3.2；03 §2.3、§4、§7）
1. **產品角色層混入個人站台的 06 硬規則**：
   02 §1.4 把「只在點名的拋棄式複本裡改；不 commit、不 push、不刪檔」寫進產品中立的 `roles/build.txt`；但 02 §3.1 明列這是 `wf` 站台層（`site.txt`）的規矩。一般產品使用者的施工員未必使用拋棄式複本，也可能需要 commit。
2. **Grep 檢查規則過窄**：
   03 §4 P0 只 grep `/home`、`wf/`、內部 agent 名，抓不到上述「語義級站台規矩」，也抓不到 `kits.json` 裡的私有模型別名（`sol`、`astra`、`luna`、`terra`、`fable`）。
3. **直接 `agent_def new` 會吃到未替換的 `<SITE_CARD>`／`<BOARD>`／`<KNOWLEDGE>`**：
   02 §3.1–3.2 與 03 §7 打算把 `proto8/templates/agent-fsm/system.txt` 換成通用層 A 版，讓不經 `aos-kit make`、直接跑 `agent_def new` 的人當底線用。但 03 §2.3 把讀 `<KNOWLEDGE>/...` 與站台小卡 `<SITE_CARD>`、`<BOARD>` 寫在 `general.A.txt` 裡；沒經過 `aos-kit make` 替換記號時，agent 會直接拿字面上的 `<SITE_CARD>` 去讀檔而報錯。

---

#### A5 `[must-fix]` P1／P2 施工順序倒置，且驗收門檻與樣本數（N=3）統計失真（指 03 §4、§5；02 §4）
1. **P1 還沒寫守門，卻要驗收 T3 越界阻擋**：
   03 §4 把實測放 P1、寫 `write_guard`/`mail_guard`/`board` 放 P2；但 P1 的驗收標準卻是 02 §4 門檻表（含 T3「越界寫入 0 次、被擋後有沒有硬試、看布告欄」）。P1 時守門跟 `board` 工具都還不存在，檔案工具又不限路徑，根本不可能測「被擋後的反應」。
2. **百分比門檻在 N=3 下等於 100% 零容錯**：
   每格只跑 3 次，A 級新組三題共 9 次、C 級兩題共 6 次（03 §5）。門檻設 `A ≥ 95%`（錯 1 次＝8/9＝88.9% 即不及格）、`C ≥ 85%`（錯 1 次＝5/6＝83.3% 即不及格），實質上都是**必須 100% 全過**，統計雜訊極大。
3. **Token 門檻受輪數干擾，且漏定 T2 門檻**：
   「T1 總 prompt token ≤ 舊組 70%」會被問腦次數波動（允許 `≤ 110%`）吃掉；應改測「**開場固定成本（做第一件正事前的 prompt token）≤ 舊組 25%（或 ≤ 2,500 tokens）**」。此外 02 §4 的門檻表完全漏了 **T2（小施工）** 的測試通過率與不汙染原樹指標。

---

#### A6 `[suggestion]` `goal pause` 等信醒來後的漏 `resume` 死鎖（指 03 §1 #5；02 §2.6）
02 §2.6 規定等信時 `goal pause`、回信來再 `resume`；03 §1 #5 則寫「隊員不等人，卡住就報 BLOCKED 再 goal pause」。若回信喚醒後，模型直接回純文字而忘了先叫 `goal resume` 或 `goal done`，因為 goal 處於 `paused`，`idle.py` 不會再發提醒，該 agent 就會無聲停死。建議統一規定「隊員只有 BLOCKED 停工才 pause」，或在收到新信時由系統自動解除 pause。

---

### (B) 替代與簡化提案（Proposals）

#### B1：廢除「站台小卡 (`card.md`)」，改為「核心站台規矩編入 `system.txt`」＋「角色規矩隨 `aos-kit add` 注入任務書」
- **做法**：不設 `card.md`。將全站必守的短規矩（凍結線、回報三條、禁碰路徑，約 600 字元）直接放進 `site.txt`，由 `aos-kit make` 拼進 `system.txt`；至於少數角色才用的長規矩（如施工員的寫碼慣例與 commit 格式），由 `aos-kit add` 在發送任務書時自動附加在任務書末尾。
- **效益**：
  1. 省下開場第 2 步讀小卡的 1 次工具呼叫與問腦；
  2. 規矩永遠留在 `system.txt`，不會因 history 裁切而失憶，D 級也看得到；
  3. 凍結線變更時，只要更新定義檔，正在跑的 agent 下一輪問腦立即生效。
- **代價**：修改站台常變規矩時，需執行一次 `aos-kit make` 更新定義夾（可加 `--refresh-active` 批次重拼線上定義的 `system.txt`）。

#### B2：`write_guard`／`mail_guard` 改用「工具參數鍵名映射＋Stack 內唯讀 `policy.json`」取代全字串掃描與環境變數
- **做法**：
  1. 不掃全部字串參數，改用小表精確指定各工具的路徑欄位（如 `write/edit/mkdir` 取 `path`、`copy/move` 取 `src/dst`、`json_*` 取 `file` 切掉 `#/`），並對「尚不存在的目標檔」先取其存在的最深父目錄跑 `realpath` 再接回剩餘路徑（防 symlink 穿越）。
  2. 硬編碼一條不可覆寫的鐵律：**任何 aos 工具均禁止寫入任何 stack 夾、定義夾與禁寫清單（活樹／使用者專區）**。
  3. 准寫清單與准寄信箱不靠環境變數，改由 `aos-kit add` 寫入 `<stack>/policy.json`（守門自身禁止任何工具修改 `policy.json`）。
- **效益**：徹底消除內文含路徑被誤擋的假陽性、封死「改 stack/def 自解限制」的第七個洞，並解決 `subagent add` 傳遞個別環境變數的問題。
- **代價**：需維護一張約 15 支工具的「工具名 → 路徑參數鍵名」對照表（約 25 行程式碼，比遞迴掃描全 JSON 更簡單穩定）。

#### B3：對調 P1 與 P2 的守門施工順序，並改用「開場零呼叫預填」
- **做法**：
  1. 把兩支守門（`write_guard`、`mail_guard`）拉到 P1 實測**之前**先在暫存樹寫好（不碰活樹 `proto8`，不違背鐵律），再跑 P1 陷阱題；實測先只跑 `sol` 新舊組 × 各 5 次（門檻改為 `≥ 9/10` 或 `4/5`），過關再測 haiku，略過不使用的 C 級 terra。
  2. 既然 `aos-kit add` 起 agent 時已知其 `who`、`ws`、`notify_box` 與 `_description.json` 摘要，直接由 `add` 預填進任務書檔頭，開場只留 `goal set` 一步。
- **效益**：讓 P1 能真正測到守門攔截效果，解決 N=3 統計失真，同時每張單再省 2 次開場問腦與約 30% 實測 token。
- **代價**：需在 P1 前先寫約百行的守門腳本與任務書預填邏輯。
