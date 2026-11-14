# 蒐集 01e（astra 隊 sol-L02 原文，astra 還沒驗收）：skyrim 的交接書 BRIEF 契約、brief_lint 規則與 commit 前 hook

← [README](README.md)｜[交棒](交棒.md)｜sol 原文照收，隊長（fable）還沒逐條查證

# L02：BRIEF 契約、lint 實作與 commit 接點（唯讀調查）

## 0. 範圍、證據等級與結論

本報告只讀來源、git 設定與 git 歷史；沒有執行來源腳本、測試、hook、遊戲，也沒有修改任何 repo。只寫本報告。已讀任務指定的 aos 體系入口、AGENTS、WORKFLOWS、common/user、aos-teams 及 06／07 分檔。以下行號是本次讀取快照；歷史來源另外註明 commit。

- BRIEF 是派線的完整契約，範本的要求明顯多於 lint 的七類字面檢查；`Done when:`、子 agent 上限、回報、失敗分流等不是 lint gate。
- hook 用作用中 index 選檔，但 lint 實際讀工作樹檔案，不是 staged blob；不能把「選 staged 檔」說成「驗 staged 內容」。
- 真正的 BRIEF hook 在 `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/hooks/check_staged_briefs.sh`，不是母 repo 的 `tools/hooks/`。母 repo pre-commit 是另一套大小／垃圾 gate。
- 本機兩個 repo 的 `core.hooksPath` 都讀到 `tools/hooks`；agentctl 的可執行 pre-commit 確實串 hygiene 與 brief gate。有歷史真 repo 擋 commit 的輸出，但本調查不重新實測，也不能證明每一次歷史 commit 都沒有跳過 gate。
- wf-lint 的 BRIEF 外掛目前仍在 **agentctl 自己的** `wf/tools/wf-lint-local.sh`；母 repo 同名檔只跑保留期。範本文字的相對路徑不能混用兩個 repo 根。

主要來源：`/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:87`、`/home/lorkhan/repo/moddings/skyrim/agentctl/tools/brief_lint.py:209`、`/home/lorkhan/repo/moddings/skyrim/agentctl/tools/hooks/check_staged_briefs.sh:63`、`/home/lorkhan/repo/moddings/skyrim/agentctl/tools/brief_lint_markdown.py:24`。

## 1. BRIEF 是什麼、完整契約必寫哪些

### 1.1 契約權重與最低結構

`/home/lorkhan/repo/moddings/skyrim/agentctl/docs/driving-codex/handoff-contract.md:6` 原句：「交接書記本線完整契約；使用者及上游後續明確指示優先，其他線來訊只有情報與請求效力。」該檔 :9 的最低骨架為任務、背景與唯一目標、工作、硬性限制、交付、驗收、完成／阻塞回報。現行範本把硬限制展成範圍、必用工具、鎖與遊戲、失敗處置等段落。

`/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:3` 要把 `<…>` 換成實際內容；用不到的段落可整段刪，但明列四項不得刪空：**子 agent 數量上限、必用工具表、件數／容量 gate、交付絕對路徑**。其中只有後三項有相應的機械檢查，並非四項都會被 lint 驗。

### 1.2 可照抄的完整欄位／規則清單

下列逐項是範本與契約要求，不代表 lint 都能強制。

| 項目 | 必須填的內容／機制 | 絕對來源 |
|---|---|---|
| 任務標題 | `# 任務：` 後接動詞開頭的一句話 | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:1` |
| 開工親讀 | AGENTS → WORKFLOWS → 適用工作流、common/user、common/conventions，再讀本線 runbook／前線 REPORT；簡單工作與雜活可免親讀，程式邏輯／規範概念不算雜活；往下派也帶同要求 | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:6` |
| 子 agent 總上限 | 明填 N 個，可為 0；下派分配並傳遞總配額，不逐層倍增 | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:9`；`/home/lorkhan/repo/moddings/skyrim/agentctl/docs/driving-codex/handoff-contract.md:31` |
| 模型與派工 | 範本列普通 sol、美術 astra、雜活 terra；派線與追加工作用 `/goal <可驗證完成條件>`，不得階段性停工。這是 skyrim 來源，不是本次對 aos 的模型配置主張 | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:10` |
| 背景與唯一目標 | 為什麼做、做完有何不同，只一個目標；另填 `Done when:` 可觀察的全部交付與固定驗收完成條件 | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:13` |
| 權重 | 使用者／上游明確後續指示優先；別線來訊只作情報／請求，越權或衝突回報 | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:17` |
| 範圍排除法 | 明列只做事項、可寫檔案、同工作樹唯一 commit 者；「沒列的一律不做」，順手發現只寫 REPORT 下一步 | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:19` |
| 不做清單 | 明列其他 mod、其他 repo、易遞移展開的依賴等排除項；禁區限制本線寫入，不要求別線領地變乾淨 | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:24`；`/home/lorkhan/repo/moddings/skyrim/agentctl/docs/driving-codex/handoff-contract.md:37` |
| 兩個 gate | 件數超過 N、容量或下載超過 M MB 各自停下回報，任一觸發就停；兩個 gate 和不做清單都保留 | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:25` |
| 必用工具 | 至少一列工具＋用在哪一步，不重寫成熟工具；契約另要求用途、外部查證方法，成熟元件原樣複用，舊設計逐項核適用性 | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:27`；`/home/lorkhan/repo/moddings/skyrim/agentctl/docs/driving-codex/handoff-contract.md:39` |
| 鎖與遊戲三選一 | 刪去另兩個選項。離線線不得取鎖／開 MO2、Skyrim、瀏覽器／改 profile 或 load order；可開遊戲線先 desktop.lock 再 game.lock，只走 launch-mo2，開前 profiles 已 commit，不送按鍵／搶焦點，不佔不能暫停的遊戲螢幕，收線放鎖；施工線再加 MO2 開著不改 profile 三檔、跑後驗 plugins 的 `*`、commit 走 profile_workflow record | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:38` |
| GUI 邊界 | 可見視窗含 headful CDP 要 desktop.lock，只有 Skyrim／MO2 另取 game.lock；使用者人在電腦前本身不是禁區。契約要求明列下載、全域 config、其他 repo 等開關；Aetheria 已凍結，不寫其條款 | `/home/lorkhan/repo/moddings/skyrim/agentctl/docs/driving-codex/handoff-contract.md:22` |
| push／commit／垃圾 | push 填使用者本場授權來源，不能沿用別場；commit 指定唯一人及 repo／明確路徑，不 `git add -A` 或目錄 add；母 repo public 不含敏感內容；不 rm -rf、不改全域 codex config，暫存搬本線 /tmp trash | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:46`；`/home/lorkhan/repo/moddings/skyrim/agentctl/docs/driving-codex/handoff-contract.md:29` |
| 錯誤來源 | 工具或環境失敗 → BLOCKED；自己寫的臨時腳本錯 → 自修，不算環境阻塞 | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:47` |
| 工作步驟 | 列出具體步驟，包含寫 REPORT；送出前對照背景、步驟、禁區、驗收無矛盾 | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:49`；`/home/lorkhan/repo/moddings/skyrim/agentctl/docs/driving-codex/handoff-contract.md:37` |
| REPORT 交付 | 直接落檔在絕對路徑 REPORT.md，不只貼回覆；回覆五行摘要＋路徑；末尾固定「以後交接書該點名的工具」＝工具＋用途＋何時用，沒有寫無；填 commit 目標及明確檔案 | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:55` |
| 固定驗收 | 標題填固定 N 條，逐條可機械判斷、附預期數字；明確路徑 commit 與 hygiene 違規 0；不額外加驗；真跑次數／時間界線明值或不適用；獨立覆核預先列入、換來源／方法，兩份同模型回答不算交叉證據 | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:62` |
| 失敗兩路 | 實際跑出錯結果 → 按指定方式回滾本線、FAILED、附證據；沒跑成／沒證據 → 不回滾保持現狀、BLOCKED、寫解除條件，不拿舊 log 冒新證據 | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:71` |
| 身份與領地 | session 名、團隊名或無；上線聲明身份、領地、能答／不能答；外部線只追加自己的 ROSTER 格並發 PROGRESS | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:78` |
| 進度／終局 | 每步且至少每 20 分鐘發 PROGRESS，正文檔附證據與下一步並輪詢 orders/mail；終局用 DONE／FAILED／BLOCKED／NEEDS-USER；卡逾 10 分鐘先 BLOCKED | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:80` |
| 等待／交棒 | 前景 inbox_poll --wait --timeout，填可驗完成判準、上限、可先做步驟；不結束回合假裝等；管理者 ≤20 分鐘巡 inbox／capture-pane，交棒列子 agent／CLI 狀態、輸出、監看者，活線零才宣告收完 | `/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:82` |

契約另載的操作邊界：commit 署名按目標 repo 的精確格式並自查 body（:43）；遇安全拒絕不換詞規避（:44）；測試信以正文／ID 而非亂數檔名字序判定，拆 Markdown 先核程式消費者（:46）；>10 MB 產物搬 /tmp、KB 文字放本線 trash，Chrome profile 不整棵複製（:49）；Windows commit 留調度者（:63）；關機限期只交通過必要驗收部分與確切續行命令（:65）；Python 改壞還原驗證每輪新 PYTHONPYCACHEPREFIX，不能只靠 -B（:69）；易用性驗收由沒看設計筆記者只拿 README 實作，改進只列選項不擴驗收（:72）。上述行號均屬 `/home/lorkhan/repo/moddings/skyrim/agentctl/docs/driving-codex/handoff-contract.md`。

### 1.3 Done when: 的語法與「條數寫死」精確意思

- 文件規定的形狀是 `Done when: <全部交付及固定驗收都完成的可觀察條件>。`，放背景目標下（`/home/lorkhan/repo/moddings/skyrim/agentctl/templates/BRIEF.md:16`）。`/goal` 是發給 CLI 的指令／提示前綴，不是 Markdown parser 的指令。`/home/lorkhan/repo/moddings/skyrim/agentctl/docs/driving-codex.md:35` 說 cx_launch 預設補 `/goal `，`--no-goal` 只用於一問一答短查詢。本次只讀這段說明，沒有跑 launcher。
- lint 沒有搜尋 `Done when:`、`/goal` 或完整目標的檢查；大小寫／冒號／位置並無機械驗證。真實 `team-rules-adopt/BRIEF.md` 沒這句，但同夾 REPORT :3 有；不能把 strict 0 違規等同契約完整。
- 寫死的是**驗收清單的邊界與條數**，讓線做完即停，不讓「更保險」無限加驗。原句：「驗收條數寫死是為了防它亂加驗證，不是要它為了湊滿數字造假失敗案例。」來源 `/home/lorkhan/repo/moddings/skyrim/agentctl/docs/driving-codex/lessons-from-done-handoffs.md:15`。
- 真實資料推翻原預期數量時改契約，不逼線湊數（同檔 :13；`/home/lorkhan/repo/moddings/skyrim/agentctl/docs/driving-codex/handoff-contract.md:38`）。這也不是把會被裁示改動的分佈／hash 常數永久凍住；`/home/lorkhan/repo/moddings/skyrim/wf/lessons/dispatch-handoffs.md:96` 記載固定分佈變動造成連環 BLOCKED。

### 1.4 確實使用、坑與 aos 對應

確實使用證據：`/home/lorkhan/repo/moddings/skyrim/agentctl/handoffs/home-2026-11-07/team-rules-adopt/BRIEF.md:15` 填 16 路徑／15 KB gate、:34 固定四條、:43 子 agent 上限 2；同夾 REPORT :21 自述 BRIEF strict 0 違規，:25 記錄規則 commit `4681fc0e`。git show 該 commit 的 stat 確含 BRIEF、模板、契約等九個路徑。這是契約實際落成並提交的證據，不是本次親自跑 lint 的證據。

坑：範本允許刪用不到的段落不代表可刪四項必填；最低骨架與現行完整模板不是同一檢查層。檔名／路徑與 CODE gate 不能替代人讀權重、風險與失敗處置。

aos 對應：`/home/lorkhan/repo/aos/wf/workflows/TEMPLATE.handoff.md:6` 有單一目標、:15 硬限制、:24 絕對交付路徑、:30 固定驗收與回報。`/home/lorkhan/repo/aos/wf/workflows/dispatch/README.md:42` 同樣禁止追加驗證，:45 也有範圍排除法與雙 gate。aos 分層規則不可與 skyrim 混同：`/home/lorkhan/repo/aos/wf/workflows/dispatch/aos-teams.md:12` 舊段寫子 agent 無上限；`/home/lorkhan/repo/aos/wf/workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md:27` 現行補充是蒐集／寫碼用 sol 走 agent-fsm、不走 codex。本報告不替兩方統一規則。

## 2. brief_lint 的 CLI、七條檢查、解析邊界及測試

### 2.1 CLI 與退出碼（靜態讀碼）

可照抄的來源介面：

```sh
python3 /home/lorkhan/repo/moddings/skyrim/agentctl/tools/brief_lint.py /absolute/BRIEF.md /absolute/BRIEF-worker.md --strict --root /home/lorkhan/repo/moddings/skyrim
```

此為介面示例，本調查未執行。依 `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/brief_lint.py:226`：

- positional `briefs`：Path，`nargs='+'`，一份或多份；不限制實際檔名一定 BRIEF，也不自動排模板／done。
- `--strict`：有違規回 1；預設即使有違規仍回 0。
- `--root`：解析工具相對路徑，預設 `Path(__file__).resolve().parents[2]`，此部署是 skyrim 根；resolve 成絕對。自身 fallback 根為 parents[1] 即 agentctl。
- 每條輸出 `<path>:<行號或-> <CODE> <說明>`；缺段位置為 `-`。先列缺段，再按行號、code 排序；最後 `brief_lint: N 違規／M 檔`。不是另外加 WARN 前綴，warning 是預設退出碼語意。
- `OSError`（包括檔案不存在／讀不到）印 `brief_lint: <error>` 到 stderr，立即回 2，不完成最後總計；先前檔案已印內容不撤回（:239）。argparse usage 錯誤依其標準行為回 2，help 回 0；程式未總攔其他例外。
- UTF-8 讀取 `errors='replace'`，不因非法 UTF-8 位元組報 decode error（`/home/lorkhan/repo/moddings/skyrim/agentctl/tools/brief_lint_markdown.py:23`）。

### 2.2 七類檢查逐條與模板差異

1. **ACCEPT-COUNT**：找第一個標題含「驗收」的段。沒有就違規；標題需匹配 `(\d+)\s*條`，不是一定要有「固定」或「做完就停」。內文逐行只數從第 1 欄開始、符合 `^\d+[.、)]\s` 的行；數量要等於 N。來源 `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/brief_lint.py:77`。**邊界**：不驗編號順序／唯一／由 1 起算，也不要求 N≥1，不判條件可觀察性、預期數字或條款真假；縮排的編號不算，子標題內的第 1 欄編號與 fenced code 內編號會算。
2. **ACCEPT-OPENWORD**：掃**全檔所有行**，不只驗收段；每行第一個命中報一條。禁字完整為「你認為必要、你覺得必要、以及其他必要、其他必要的驗證、其他必要驗證、其他你認為、其它你認為、自行追加驗證、視情況追加驗證、視需要追加驗證」。來源 `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/brief_lint.py:48`、:97。**邊界**：引用歷史、否定句「不要做…」、code block 也照報；同義但未列的說法不會判。
3. **LOCK-SECTION**：第一個標題含「鎖」即可；內文出現「離線線、可開遊戲、施工線」中兩種以上才報衝突。來源 `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/brief_lint.py:108`。**差異**：範本要恰選一個，但程式允許零個、空鎖段；只看字串存在，不判是否否定、順序、真鎖路徑、GUI 開關與收鎖。
4. **TOOLS-SECTION**：第一個標題含「必用工具」；要有 table_rows 認定的資料列。對資料列**全部儲存格**中單反引號內容，抽第一個可能路徑 token，存在性不過才報。來源 `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/brief_lint.py:123`。抽 token 只先跳開頭連續的 `python3/python/bash/sh/zsh/sudo/env`，下一 token 以 `-` 開頭就不驗；有 `/` 或結尾 .py/.sh 才算路徑（:64）。絕對 token 直接 exists；相對 token 依序試 root/token、SELF_ROOT/token；有 agentctl/ 前綴再剝前綴試 SELF_ROOT（:146）。**差異**：不是檢查可執行性或檔案型別，目錄存在也算；純文字／裸命令或沒有反引號都可有列卻不驗路徑；`python3 -u tools/x.py` 因旗標跳過，不會繼續找 x.py；不驗用途非空、不驗工具確實會用，不繼承 COMMON.md。
5. **DELIVER-ABSPATH**：第一個標題含「交付」，內文至少一個符合 ABSPATH regex 的片段。來源 `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/brief_lint.py:43`、:157。regex 要以行首或空白／指定括號等邊界開頭，路徑由 `/` 起且後面另有 `/`；不是單層 `/tmp`，也不把「和/或」當絕對路徑。**差異**：不限定 /home、不必 REPORT.md、不檢查存在／可寫、不要求交付物每列都絕對；段裡提別的絕對路徑即可過，`~/...` 與 Windows C:\\... 不等於這支 regex 的絕對路徑。
6. **SCOPE-GATE**：第一個標題含「範圍」；`section.text()` 包括標題與內文，只查大小寫不敏感的 `件數\s*gate`、`容量\s*gate`，及「不做」子字串；缺項合成一條 finding。來源 `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/brief_lint.py:171`。**差異**：不驗 N/M 數字、單位、停下回報或排除清單有效；只有三個關鍵詞也能過，標題裡有也算。
7. **PLACEHOLDER**：全檔每行匹配 `<([^<>\n]{1,60})>`；內部 1～60 字元，最多展示前三個殘留，但每行只報一條。來源 `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/brief_lint.py:192`。例外為 inner 以 `!` 或 `/` 起、含 `://` 或 `@`、或小寫化後等於白名單 HTML tag（也容許尾 `/`）。白名單完整為 br p b i u em strong code kbd sub sup hr div span ul ol li table tr td th img a details summary pre blockquote（:55）。**邊界**：不是通用 HTML parser；`<details>` 過、帶屬性的開標籤不因 tag 名自動豁免；網址／email／註解／所有斜線開頭內容放行，超過 60 字元的整體佔位不會當一個匹配。

以上七類的 dispatch 順序為 count → openword → lock → tools → deliver → scope → placeholder，之後重新排序（`/home/lorkhan/repo/moddings/skyrim/agentctl/tools/brief_lint.py:209`）。沒有檢查背景唯一目標、Done when、子 agent 配額、工作段、權重、commit 唯一人、REPORT 真落檔、失敗兩路或 PROGRESS；strict 並不是完整契約的證明。

### 2.3 Markdown 解析的精確邊界

來源 `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/brief_lint_markdown.py:5`：

- 只認 ATX `#`～`######` 標題，最多三個前導空白、`#` 後需空白，支援尾端 `#`；不認 Setext、blockquote 標題或一般縮排 code 的完整 Markdown 語意。
- fence regex 為最多三空白後三個以上 backtick 或 tilde。**每次命中就翻 inside 布林**，不核開關字元種類、長度或 closing 後內容；未閉 fence 會持續遮掉後面的標題。
- fenced 行不建立 section，但被原封加入目前所有祖先 section 的 body。因此「忽略 code block 標題」不等於「忽略 code block 檢查」；code 的編號、工具表、關鍵字仍會影響其他檢查。
- section body 包含至下一個同級或更高級標題前的內容，且包含子標題及子段內容；`find_section` 回傳標題子字串匹配的第一段，不做全名／level／重複段驗證。第一段錯誤不會因後面另有正確段而消失。
- 表格只認 strip 後由 `|` 開頭的行，按未被反斜線 escape 的 `|` 分欄；一行只含 `| 空白 : -` 即視為分隔列，後續 pipe 行算資料。非 pipe 行重置狀態，不驗欄數或表頭名稱，也不處理 inline-code 中的 pipe。
- 沒分隔列時用 pending：只有在結束時 pending 還在、且之前沒資料列，才把最後 pending 那列當資料。多列無 separator 不會完整當資料列；後面若有非 pipe 行，pending 也清空。不是一般 Markdown 表格 parser。

### 2.4 test_brief_lint.py 靜態覆蓋盤點（沒有跑）

共 24 個 `test_` 方法；fixture CLEAN 和 subprocess helpers 在 `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/test_brief_lint.py:12`、:74。CLEAN 沒有 Done when、子 agent 配額、完成回報或失敗處置，正好證明此測試的「乾淨」只針對七種 lint。

| 覆蓋 | 方法所在絕對位置 |
|---|---|
| 乾淨預設／strict 零違規與 summary | `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/test_brief_lint.py:84`、:91 |
| 驗收條數不符／標題無數字／缺段 | `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/test_brief_lint.py:97`、:104、:110 |
| 開放驗收字樣一例 | `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/test_brief_lint.py:118` |
| 鎖缺段／留兩個選項 | `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/test_brief_lint.py:127`、:133 |
| 工具路徑不存在／空表／缺段／絕對路徑／root override／agentctl 前綴 fallback | `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/test_brief_lint.py:144`、:154、:160、:165、:174、:184 |
| 交付僅相對路徑／缺段 | `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/test_brief_lint.py:193`、:198 |
| scope 三項全缺／只缺容量 | `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/test_brief_lint.py:205`、:212 |
| 佔位殘留／br、autolink、HTML comment 例外 | `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/test_brief_lint.py:224`、:230 |
| 預設 0／strict 1、多檔總結、缺檔 2、help 0 | `/home/lorkhan/repo/moddings/skyrim/agentctl/tools/test_brief_lint.py:239`、:244、:253、:258 |

本 test 檔沒有直接涵蓋：fence／tilde 開關、巢狀／重複 section、code 裡的計數、表格 escape 或缺 separator 邊界、N=0／非連續編號／縮排編號、所有禁字及否定句誤報、無鎖選項、無反引號工具／interpreter 旗標、工具是目錄、交付路徑 regex 全邊界、佔位 60 字上限／所有 HTML 例外、單獨缺範圍段、檔案權限錯誤、缺參數、執行 hook 或 staged／工作樹不同內容。未測不等於必然壞；這裡是測試存在性盤點。

確實使用／歷史修正：`/home/lorkhan/repo/moddings/skyrim/wf/lessons/tool-portability.md:11` 記獨立 clone 讓母根推導錯、合格工具路徑全假紅；git commit `c75ac803b330598057f0ce6c27efd005a1447d0d` 的訊息明載 fallback 與回歸測試，現碼 :146、test :184 與之相符。

aos 對應：在 `/home/lorkhan/repo/aos/wf` 以檔名查 brief／handoff／runtime／pre-commit，及對 md 搜 `brief_lint|check_staged_briefs|brief gate`，沒找到這兩支同名機械 gate；這是限定搜尋範圍的「沒找到」，不是宣稱整個 aos 沒有任何 lint。aos 固定驗收的人讀規則在 `/home/lorkhan/repo/aos/wf/workflows/dispatch/README.md:42`；其模板 :35 自己就含「其他你認為必要的驗證」的否定引用，照 skyrim 全文禁字規則會命中，故不能把兩份模板視為相同輸入契約。
