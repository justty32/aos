# 蒐集 01g（ok-skyrim 隊 sky-sol-b 原文）：skyrim 的角色與配額、BRIEF 契約與 lint、回報等待與交棒、外部 CLI 啟動與判活、收線與 commit 閘門

← [README](README.md)｜[02 借鑑清單](02-借鑑清單.md)｜隊員原文照收，隊長只加這兩行；它只陳述事實、不做借鑑判斷。檔內提到的 `out/01?-*.md` 是隊員工作區裡的原檔名。

角色與模型配額：三層分工、子 agent 總配額、context 與 session goal。
BRIEF 品質閘門：有界任務、固定驗收、工具點名、lint 與 commit hook。
回報與交棒契約：進度、終局、輪詢、產物落檔及失敗分類。
外部 CLI 駕駛：啟動確認、程序判活、卡住警示、Windows 派線與負載限制。
收線與交付：明確路徑 commit、gitlink、大小閘門及使用者驗收範本。

下文 `agentctl/...` 根為 `/home/lorkhan/repo/moddings/skyrim/`；出處以標題／函式定位。本次只靜態閱讀，REPORT 結果是原作者紀錄。

## 一、角色、模型、配額與 session goal

1. **是什麼**
頂層接使用者、領導切線驗收、工人完成有界任務。模型選型與外部 CLI／子 agent 配額分開管理；現行基準標在 2026-11-07，優先於較舊分級及 headcount 範例。（出處：`agentctl/docs/team-model.md`「現行派工基準」；`agentctl/docs/team-model/roles.md`「一、角色三層」）

2. **出處**
`agentctl/docs/team-model.md`「現行派工基準」「選人判準」「信箱」；`agentctl/docs/team-model/roles.md` 三個角色標題；`agentctl/docs/team-model/intelligence-tiers.md`「聰明度分級」；`agentctl/docs/team-model/plans.md`「2026-09-25 更新」；`agentctl/docs/team-model/context.md`；`agentctl/docs/team-model/speed-and-driving.md`「三個因素相乘」；`agentctl/docs/session-goal-template.md`「可改數字版」「會跟著場次變的欄位」。

3. **怎麼運作**
- 原句：「一個工作樹同時只有一個 commit 者」。有界單一任務直接掛 codex；需同時看至少三條線且有仲裁需求才加管理層。（`roles.md` 各角色段）
- 現行普通工作 `gpt-6.1-sol`、美術創意 `gpt-6-astra`、雜活 `gpt-6.1-terra`；Claude 普通 Opus、雜活 Sonnet。查找、盤點、收指令結果及純文字小改才算簡單；程式邏輯、概念／規範改寫不算。此處 GPT 做設計／架構是「優先級較低」，不是禁止，也沒有把 aos 固定隊形直接搬來。（`team-model.md` 現行基準）
- 家機每隊最多一個外部 codex；同程序子 agent 另計。原句：「每線交接書必寫子 agent 數量上限（可填 0）」。下派同一總額、不倍增。舊分級及「退 GPT 後」表只供背景／備案。（`team-model.md` 現行基準；`plans.md` 更新）
- 一般 agent 親讀適用 `wf/`，領隊摘要不能取代；簡單工作、雜活例外。context 由上級管理，交接書預定里程碑後 compact；頂層和使用者商量，codex 從 stdin 送 `/compact`，Claude 子 agent 沒外部 compact 入口就一段一線接力，只帶產物路徑。（`team-model.md` 現行基準；`context.md` 五條）
- session goal 是本場的編制、資源與收尾期限開場詞，不是 BRIEF 替代品。可改欄位含地點、工具、團隊數、直接成員、子 agent 配額、網路、鍵鼠螢幕與收尾／關機時間；原文歷史數字不覆蓋現行規則及每線 BRIEF。每線另寫可觀察的 `Done when:`，用 `/goal` 指派。（`session-goal-template.md` 開頭及可改數字版；`driving-codex/handoff-contract.md` 必寫規則後段）

4. **為什麼這樣定**
速度頁把 token 速度、繞圈數、模型癖好相乘；08-30 體感記錄說 sol 過度驗證拉長時間。context 頁理由是清掉上一段殘渣。11-07 子 agent 總額上限的原話在 `agentctl/handoffs/home-2026-11-07/team-rules-adopt/BRIEF.md`「背景與唯一目標」。

5. **靠什麼落實**
主要靠文件和每線 BRIEF。`agentctl/tools/cx_launch.sh` 預設提示傳遞親讀、總配額、進度及 `/goal`；但不計數子 agent，也不驗模型是否符合分類。`agentctl/tools/brief_lint.py` 的 `lint()` 只有七類檢查，沒有子 agent 上限、context 或模型檢查。`session-goal-template.md` 是手動填寫範本，未見專用解析／強制工具。

6. **實際有沒有在用**
`agentctl/handoffs/home-2026-11-07/team-rules-adopt/REPORT.md` 第 1、2、4 節記規則與 launcher 更新；`agentctl/handoffs/home-2026-11-07/wrap/BRIEF.md` 上限 2，同行 REPORT 記用 2、向下 0、無新增外部 codex。未讀到 session 開場 transcript。

## 二、BRIEF 契約與品質 lint

1. **是什麼**
BRIEF 定範圍、停點、交付及驗收。範本要求多於 lint，通過不等於契約／內容全對。（出處：`agentctl/templates/BRIEF.md`；`agentctl/tools/brief_lint.py` `lint()`）

2. **出處**
`agentctl/docs/driving-codex/handoff-contract.md`「寫交接書」；`agentctl/templates/BRIEF.md` 各節及末尾機械 gate 說明；`agentctl/tools/brief_lint.py` 各 `check_*`／`main()`；`agentctl/tools/brief_lint_markdown.py` 的 `parse_sections()`／`table_rows()`；`agentctl/tools/test_brief_lint.py`；`agentctl/tools/hooks/pre-commit`；`agentctl/tools/hooks/check_staged_briefs.sh`；`agentctl/tools/test_check_staged_briefs.py`。

3. **怎麼運作**
- 契約最小骨架是背景與唯一目標、工作、硬性限制、交付、固定驗收、完成／阻塞回報。完整範本再列範圍排除法、必用工具表、鎖與遊戲、失敗處置；開頭寫親讀要求與子 agent 上限。原句：「只做下面列出的事；沒列的一律不做」。件數／容量任一超標就停，交付指定絕對 REPORT 路徑及唯一 commit 者。（`handoff-contract.md` 骨架及必寫規則；`templates/BRIEF.md` 範圍、交付）
- `ACCEPT-COUNT`：找第一個標題含「驗收」的段落，從標題抓 N 條，再數段內行首編號是否等於 N。`ACCEPT-OPENWORD`：全文找「其他必要驗證」等開放字詞。`LOCK-SECTION`：找含「鎖」的標題，缺段或同時出現三種選項中的兩種以上就報錯；程式沒有強制至少選中其中一種。（`brief_lint.py` `check_acceptance()`、`check_open_words()`、`check_lock()`）
- `TOOLS-SECTION`：工具段要有表格資料列，逐個檢查反引號內可辨識的路徑是否存在；可從母根、agentctl 自身根及去掉 `agentctl/` 前綴解析。它不是驗工具真的執行過。`DELIVER-ABSPATH`：交付段有符合規則的斜線絕對路徑即可，不專門辨識 REPORT，也不驗路徑可寫。（同檔 `check_tools()`、`tool_path_exists()`、`check_deliver()`）
- `SCOPE-GATE` 只驗「件數 gate」「容量 gate」「不做」字詞存在，不解析門檻數字或是否合理。`PLACEHOLDER` 找剩下的 `<…>`，排除部分 HTML、網址、郵件格式。Markdown 解析會跳過圍欄內的假標題，但圍欄文字仍留在所屬段落；開放字詞及佔位檢查仍掃原文。（同檔 `check_scope()`、`check_placeholders()`；`brief_lint_markdown.py` `fenced_flags()`、`parse_sections()`）

4. **為什麼這樣定**
`brief_lint.py` 檔頭引用 2026-10-03 retro：「被交接書點名的工具用了 134 次，沒被點名的 0 次」。固定驗收防止線自行加驗到燒光 token；排除清單防「相關的」一路展開。`agentctl/docs/driving-codex/lessons-from-done-handoffs.md` 記三個 08-30 經驗：庫存預掃漏 C 組、實測只有兩個陷阱卻契約寫三個、背景與工作步驟互相矛盾。原句：「驗收條數寫死是為了防它亂加驗證，不是要它為了湊滿數字造假失敗案例。」

5. **靠什麼落實**
`brief_lint.py` 預設印違規但 exit 0；`--strict` 有違規 exit 1，讀檔失敗 exit 2。`hooks/pre-commit` 先跑 hygiene，再跑 `check_staged_briefs.sh`；後者只選作用中 index 的 `handoffs/**/BRIEF*.md` 新增／修改等項目，排除 templates、done、superseded 及刪除，再以 strict 擋 commit。它尊重 `GIT_INDEX_FILE`，避免 pathspec commit 被別線 staged 的壞 BRIEF 擋住；但選出檔名後 lint 讀工作樹檔案，不是從 index 擷取正文。找不到 lint 腳本會警告後放行；跳過需頂層或使用者授權。平日 `agentctl/wf/tools/wf-lint-local.sh` 則掃現役 BRIEF，平常是 warning。

6. **實際有沒有在用**
本次檔名盤點在 `agentctl/handoffs/` 找到 10 份 `BRIEF*.md`，分布 11-05 與 11-07；只對已讀的 adopt、wrap、nexus 三份寫內容判斷。`test_brief_lint.py` 有 24 個 `test_` 方法，含乾淨／違規、strict、缺檔與路徑 fallback；`test_check_staged_briefs.py` 有真暫存 repo commit 測試，驗證 pathspec 不吃別線 staged BRIEF。`home-2026-11-07/wrap/REPORT.md` 第 3 節記 strict lint 0 違規。本次未重跑測試，也未查實機 hooksPath 設定。

## 三、回報、等待與交棒

1. **是什麼**
回報含正文檔、證據、未完成與待決事項；對等來訊只是情報／請求。（出處：`agentctl/docs/driving-codex/handoff-contract.md` 開頭；`agentctl/templates/BRIEF.md` 完成／阻塞回報）

2. **出處**
`agentctl/docs/driving-codex/communication.md`「五、通訊」；`agentctl/docs/team-model.md`「信箱」；`agentctl/docs/driving-codex.md`「管理者休眠前的自檢」「收線」；`agentctl/templates/BRIEF.md`「交付」「失敗怎麼處置」「完成／阻塞回報」；`agentctl/docs/driving-codex/monitoring.md` 交棒相關護欄。

3. **怎麼運作**
- 開線聲明身份、領地與能答／不能答；每完成一步且至少每 20 分鐘發 `PROGRESS`，正文給 `body_file`，寫已完成、證據路徑、下一步。卡超過 10 分鐘先 `BLOCKED`，終局選 `DONE`／`FAILED`／`BLOCKED`／`NEEDS-USER`。REPORT 必須直接落檔，回覆只留五行摘要與路徑，末尾有「以後交接書該點名的工具」。（BRIEF 範本交付、回報；communication.md）
- 文件說 `inbox_send.sh` 依 `teams/*/members` 路由到領導，不需工人知道上游名字；領導上呈重寫標題、帶判斷。工人每步 `inbox_poll.sh 自己 --once`，領導用 `--wait` 醒鐘；一般頂層只由要緊訊息叫醒。這是文件所載路由，本次沒有追讀 inbox 工具實作。（team-model.md 信箱；communication.md）
- 等他線須寫可驗條件、逾時和可先做的事，前景 `--wait --timeout`；原句：「不要結束回合假裝等待」。管理者交棒列全部 CLI／子 agent 的當下狀態、輸出、下一步及監看者，交前確認畫面有 Working／輸出，接手者逐線巡視；活線為零才報全部收完。（BRIEF 範本回報；driving-codex.md 自檢；monitoring.md）
- 測試跑成但結果壞：依契約回滾本線、`FAILED`；根本沒測成、沒證據：保持現狀、`BLOCKED`，不得用舊 log 代替。工具／環境壞與自己臨時腳本壞也分開：後者自行修，不算外部阻塞。（BRIEF 範本鎖與遊戲、失敗處置）

4. **為什麼這樣定**
`monitoring.md` 記領導接棒後發現四線兩線空轉、字型指令沒送出；也記領導只看 `new/`，差點漏掉已路由到 `mail/<lead>/` 的終局。省略 `body_file` 會靜默等 stdin。這些是具體踩坑；失敗分類的效果是把「沒證據」與「證明壞了」分開，原範本直接明寫兩者不同。

5. **靠什麼落實**
`agentctl/tools/cx_watch.sh` 的 `check_mail()` 透過 inbox poll 讀本線訊息，終局令 watcher 返回，PROGRESS 只印 NOTE 後續看；REPORT 格式、回報頻率與交棒完整性在已讀 lint 中沒有機械檢查。`agentctl/docs/driving-codex.md` 收線要求領導逐條核固定驗收，不能只信自稱完成。

6. **實際有沒有在用**
`agentctl/handoffs/home-2026-11-07/STATE.md` 列五線 REPORT 與終局；同行 `wrap/REPORT.md` 第 5 節記 68 封首次 ack及子 agent 收工。`nexus-198176/BRIEF.md` 實寫等 chronicon 的 REPORT 加 session 結束或終局信、每 60 秒前景查。本次未核原信／transcript。

## 四、外部 CLI、Windows 派線與限流

1. **是什麼**
家機用 tmux，分驗送出、判活與卡住；公司 Windows 用背景 `codex exec`。在這兩份文件中，派工由 tmux session／背景 process 承載。（出處：`agentctl/docs/driving-codex.md` 啟動；`agentctl/docs/dispatch-windows.md` 第一節）

2. **出處**
`agentctl/tools/cx_launch.sh` 頂部說明及啟動迴圈；`agentctl/tools/cx_watch.sh` `check_session()`、`check_mail()`、主迴圈；`agentctl/docs/driving-codex/monitoring.md`；`agentctl/docs/dispatch-windows.md` 資源規則、交付；`agentctl/docs/dispatch-windows/launch.md` 日期更正；`agentctl/docs/dispatch-windows/communication.md`「2026-09-02 更正」；`agentctl/docs/resource-locks.md`「CPU 限流」「並行負載與重操作」。

3. **怎麼運作**
- `cx_launch.sh 線名 BRIEF.md` 拒絕同名 session，等 composer／trust 提示，文字用 `send-keys -l`，Enter 另送；預設補 `/goal`，送後等 4 秒找 `Working|esc to interrupt`，最多 3 次 Enter。boot 預設 40 秒；未工作 exit 3、同名 exit 4、boot 超時 exit 5。它不取遊戲鎖，也不跑 BRIEF lint；未傳 `--model` 就用 codex 配置預設，非自動固定 sol。（`cx_launch.sh` usage、參數與啟動迴圈）
- `cx_watch.sh` 預設每 20 秒輪詢，從 `/proc/*/status` 的 PPid 看 pane shell 有沒有直接子程序，不把舊畫面 Working 當活證據；session 不見／無子程序 exit 4。批准字樣 `Would you like to run` 等 exit 5；活著但畫面 hash 900 秒沒變預設 STALL／exit 6；timeout exit 3，不會自動殺線。終局信 exit 0；同輪有更高優先異常仍用該碼。`--once` 是單輪，不等同長期停滯監看。（`cx_watch.sh` 全文）
- Windows 無 tmux，用一線一背景 process、單次 `-c` 不改全域 config，預設斷網、不 GUI、不下載、最多三線，不用 taskset。08-31 曾歸因多可寫根不可用，09-01 更正至少一個原因是 `-C` 用 8.3 短路徑；單一長路徑根可啟動，多根當次未重測。stdin 在 sh 用 `< /dev/null`，PowerShell 不能照貼；09-02 可用配方由調度者 Git Bash 起。（dispatch-windows.md；launch.md 更正；communication.md 更正）
- Windows 工人 09-02 實測僅 `cmd.exe /c python` 穩，驗收先寫 `.py` 再跑，不用易碎的 `python -c`。直接寫 inbox Markdown，含 from／status／at 與做了什麼／產出／未做／待決；調度者到線用 `orders/<session>.md` 每步讀，`codex queue` 回 Queued 不算收到。工人不 commit／push、不用副本繞 Git metadata 權限，由調度者核 diff。舊 Windows 頁模型較舊，現行入口已明說模型／headcount 舊例不覆蓋 11-07 基準。（communication.md；dispatch-windows.md 交付；team-model.md 現行基準）
- CPU 原句：「按行程樹限流，不要按名稱。」重操作例用 `nice -n 19 taskset -c 0-5`；約 80% 是上限，不是目標。外部程序與子 agent 配額分開；按本機 CPU、load、可用記憶體及實際程序樹設監看，超標只通知，先停加開或輪流重操作，不自動殺程序，不搬 WSL 暫定數字。桌面／遊戲資源另走 desktop→game 鎖序。（resource-locks.md CPU、並行、遊戲鎖）

4. **為什麼這樣定**
`monitoring.md` 記長訊息卡輸入框與交棒後空轉；`cx_watch.sh` 檔頭說 Working 可能只是死 scrollback。Windows `launch.md` 記滿屏 ERROR 後 7 分鐘仍交出可核產出，不能只憑錯誤畫面判死，也不能只信 exit 0。CPU 頁的原句是「別操使用者的電腦」；houseCARL 每個 client 各一份，按名稱限流會誤傷別線。

5. **靠什麼落實**
launcher／watcher 有程式判定與退出碼，`agentctl/tools/test_cx_tools.py` 用假 tmux、假 `/proc` 測補 Enter、同名拒絕、死 Working、批准、停滯、終局及 timeout；不是實機 codex 測試。CPU／外部數量上限在這兩支工具沒有全機計數、429 偵測或自動退避；依文件由上級負載監看與改派。`team-model.md` 現行基準要求額度／API 不穩按能力改派平台、寫檔接力，不擴沙箱或降驗收。`agentctl/tools/lock.sh` 則有 mkdir 取鎖及 owner 檢查，錯鎖序預設警告、`--strict` 才拒絕，不是所有規則都硬擋。

6. **實際有沒有在用**
Windows `launch.md` 留 09-01 三線斷網與長路徑探路紀錄，`communication.md` 留 09-02 四線 `.py` 成功紀錄，僅證歷史狀態。11-07 `team-rules-adopt/REPORT.md` 第 2、3 節記 launcher dry-run／語法驗證；未驗現機 CLI、API 或負載。

## 五、收線、commit 閘門與使用者交付

1. **是什麼**
收線把可提交產物、gitlink、遠端與使用者待驗分開處理，不以線自稱 DONE 代替核驗。（出處：`agentctl/docs/driving-codex.md`「收線」；`agentctl/templates/user-runtime-checklist.md`）

2. **出處**
`agentctl/tools/wrap.sh`、`agentctl/tools/wrap.py` 的 `do_commit()`／`pin()`／`push()`／`main()`；`agentctl/tools/wrap_git.py` `guard_index()`；`agentctl/tools/repo_hooks/README.md`、`policies.json`、`precommit_gate.py` `check()`、`install_hooks.sh`；`agentctl/templates/README.md`、`user-runtime-checklist.md`、`artifact-page.html` 檔頭。

3. **怎麼運作**
- `wrap.sh` 轉呼叫 Python，掃 dirty／unpushed，只收 `REPO:PATH` 明確檔案，拒目錄、越界路徑、手列 gitlink及外線 staged 內容；hygiene 違規就不 pin／push。由內向外 pin，推送要 `--push --apply`；先 fetch 查全部遠端，任一領先本地就停止全部推送。未加 apply 不 commit／pin／push，但 `--push` dry-run 仍會 fetch。（wrap.py、wrap_git.py）
- repo_hooks 另管五個 repo staged blob 的大小及 16 類垃圾 pattern：母、instance、profiles、modpack-design 超 1 MiB 擋；mod-library 超 25 MiB 警告、超 95 MiB 擋。例外只對自身政策有效，gitlink 跳過。違規 exit 1、設定／Git 錯 exit 2；安裝問 Git hooks 路徑，不覆寫既有 hook，缺 gate 警告後放行。（repo_hooks 政策、程式及安裝器）
- 使用者驗收範本每項只寫做什麼、看到什麼、不對回報什麼，依武器／場景分組；「看不出來」不等於壞。artifact-page 是共用頁面骨架，含主題 token、深淺色、手機寬、決策卡及變更單，不是 CLI 控制台。（templates README、checklist、HTML 檔頭）

4. **為什麼這樣定**
`wrap.py` 檔頭記母 repo 的 on-demand 會連推未列子專案，因此先列推送影響。repo_hooks README 說 private agentctl 在乾淨 clone 可能缺席，缺工具就擋死所有 commit 比放行更糟。templates README 記 10-03 retro 發現五線交接開頭相同，改用共用範本。

5. **靠什麼落實**
wrap 的路徑／index／遠端護欄有程式強制，但不驗使用者 push 授權；授權仍靠契約。`test_wrap.py` 用暫存 repo＋bare remote 測明確路徑、外線 staged 阻擋、pin／push及遠端領先；`repo_hooks/test_precommit_gate.py` 測 staged 大小、政策例外、安裝後擋 commit。使用者清單與 HTML 是文件範本，不是自動驗收。

6. **實際有沒有在用**
`agentctl/handoffs/home-2026-11-07/wrap/REPORT.md` 第 4 節記 wrap 推送與後續 17 repo／16 gitlink 核對；這個 17 repo 全掃是該線另做，不是 wrap 內建六 repo 表。repo_hooks README 記安裝情況，本次未獨立驗各 repo hook 配置；使用者清單及 artifact 成品未抽讀，實際採用看不出來。

## 沒讀到／不確定的

- 指定主檔、各主題、模板及工具均已讀；artifact HTML 只讀用途與骨架，子目錄 README 導航未逐份讀。
- 未跑工具／測試／hook 安裝，未驗現機程序數、沙箱、API／429、hooksPath、遠端 hash。
- 通訊僅核指定文件、watcher 呼叫與場次紀錄，未追讀完整 inbox 協議／腳本。未見獨立「派工視窗」實作；Windows 頁有歷史更正，不能當目前環境探測結果。
- `agentctl/docs/driving-codex/patch-delete-add-pitfall.md` 記 08-29 Delete／Add 間缺檔 23 秒，要求 Update File；入口施工經驗已把刪除檢查修成對照開工基線，本次沒有重現事故或追 git history。
